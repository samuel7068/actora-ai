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
MAX_PHOTO_BYTES = 30 * 1024 * 1024  # 30 MB — 스마트폰·DSLR 원본 사진 대응
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

# ─────────────────────────────────────────────────────────
# 삭제 대장 — 개발 PC ↔ 운영 서버 파일 동기화용
# ─────────────────────────────────────────────────────────
# DB 와 Qdrant 는 두 환경이 공유하지만 파일은 각자 디스크에 있다.
# rsync 는 삭제를 전파하지 않으므로(전파시키면 반대편에서만 등록한 파일이 지워진다),
# 여기에 "지운 경로" 를 남겨 두고 동기화 스크립트가 그 목록만 반대편에서 지운다.
#
# 이 파일은 rsync 대상에서 제외한다 (scripts/sync-uploads.sh 참조).
DELETION_LOG_NAME = ".deleted.log"


def deletion_log_path() -> Path:
    return Path(get_settings().UPLOAD_DIR) / DELETION_LOG_NAME


def record_deletion(relative_key: str) -> None:
    """삭제한 상대 경로를 대장에 남긴다 (best-effort — 실패해도 삭제는 진행).

    relative_key 는 uploads 기준 상대 경로.
        talent/12/portfolio/12_22.mp4
        talent/12                      ← 디렉토리 통째로 지운 경우
    """
    key = (relative_key or "").strip().strip("/")
    if not key:
        return
    try:
        path = deletion_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{key}\n")
    except Exception as e:
        logger.warning(f"삭제 대장 기록 실패 ({key}): {e}")
