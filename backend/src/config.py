from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import redis.asyncio as aioredis


class Settings(BaseSettings):

    ENVIRONMENT: str = "loc"

    # App
    APP_NAME: str = "Actora"
    SECRET_KEY: str
    ROOT_PATH: str = ""

    # CORS
    ALLOWED_DOMAINS: str = "http://localhost:3000"

    # Database (PostgreSQL, sync URL — async 변환은 database.py에서 처리)
    DATABASE_URL: str = ""

    # Qdrant (vector DB) — docker network 내부 호스트명
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str = ""

    # Redis (optional in prototype)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: str = "6379"
    REDIS_SESSION_TIMEOUT: int = 3600

    # 업로드 파일 저장 디렉토리 (운영=/app/uploads bind mount, dev=./uploads)
    UPLOAD_DIR: str = "./uploads"
    # nginx X-Accel-Redirect 사용 시 사용자에게 응답할 internal location prefix (옵션 C)
    # 비어있으면 백엔드가 직접 파일 stream (Mac dev)
    XACCEL_PREFIX: str = ""

    # Logging
    LOGGING_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=os.path.join(".", f".env.{os.getenv('ENVIRONMENT', 'loc')}"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()


async def init_redis():
    config = get_settings()
    return aioredis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )
