"""미디어 라우터.

- POST /talent/me/media        : 현재 로그인된 talent 가 자기 미디어 업로드
- GET  /talent/me/media        : 자기 미디어 목록
- GET  /media/{media_id}       : 미디어 조회 (권한 체크 → 서명 URL redirect 또는 stream)
- DELETE /talent/me/media/{id} : 자기 미디어 삭제
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.auth.deps import get_current_account
from src.media.schemas import MediaInfo, MediaListResponse
from src.analysis.rag_index import delete_media_points
from src.media.service import (
    save_upload_file,
    stream_url_for,
)
from src.storage import get_storage
from src.talent.models import TalentMaster, TalentMedia

logger = logging.getLogger(__name__)

talent_media_router = APIRouter()
media_router = APIRouter()


def _to_info(row: TalentMedia) -> MediaInfo:
    return MediaInfo(
        talent_media_id=row.talent_media_id,
        account_id=row.account_id,
        media_type=row.media_type,
        media_path=row.media_path,
        thumbnail_path=row.thumbnail_path,
        original_file_name=row.original_file_name,
        stored_file_name=row.stored_file_name,
        file_size=row.file_size,
        mime_type=row.mime_type,
        title=row.title,
        description=row.description,
        ai_summary=row.ai_summary,
        sort_order=row.sort_order,
        is_main=row.is_main,
        is_public=row.is_public,
        view_count=row.view_count,
        created_at=row.created_at,
        stream_url=stream_url_for(row.talent_media_id),
    )


# ─────────────────────────────────────────────────────────
# POST /talent/me/media
# ─────────────────────────────────────────────────────────
@talent_media_router.post("/me/media", response_model=MediaInfo)
async def upload_my_media(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    is_main: bool = Form(default=False),
    is_public: bool = Form(default=True),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    account, _admin = current
    if account.account_type != "TALENT":
        raise HTTPException(status_code=403, detail="TALENT_ONLY")

    # talent_master 행 있는지 확인 (없으면 회원가입 미완)
    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == account.account_id)
        )
    ).scalar_one_or_none()
    if not talent:
        raise HTTPException(status_code=404, detail="TALENT_PROFILE_NOT_FOUND")

    # 디스크 저장
    stored, relative_key, size, mime, media_type = await save_upload_file(
        file, account.account_id
    )

    # is_main=True 면 기존 main 해제 (partial unique 충돌 회피)
    if is_main:
        await db.execute(
            update(TalentMedia)
            .where(TalentMedia.account_id == account.account_id, TalentMedia.is_main.is_(True))
            .values(is_main=False)
        )

    # sort_order: 같은 account 의 max + 100 (없으면 100)
    cur_max = (
        await db.execute(
            select(TalentMedia.sort_order)
            .where(TalentMedia.account_id == account.account_id)
            .order_by(TalentMedia.sort_order.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_order = (cur_max or 0) + 100

    row = TalentMedia(
        account_id=account.account_id,
        media_type=media_type,
        media_path=relative_key,
        original_file_name=file.filename,
        stored_file_name=stored,
        file_size=size,
        mime_type=mime,
        title=title,
        description=description,
        sort_order=next_order,
        is_main=is_main,
        is_public=is_public,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return _to_info(row)


# ─────────────────────────────────────────────────────────
# GET /talent/me/media
# ─────────────────────────────────────────────────────────
@talent_media_router.get("/me/media", response_model=MediaListResponse)
async def list_my_media(
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    account, _ = current
    if account.account_type != "TALENT":
        raise HTTPException(status_code=403, detail="TALENT_ONLY")

    rows = (
        await db.execute(
            select(TalentMedia)
            .where(TalentMedia.account_id == account.account_id)
            .order_by(TalentMedia.sort_order.asc(), TalentMedia.talent_media_id.asc())
        )
    ).scalars().all()

    return MediaListResponse(items=[_to_info(r) for r in rows], total=len(rows))


# ─────────────────────────────────────────────────────────
# DELETE /talent/me/media/{media_id}
# ─────────────────────────────────────────────────────────
@talent_media_router.delete("/me/media/{media_id}")
async def delete_my_media(
    media_id: int,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    account, _ = current

    row = (
        await db.execute(
            select(TalentMedia).where(TalentMedia.talent_media_id == media_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MEDIA_NOT_FOUND")
    if row.account_id != account.account_id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    # 저장소 파일 제거 (실패해도 DB 는 삭제)
    # 버킷을 두 환경이 공유하므로 여기서 지우면 양쪽에서 함께 사라진다.
    store = get_storage()
    store.delete(row.media_path)
    store.delete(f"rag/{row.account_id}_{row.talent_media_id}.txt")

    # Qdrant 벡터 제거 — talent_media_id 필터로 해당 영상의 scene 포인트 일괄 삭제 (best-effort)
    try:
        await delete_media_points(row.talent_media_id)
    except Exception as e:
        logger.warning(f"qdrant delete failed: {e}")

    await db.delete(row)
    await db.commit()
    return {"success": True, "deleted_id": media_id}


# ─────────────────────────────────────────────────────────
# GET /media/{media_id}/thumbnail — 카드 목록용 포스터
# ─────────────────────────────────────────────────────────
# 반드시 /{media_id} 보다 위에 선언한다 — 아래에 두면 경로가 가로채인다.
@media_router.get("/{media_id}/thumbnail")
async def get_media_thumbnail(
    media_id: int,
    db: AsyncSession = Depends(get_db),
):
    """영상 포스터(WebP). 없으면 404 — 화면은 아이콘으로 폴백한다."""
    row = (
        await db.execute(
            select(TalentMedia).where(TalentMedia.talent_media_id == media_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MEDIA_NOT_FOUND")
    if not row.is_public:
        raise HTTPException(status_code=401, detail="NOT_PUBLIC_AUTH_REQUIRED")
    if not row.thumbnail_path:
        # 포스터 도입 전에 분석한 영상 — 백필 스크립트로 만들 수 있다
        raise HTTPException(status_code=404, detail="THUMBNAIL_NOT_GENERATED")

    store = get_storage()
    signed = store.presigned_url(row.thumbnail_path, content_type="image/webp")
    if signed:
        return RedirectResponse(
            signed, status_code=307, headers={"Cache-Control": "no-store"}
        )
    if not store.exists(row.thumbnail_path):
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
    return StreamingResponse(
        store.iter_chunks(row.thumbnail_path), media_type="image/webp"
    )


# ─────────────────────────────────────────────────────────
# GET /media/{media_id}  — 공용 stream (권한 체크 후)
# ─────────────────────────────────────────────────────────
@media_router.get("/{media_id}")
async def get_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
):
    """미디어 조회.

    - is_public 이면 누구나
    - 비공개면 본인만 (향후 권한 정책 확장)
    - 저장소가 S3 계열이면 서명 URL 로 307 redirect (바이트는 백엔드를 안 거친다)
    - 로컬 디스크 폴백이면 백엔드가 직접 stream
    """
    row = (
        await db.execute(
            select(TalentMedia).where(TalentMedia.talent_media_id == media_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MEDIA_NOT_FOUND")

    # 공개 정책 (프로토타입 단순화): is_public=True 면 모두 허용
    # 비공개 미디어 권한 정책은 추후 (현재는 401)
    if not row.is_public:
        raise HTTPException(status_code=401, detail="NOT_PUBLIC_AUTH_REQUIRED")

    # 조회수 증가 (best-effort, 트랜잭션 분리)
    try:
        await db.execute(
            update(TalentMedia)
            .where(TalentMedia.talent_media_id == media_id)
            .values(view_count=TalentMedia.view_count + 1)
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"view_count update failed: {e}")

    store = get_storage()
    mime = row.mime_type or "application/octet-stream"

    # 서명 URL 로 302 — 영상 바이트가 백엔드를 거치지 않는다.
    # 브라우저가 버킷에서 직접 받으므로 Range 요청(구간 탐색)도 그대로 동작하고,
    # 긴 영상이 백엔드 워커를 점유하지 않는다.
    signed = store.presigned_url(
        row.media_path,
        content_type=mime,
        filename=row.original_file_name or row.stored_file_name or "",
    )
    if signed:
        logger.info(f"media {media_id} → 서명 URL 발급 (key={row.media_path})")
        # 서명이 만료된 뒤 캐시된 302 가 재사용되면 재생이 깨진다
        return RedirectResponse(
            signed, status_code=307, headers={"Cache-Control": "no-store"}
        )

    # 로컬 디스크 폴백 (S3_BUCKET 미설정)
    if not store.exists(row.media_path):
        logger.error(
            f"media {media_id} 파일 없음 → 404. media_path={row.media_path!r} / "
            f"backend={getattr(store, 'backend', '?')} — "
            "S3_BUCKET 이 설정되지 않아 로컬 디스크를 보고 있다. "
            "반대쪽 환경에서 올린 파일이라면 이 서버에는 없다."
        )
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
    return StreamingResponse(store.iter_chunks(row.media_path), media_type=mime)
