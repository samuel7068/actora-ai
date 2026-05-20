import logging
from typing import Optional

from qdrant_client import AsyncQdrantClient

from src.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncQdrantClient] = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Lazy singleton. 첫 호출 시 AsyncQdrantClient 생성하고 그 이후 재사용.

    QDRANT_URL 이 설정되어 있으면 원격 Qdrant 서버에 연결 (운영).
    비어있으면 로컬 임베디드 모드로 './qdrant_local' 디렉토리에 영속 (Mac dev).
    """
    global _client
    if _client is not None:
        return _client

    config = get_settings()
    if config.QDRANT_URL:
        _client = AsyncQdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY or None,
            prefer_grpc=False,
        )
        logger.info(f"Qdrant 원격 연결: {config.QDRANT_URL}")
    else:
        local_path = "./qdrant_local"
        _client = AsyncQdrantClient(path=local_path)
        logger.info(f"Qdrant 로컬 임베디드 모드: {local_path}")

    return _client


async def close_qdrant_client() -> None:
    global _client
    if _client is None:
        return
    try:
        await _client.close()
    except Exception as e:
        logger.warning(f"Qdrant client close 중 예외: {e}")
    finally:
        _client = None


async def ping_qdrant() -> dict:
    """연결 + 기본 조회 검증. 성공 시 {'ok': True, 'collections': N}"""
    client = get_qdrant_client()
    resp = await client.get_collections()
    return {"ok": True, "collections": len(resp.collections)}
