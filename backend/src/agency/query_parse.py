"""에이전시 검색어 파서 — 자연어 → talent_master 필터 조건(LLM).

search_query_parse.toml 의 [query_parse] 프롬프트로 GPT 를 호출해
{age_min, age_max, gender, height_min, height_max, weight_min, weight_max,
 skills, languages, emotions, search_text}
구조를 추출한다. 실패하면 빈 dict 반환(필터 없이 진행).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from src.analysis.prompts import get_prompt

logger = logging.getLogger(__name__)

_INT_KEYS = (
    "age_min", "age_max", "height_min", "height_max", "weight_min", "weight_max",
)
_LIST_KEYS = ("skills", "languages", "emotions")
# search_text: 벡터 검색에 넣을 장면 묘사 문장 (짧은 질의를 풀어 쓴 것)
_STR_KEYS = ("search_text",)


def _coerce(raw: dict[str, Any]) -> dict[str, Any]:
    """타입 정규화: 숫자 필드 → int|None, 배열 필드 → list[str]."""
    out: dict[str, Any] = {}
    for k in _INT_KEYS:
        v = raw.get(k)
        try:
            out[k] = int(v) if v is not None and v != "" else None
        except (ValueError, TypeError):
            out[k] = None
    g = raw.get("gender")
    out["gender"] = g if g in ("MALE", "FEMALE") else None
    for k in _LIST_KEYS:
        v = raw.get(k)
        out[k] = [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []
    # 문자열 필드. _coerce 는 화이트리스트라, 여기에 적지 않은 키는
    # GPT 가 채워 줘도 조용히 버려진다 (search_text 를 추가하며 실제로 겪었다).
    for k in _STR_KEYS:
        v = raw.get(k)
        out[k] = v.strip() if isinstance(v, str) else ""
    return out


def parse_search_query(query: str, openai_api_key: str) -> dict[str, Any]:
    """검색 문장 → 필터 조건 dict (동기 — 호출부에서 thread 로 감쌈).

    LLM/파싱 실패 시 모든 조건이 비어있는 dict 반환(= 필터 없음).
    """
    empty = _coerce({})
    if not query.strip() or not openai_api_key:
        return empty

    from openai import OpenAI

    p = get_prompt("query_parse", file="search_query_parse.toml")
    client = OpenAI(api_key=openai_api_key)
    try:
        res = client.chat.completions.create(
            model=p.get("model", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": p["system"]},
                {"role": "user", "content": p["user_template"].format(query=query)},
            ],
            temperature=p.get("temperature", 0.0),
        )
        raw = json.loads(res.choices[0].message.content or "{}")
        return _coerce(raw)
    except Exception as e:
        logger.warning(f"query parse failed (필터 없이 진행): {e}")
        return empty
