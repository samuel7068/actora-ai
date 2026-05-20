"""미디어 파일 저장/검증/조회 헬퍼.

저장 구조:
    {UPLOAD_DIR}/talent/{account_id}/{stored_file_name}

media_path 는 상대 키만 저장:
    talent/{account_id}/{stored_file_name}
"""
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from src.config import get_settings

logger = logging.getLogger(__name__)

# 허용 MIME / 확장자 / 사이즈
_ALLOWED_PHOTO_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_ALLOWED_MOVIE_MIME = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
}
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_MOVIE_BYTES = 500 * 1024 * 1024  # 500 MB


def determine_media_type(content_type: Optional[str]) -> str:
    """MIME → media_type ('PHOTO'/'MOVIE'). 알 수 없으면 HTTPException 400."""
    if not content_type:
        raise HTTPException(status_code=400, detail="MIME_TYPE_MISSING")
    ct = content_type.lower()
    if ct in _ALLOWED_PHOTO_MIME:
        return "PHOTO"
    if ct in _ALLOWED_MOVIE_MIME:
        return "MOVIE"
    raise HTTPException(status_code=400, detail=f"UNSUPPORTED_MIME:{ct}")


def _ext_for_mime(content_type: str) -> str:
    ct = content_type.lower()
    return _ALLOWED_PHOTO_MIME.get(ct) or _ALLOWED_MOVIE_MIME.get(ct) or "bin"


def _max_size_for_media_type(media_type: str) -> int:
    return MAX_PHOTO_BYTES if media_type == "PHOTO" else MAX_MOVIE_BYTES


def build_relative_key(account_id: int, stored_file_name: str) -> str:
    return f"talent/{account_id}/{stored_file_name}"


def absolute_path(relative_key: str) -> Path:
    config = get_settings()
    return Path(config.UPLOAD_DIR) / relative_key


async def save_upload_file(
    upload: UploadFile, account_id: int
) -> tuple[str, str, int, str, str]:
    """업로드 파일을 디스크에 저장.

    반환: (stored_file_name, media_path, file_size, mime_type, media_type)
    """
    media_type = determine_media_type(upload.content_type)
    ext = _ext_for_mime(upload.content_type or "")
    max_bytes = _max_size_for_media_type(media_type)

    stored_file_name = f"{uuid.uuid4().hex}.{ext}"
    relative_key = build_relative_key(account_id, stored_file_name)
    dest_path = absolute_path(relative_key)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 스트리밍 저장 + 사이즈 검증
    total = 0
    CHUNK = 1024 * 1024  # 1 MB
    with dest_path.open("wb") as f:
        while True:
            chunk = await upload.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                f.close()
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                raise HTTPException(
                    status_code=413,
                    detail=f"FILE_TOO_LARGE:max_bytes={max_bytes}",
                )
            f.write(chunk)

    return (
        stored_file_name,
        relative_key,
        total,
        upload.content_type or "application/octet-stream",
        media_type,
    )


def stream_url_for(media_id: int) -> str:
    """클라이언트에게 알려줄 미디어 조회 URL."""
    return f"/api/media/{media_id}"
