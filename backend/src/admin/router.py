"""관리자 전용 API (account_type='ADMIN' 만 접근)."""
import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.models import AccountMaster
from src.analysis.rag_index import delete_media_points, get_media_scenes
from src.auth.deps import get_current_account
from src.database import get_db
from src.media.service import save_profile_photo, stream_url_for
from src.talent.models import TalentMaster, TalentMedia
from src.storage import get_storage
from src.talent.router import (
    _completion_rate,
    _to_response,
)
from src.talent.schemas import TalentProfileResponse, TalentProfileUpdateRequest

logger = logging.getLogger(__name__)

admin_router = APIRouter()


class AdminTalentCreate(BaseModel):
    """관리자 대행 인재 등록 입력 — 이름만.

    계정 식별자(login_id/email/password)는 받지 않는다 — 시드 데이터이므로
    시스템이 placeholder 로 자동 생성하고 로그인 불가 상태로 둔다.
    상세 프로필은 생성 후 연기자와 동일한 프로필 편집 화면(탭)에서 입력한다.
    """

    name: str


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
            "thumbnail_path": m.thumbnail_path,
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


# 관리자 목록의 나이대 필터.
# 나이를 SQL 에서 계산하면(age(birth_date)) 인덱스를 못 타므로,
# "나이 범위" 를 "생년월일 범위" 로 바꿔서 비교한다.
_AGE_BANDS = {
    "under_10": (None, 10),   # 10세 미만
    "10s": (10, 20),
    "20s": (20, 30),
    "30s": (30, 40),
    "40s": (40, 50),
    "50s": (50, 60),
    "60s": (60, 70),
    "70s_plus": (70, None),   # 70세 이상
}


def _years_ago(base: date, years: int) -> date:
    """base 에서 years 년 전 날짜. 2월 29일은 28일로 내린다."""
    try:
        return base.replace(year=base.year - years)
    except ValueError:
        return base.replace(year=base.year - years, day=28)


def _age_band_condition(band: str):
    """나이대 코드 → birth_date 조건 목록 (알 수 없는 코드면 빈 목록)."""
    lo, hi = _AGE_BANDS.get(band, (None, None))
    if lo is None and hi is None:
        return []
    today = date.today()
    conds = []
    # 나이 >= lo  ⇔  생일이 lo 년 전보다 이르거나 같다
    if lo is not None:
        conds.append(TalentMaster.birth_date <= _years_ago(today, lo))
    # 나이 < hi   ⇔  생일이 hi 년 전보다 늦다
    if hi is not None:
        conds.append(TalentMaster.birth_date > _years_ago(today, hi))
    return conds


@admin_router.get("/talents")
async def list_talents(
    q: str | None = Query(default=None, description="이름 또는 예명 부분검색"),
    gender: str | None = Query(default=None, description="성별 필터. MALE / FEMALE"),
    age_band: str | None = Query(
        default=None,
        description="나이대. under_10 / 10s / 20s / 30s / 40s / 50s / 60s / 70s_plus",
    ),
    main_category: str | None = Query(default=None, description="주 분야. ACTOR / MODEL 등"),
    page: int = Query(default=1, ge=1, description="1부터 시작"),
    size: int = Query(default=20, ge=1, le=100, description="페이지당 건수"),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """등록된 talent_master 목록 (관리자). 이름·성별·나이대·분야 검색 + 페이지네이션."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    # 검색 조건 — 이름/예명 부분일치, 성별 정확일치
    conds = []
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(
            or_(AccountMaster.name.ilike(like), TalentMaster.stage_name.ilike(like))
        )
    if gender in ("MALE", "FEMALE"):
        conds.append(TalentMaster.gender == gender)
    if age_band:
        conds.extend(_age_band_condition(age_band))
    if main_category and main_category.strip():
        conds.append(TalentMaster.main_category == main_category.strip())

    # 전체 건수는 페이지와 무관하게 조건만 적용해 센다
    total = (
        await db.execute(
            select(func.count())
            .select_from(AccountMaster)
            .join(TalentMaster, AccountMaster.account_id == TalentMaster.account_id)
            .where(*conds)
        )
    ).scalar_one()

    rows = (
        await db.execute(
            select(
                AccountMaster.account_id,
                AccountMaster.name,
                AccountMaster.created_at,
                TalentMaster.stage_name,
                TalentMaster.gender,
                TalentMaster.birth_date,
                TalentMaster.height_cm,
                TalentMaster.weight_kg,
                TalentMaster.region_code,
                TalentMaster.main_category,
                TalentMaster.skills,
                TalentMaster.languages,
                TalentMaster.career_level,
                TalentMaster.career_years,
                TalentMaster.profile_completion_rate,
            )
            .join(TalentMaster, AccountMaster.account_id == TalentMaster.account_id)
            .where(*conds)
            .order_by(AccountMaster.account_id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    # 인재별 영상 개수 — 현재 페이지에 보이는 인재만 집계
    page_ids = [r[0] for r in rows]
    count_rows = (
        (
            await db.execute(
                select(
                    TalentMedia.account_id,
                    func.count(TalentMedia.talent_media_id),
                )
                .where(TalentMedia.account_id.in_(page_ids))
                .group_by(TalentMedia.account_id)
            )
        ).all()
        if page_ids
        else []
    )
    media_counts = {acc_id: cnt for acc_id, cnt in count_rows}

    items = [
        {
            "account_id": r[0],
            "name": r[1],
            "created_at": r[2],
            "stage_name": r[3],
            "gender": r[4],
            "age": _calc_age(r[5]),
            "height_cm": r[6],
            "weight_kg": r[7],
            "region_code": r[8],
            "main_category": r[9],
            "skills": r[10] or [],
            "languages": r[11] or [],
            "career_level": r[12],
            "career_years": r[13],
            "profile_completion_rate": r[14],
            "media_count": media_counts.get(r[0], 0),
        }
        for r in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "total_pages": max(1, (total + size - 1) // size),
    }


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

    talent = TalentMaster(account_id=acc.account_id)
    db.add(talent)
    await db.commit()

    return {"account_id": acc.account_id, "name": req.name}


@admin_router.get("/talents/{account_id}", response_model=TalentProfileResponse)
async def get_talent_for_edit(
    account_id: int,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """인재 수정 화면용 전체 프로필 — 연기자 GET /talent/profile 과 동일 구조."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == account_id)
        )
    ).scalar_one_or_none()
    if talent is None:
        raise HTTPException(status_code=404, detail="TALENT_NOT_FOUND")
    return _to_response(talent)


@admin_router.put("/talents/{account_id}", response_model=TalentProfileResponse)
async def update_talent(
    account_id: int,
    req: TalentProfileUpdateRequest,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """인재 프로필 수정 — 연기자 PUT /talent/profile 과 동일 구조."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == account_id)
        )
    ).scalar_one_or_none()
    if talent is None:
        raise HTTPException(status_code=404, detail="TALENT_NOT_FOUND")

    data = req.model_dump(exclude_unset=False)
    for field, value in data.items():
        setattr(talent, field, value)
    talent.profile_completion_rate = _completion_rate(talent)
    talent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(talent)
    return _to_response(talent)


@admin_router.get("/talents/{account_id}/media")
async def list_talent_media(
    account_id: int,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """특정 인재의 영상 목록 (관리자 포트폴리오). 본인 /talent/me/media 와 같은 형태."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    rows = (
        await db.execute(
            select(TalentMedia)
            .where(TalentMedia.account_id == account_id)
            .order_by(TalentMedia.sort_order.asc(), TalentMedia.talent_media_id.asc())
        )
    ).scalars().all()
    items = [
        {
            "talent_media_id": r.talent_media_id,
            "media_type": r.media_type,
            "title": r.title,
            "original_file_name": r.original_file_name,
            "ai_summary": r.ai_summary,
            "created_at": r.created_at,
            "view_count": r.view_count,
            "is_main": r.is_main,
            "stream_url": stream_url_for(r.talent_media_id),
            "thumbnail_path": r.thumbnail_path,
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


@admin_router.delete("/talents/{account_id}/media/{media_id}")
async def delete_talent_media(
    account_id: int,
    media_id: int,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """관리자 대행 영상 삭제 — 파일 + RAG .txt + Qdrant 포인트 + DB 행 제거."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    row = (
        await db.execute(
            select(TalentMedia).where(TalentMedia.talent_media_id == media_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MEDIA_NOT_FOUND")
    if row.account_id != account_id:
        raise HTTPException(status_code=400, detail="ACCOUNT_MISMATCH")

    # 영상 파일 + RAG .txt
    # 버킷을 개발 PC 와 운영 서버가 공유하므로 여기서 지우면 양쪽에서 사라진다.
    store = get_storage()
    store.delete(row.media_path)
    store.delete(f"rag/{account_id}_{media_id}.txt")
    # Qdrant
    try:
        await delete_media_points(media_id)
    except Exception as e:
        logger.warning(f"qdrant delete failed: {e}")

    await db.delete(row)
    await db.commit()
    return {"success": True, "deleted_id": media_id}


@admin_router.delete("/talents/{account_id}")
async def delete_talent(
    account_id: int,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """관리자 인재 완전 삭제 — 계정 + 프로필 + 모든 영상/사진 파일 + RAG .txt + Qdrant 포인트.

    DB 는 account_master → talent_master → talent_media 가 FK CASCADE 라 계정 행만
    지우면 연쇄 삭제되지만, 디스크 파일과 Qdrant 포인트는 수동 정리해야 한다.
    """
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    target = (
        await db.execute(
            select(AccountMaster).where(AccountMaster.account_id == account_id)
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="ACCOUNT_NOT_FOUND")
    if target.account_type != "TALENT":
        raise HTTPException(status_code=400, detail="NOT_A_TALENT")

    # 이 인재의 모든 미디어 — Qdrant 포인트 + RAG .txt 정리
    media_rows = (
        await db.execute(
            select(TalentMedia.talent_media_id).where(
                TalentMedia.account_id == account_id
            )
        )
    ).scalars().all()
    for media_id in media_rows:
        try:
            await delete_media_points(media_id)
        except Exception as e:
            logger.warning(f"qdrant delete failed (media={media_id}): {e}")
        get_storage().delete(f"rag/{account_id}_{media_id}.txt")

    # 아티스트 파일 전체 제거 (영상·프로필 사진·썸네일 = talent/{account_id}/ 아래)
    removed = get_storage().delete_prefix(f"talent/{account_id}")
    logger.info(f"계정 삭제: 파일 {removed}개 제거 (account={account_id})")

    # 계정 행 삭제 → talent_master / talent_media 행은 FK CASCADE 로 연쇄 삭제
    await db.delete(target)
    await db.commit()
    return {"success": True, "deleted_account_id": account_id}


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

    # 검증·리사이즈·업로드는 service 가 담당한다 (아티스트 셀프 업로드와 같은 코드)
    filename, url, _size = await save_profile_photo(file, account_id)
    talent.profile_image_urls = [url]  # 대표 사진 1장으로 설정
    await db.commit()
    return {"url": url, "filename": filename}
