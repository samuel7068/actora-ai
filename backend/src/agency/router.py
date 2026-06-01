"""에이전시 전용 API."""
import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from qdrant_client import models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.models import AccountMaster
from src.analysis.rag_index import search_scenes
from src.agency.query_parse import parse_search_query
from src.auth.deps import get_current_account
from src.config import get_settings
from src.database import get_db
from src.talent.models import TalentMaster

logger = logging.getLogger(__name__)

agency_router = APIRouter()


def _calc_age(birth: date | None) -> int | None:
    if not birth:
        return None
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _has_all(haystack, needles: list[str]) -> bool:
    """haystack(JSONB 배열) 이 needles 의 모든 항목을 (부분일치로) 포함하는지."""
    hay = [str(x).lower() for x in (haystack or [])]
    for n in needles:
        nl = n.lower()
        if not any(nl in h for h in hay):
            return False
    return True


def _profile_dict(aid, name, birth, gender, height_cm, weight_kg, skills, languages) -> dict:
    return {
        "account_id": aid,
        "name": name,
        "age": _calc_age(birth),
        "gender": gender,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "skills": skills or [],
        "languages": languages or [],
    }


def _passes_db_filter(prof: dict, cond: dict) -> bool:
    """프로필이 LLM 추출 조건(cond)을 모두 만족하는지."""
    age = prof.get("age")
    if cond.get("age_min") is not None and (age is None or age < cond["age_min"]):
        return False
    if cond.get("age_max") is not None and (age is None or age > cond["age_max"]):
        return False
    if cond.get("gender") and prof.get("gender") != cond["gender"]:
        return False
    h = prof.get("height_cm") or 0
    if cond.get("height_min") is not None and h < cond["height_min"]:
        return False
    if cond.get("height_max") is not None and (prof.get("height_cm") is None or h > cond["height_max"]):
        return False
    w = prof.get("weight_kg") or 0
    if cond.get("weight_min") is not None and w < cond["weight_min"]:
        return False
    if cond.get("weight_max") is not None and (prof.get("weight_kg") is None or w > cond["weight_max"]):
        return False
    if cond.get("skills") and not _has_all(prof.get("skills"), cond["skills"]):
        return False
    if cond.get("languages") and not _has_all(prof.get("languages"), cond["languages"]):
        return False
    return True


def _has_any_condition(cond: dict) -> bool:
    return any(
        cond.get(k) not in (None, [], "")
        for k in (
            "age_min", "age_max", "gender", "height_min", "height_max",
            "weight_min", "weight_max", "skills", "languages",
        )
    )


@agency_router.get("/search")
async def search_talents(
    q: str = Query(..., min_length=1, description="자연어 검색 문장"),
    limit: int = Query(20, ge=1, le=50),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """하이브리드 검색 (LLM 파싱 기반).

    1) LLM 이 검색 문장에서 talent_master 조건(나이·성별·키·몸무게·특기·언어) 추출
    2) DB 1차 필터 → 조건 충족 account_id 후보
    3) 검색 문장 전체로 RAG 2차 벡터 검색 (후보 account 로 한정, 유사도 컷오프)
    AGENCY / ADMIN 만 접근.
    """
    account, _admin = current
    if account.account_type not in ("AGENCY", "ADMIN"):
        raise HTTPException(status_code=403, detail="AGENCY_OR_ADMIN_ONLY")

    config = get_settings()

    # ── 1) LLM 파싱 ──
    cond = await asyncio.to_thread(parse_search_query, q, config.OPENAI_API_KEY)
    has_cond = _has_any_condition(cond)

    # ── 2) DB 1차 필터 → 후보 account_id + 프로필 ──
    profiles: dict[int, dict] = {}
    candidate_ids: set[int] | None = None
    if has_cond:
        rows = (
            await db.execute(
                select(
                    AccountMaster.account_id,
                    AccountMaster.name,
                    TalentMaster.birth_date,
                    TalentMaster.gender,
                    TalentMaster.height_cm,
                    TalentMaster.weight_kg,
                    TalentMaster.skills,
                    TalentMaster.languages,
                ).join(TalentMaster, AccountMaster.account_id == TalentMaster.account_id)
            )
        ).all()
        candidate_ids = set()
        for row in rows:
            prof = _profile_dict(*row)
            if _passes_db_filter(prof, cond):
                profiles[prof["account_id"]] = prof
                candidate_ids.add(prof["account_id"])

        # 조건 충족자가 없으면 RAG 돌릴 필요 없음
        if not candidate_ids:
            return {"query": q, "conditions": cond, "count": 0, "results": []}

    # ── 3) RAG 2차 (후보 account 로 한정) ──
    qfilter = None
    if candidate_ids is not None:
        qfilter = models.Filter(
            must=[
                models.FieldCondition(
                    key="account_id",
                    match=models.MatchAny(any=list(candidate_ids)),
                )
            ]
        )

    # 벡터 검색은 검색 문장 전체로. (의미 단어만 떼면 "수다스런" 같은 단어는 임베딩이
    #  빈약해져 유사도가 불안정 — 전체 문장이 맥락이 풍부해 더 안정적.)
    # 유사도 컷오프는 일단 제거 — 데이터가 적어 튜닝 의미가 적으므로 전부 노출.
    raw = await search_scenes(
        q,
        limit=limit,
        openai_api_key=config.OPENAI_API_KEY,
        query_filter=qfilter,
    )

    # ── 프로필 병합 (조건 없던 경우 여기서 조회) ──
    missing = {
        _to_int((r.get("payload") or {}).get("account_id")) for r in raw
    } - set(profiles.keys())
    missing.discard(None)
    if missing:
        rows = (
            await db.execute(
                select(
                    AccountMaster.account_id,
                    AccountMaster.name,
                    TalentMaster.birth_date,
                    TalentMaster.gender,
                    TalentMaster.height_cm,
                    TalentMaster.weight_kg,
                    TalentMaster.skills,
                    TalentMaster.languages,
                ).join(
                    TalentMaster,
                    AccountMaster.account_id == TalentMaster.account_id,
                    isouter=True,
                ).where(AccountMaster.account_id.in_(missing))
            )
        ).all()
        for row in rows:
            prof = _profile_dict(*row)
            profiles[prof["account_id"]] = prof

    for r in raw:
        aid = _to_int((r.get("payload") or {}).get("account_id"))
        r["profile"] = profiles.get(aid)

    return {"query": q, "conditions": cond, "count": len(raw), "results": raw}


@agency_router.get("/talent/{account_id}")
async def talent_detail(
    account_id: int,
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """연기자 프로필 상세 (에이전시 검색 결과에서 이름 클릭 시). AGENCY / ADMIN."""
    account, _admin = current
    if account.account_type not in ("AGENCY", "ADMIN"):
        raise HTTPException(status_code=403, detail="AGENCY_OR_ADMIN_ONLY")

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
        "age": _calc_age(t.birth_date),
        "nationality": t.nationality,
        "region_code": t.region_code,
        "main_category": t.main_category,
        "sub_categories": t.sub_categories or [],
        "height_cm": t.height_cm,
        "weight_kg": t.weight_kg,
        "weight_range": t.weight_range,
        "skills": t.skills or [],
        "languages": t.languages or [],
        "education_level": t.education_level,
        "education_major": t.education_major,
        "career_level": t.career_level,
        "career_years": t.career_years,
        "introduction": t.introduction,
        "profile_image_urls": t.profile_image_urls or [],
        "instagram_url": t.instagram_url,
        "youtube_url": t.youtube_url,
        "tiktok_url": t.tiktok_url,
    }
