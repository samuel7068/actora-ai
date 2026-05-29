from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging

from src.exceptions import http_exception_handler, global_exception_handler
from src.config import get_settings, init_redis
from src.qdrant import get_qdrant_client, close_qdrant_client, ping_qdrant
from src.auth.router import auth_router
from src.media.router import talent_media_router, media_router
from src.admin.router import admin_router
from src.talent.router import talent_profile_router
from src.logging_config import (
    setup_logging,
    cleanup_old_logs,
    start_periodic_log_cleanup,
    stop_periodic_log_cleanup,
)


class IgnoreHeartbeat(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/auth/heartbeat" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(IgnoreHeartbeat())

config = get_settings()
environment = os.getenv("ENVIRONMENT", "loc")

logger = setup_logging(log_level=config.LOGGING_LEVEL, log_dir="logs")
logger.info(f"환경: {environment} | APP: {config.APP_NAME} | ROOT_PATH: {config.ROOT_PATH}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_old_logs(log_dir="logs", max_age_days=7)
    start_periodic_log_cleanup(log_dir="logs", max_age_days=7, interval_hours=24)

    # Redis (선택적)
    try:
        redis_client = await init_redis()
        app.state.redis = redis_client
        logger.info("Redis 초기화 완료")
    except Exception as e:
        logger.warning(f"Redis 초기화 실패 (계속 진행): {e}")

    # Qdrant (선택적 — 실패해도 앱은 동작, 벡터 검색만 안 됨)
    try:
        app.state.qdrant = get_qdrant_client()
        result = await ping_qdrant()
        logger.info(f"Qdrant 초기화 완료 (collections={result['collections']})")
    except Exception as e:
        logger.warning(f"Qdrant 초기화 실패 (계속 진행): {e}")

    try:
        yield
    finally:
        stop_periodic_log_cleanup()
        if hasattr(app.state, "redis"):
            try:
                await app.state.redis.close()
            except Exception as e:
                logger.warning(f"Redis close 예외: {e}")
        await close_qdrant_client()


if environment == "loc":
    app = FastAPI(title=config.APP_NAME, lifespan=lifespan, root_path=config.ROOT_PATH)
else:
    app = FastAPI(
        title=config.APP_NAME,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
        root_path=config.ROOT_PATH,
    )

allowed_domains = config.ALLOWED_DOMAINS
if isinstance(allowed_domains, str):
    allowed_domains = [d.strip() for d in allowed_domains.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_domains,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(talent_profile_router, prefix="/talent", tags=["talent-profile"])
app.include_router(talent_media_router, prefix="/talent", tags=["talent-media"])
app.include_router(media_router, prefix="/media", tags=["media"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/health", include_in_schema=False)
async def health_check():
    qdrant_status: dict
    try:
        qdrant_status = await ping_qdrant()
    except Exception as e:
        qdrant_status = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"status": "Good", "qdrant": qdrant_status}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, proxy_headers=True, forwarded_allow_ips="*")
