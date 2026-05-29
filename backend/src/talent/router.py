import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import get_db
from src.account.models import AccountMaster
from src.admin.models import AdminMaster
from src.auth.deps import get_current_account
from src.auth.security import decode_access_token
from src.media.service import absolute_path
from src.talent.models import TalentMaster
from src.talent.schemas import TalentProfileResponse, TalentProfileUpdateRequest

logger = logging.getLogger(__name__)

talent_profile_router = APIRouter()

# 프로필 사진 저장/검증
_PROFILE_PHOTO_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_MAX_PROFILE_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB

def _profile_relative_key(account_id: int, filename: str) -> str:
    return f"talent/{account_id}/profile/{filename}"

def _profile_public_url(account_id: int, filename: str) -> str:
    return f"/api/talent/profile-photo/{account_id}/{filename}"

def _mime_from_filename(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp", "gif": "image/gif",
    }.get(ext, "application/octet-stream")


# talent_master 의 필수값 6개 (사용자 정의)
_REQUIRED_FIELDS = (
    "gender", "birth_date", "nationality", "main_category", "height_cm", "weight_kg",
)

# 완성도(%) 계산 대상 필드 — 전체 talent_master 사용자 입력 필드
_COMPLETION_FIELDS = (
    "stage_name", "gender", "gender_self_description", "birth_date", "nationality",
    "region_code", "main_category", "sub_categories", "profile_image_url",
    "profile_image_urls",
    "introduction", "height_cm", "weight_kg", "weight_range", "body_type", "face_type",
    "visual_keywords", "languages", "skills", "education_level", "education_major",
    "instagram_url", "youtube_url", "tiktok_url", "career_level", "career_years",
)


def _completion_rate(t: TalentMaster) -> int:
    filled = 0
    for f in _COMPLETION_FIELDS:
        v = getattr(t, f, None)
        if v is None:
            continue
        if isinstance(v, (list, str)) and len(v) == 0:
            continue
        filled += 1
    total = len(_COMPLETION_FIELDS)
    return round(filled * 100 / total)


def _to_response(t: TalentMaster) -> TalentProfileResponse:
    return TalentProfileResponse(
        account_id=t.account_id,
        stage_name=t.stage_name,
        gender=t.gender,
        gender_self_description=t.gender_self_description,
        birth_date=t.birth_date,
        nationality=t.nationality,
        region_code=t.region_code,
        main_category=t.main_category,
        sub_categories=t.sub_categories,
        profile_image_url=t.profile_image_url,
        profile_image_urls=t.profile_image_urls,
        introduction=t.introduction,
        height_cm=t.height_cm,
        weight_kg=t.weight_kg,
        weight_range=t.weight_range,
        body_type=t.body_type,
        face_type=t.face_type,
        visual_keywords=t.visual_keywords,
        languages=t.languages,
        skills=t.skills,
        education_level=t.education_level,
        education_major=t.education_major,
        instagram_url=t.instagram_url,
        youtube_url=t.youtube_url,
        tiktok_url=t.tiktok_url,
        career_level=t.career_level,
        career_years=t.career_years,
        visibility_status=t.visibility_status,
        approval_status=t.approval_status,
        profile_completion_rate=t.profile_completion_rate,
        ai_match_score=t.ai_match_score,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@talent_profile_router.get("/profile", response_model=TalentProfileResponse)
async def get_my_profile(
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    account: AccountMaster
    admin: AdminMaster | None
    account, _admin = current

    if account.account_type != "TALENT":
        raise HTTPException(status_code=403, detail="NOT_A_TALENT")

    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == account.account_id)
        )
    ).scalar_one_or_none()
    if talent is None:
        raise HTTPException(status_code=404, detail="TALENT_PROFILE_NOT_FOUND")

    return _to_response(talent)


@talent_profile_router.put("/profile", response_model=TalentProfileResponse)
async def update_my_profile(
    req: TalentProfileUpdateRequest,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    account, _admin = current
    if account.account_type != "TALENT":
        raise HTTPException(status_code=403, detail="NOT_A_TALENT")

    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == account.account_id)
        )
    ).scalar_one_or_none()
    if talent is None:
        raise HTTPException(status_code=404, detail="TALENT_PROFILE_NOT_FOUND")

    data = req.model_dump(exclude_unset=False)
    for field, value in data.items():
        setattr(talent, field, value)

    talent.profile_completion_rate = _completion_rate(talent)
    talent.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(talent)
    return _to_response(talent)


# ─────────────────────────────────────────────────────────
# POST /talent/profile/photo — 프로필 사진 1장 업로드
# ─────────────────────────────────────────────────────────
@talent_profile_router.post("/profile/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current=Depends(get_current_account),
):
    account, _admin = current
    if account.account_type != "TALENT":
        raise HTTPException(status_code=403, detail="TALENT_ONLY")

    if not file.content_type or file.content_type.lower() not in _PROFILE_PHOTO_MIME:
        raise HTTPException(
            status_code=400, detail=f"UNSUPPORTED_MIME:{file.content_type}"
        )

    ext = _PROFILE_PHOTO_MIME[file.content_type.lower()]
    filename = f"{uuid.uuid4().hex}.{ext}"
    relative_key = _profile_relative_key(account.account_id, filename)
    dest_path = absolute_path(relative_key)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    CHUNK = 1024 * 1024
    with dest_path.open("wb") as f:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_PROFILE_PHOTO_BYTES:
                f.close()
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                raise HTTPException(
                    status_code=413,
                    detail=f"FILE_TOO_LARGE:max_bytes={_MAX_PROFILE_PHOTO_BYTES}",
                )
            f.write(chunk)

    return {
        "url": _profile_public_url(account.account_id, filename),
        "filename": filename,
        "size": total,
    }


# ─────────────────────────────────────────────────────────
# GET /talent/profile-photo/{account_id}/{filename}
#   인증 필요 (Bearer 또는 ?token= 쿼리 파라미터 - <img src> 용).
# ─────────────────────────────────────────────────────────
@talent_profile_router.get("/profile-photo/{account_id}/{filename}")
async def get_profile_photo(
    account_id: int,
    filename: str,
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
):
    auth_token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        auth_token = authorization.split(" ", 1)[1].strip()
    elif token:
        auth_token = token.strip()
    if not auth_token:
        raise HTTPException(status_code=401, detail="MISSING_TOKEN")
    payload = decode_access_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    # 경로 traversal 방지 — filename 은 영숫자 + 점만
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="INVALID_FILENAME")

    relative_key = _profile_relative_key(account_id, filename)
    mime = _mime_from_filename(filename)
    config = get_settings()

    if config.XACCEL_PREFIX:
        internal_path = f"{config.XACCEL_PREFIX.rstrip('/')}/{relative_key}"
        return Response(
            status_code=200,
            headers={
                "X-Accel-Redirect": internal_path,
                "Content-Type": mime,
            },
        )

    path = absolute_path(relative_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND_ON_DISK")
    return FileResponse(path, media_type=mime)
