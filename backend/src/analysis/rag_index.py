"""RAG scene → Qdrant 색인.

영상 분석(단계 6)에서 생성된 scene JSON 들을 OpenAI 임베딩으로 벡터화하여
Qdrant collection 'talent_scenes' 에 scene 단위로 upsert.

- 임베딩: OpenAI text-embedding-3-small (1536 차원, Cosine)
- point id: 결정적 (talent_media_id * 1000 + scene_index) → 재적재/삭제 용이
- 삭제: talent_media_id 필터로 해당 영상의 모든 scene 포인트 일괄 제거

엄격 정책: 적재 실패 시 예외를 그대로 raise (호출부에서 분석 단계 실패로 표기).
삭제는 best-effort (호출부에서 예외를 잡아 경고 로그).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from qdrant_client import models

from src.qdrant import get_qdrant_client

logger = logging.getLogger(__name__)

COLLECTION = "talent_scenes"
EMBED_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
# point id = talent_media_id * _ID_STRIDE + scene_index (scene 수가 이보다 적다고 가정)
_ID_STRIDE = 1000


def _text(v: Any) -> str:
    return v.strip() if isinstance(v, str) and v.strip() else ""


def _joined(v: Any) -> str:
    return " ".join(str(k) for k in v if k).strip() if isinstance(v, list) else ""


def _scene_embed_text(scene: dict[str, Any]) -> str:
    """임베딩 입력 텍스트 생성.

    scene_summary·키워드에 더해 **감정과 표현 방식** 을 함께 싣는다.
    "오열 연기", "분노 폭발", "눌러 담는 슬픔" 같은 검색은 감정 서술이
    임베딩에 들어가 있어야만 걸린다 (이전에는 요약·키워드만 넣어서
    GPT 가 뽑아낸 감정·표정·음색 정보가 검색에 전혀 반영되지 않았다).
    """
    emotion = scene.get("emotion_analysis") or {}
    physical = scene.get("physical_expression") or {}
    speech = scene.get("speech_analysis") or {}
    acting = scene.get("acting_analysis") or {}

    parts: list[str] = [
        _text(scene.get("scene_summary")),
        _joined(scene.get("search_keywords")),
        _joined(scene.get("mood_keywords")),
        # 감정 — 검색의 핵심 축
        _text(emotion.get("primary_emotion")),
        _joined(emotion.get("emotion_keywords")),
        _text(emotion.get("intensity")),
        _text(emotion.get("emotion_arc")),
        _joined(emotion.get("expression_channels")),
        _text(emotion.get("emotion_detail")),
        # 감정이 드러나는 경로 — 표정 / 음색 / 연기 톤
        _joined(physical.get("facial_expression_keywords")),
        _joined(speech.get("tone_keywords")),
        _joined(acting.get("acting_style")),
        _text(acting.get("emotion_delivery")),
    ]
    return " ".join(p for p in parts if p).strip()


# role.age_range 정규 값 — 프롬프트(portfolio_video_analysis_*.toml)와 동일.
# 긴 값을 먼저 두어야 "70s_plus" 가 "70s" 로 잘리지 않는다.
_AGE_RANGE_CANON = (
    "child_actor", "elementary", "middle_school", "high_school",
    "70s_plus", "60s", "50s", "40s", "30s", "20s",
)


def _normalize_age_range(value: Any) -> str | None:
    """GPT 가 "20s_early" 처럼 목록에 없는 변형을 낼 때가 있어 정규 값으로 맞춘다.

    맞추지 못하면 None — 잘못된 값으로 필터 검색을 오염시키는 것보다 낫다.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip().lower()
    if v in _AGE_RANGE_CANON:
        return v
    # "20s_early" 처럼 정규 값을 품고 있는 경우
    for canon in _AGE_RANGE_CANON:
        if canon in v:
            return canon
    # "70s" 처럼 정규 값의 앞부분만 온 경우 (→ "70s_plus")
    for canon in _AGE_RANGE_CANON:
        if len(v) >= 2 and canon.startswith(v):
            return canon
    return None


def _scene_payload(
    account_id: int, talent_media_id: int, scene: dict[str, Any]
) -> dict[str, Any]:
    """검색·필터링에 쓰는 주요 필드만 평탄화해 payload 구성."""
    role = scene.get("role") or {}
    era = scene.get("era") or {}
    appearance = scene.get("appearance") or {}
    emotion = scene.get("emotion_analysis") or {}
    return {
        "account_id": account_id,
        "talent_media_id": talent_media_id,
        "scene_id": scene.get("scene_id"),
        "scene_start_sec": scene.get("scene_start_sec"),
        "scene_end_sec": scene.get("scene_end_sec"),
        "search_keywords": scene.get("search_keywords") or [],
        "mood_keywords": scene.get("mood_keywords") or [],
        "age_range": _normalize_age_range(role.get("age_range")),
        "gender_appearance": role.get("gender_appearance"),
        "character_type": role.get("character_type"),
        "occupation": role.get("occupation"),
        "period": era.get("period"),
        "setting": era.get("setting"),
        "image_type": appearance.get("image_type"),
        "hair_length": appearance.get("hair_length"),
        "body_type": appearance.get("body_type"),
        "body_style": appearance.get("body_style"),
        "scene_summary": scene.get("scene_summary"),
        # 감정 — 필터 검색용 (예: primary_emotion="분노", intensity="폭발적")
        "primary_emotion": emotion.get("primary_emotion"),
        "emotion_keywords": emotion.get("emotion_keywords") or [],
        "emotion_intensity": emotion.get("intensity"),
        "emotion_arc": emotion.get("emotion_arc"),
        # 단계 3.5 얼굴 식별 결과 — 검색 시 "인재가 실제로 확인된 scene" 필터링용.
        # None 이면 식별을 수행하지 않은 영상 (프로필 사진 없음 등).
        "target_identified": scene.get("target_identified"),
        "target_confident": scene.get("target_confident"),
        "target_similarity": scene.get("target_similarity"),
        "scene_face_count": scene.get("scene_face_count"),
    }


def _embed_texts(texts: list[str], openai_api_key: str) -> list[list[float]]:
    """OpenAI 임베딩 (동기 — 호출부에서 thread 로 감쌈)."""
    from openai import OpenAI

    client = OpenAI(api_key=openai_api_key)
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


async def ensure_collection() -> None:
    """collection 없으면 생성 (1536 / Cosine)."""
    client = get_qdrant_client()
    if not await client.collection_exists(COLLECTION):
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE, distance=models.Distance.COSINE
            ),
        )
        logger.info(f"Qdrant collection 생성: {COLLECTION}")


async def index_scenes(
    *,
    account_id: int,
    talent_media_id: int,
    rag_scenes: list[dict[str, Any]],
    openai_api_key: str,
) -> int:
    """scene 들을 임베딩해 Qdrant 에 upsert. 적재한 포인트 수 반환.

    엄격 정책: 임베딩/upsert 실패 시 예외를 그대로 전파.
    """
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY_MISSING")

    # 임베딩 가능한 scene 만 선별 (error scene / 텍스트 없는 scene 제외)
    items: list[tuple[int, dict[str, Any], str]] = []
    for idx, scene in enumerate(rag_scenes):
        if not isinstance(scene, dict) or scene.get("error"):
            continue
        text = _scene_embed_text(scene)
        if text:
            items.append((idx, scene, text))

    if not items:
        return 0

    vectors = await asyncio.to_thread(
        _embed_texts, [t for _, _, t in items], openai_api_key
    )

    await ensure_collection()
    client = get_qdrant_client()
    points = [
        models.PointStruct(
            id=talent_media_id * _ID_STRIDE + idx,
            vector=vec,
            payload=_scene_payload(account_id, talent_media_id, scene),
        )
        for (idx, scene, _), vec in zip(items, vectors)
    ]
    await client.upsert(collection_name=COLLECTION, points=points)
    return len(points)


async def get_media_scenes(talent_media_id: int) -> list[dict[str, Any]]:
    """특정 영상의 모든 scene 포인트를 payload 째 조회 (관리자 열람용 — .txt 대체)."""
    client = get_qdrant_client()
    if not await client.collection_exists(COLLECTION):
        return []
    points, _ = await client.scroll(
        collection_name=COLLECTION,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="talent_media_id",
                    match=models.MatchValue(value=talent_media_id),
                )
            ]
        ),
        with_payload=True,
        with_vectors=False,
        limit=500,
    )
    rows = [{"id": p.id, "payload": p.payload} for p in points]
    # scene_id 기준 정렬 (scene_001, scene_002 ...)
    rows.sort(key=lambda r: str((r["payload"] or {}).get("scene_id", "")))
    return rows


async def search_scenes(
    query: str,
    *,
    limit: int,
    openai_api_key: str,
    query_filter: "models.Filter | None" = None,
    score_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """자연어 query 를 임베딩해 유사 scene 을 검색 (에이전시 검색용).

    query_filter: payload 조건 필터. None 이면 의미 검색만.
    score_threshold: 이 코사인 유사도 미만 결과는 제외(관련 없음 컷오프). None 이면 컷 안 함.
    반환: [{score, payload}] (유사도 내림차순).
    """
    if not query.strip():
        return []
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY_MISSING")
    client = get_qdrant_client()
    if not await client.collection_exists(COLLECTION):
        return []
    vector = (await asyncio.to_thread(_embed_texts, [query], openai_api_key))[0]
    res = await client.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=limit,
        with_payload=True,
        query_filter=query_filter,
        score_threshold=score_threshold,
    )
    return [{"score": pt.score, "payload": pt.payload} for pt in res.points]


async def delete_media_points(talent_media_id: int) -> None:
    """해당 영상의 모든 scene 포인트를 talent_media_id 필터로 삭제 (best-effort)."""
    client = get_qdrant_client()
    if not await client.collection_exists(COLLECTION):
        return
    await client.delete(
        collection_name=COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="talent_media_id",
                        match=models.MatchValue(value=talent_media_id),
                    )
                ]
            )
        ),
    )
