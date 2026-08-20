"""미디어 파일 저장/검증/조회 헬퍼.

파일은 오브젝트 스토리지(또는 로컬 폴백)에 둔다 — src/storage.py 참조.
개발 PC 와 운영 서버가 같은 버킷을 보므로 파일 동기화가 필요 없다.

키 규칙 (DB 의 media_path 와 동일):
    talent/{account_id}/{stored_file_name}
    talent/{account_id}/profile/{filename}          원본 (얼굴 임베딩용)
    talent/{account_id}/profile/thumb/{stem}.webp   썸네일 (화면 표시용)
"""
import io
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from src.config import get_settings
from src.storage import CHUNK, StorageError, get_storage

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


# ─────────────────────────────────────────────────────────
# 업로드 → 저장소
# ─────────────────────────────────────────────────────────
async def spool_to_temp(upload: UploadFile, max_bytes: int) -> tuple[Path, int]:
    """업로드를 임시파일로 받으며 크기를 검증한다.

    저장소에 올리기 전에 로컬에 한 번 받는 이유:
      - 크기 초과를 다 받기 전에 끊을 수 있다 (메모리에 쌓지 않는다)
      - 초과·실패 시 버킷에 잘린 오브젝트가 남지 않는다
    """
    tmp = Path(tempfile.mkstemp(prefix="actora_up_")[1])
    total = 0
    try:
        with tmp.open("wb") as f:
            while True:
                chunk = await upload.read(CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"FILE_TOO_LARGE:max_bytes={max_bytes}",
                    )
                f.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp, total


async def save_upload_file(
    upload: UploadFile, account_id: int
) -> tuple[str, str, int, str, str]:
    """업로드 파일을 저장소에 보관.

    반환: (stored_file_name, media_path, file_size, mime_type, media_type)
    """
    media_type = determine_media_type(upload.content_type)
    ext = _ext_for_mime(upload.content_type or "")
    mime = upload.content_type or "application/octet-stream"

    stored_file_name = f"{uuid.uuid4().hex}.{ext}"
    relative_key = build_relative_key(account_id, stored_file_name)

    tmp, total = await spool_to_temp(upload, _max_size_for_media_type(media_type))
    try:
        # put_file 은 성공하면 임시파일을 정리한다
        get_storage().put_file(tmp, relative_key, content_type=mime)
    except StorageError as e:
        logger.error(f"업로드 저장 실패 ({relative_key}): {e}")
        raise HTTPException(status_code=502, detail="STORAGE_UPLOAD_FAILED") from e
    finally:
        tmp.unlink(missing_ok=True)

    return stored_file_name, relative_key, total, mime, media_type


def stream_url_for(media_id: int) -> str:
    """클라이언트에게 알려줄 미디어 조회 URL."""
    return f"/api/media/{media_id}"


# ─────────────────────────────────────────────────────────
# 프로필 사진 — 원본 + 썸네일
# ─────────────────────────────────────────────────────────
# 원본을 목록·카드에 그대로 내리면 장당 2MB 가 넘어 전송량이 영상보다 빨리 찬다.
# (실측: 사진 평균 2.21MB → 카드 12개 한 페이지가 26MB)
# 그래서 폭을 줄인 WebP 를 함께 만들어 화면에는 그것만 보낸다.
# 원본은 얼굴 임베딩(InsightFace)이 해상도를 필요로 하므로 버킷에 남긴다.
PROFILE_PHOTO_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_PROFILE_PHOTO_BYTES = MAX_PHOTO_BYTES


def profile_relative_key(account_id: int, filename: str) -> str:
    return f"talent/{account_id}/profile/{filename}"


def profile_thumb_key(account_id: int, filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    return f"talent/{account_id}/profile/thumb/{stem}.webp"


def profile_public_url(account_id: int, filename: str) -> str:
    return f"/api/talent/profile-photo/{account_id}/{filename}"


# ─────────────────────────────────────────────────────────
# 영상 포스터 (카드 목록에 보이는 대표 이미지)
# ─────────────────────────────────────────────────────────
# 영상 자체를 카드에 로드하면 30MB 가 넘게 오간다. 분석 때 이미 뽑아 둔
# 대표 프레임(인재 얼굴이 가장 잘 잡힌 장면)을 작은 WebP 로 저장해 쓴다.
def portfolio_thumb_key(account_id: int, media_id: int) -> str:
    return f"talent/{account_id}/portfolio/thumb/{account_id}_{media_id}.webp"


def save_portfolio_thumbnail(
    frame_path: Path, account_id: int, media_id: int
) -> Optional[str]:
    """대표 프레임 이미지를 영상 포스터로 저장하고 키를 돌려준다.

    실패하면 None — 포스터가 없으면 화면이 아이콘으로 폴백하므로
    분석 자체를 실패시키지 않는다.
    """
    data = make_thumbnail(frame_path, width=get_settings().VIDEO_THUMB_WIDTH)
    if not data:
        return None
    key = portfolio_thumb_key(account_id, media_id)
    try:
        get_storage().put_bytes(data, key, content_type="image/webp")
    except StorageError as e:
        logger.warning(f"영상 포스터 저장 실패 ({key}): {e}")
        return None
    logger.info(f"영상 포스터 저장 {key} ({len(data) / 1024:,.0f}KB)")
    return key


def make_thumbnail(source: Path, width: int = 0) -> Optional[bytes]:
    """이미지 → WebP 썸네일. 실패하면 None (호출자가 원본으로 폴백).

    width 를 주지 않으면 프로필 사진 기준 폭을 쓴다.
    """
    config = get_settings()
    try:
        from PIL import Image, ImageOps

        with Image.open(source) as im:
            # 스마트폰 사진의 EXIF 회전 정보를 픽셀에 반영해 둔다
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            width = width or config.PROFILE_THUMB_WIDTH
            if im.width > width:
                im = im.resize(
                    (width, round(im.height * width / im.width)),
                    Image.LANCZOS,
                )
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=config.PROFILE_THUMB_QUALITY, method=4)
            return buf.getvalue()
    except Exception as e:
        logger.warning(f"썸네일 생성 실패 ({source.name}): {e} — 원본으로 서빙한다")
        return None


async def save_profile_photo(
    upload: UploadFile, account_id: int
) -> tuple[str, str, int]:
    """프로필 사진을 원본 + 썸네일로 저장.

    반환: (filename, public_url, original_size)
    """
    ct = (upload.content_type or "").lower()
    if ct not in PROFILE_PHOTO_MIME:
        raise HTTPException(
            status_code=400, detail=f"UNSUPPORTED_MIME:{upload.content_type}"
        )

    filename = f"{uuid.uuid4().hex}.{PROFILE_PHOTO_MIME[ct]}"
    key = profile_relative_key(account_id, filename)

    tmp, total = await spool_to_temp(upload, MAX_PROFILE_PHOTO_BYTES)
    store = get_storage()
    try:
        thumb = make_thumbnail(tmp)  # 원본을 옮기기 전에 만든다
        store.put_file(tmp, key, content_type=ct)
        if thumb:
            store.put_bytes(
                thumb,
                profile_thumb_key(account_id, filename),
                content_type="image/webp",
            )
            logger.info(
                f"프로필 사진 저장 account={account_id} "
                f"원본 {total / 1024:,.0f}KB → 썸네일 {len(thumb) / 1024:,.0f}KB"
            )
    except StorageError as e:
        logger.error(f"프로필 사진 저장 실패 ({key}): {e}")
        raise HTTPException(status_code=502, detail="STORAGE_UPLOAD_FAILED") from e
    finally:
        tmp.unlink(missing_ok=True)

    return filename, profile_public_url(account_id, filename), total
