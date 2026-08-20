import logging
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
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.account.models import AccountMaster
from src.admin.models import AdminMaster
from src.auth.deps import get_current_account
from src.auth.security import decode_access_token
from src.media.service import (
    profile_relative_key,
    profile_thumb_key,
    save_profile_photo,
)
from src.storage import get_storage
from src.talent.models import TalentMaster
from src.talent.schemas import TalentProfileResponse, TalentProfileUpdateRequest

logger = logging.getLogger(__name__)

talent_profile_router = APIRouter()

# 프로필 사진 저장/검증 로직은 src/media/service.py 에 모여 있다
# (talent 셀프 업로드와 admin 대행 업로드가 같은 코드를 쓰도록)

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

    # 검증·리사이즈·업로드는 service 가 담당한다 (admin 대행 업로드와 같은 코드)
    filename, url, total = await save_profile_photo(file, account.account_id)
    return {"url": url, "filename": filename, "size": total}


# ─────────────────────────────────────────────────────────
# GET /talent/profile-photo/{account_id}/{filename}
#   인증 필요 (Bearer 또는 ?token= 쿼리 파라미터 - <img src> 용).
# ─────────────────────────────────────────────────────────
@talent_profile_router.get("/profile-photo/{account_id}/{filename}")
async def get_profile_photo(
    account_id: int,
    filename: str,
    original: bool = Query(default=False, description="1이면 리사이즈 전 원본"),
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

    store = get_storage()

    # 기본은 썸네일. 원본(2MB+)을 목록·카드에 그대로 내리면 전송량이 빨리 찬다.
    # 얼굴 임베딩처럼 해상도가 필요한 쪽은 백엔드가 저장소에서 직접 원본을 읽는다.
    # ?original=1 은 사람이 원본을 확인해야 할 때를 위한 탈출구.
    key = profile_relative_key(account_id, filename)
    mime = _mime_from_filename(filename)
    if not original:
        thumb_key = profile_thumb_key(account_id, filename)
        # 썸네일 도입 전에 올린 사진에는 썸네일이 없다 → 원본으로 폴백
        if store.exists(thumb_key):
            key, mime = thumb_key, "image/webp"

    # S3 계열: 브라우저가 버킷에서 직접 받아가게 서명 URL 로 넘긴다.
    # 사진 바이트가 백엔드를 거치지 않으므로 워커를 잡아 두지 않는다.
    signed = store.presigned_url(key, content_type=mime)
    if signed:
        # 302 는 캐시되면 만료된 URL 이 재사용되므로 캐시를 막는다
        return RedirectResponse(
            signed, status_code=307, headers={"Cache-Control": "no-store"}
        )

    # 로컬 디스크 폴백
    if not store.exists(key):
        logger.error(
            f"프로필 사진 없음 → 404. key={key} account={account_id} "
            f"backend={getattr(store, 'backend', '?')}"
        )
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
    return StreamingResponse(store.iter_chunks(key), media_type=mime)
