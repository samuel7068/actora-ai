"""미디어 라우터.

- POST /talent/me/media        : 현재 로그인된 talent 가 자기 미디어 업로드
- GET  /talent/me/media        : 자기 미디어 목록
- GET  /media/{media_id}       : 미디어 조회 (권한 체크 → stream 또는 X-Accel-Redirect)
- DELETE /talent/me/media/{id} : 자기 미디어 삭제
"""
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import get_db
from src.auth.deps import get_current_account
from src.media.schemas import MediaInfo, MediaListResponse
from src.analysis.rag_index import delete_media_points
from src.media.service import (
    absolute_path,
    save_upload_file,
    stream_url_for,
)
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

    # 디스크 파일 제거 (실패해도 DB 는 삭제)
    try:
        path = absolute_path(row.media_path)
        if path.exists():
            os.remove(path)
    except OSError as e:
        logger.warning(f"media file remove failed: {e}")

    # RAG .txt 제거 (uploads/rag/{account_id}_{talent_media_id}.txt) — best-effort
    try:
        rag_path = absolute_path(
            f"rag/{row.account_id}_{row.talent_media_id}.txt"
        )
        if rag_path.exists():
            os.remove(rag_path)
    except OSError as e:
        logger.warning(f"rag txt remove failed: {e}")

    # Qdrant 벡터 제거 — talent_media_id 필터로 해당 영상의 scene 포인트 일괄 삭제 (best-effort)
    try:
        await delete_media_points(row.talent_media_id)
    except Exception as e:
        logger.warning(f"qdrant delete failed: {e}")

    await db.delete(row)
    await db.commit()
    return {"success": True, "deleted_id": media_id}


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
    - nginx X-Accel-Redirect 환경(XACCEL_PREFIX 설정)에선 redirect 헤더만,
      그 외엔 백엔드가 직접 FileResponse 로 stream.
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

    config = get_settings()

    if config.XACCEL_PREFIX:
        # nginx X-Accel-Redirect — 백엔드는 헤더만 보내고 nginx 가 실제 파일 stream.
        #
        # 넘기기 전에 파일이 컨테이너에 보이는지 반드시 확인한다.
        # 확인 없이 헤더만 보내면 파일이 없어도 백엔드는 200 을 남기고 nginx 만 404 를
        # 내므로, 화면에서는 "재생 안 됨"인데 백엔드 로그에는 아무 단서가 없다.
        # (실제로 볼륨 마운트 경로가 어긋나 이 증상을 겪었다)
        path = absolute_path(row.media_path)
        if not path.exists():
            logger.error(
                f"media {media_id} 파일 없음 → 404. "
                f"media_path={row.media_path!r} / 확인한 경로={path} / "
                f"UPLOAD_DIR={config.UPLOAD_DIR} — "
                f"호스트의 uploads 디렉토리가 컨테이너에 제대로 마운트됐는지 확인할 것"
            )
            raise HTTPException(status_code=404, detail="FILE_NOT_FOUND_ON_DISK")

        internal_path = f"{config.XACCEL_PREFIX.rstrip('/')}/{row.media_path}"
        logger.info(
            f"media {media_id} X-Accel → {internal_path} "
            f"({path.stat().st_size:,} bytes)"
        )
        return Response(
            status_code=200,
            headers={
                "X-Accel-Redirect": internal_path,
                "Content-Type": row.mime_type or "application/octet-stream",
            },
        )

    # 백엔드 직접 stream (Mac dev / nginx 없는 환경)
    path = absolute_path(row.media_path)
    if not path.exists():
        logger.error(
            f"media {media_id} 파일 없음 → 404. "
            f"media_path={row.media_path!r} / 확인한 경로={path} / "
            f"UPLOAD_DIR={config.UPLOAD_DIR}"
        )
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND_ON_DISK")
    return FileResponse(
        path,
        media_type=row.mime_type or "application/octet-stream",
        filename=row.original_file_name or row.stored_file_name,
    )
