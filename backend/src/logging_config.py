import logging
import logging.handlers
from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
from typing import Optional
from zoneinfo import ZoneInfo
import os


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

    class UTCFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            tz = ZoneInfo("Asia/Seoul") if environment == "loc" else timezone.utc
            dt = datetime.fromtimestamp(record.created, tz=tz)
            if datefmt:
                return dt.strftime(datefmt)
            return dt.strftime('%Y-%m-%d %H:%M:%S %Z')

    formatter = UTCFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if not is_local:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        info_handler = logging.handlers.RotatingFileHandler(
            filename=log_path / 'app.log',
            maxBytes=1 * 1024 * 1024 * 1024,
            backupCount=2,
            encoding='utf-8'
        )
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)
        root_logger.addHandler(info_handler)

        error_handler = logging.handlers.RotatingFileHandler(
            filename=log_path / 'error.log',
            maxBytes=500 * 1024 * 1024,
            backupCount=2,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
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
