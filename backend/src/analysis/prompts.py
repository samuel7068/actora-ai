"""프롬프트 로더 — backend/prompts/*.toml 를 로드해 dict 로 제공.

정책: 프롬프트 1개당 .toml 파일 1개. 호출 시 file 로 어떤 파일인지 명시.

사용:
    from src.analysis.prompts import get_prompt
    p = get_prompt("scene_analysis", file="portfolio_video_analysis_actor.toml")
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
from threading import Lock

logger = logging.getLogger(__name__)

# backend/src/analysis/prompts.py → backend/prompts/
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

# 파일별 캐시: filename → (mtime, dict)
_cache: dict[str, tuple[float, dict]] = {}
# 캐시 채우기를 직렬화한다.
# 장면 분석은 동시에 5개가 돌아서(SCENE_CONCURRENCY), 락이 없으면 다섯 스레드가
# 캐시가 비어 있는 것을 동시에 보고 각자 파일을 읽는다. 그러면 같은 로그가 5줄
# 찍히고 파싱도 5번 한다. 실제 로그에서 그렇게 나타났다.
_lock = Lock()


def _version_of(data: dict) -> str:
    """로그에 남길 버전. 섹션에 적힌 version 을 모아 준다 (mtime 숫자보다 쓸모 있다)."""
    vs = [
        str(v["version"])
        for v in data.values()
        if isinstance(v, dict) and v.get("version")
    ]
    return ", ".join(dict.fromkeys(vs)) if vs else "-"


def _load_file(filename: str) -> dict:
    """mtime 기반 자동 reload — TOML 파일 수정 시 다음 호출에서 자동 반영."""
    path = _PROMPTS_DIR / filename
    mtime = path.stat().st_mtime
    cached = _cache.get(filename)
    if cached and cached[0] == mtime:
        return cached[1]

    with _lock:
        # 락을 기다리는 동안 다른 스레드가 이미 채웠을 수 있다
        cached = _cache.get(filename)
        if cached and cached[0] == mtime:
            return cached[1]
        with path.open("rb") as f:
            data = tomllib.load(f)
        _cache[filename] = (mtime, data)
        logger.info(f"프롬프트 로드: {filename} (version={_version_of(data)})")
        return data


def get_prompt(name: str, *, file: str) -> dict:
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
