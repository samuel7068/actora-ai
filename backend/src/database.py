import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config import get_settings

config = get_settings()

logging.basicConfig(level=config.LOGGING_LEVEL)
logger = logging.getLogger(__name__)

Base = declarative_base()

_async_engine = None
_AsyncSessionLocal = None


def _get_async_session_local():
    global _async_engine, _AsyncSessionLocal
    if _AsyncSessionLocal is not None:
        return _AsyncSessionLocal

    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    # env의 sync 드라이버(psycopg2) → async 드라이버(asyncpg)로 교체
    async_url = config.DATABASE_URL.replace("postgresql+psycopg2", "postgresql+asyncpg")

    # PG max_connections=20, superuser 예약 3개 제외하면 일반 17개 가용.
    # 백엔드는 풀 8 + overflow 4 = 최대 12개 사용 (여유분 확보).
    _async_engine = create_async_engine(
        async_url,
        pool_size=8,
        max_overflow=4,
        pool_timeout=20,
        pool_recycle=1800,
    )
    _AsyncSessionLocal = sessionmaker(
        bind=_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _AsyncSessionLocal


async def get_db():
    AsyncSessionLocal = _get_async_session_local()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def with_new_session():
    gen = get_db()
    try:
        db = await gen.__anext__()
        try:
            yield db
        finally:
            await gen.aclose()
    except StopAsyncIteration:
        raise RuntimeError("get_db yielded no session")
