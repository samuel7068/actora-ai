"""프롬프트 로더 — backend/prompts/*.toml 를 로드해 dict 로 제공.

사용:
    from src.analysis.prompts import get_prompt
    p = get_prompt("scene_analysis")
    system = p["system"]
    user_msg = p["user_template"].format(scene_id="...", ...)
    model = p.get("model", "gpt-4o-mini")
    temperature = p.get("temperature", 0.3)

운영 중 프롬프트만 바꿔서 컨테이너 재시작하면 반영. 코드 수정 불필요.
"""
from __future__ import annotations

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

# backend/src/analysis/prompts.py → backend/prompts/
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

# 파일별 캐시: filename → (mtime, dict)
_cache: dict[str, tuple[float, dict]] = {}


def _load_file(filename: str) -> dict:
    """mtime 기반 자동 reload — TOML 파일 수정 시 다음 호출에서 자동 반영."""
    path = _PROMPTS_DIR / filename
    mtime = path.stat().st_mtime
    cached = _cache.get(filename)
    if cached and cached[0] == mtime:
        return cached[1]
    with path.open("rb") as f:
        data = tomllib.load(f)
    _cache[filename] = (mtime, data)
    logger.info(f"loaded prompts from {filename} (mtime={mtime})")
    return data


def get_prompt(name: str, *, file: str = "analysis.toml") -> dict:
    """프롬프트 dict 반환. 키: system, user_template, model, temperature, version, description."""
    data = _load_file(file)
    if name not in data:
        raise KeyError(
            f"prompt '{name}' not found in {file}. Available: {list(data.keys())}"
        )
    return data[name]


def reload_prompts():
    """수동 캐시 클리어 — mtime 자동 reload 이지만 강제 클리어가 필요한 경우."""
    _cache.clear()
