"""요청 추적 미들웨어 — 로그 관리 규칙 2·3 구현 (규칙 전문: src/log_context.py).

요청마다 짧은 ID 를 발급해 그 요청에서 나온 모든 로그에 붙이고,
완료 시 `메서드 경로 → 상태 (소요시간)` 한 줄을 남긴다.

BaseHTTPMiddleware 대신 **순수 ASGI 미들웨어**로 작성한 이유:
BaseHTTPMiddleware 는 다음 앱을 별도 task 로 실행해서, 엔드포인트(의존성)에서
set 한 ContextVar 가 미들웨어로 돌아오지 않는다. 그러면 요청 완료 로그에
account_id 를 담을 수 없다. 순수 ASGI 는 같은 컨텍스트에서 실행되어
엔드포인트가 채운 acc 값을 그대로 읽을 수 있다.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import unquote_plus
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.log_context import account_id_var, request_id_var

logger = logging.getLogger("src.request")

# 주기적으로 계속 들어와 로그를 채우는 경로 — 완료 로그를 남기지 않는다
SKIP_PATHS = frozenset({"/health", "/auth/heartbeat"})

# 이 시간을 넘으면 WARNING 으로 올려 느린 요청을 눈에 띄게 한다
SLOW_REQUEST_MS = 3000

# 쿼리스트링이 이보다 길면 잘라 붙인다 (로그 한 줄이 화면을 넘기지 않게)
MAX_QUERY_LEN = 200


def _path_with_query(scope) -> str:
    """경로 + 쿼리스트링.

    경로만 남기면 "GET /agency/search → 200" 처럼 **무엇을 요청했는지 알 수 없어**
    문제를 재현할 수 없다. 검색어·필터가 쿼리에 담기므로 함께 남긴다.
    값 자체의 마스킹(token=, api_key= 등)은 SecretMaskFilter 가 출력 직전에 처리한다.
    """
    path = scope.get("path", "")
    raw = scope.get("query_string") or b""
    if not raw:
        return path
    q = raw.decode("utf-8", "replace")
    # 퍼센트 인코딩을 풀어야 한글 검색어를 그대로 읽을 수 있다
    # ("q=%EB%8B%A4%EC%B9%9C" 보다 "q=다친 연기" 가 추적에 쓸모 있다)
    try:
        q = unquote_plus(q)
    except Exception:
        pass
    # 개행·제어문자가 섞이면 로그 한 줄이 깨지므로 공백으로 바꾼다
    q = "".join(" " if ord(c) < 32 else c for c in q)
    if len(q) > MAX_QUERY_LEN:
        q = q[:MAX_QUERY_LEN] + "…"
    return f"{path}?{q}"


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:8]
        rid_token = request_id_var.set(request_id)
        acc_token = account_id_var.set("-")

        method: str = scope.get("method", "?")
        path: str = scope.get("path", "?")
        started = time.perf_counter()
        status = {"code": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                # 화면에서 오류를 겪은 사용자가 이 값을 알려주면
                # 서버 로그에서 해당 요청만 바로 골라낼 수 있다
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000
            # 여기서 로그를 남기지 않으면 어느 요청이 터졌는지 알 수 없다
            logger.exception(
                f"{method} {_path_with_query(scope)} → 처리 중 예외 ({elapsed:.0f}ms)"
            )
            raise
        else:
            if path not in SKIP_PATHS:
                elapsed = (time.perf_counter() - started) * 1000
                code = status["code"]
                message = f"{method} {_path_with_query(scope)} → {code} ({elapsed:.0f}ms)"
                if code >= 500:
                    logger.error(message)
                elif code >= 400:
                    logger.warning(message)
                elif elapsed >= SLOW_REQUEST_MS:
                    logger.warning(f"{message} — 느린 요청")
                else:
                    logger.info(message)
        finally:
            request_id_var.reset(rid_token)
            account_id_var.reset(acc_token)
