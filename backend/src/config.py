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

    # ── 파일 저장 ────────────────────────────────────────────
    # S3_BUCKET 이 있으면 오브젝트 스토리지, 없으면 로컬 디스크를 쓴다.
    # (src/storage.py 가 이 설정만 보고 구현을 고른다)
    #
    # 개발 PC 와 운영 서버가 **같은 버킷**을 쓴다. DB·Qdrant 를 이미 공유하고
    # 있으므로 파일도 한 곳에 두어야 "DB 에는 있는데 파일이 없는" 상태가 없다.
    S3_BUCKET: str = ""
    S3_REGION: str = "ap-northeast-2"
    # Lightsail 버킷 / R2 등 비 AWS 엔드포인트용. 비우면 AWS 기본 엔드포인트.
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    # presigned URL 유효시간. 긴 영상 재생 중 만료되지 않도록 넉넉히 준다.
    S3_PRESIGN_TTL: int = 6 * 60 * 60  # 6시간

    # 로컬 디스크 저장 경로 (S3_BUCKET 이 비어 있을 때만 쓰인다)
    UPLOAD_DIR: str = "./uploads"
    # nginx X-Accel-Redirect 사용 시 사용자에게 응답할 internal location prefix.
    # 비어있으면 백엔드가 직접 파일 stream (Mac dev).
    # S3 를 쓰면 nginx 를 거치지 않으므로 이 값은 무시된다.
    XACCEL_PREFIX: str = ""

    # 프로필 사진 썸네일 — 원본(2MB+)을 목록에 그대로 내리면 전송량이 빨리 찬다.
    # 폭 이 값 이하로 줄인 WebP 를 따로 저장해 화면에는 그것만 보낸다.
    PROFILE_THUMB_WIDTH: int = 800
    PROFILE_THUMB_QUALITY: int = 82

    # 영상 카드에 보이는 포스터 폭. 분석 때 뽑은 대표 프레임을 이 크기로 저장한다.
    # 카드는 300px 남짓으로 표시되므로 고해상도 화면(2x)까지 640 이면 충분하다.
    VIDEO_THUMB_WIDTH: int = 640

    # OpenAI (영상 분석 STT / GPT 평가)
    OPENAI_API_KEY: str = ""

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
