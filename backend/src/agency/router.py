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

# 검색 필수 필터 — 주 분야 화이트리스트 (talent_master.main_category 와 동일)
_MAIN_CATEGORIES = {
    "ACTOR", "MODEL", "INFLUENCER", "VOCAL", "DANCER", "MC", "CREATOR",
}


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


# 이 유사도 미만이면 프론트에서 "부족" 으로 표시되던 구간 — 캐스팅 후보로 쓸 수 없어
# 응답에서 제외한다. TalentSearchView 의 scoreTier "보통" 하한과 같은 값이어야
# 걸러진 기준과 표시가 어긋나지 않는다.
MIN_SCORE = 0.35


# scene 의 role.age_range 값 — 프롬프트(portfolio_video_analysis_*.toml)와 동일해야 한다
_ROLE_AGE_RANGES = (
    "child_actor", "elementary", "middle_school", "high_school",
    "20s", "30s", "40s", "50s", "60s", "70s_plus",
)


@agency_router.get("/search")
async def search_talents(
    q: str = Query(..., min_length=1, description="자연어 검색 문장 (이미지·분위기)"),
    main_category: str = Query(
        ..., description="주 분야 (필수). ACTOR/MODEL/INFLUENCER/VOCAL/DANCER/MC/CREATOR"
    ),
    gender: str = Query(..., description="성별 (필수). MALE / FEMALE"),
    age_min: int | None = Query(None, ge=0, le=120, description="연령대 하한 (선택)"),
    age_max: int | None = Query(None, ge=0, le=120, description="연령대 상한 (선택)"),
    height_min: int | None = Query(None, ge=100, le=250, description="키 하한 cm (선택)"),
    height_max: int | None = Query(None, ge=100, le=250, description="키 상한 cm (선택)"),
    role_age_range: str | None = Query(
        None,
        description="영상에서 **연기한 역할**의 연령대 (선택). "
        "child_actor/elementary/middle_school/high_school/20s/30s/40s/50s/60s/70s_plus. "
        "인재의 실제 나이(age_min/age_max)와 별개 — 20대 배우가 40대 엄마 역을 한 장면이 잡힌다.",
    ),
    limit: int = Query(20, ge=1, le=50),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """하이브리드 검색.

    1) 주 분야 + 성별 (필수) + 화면에서 고른 연령대·키 + LLM 이 문장에서 추출한
       조건(나이·키·몸무게·특기·언어)으로 DB 1차 필터 → 후보 account_id
    2) 후보 account 로 한정해 검색 문장 전체로 RAG 2차 벡터 검색
       (영상 분석으로 쌓인 scene 단위 RAG 데이터가 검색 대상)
    AGENCY / ADMIN 만 접근.

    화면에서 직접 고른 조건은 문장에서 추출한 값보다 우선한다.
    """
    account, _admin = current
    if account.account_type not in ("AGENCY", "ADMIN"):
        raise HTTPException(status_code=403, detail="AGENCY_OR_ADMIN_ONLY")
    if main_category not in _MAIN_CATEGORIES:
        raise HTTPException(status_code=400, detail="INVALID_MAIN_CATEGORY")
    if gender not in ("MALE", "FEMALE"):
        raise HTTPException(status_code=400, detail="INVALID_GENDER")
    if role_age_range and role_age_range not in _ROLE_AGE_RANGES:
        raise HTTPException(status_code=400, detail="INVALID_ROLE_AGE_RANGE")

    config = get_settings()

    # 검색 문장을 벡터로 바꿔야 하므로 임베딩 API 키가 필수다.
    # 설정 누락을 500 으로 흘리면 "검색 실패" 로만 보여 원인 파악이 어렵다
    # → 503 + 명확한 코드로 알리고, DB 조회에 들어가기 전에 끊는다.
    if not config.OPENAI_API_KEY:
        logger.error("검색 불가: OPENAI_API_KEY 미설정 (.env 확인 필요)")
        raise HTTPException(
            status_code=503, detail="SEARCH_UNAVAILABLE:OPENAI_API_KEY_MISSING"
        )

    # ── 1) LLM 파싱 (나이·키·몸무게·특기·언어) ──
    cond = await asyncio.to_thread(parse_search_query, q, config.OPENAI_API_KEY)
    cond["gender"] = None  # 명시 성별 필터가 authoritative

    # 화면에서 직접 고른 조건이 문장 추출값을 덮어쓴다.
    # (사용자가 "20대" 를 골랐는데 문장의 "서른쯤" 때문에 걸러지면 안 된다)
    explicit = {
        "age_min": age_min,
        "age_max": age_max,
        "height_min": height_min,
        "height_max": height_max,
    }
    scene_filter = {"role_age_range": role_age_range}
    for key, value in explicit.items():
        if value is not None:
            cond[key] = value

    # ── 2) DB 1차 필터: 주 분야 + 성별(필수) + LLM 조건 → 후보 account_id + 프로필 ──
    profiles: dict[int, dict] = {}
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
            )
            .join(TalentMaster, AccountMaster.account_id == TalentMaster.account_id)
            .where(
                TalentMaster.main_category == main_category,
                TalentMaster.gender == gender,
            )
        )
    ).all()
    candidate_ids: set[int] = set()
    for row in rows:
        prof = _profile_dict(*row)
        if _passes_db_filter(prof, cond):
            profiles[prof["account_id"]] = prof
            candidate_ids.add(prof["account_id"])

    # 후보가 없으면 RAG 돌릴 필요 없음
    if not candidate_ids:
        return {
            "query": q,
            "conditions": cond,
            "main_category": main_category,
            "gender": gender,
            "explicit": explicit,
            "scene_filter": scene_filter,
            "count": 0,
            "results": [],
        }

    # ── 3) RAG 2차 (후보 account 로 한정) ──
    must = [
        models.FieldCondition(
            key="account_id",
            match=models.MatchAny(any=list(candidate_ids)),
        )
    ]
    if role_age_range:
        # 인재의 실제 나이가 아니라 **그 장면에서 연기한 역할**의 연령대로 거른다.
        must.append(
            models.FieldCondition(
                key="age_range",
                match=models.MatchValue(value=role_age_range),
            )
        )
    qfilter = models.Filter(must=must)

    # 벡터 검색은 검색 문장 전체로. (의미 단어만 떼면 "수다스런" 같은 단어는 임베딩이
    #  빈약해져 유사도가 불안정 — 전체 문장이 맥락이 풍부해 더 안정적.)
    # scene 단위라 한 인재가 여러 건 나올 수 있으므로 넉넉히 받아 dedup 후 trim.
    try:
        raw = await search_scenes(
            q,
            limit=limit * 5,
            openai_api_key=config.OPENAI_API_KEY,
            query_filter=qfilter,
        )
    except Exception as e:
        # 임베딩 API 오류 / 레이트리밋 / Qdrant 장애 — 클라이언트 잘못이 아니므로 503.
        logger.exception("RAG 벡터 검색 실패")
        raise HTTPException(
            status_code=503, detail=f"SEARCH_BACKEND_ERROR:{type(e).__name__}"
        ) from e

    # ── 인재(account) 단위 중복 제거 — 같은 인재의 여러 scene 중 최고 점수 1건만 ──
    # raw 는 유사도 내림차순이므로 먼저 만난 account 가 그 인재의 최고 점수 scene.
    seen: set[int] = set()
    deduped: list[dict] = []
    dropped_low_score = 0
    for r in raw:
        aid = _to_int((r.get("payload") or {}).get("account_id"))
        if aid is None or aid in seen:
            continue
        seen.add(aid)
        # raw 는 내림차순이라 이 scene 이 그 인재의 최고점.
        # 최고점이 임계값 미달이면 캐스팅 후보로 쓸 수 없어 제외한다.
        if float(r.get("score") or 0.0) < MIN_SCORE:
            dropped_low_score += 1
            continue
        deduped.append(r)
        if len(deduped) >= limit:
            break
    raw = deduped

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

    return {
        "query": q,
        "conditions": cond,
        "main_category": main_category,
        "gender": gender,
        "explicit": explicit,
        "scene_filter": scene_filter,
        "min_score": MIN_SCORE,
        # 유사도가 낮아 제외된 인재 수 — 프론트에서 "왜 결과가 적은지" 안내에 쓴다
        "dropped_low_score": dropped_low_score,
        "count": len(raw),
        "results": raw,
    }


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
