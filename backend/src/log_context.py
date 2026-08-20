"""요청 단위 로그 컨텍스트 — request_id / account_id 를 모든 로그 줄에 자동으로 싣는다.

로그 관리 규칙 (Actora)
─────────────────────────────────────────────────────────────────
1. 시각은 항상 **한국시간(KST)**. 운영·로컬 구분 없이 동일하게 찍는다.
   (서버가 UTC 로 찍으면 사용자 문의 시각과 대조가 안 된다)

2. 모든 줄에 **요청 추적 정보**를 붙인다.
       시각 KST | LEVEL | req=<8자리> | acc=<account_id> | 모듈 | 메시지
   - req : 요청마다 발급되는 짧은 ID. 응답 헤더 X-Request-ID 로도 내려주므로
           사용자가 겪은 화면 오류와 서버 로그를 1:1로 맞출 수 있다.
   - acc : 인증된 계정 ID. 비로그인 요청은 '-'.
   - 요청 밖(기동·백그라운드 작업)에서는 둘 다 '-'.

3. **요청 1건당 완료 로그 1줄**을 남긴다 (메서드·경로·상태·소요시간).
   느린 요청(3초 초과)은 WARNING 으로 올려 눈에 띄게 한다.

4. **민감정보는 로그에 남기지 않는다.** API 키·토큰·비밀번호·DB URL 의
   비밀번호 부분은 마스킹한다 (SecretMaskFilter). 실수로 f-string 에
   넣어도 파일·콘솔에 원문이 남지 않는다.

5. 파일 로그는 운영에서만 남긴다 (app.log / error.log, 로테이션 + 7일 정리).
   로컬은 콘솔만 — 개발 중 디스크를 채우지 않는다.
"""
from __future__ import annotations

import logging
import re
from contextvars import ContextVar

# 요청 스코프 값 — 미들웨어가 채우고, 로그 필터가 읽는다
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
account_id_var: ContextVar[str] = ContextVar("account_id", default="-")


class RequestContextFilter(logging.Filter):
    """모든 LogRecord 에 req / acc 필드를 채워 넣는다 (없으면 '-')."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.req = request_id_var.get()
        record.acc = account_id_var.get()
        return True


# ─────────────────────────────────────────────────────────
# 민감정보 마스킹
# ─────────────────────────────────────────────────────────
# 실수로 로그에 들어가도 원문이 남지 않도록 출력 직전에 가린다.
# (실제로 DB 비밀번호가 터미널에 찍힌 일이 있었다)
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # OpenAI 계열 키
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    # Bearer 토큰 / JWT
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.I), r"\1***"),
    (re.compile(r"eyJ[A-Za-z0-9._\-]{16,}"), "***JWT***"),
    # DB URL 의 비밀번호 (scheme://user:PASSWORD@host)
    (re.compile(r"(://[^:/\s]+:)[^@\s]+(@)"), r"\1***\2"),
    # key=value / "key": "value" 형태
    (
        # key=value, "key": "value", key: value 모두 커버.
        # 키 뒤 따옴표(JSON) 를 허용하지 않으면 {"api_key": "..."} 가 새어 나간다.
        re.compile(
            r"((?:password|passwd|secret|token|api_key|apikey|secret_key)"
            r"[\"']?\s*[=:]\s*[\"']?)([^\s\"',}]+)",
            re.I,
        ),
        r"\1***",
    ),
)


def mask_secrets(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


class SecretMaskFilter(logging.Filter):
    """포맷된 메시지에서 키·토큰·비밀번호를 가린다."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        masked = mask_secrets(msg)
        if masked != msg:
            # args 를 이미 소비했으므로 msg 로 확정하고 args 는 비운다
            record.msg = masked
            record.args = ()
        return True
