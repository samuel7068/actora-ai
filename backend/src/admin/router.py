"""관리자 전용 API (account_type='ADMIN' 만 접근)."""
import logging
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.models import AccountMaster
from src.analysis.rag_index import get_media_scenes
from src.auth.deps import get_current_account
from src.database import get_db
from src.media.service import absolute_path
from src.talent.models import TalentMaster, TalentMedia
from src.talent.router import (
    _MAX_PROFILE_PHOTO_BYTES,
    _PROFILE_PHOTO_MIME,
    _profile_public_url,
    _profile_relative_key,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter()


class AdminTalentCreate(BaseModel):
    """관리자 대행 인재 등록 입력.

    계정 식별자(login_id/email/password)는 받지 않는다 — 본인이 아직 없는
    시드 데이터이므로 시스템이 placeholder 로 자동 생성하고, 로그인은 불가 상태로 둔다.
    (추후 본인이 실제 가입할 때 이 레코드를 클레임/연결)
    """

    name: str
    # 프로필 (talent_master)
    stage_name: Optional[str] = None
    gender: Optional[str] = None          # MALE / FEMALE / SELF_DESCRIBED
    birth_date: Optional[date] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    region_code: Optional[str] = None
    main_category: Optional[str] = None   # ACTOR / MODEL / ...
    skills: list[str] = []
    languages: list[str] = []
    introduction: Optional[str] = None


def _calc_age(birth: date | None) -> int | None:
    if not birth:
        return None
    from datetime import date as _d

    today = _d.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )

# TASK_SHARE.md 위치 — 프로젝트 루트
# 컨테이너 내부: /app/TASK_SHARE.md (backend WORKDIR=/app, 코드 COPY . . 시 포함)
# Mac dev: backend/ 기준 상위 디렉토리의 TASK_SHARE.md
_TASK_SHARE_PATHS = [
    Path("/app/TASK_SHARE.md"),
    Path(__file__).resolve().parent.parent.parent.parent / "TASK_SHARE.md",
    Path(__file__).resolve().parent.parent.parent / "TASK_SHARE.md",
]


def _read_task_share() -> str:
    for p in _TASK_SHARE_PATHS:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"TASK_SHARE.md read error at {p}: {e}")
    return "# TASK_SHARE.md 를 찾을 수 없습니다.\n\n프로젝트 루트에 파일을 생성하세요."


@admin_router.get("/task-share")
async def get_task_share(current=Depends(get_current_account)):
    """관리자 전용 개발 공유 노트. ADMIN(SUPER/OPERATOR/CS) 전체 허용."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    content = _read_task_share()
    return {"content": content}


@admin_router.get("/media")
async def list_all_media(
    name: str | None = Query(default=None, description="연기자 이름(account_master.name) 부분검색"),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """전체 talent_media 목록 (관리자). name 주면 연기자 이름으로 필터."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    stmt = (
        select(TalentMedia, AccountMaster.name)
        .join(AccountMaster, TalentMedia.account_id == AccountMaster.account_id)
        .order_by(TalentMedia.talent_media_id.desc())
    )
    if name and name.strip():
        stmt = stmt.where(AccountMaster.name.ilike(f"%{name.strip()}%"))

    rows = (await db.execute(stmt)).all()
    items = [
        {
            "talent_media_id": m.talent_media_id,
            "account_id": m.account_id,
            "account_name": nm,
            "original_file_name": m.original_file_name,
            "ai_summary": m.ai_summary,
            "created_at": m.created_at,
        }
        for m, nm in rows
    ]
    return {"items": items, "total": len(items)}


@admin_router.get("/media/{media_id}/scenes")
async def get_media_rag_scenes(
    media_id: int, current=Depends(get_current_account)
):
    """영상의 RAG scene 데이터를 Qdrant 에서 조회 (.txt 대체 — 적재 payload 열람)."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    scenes = await get_media_scenes(media_id)
    return {"talent_media_id": media_id, "count": len(scenes), "scenes": scenes}


@admin_router.get("/talents")
async def list_talents(
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """등록된 전체 talent_master 목록 (관리자)."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    rows = (
        await db.execute(
            select(
                AccountMaster.account_id,
                AccountMaster.name,
                AccountMaster.created_at,
                TalentMaster.gender,
                TalentMaster.birth_date,
                TalentMaster.height_cm,
                TalentMaster.weight_kg,
                TalentMaster.region_code,
                TalentMaster.main_category,
                TalentMaster.skills,
                TalentMaster.languages,
            )
            .join(TalentMaster, AccountMaster.account_id == TalentMaster.account_id)
            .order_by(AccountMaster.account_id.desc())
        )
    ).all()
    items = [
        {
            "account_id": r[0],
            "name": r[1],
            "created_at": r[2],
            "gender": r[3],
            "age": _calc_age(r[4]),
            "height_cm": r[5],
            "weight_kg": r[6],
            "region_code": r[7],
            "main_category": r[8],
            "skills": r[9] or [],
            "languages": r[10] or [],
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


@admin_router.post("/talents", status_code=201)
async def create_talent(
    req: AdminTalentCreate,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """관리자 대행 인재 등록 — TALENT 계정 + talent_master 프로필 동시 생성."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    # 실제 로그인 계정이 아니라 시드 데이터 → 식별자는 자동 생성, 로그인 불가 상태.
    seed = uuid.uuid4().hex[:12]
    acc = AccountMaster(
        login_id=f"seed_{seed}",
        email=f"seed_{seed}@seed.actora.local",
        password=uuid.uuid4().hex,  # 랜덤 — 로그인 불가 (본인 클레임 시 재설정)
        name=req.name,
        account_type="TALENT",
    )
    db.add(acc)
    try:
        await db.flush()  # account_id 발급
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="SEED_ACCOUNT_CONFLICT")

    talent = TalentMaster(
        account_id=acc.account_id,
        stage_name=req.stage_name,
        gender=req.gender,
        birth_date=req.birth_date,
        height_cm=req.height_cm,
        weight_kg=req.weight_kg,
        region_code=req.region_code,
        main_category=req.main_category,
        skills=req.skills or None,
        languages=req.languages or None,
        introduction=req.introduction,
    )
    db.add(talent)
    await db.commit()

    return {"account_id": acc.account_id, "name": req.name}


@admin_router.get("/talents/{account_id}")
async def get_talent_for_edit(
    account_id: int,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """인재 수정 화면용 전체 프로필 (birth_date 포함)."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    res = (
        await db.execute(
            select(AccountMaster.name, TalentMaster)
            .join(TalentMaster, AccountMaster.account_id == TalentMaster.account_id)
            .where(AccountMaster.account_id == account_id)
        )
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="TALENT_NOT_FOUND")

    name, t = res
    return {
        "account_id": account_id,
        "name": name,
        "stage_name": t.stage_name,
        "gender": t.gender,
        "birth_date": t.birth_date.isoformat() if t.birth_date else None,
        "height_cm": t.height_cm,
        "weight_kg": t.weight_kg,
        "region_code": t.region_code,
        "main_category": t.main_category,
        "skills": t.skills or [],
        "languages": t.languages or [],
        "introduction": t.introduction,
        "profile_image_urls": t.profile_image_urls or [],
    }


@admin_router.put("/talents/{account_id}")
async def update_talent(
    account_id: int,
    req: AdminTalentCreate,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """인재 프로필 수정 (이름 + talent_master 전체)."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    acc = (
        await db.execute(
            select(AccountMaster).where(AccountMaster.account_id == account_id)
        )
    ).scalar_one_or_none()
    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == account_id)
        )
    ).scalar_one_or_none()
    if not acc or not talent:
        raise HTTPException(status_code=404, detail="TALENT_NOT_FOUND")

    acc.name = req.name
    talent.stage_name = req.stage_name
    talent.gender = req.gender
    talent.birth_date = req.birth_date
    talent.height_cm = req.height_cm
    talent.weight_kg = req.weight_kg
    talent.region_code = req.region_code
    talent.main_category = req.main_category
    talent.skills = req.skills or None
    talent.languages = req.languages or None
    talent.introduction = req.introduction
    await db.commit()

    return {"account_id": account_id, "name": req.name}


@admin_router.post("/talents/{account_id}/photo")
async def upload_talent_photo(
    account_id: int,
    file: UploadFile = File(...),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """관리자 대행 프로필 사진 업로드 — 저장 + talent_master.profile_image_urls 갱신."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == account_id)
        )
    ).scalar_one_or_none()
    if not talent:
        raise HTTPException(status_code=404, detail="TALENT_NOT_FOUND")

    if not file.content_type or file.content_type.lower() not in _PROFILE_PHOTO_MIME:
        raise HTTPException(status_code=400, detail=f"UNSUPPORTED_MIME:{file.content_type}")

    ext = _PROFILE_PHOTO_MIME[file.content_type.lower()]
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest_path = absolute_path(_profile_relative_key(account_id, filename))
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

    url = _profile_public_url(account_id, filename)
    talent.profile_image_urls = [url]  # 대표 사진 1장으로 설정
    await db.commit()
    return {"url": url, "filename": filename}
