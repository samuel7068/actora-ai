import logging
import logging.handlers
from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
from typing import Optional
from zoneinfo import ZoneInfo
import os

from src.log_context import RequestContextFilter, SecretMaskFilter

_KST = ZoneInfo("Asia/Seoul")


class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            if '/health' in message and ('GET' in message or 'POST' in message):
                return False
        return True


def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    environment = os.getenv("ENVIRONMENT", "prod").strip().lower()
    is_local = environment == "loc"

    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')

    # 시각은 운영·로컬 모두 한국시간(KST). 서버가 UTC 로 찍으면
    # 사용자 문의 시각과 로그를 대조할 수 없다. — src/log_context.py 규칙 1
    class KstFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            dt = datetime.fromtimestamp(record.created, tz=_KST)
            return dt.strftime(datefmt) if datefmt else dt.strftime('%Y-%m-%d %H:%M:%S')

    # req(요청 ID) / acc(계정 ID) 를 모든 줄에 — 규칙 2
    formatter = KstFormatter(
        '%(asctime)s KST | %(levelname)-7s | req=%(req)s | acc=%(acc)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 모든 핸들러에 공통으로 붙일 필터
    #   - RequestContextFilter: req/acc 필드 주입 (없으면 포맷 에러가 난다)
    #   - SecretMaskFilter: 키·토큰·비밀번호 마스킹 — 규칙 4
    context_filter = RequestContextFilter()
    mask_filter = SecretMaskFilter()

    def _attach(handler: logging.Handler) -> logging.Handler:
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)
        handler.addFilter(mask_filter)
        return handler

    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(_attach(console_handler))

    if not is_local:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # 로테이션: 파일당 50MB × 5개 (기존 1GB 는 열어보기도 어렵고 디스크 위험)
        info_handler = logging.handlers.RotatingFileHandler(
            filename=log_path / 'app.log',
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        info_handler.setLevel(logging.INFO)
        root_logger.addHandler(_attach(info_handler))

        error_handler = logging.handlers.RotatingFileHandler(
            filename=log_path / 'error.log',
            maxBytes=20 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(_attach(error_handler))

    logging.getLogger("httpx").setLevel(logging.WARNING)
    # uvicorn 의 access 로그는 RequestContextMiddleware 의 완료 로그와 중복이고
    # req/acc 정보가 없다. WARNING 으로 올려 사실상 끈다 — 규칙 3
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

    return logging.getLogger(__name__)


def cleanup_old_logs(log_dir: str = "logs", max_age_days: int = 7):
    log_path = Path(log_dir)
    if not log_path.exists():
        return
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for log_file in log_path.glob("*.log*"):
        if log_file.name in ['app.log', 'error.log']:
            continue
        try:
            if log_file.stat().st_mtime < cutoff.timestamp():
                log_file.unlink()
        except Exception:
            pass


_cleanup_task: Optional[asyncio.Task] = None


async def _periodic_cleanup(log_dir, max_age_days, interval_hours):
    while True:
        try:
            await asyncio.sleep(interval_hours * 3600)
            cleanup_old_logs(log_dir, max_age_days)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


def start_periodic_log_cleanup(log_dir: str = "logs", max_age_days: int = 7, interval_hours: int = 24):
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(
            _periodic_cleanup(log_dir, max_age_days, interval_hours)
        )


def stop_periodic_log_cleanup():
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
