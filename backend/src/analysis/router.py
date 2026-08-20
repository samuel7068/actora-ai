"""영상 분석 디버그 API.

POST /talent/portfolio/analyze-debug — 영상 업로드 + 1~4단계 파이프라인 실행
→ 모든 중간 산출물(probe / scenes / keyframes / stt)을 JSON 으로 반환.

처리 흐름:
1. 업로드된 영상을 /tmp/actora-analyze/{job_id}/ 에 저장
2. 단계별 실행 (실패 단계는 error 표기, 다음 단계는 가능하면 진행)
3. 응답 후 디렉토리 cleanup
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.face import (
    embed_profile_images,
    identify_talent_in_keyframes,
    source_hash,
)
from src.analysis.pipeline import (
    analyze_scene_with_gpt,
    detect_scenes,
    extract_audio,
    extract_audio_features_per_scene,
    extract_keyframes,
    normalize_video,
    probe_video,
    summarize_media_scenes,
    transcribe_whisper,
)
from src.analysis.rag_index import delete_media_points, index_scenes
from src.analysis.schemas import AnalyzeDebugResponse, StageInfo
from src.auth.deps import get_current_account
from src.config import get_settings
from src.database import get_db
from src.media.service import save_portfolio_thumbnail
from src.storage import StorageError, get_storage
from src.talent.models import TalentMaster, TalentMedia

logger = logging.getLogger(__name__)

analysis_router = APIRouter()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _portfolio_relative_key(account_id: int, media_id: int) -> str:
    """체계적 파일명: talent/{account_id}/portfolio/{account_id}_{media_id}.mp4"""
    return f"talent/{account_id}/portfolio/{account_id}_{media_id}.mp4"


# scene 요약을 그대로 이어 붙이는 fallback 의 길이 상한.
# scene 70개면 8,000자가 넘어 카드·목록 어디에도 쓸 수 없다.
_AI_SUMMARY_FALLBACK_MAX = 1000


def _build_ai_summary(
    rag_scenes: list[dict[str, Any]],
    *,
    openai_api_key: str | None = None,
    main_category: str | None = None,
) -> str | None:
    """talent_media.ai_summary 용 대표 서술 생성 (단계 6.5).

    GPT 로 scene 요약들을 종합한다 — 반복 표현은 통합하고 서로 다른 장소·상황은 모두 살린다.
    호출이 실패하면 기존처럼 이어 붙이되, 길이 상한을 두어 폭주를 막는다.
    """
    if openai_api_key:
        try:
            summary = summarize_media_scenes(
                rag_scenes=rag_scenes,
                openai_api_key=openai_api_key,
                main_category=main_category,
            )
            if summary:
                return summary
            logger.warning("media_summary 결과가 비어 fallback 사용")
        except Exception as e:
            logger.warning(f"media_summary 실패 — fallback 사용: {type(e).__name__}: {e}")

    parts: list[str] = []
    for s in rag_scenes:
        if isinstance(s, dict):
            summ = s.get("scene_summary")
            if isinstance(summ, str) and summ.strip():
                parts.append(summ.strip())
    if not parts:
        return None
    joined = " ".join(parts)
    if len(joined) > _AI_SUMMARY_FALLBACK_MAX:
        joined = joined[:_AI_SUMMARY_FALLBACK_MAX].rstrip() + "…"
    return joined


class StageList(list):
    """append 될 때마다 진행 상황을 스트리밍 구독자에게 흘려보내는 stages 리스트.

    분석 본체 코드는 그대로 \`stages.append(StageInfo(...))\` 만 하면 되고,
    스트리밍 여부는 이 리스트가 emit 콜백을 들고 있는지에만 달려 있다.
    이벤트에는 무거운 \`data\` (base64 썸네일·얼굴 crop) 를 싣지 않는다 — 최종 결과에만 담는다.
    """

    def __init__(self, emit=None):
        super().__init__()
        self._emit = emit

    def append(self, item: StageInfo) -> None:  # type: ignore[override]
        super().append(item)
        # 서버 로그에도 남긴다 — 진행 중 어디까지 갔는지 로그만으로 추적할 수 있어야 한다
        line = f"[{item.stage}] {item.label} — {'완료' if item.success else '실패'} ({item.elapsed_ms}ms)"
        if item.error:
            logger.warning(f"{line} · {item.error}")
        else:
            logger.info(line)
        if self._emit:
            self._emit({
                "type": "stage",
                "stage": item.stage,
                "label": item.label,
                "success": item.success,
                "elapsed_ms": item.elapsed_ms,
                "error": item.error,
            })


async def _run_sync(func, *args, **kwargs):
    """블로킹 함수를 thread pool 에서 실행 (event loop 보호)."""
    return await asyncio.to_thread(func, *args, **kwargs)


# 장면별 GPT 분석 동시 실행 수. 대부분 응답 대기라 병렬이 효과적이지만,
# 너무 올리면 OpenAI 레이트리밋(429)에 걸린다.
SCENE_CONCURRENCY = 5

# scene 당 후보 프레임 수 — 장면 중앙에서 인재가 뒤돌아 있거나 화면 밖일 때를
# 대비해 여러 시점을 뽑고, 단계 3.5 가 그중 인재가 가장 잘 잡힌 것을 대표로 삼는다.
KEYFRAME_SAMPLES_PER_SCENE = 3


def _poster_frame_path(keyframes: list[dict[str, Any]]) -> Path | None:
    """카드에 쓸 포스터로 가장 좋은 대표 프레임을 고른다.

    우선순위:
      1) 인재로 확신(target_confident)한 장면 중 유사도가 가장 높은 프레임
      2) 인재가 잡힌(target_present) 장면 중 유사도가 가장 높은 프레임
      3) 얼굴 식별이 없었으면 영상 앞부분을 피해 중간쯤 장면

    얼굴이 보이는 프레임을 쓰면 목록에서 누구의 영상인지 바로 알 수 있다.
    검은 화면·타이틀로 시작하는 영상이 많아 첫 프레임은 쓰지 않는다.
    """
    if not keyframes:
        return None

    def sim(kf: dict[str, Any]) -> float:
        try:
            return float(kf.get("target_similarity") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    for pick in (
        [k for k in keyframes if k.get("target_confident")],
        [k for k in keyframes if k.get("target_present")],
    ):
        if pick:
            best = max(pick, key=sim)
            path = best.get("file_path")
            if path and Path(path).exists():
                return Path(path)

    # 폴백 — 중간 장면부터 실제로 존재하는 파일을 찾는다
    order = sorted(range(len(keyframes)), key=lambda i: abs(i - len(keyframes) // 2))
    for i in order:
        path = keyframes[i].get("file_path")
        if path and Path(path).exists():
            return Path(path)
    return None


def _profile_image_keys(talent: TalentMaster) -> list[str]:
    """talent.profile_image_urls → 저장소 키 목록 (실제로 있는 것만).

    파일을 내려받지 않고 키만 확인한다. 얼굴 임베딩 캐시가 살아 있으면
    사진을 받을 필요가 없기 때문이다.
    """
    urls = list(talent.profile_image_urls or [])
    if not urls and talent.profile_image_url:
        urls = [talent.profile_image_url]

    store = get_storage()
    keys: list[str] = []
    missing: list[str] = []
    for url in urls:
        if not isinstance(url, str) or not url.strip():
            continue
        # URL 은 /api/talent/profile-photo/{account_id}/{filename} 형식.
        # 마지막 세그먼트만 취해 경로 조작을 차단한다.
        filename = url.rstrip("/").rsplit("/", 1)[-1]
        if not filename or filename in (".", ".."):
            continue
        key = f"talent/{talent.account_id}/profile/{filename}"
        (keys if store.exists(key) else missing).append(key)

    # DB 의 URL 이 가리키는 파일이 없으면 얼굴 임베딩이 조용히 건너뛰어진다.
    # (프로필 사진을 여러 번 올려 URL 과 실제 파일이 어긋나는 경우)
    # 그 상태를 로그로 드러내야 원인을 찾을 수 있다.
    if missing:
        logger.warning(
            f"프로필 사진 없음 {len(missing)}건 (account={talent.account_id}) "
            f"— DB URL 과 저장소 내용이 어긋남: {missing[:3]}"
        )
    return keys


async def _ensure_face_embeddings(
    talent: TalentMaster, db: AsyncSession
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """프로필 얼굴 임베딩을 확보 (캐시 우선, 사진이 바뀌었으면 재계산).

    저장소 **키** 목록으로 지문을 만든다. 키에는 업로드 때 발급한 uuid 파일명이
    들어 있으므로 사진을 교체하면 지문이 달라져 자동으로 무효화된다.
    (로컬 경로로 지문을 만들면 임시 디렉토리 이름이 매번 바뀌어 캐시가 늘 빗나간다)
    """
    keys = _profile_image_keys(talent)
    if not keys:
        registered = len(talent.profile_image_urls or [])
        logger.warning(
            f"얼굴 임베딩 생략 (account={talent.account_id}): 사용할 프로필 사진이 없음 "
            f"— DB 등록 {registered}건, 저장소에서 찾은 파일 0건. "
            f"이 상태에서는 영상에서 인재를 특정할 수 없다."
        )
        return None, {
            "source": "none",
            "reason": "NO_PROFILE_IMAGE",
            "registered_urls": registered,
        }

    digest = source_hash(keys)
    cached = talent.face_embeddings
    if (
        isinstance(cached, dict)
        and cached.get("source_hash") == digest
        and cached.get("items")
    ):
        # 캐시 적중 — 사진을 내려받지 않는다
        return cached, {
            "source": "cache",
            "profile_image_count": len(keys),
            "reference_count": len(cached["items"]),
        }

    # InsightFace 는 로컬 파일 경로를 받으므로 원본을 임시로 내려받는다.
    # (썸네일이 아니라 원본 — 얼굴 인식 정확도는 해상도에 좌우된다)
    with tempfile.TemporaryDirectory(prefix="actora_face_") as tmp:
        store = get_storage()
        paths: list[str] = []
        for key in keys:
            local = Path(tmp) / key.rsplit("/", 1)[-1]
            try:
                store.download_to(key, local)
                paths.append(str(local))
            except StorageError as e:
                logger.warning(f"프로필 사진 다운로드 실패 ({key}): {e}")
        if not paths:
            return None, {
                "source": "none",
                "reason": "PROFILE_IMAGE_DOWNLOAD_FAILED",
                "registered_urls": len(keys),
            }
        result = await _run_sync(embed_profile_images, paths)

    result["source_hash"] = digest
    result["computed_at"] = datetime.now(timezone.utc).isoformat()

    talent.face_embeddings = result
    try:
        await db.commit()
        await db.refresh(talent)
    except Exception as e:  # 캐시 저장 실패는 분석을 막지 않는다
        await db.rollback()
        logger.warning(f"face_embeddings 저장 실패 (account_id={talent.account_id}): {e}")

    items, failed = result.get("items") or [], result.get("failed") or []
    if failed:
        logger.warning(
            f"프로필 사진에서 얼굴 추출 실패 {len(failed)}건 "
            f"(account={talent.account_id}): {failed}"
        )
    logger.info(
        f"프로필 얼굴 임베딩 계산 (account={talent.account_id}): "
        f"사진 {len(keys)}장 → 참조 {len(items)}개"
    )
    return result, {
        "source": "computed",
        "profile_image_count": len(keys),
        "reference_count": len(items),
        "failed": failed,
    }


async def _resolve_target(
    *,
    account_id: int | None,
    current,
    db: AsyncSession,
    content_type: str | None,
) -> tuple[int, TalentMaster]:
    """권한 · MIME · talent 존재를 검증하고 (target_account_id, talent) 반환.

    스트리밍 응답은 일단 시작되면 상태 코드를 바꿀 수 없으므로, 검증은 반드시
    응답을 열기 전에 끝내야 한다. 업로드를 디스크에 쓰기 전에 거르는 효과도 있다.
    """
    account, _admin = current
    # 대행 업로드(account_id 지정)면 ADMIN, 아니면 본인(TALENT)
    if account_id is not None:
        if account.account_type != "ADMIN":
            raise HTTPException(status_code=403, detail="ADMIN_ONLY_FOR_PROXY_UPLOAD")
        target_account_id = account_id
    else:
        if account.account_type != "TALENT":
            raise HTTPException(status_code=403, detail="TALENT_ONLY")
        target_account_id = account.account_id

    if not content_type or not content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail=f"NOT_A_VIDEO:{content_type}")

    # talent_master 행 존재 확인 (가입 미완 방지)
    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == target_account_id)
        )
    ).scalar_one_or_none()
    if not talent:
        raise HTTPException(status_code=404, detail="TALENT_PROFILE_NOT_FOUND")

    return target_account_id, talent


async def _spool_upload(file: UploadFile) -> tuple[str, Path, Path, int]:
    """업로드를 작업 디렉토리에 저장하고 (job_id, work_dir, original_path, size) 반환.

    **반드시 엔드포인트 함수 안에서 호출할 것.** StreamingResponse 의 제너레이터가
    돌기 시작할 때는 FastAPI 가 이미 UploadFile 을 닫은 뒤라
    거기서 read 하면 `ValueError: read of closed file` 이 난다.
    """
    job_id = uuid.uuid4().hex
    work_dir = Path(tempfile.gettempdir()) / "actora-analyze" / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    original_path = work_dir / f"original_{file.filename or 'upload.mp4'}"

    total = 0
    CHUNK = 1024 * 1024
    with original_path.open("wb") as fp:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            fp.write(chunk)
    return job_id, work_dir, original_path, total


async def _analyze(
    *,
    filename: str,
    job_id: str,
    work_dir: Path,
    original_path: Path,
    upload_size_bytes: int,
    target_account_id: int,
    talent: TalentMaster,
    db: AsyncSession,
    emit=None,
):
    """이미 디스크에 저장된 업로드 영상으로 분석 파이프라인 실행 + 영구 저장.

    검증(권한·MIME·talent 존재)과 업로드 저장은 호출 측에서 끝내고 들어온다
    — `_resolve_target()` / `_spool_upload()` 참조.

    - 정규화/RAG/Qdrant 적재 성공 시에만 talent_media 확정 (무결성)
    - emit 이 주어지면 진행 상황을 이벤트로 흘려보낸다
    """
    started_total = _now_ms()
    normalized_path = work_dir / "normalized.mp4"
    keyframes_dir = work_dir / "keyframes"
    audio_path = work_dir / "audio.m4a"

    stages = StageList(emit)
    scenes: list[dict[str, Any]] = []
    normalized_ok = False

    def begin(stage: str, label: str) -> None:
        """단계 시작을 알린다.

        stages.append 는 단계가 **끝난 뒤** 호출되므로, 정규화처럼 수십 초 걸리는
        단계에서는 그동안 화면·로그에 아무 정보가 없다. 시작 시점을 따로 알린다.
        """
        logger.info(f"[{stage}] {label} — 시작")
        if emit:
            emit({"type": "stage_start", "stage": stage, "label": label})

    try:
        # ─────── 단계 1: probe + normalize ───────
        begin("probe_normalize", "원본 정보 확인 · 영상 정규화")
        t0 = _now_ms()
        try:
            probe_orig = await _run_sync(probe_video, original_path)
            probe_norm = await _run_sync(normalize_video, original_path, normalized_path)
            normalized_ok = True
            stages.append(StageInfo(
                stage="probe_normalize",
                label="원본 정보 확인 · 영상 정규화",
                success=True,
                elapsed_ms=_now_ms() - t0,
                data={
                    "original": probe_orig,
                    "normalized": probe_norm,
                    "target": {
                        "max_fps": 30,
                        "max_height": 1080,
                        "codec": "h264",
                        "crf": 21,
                        "preset": "medium",
                        "audio": "aac 128k",
                        "container": "mp4 +faststart",
                    },
                },
            ))
        except subprocess.CalledProcessError as e:
            stages.append(StageInfo(
                stage="probe_normalize",
                label="원본 정보 확인 · 영상 정규화",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"FFMPEG_ERROR: {e.stderr.decode('utf-8', errors='ignore')[:500] if e.stderr else str(e)}",
            ))
        except Exception as e:
            stages.append(StageInfo(
                stage="probe_normalize",
                label="원본 정보 확인 · 영상 정규화",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"{type(e).__name__}: {e}",
            ))

        analysis_target = normalized_path if normalized_ok else original_path

        # ─────── 단계 2: scene split ───────
        begin("scene_split", "장면 분리")
        t0 = _now_ms()
        try:
            scenes = await _run_sync(detect_scenes, analysis_target)
            stages.append(StageInfo(
                stage="scene_split",
                label="장면 분리",
                success=True,
                elapsed_ms=_now_ms() - t0,
                data={
                    "scene_count": len(scenes),
                    "scenes": scenes,
                    "threshold": 27.0,
                },
            ))
        except Exception as e:
            stages.append(StageInfo(
                stage="scene_split",
                label="장면 분리",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"{type(e).__name__}: {e}",
            ))

        # ─────── 단계 3: keyframe extraction ───────
        begin("keyframes", "대표 프레임 추출")
        t0 = _now_ms()
        keyframes_data: list[dict[str, Any]] = []
        if scenes:
            try:
                keyframes_data = await _run_sync(
                    extract_keyframes,
                    analysis_target,
                    scenes,
                    keyframes_dir,
                    samples_per_scene=KEYFRAME_SAMPLES_PER_SCENE,
                )
                stages.append(StageInfo(
                    stage="keyframes",
                    label="대표 프레임 추출",
                    success=True,
                    elapsed_ms=_now_ms() - t0,
                    data={
                        "count": len(keyframes_data),
                        "frames": keyframes_data,
                    },
                ))
            except Exception as e:
                stages.append(StageInfo(
                    stage="keyframes",
                    label="대표 프레임 추출",
                    success=False,
                    elapsed_ms=_now_ms() - t0,
                    error=f"{type(e).__name__}: {e}",
                ))
        else:
            stages.append(StageInfo(
                stage="keyframes",
                label="대표 프레임 추출",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error="NO_SCENES",
            ))

        # ─────── 단계 3.5: 인재 얼굴 식별 (InsightFace) ───────
        begin("face_identify", "인재 얼굴 식별")
        # 여러 인물이 등장하는 영상에서 "어느 얼굴이 이 인재인가" 를 특정한다.
        # keyframes_data 를 제자리 수정하므로 이후 단계(6)가 그대로 활용한다.
        t0 = _now_ms()
        try:
            face_embeddings, emb_meta = await _ensure_face_embeddings(talent, db)
            if keyframes_data:
                identify_result = await _run_sync(
                    identify_talent_in_keyframes, keyframes_data, face_embeddings
                )
            else:
                identify_result = {
                    "enabled": False,
                    "reason": "NO_KEYFRAMES",
                    "scene_total": 0,
                    "scene_with_target": 0,
                }
            stages.append(StageInfo(
                stage="face_identify",
                label="인재 얼굴 식별",
                success=bool(identify_result.get("enabled")),
                elapsed_ms=_now_ms() - t0,
                data={
                    "profile_embedding": emb_meta,
                    "identification": identify_result,
                    "scenes": [
                        {
                            "scene_id": kf.get("scene_id"),
                            "target_present": kf.get("target_present"),
                            "target_similarity": kf.get("target_similarity"),
                            "target_confident": kf.get("target_confident"),
                            "target_face_ratio": kf.get("target_face_ratio"),
                            "face_count": kf.get("face_count"),
                            "representative_swapped": kf.get("representative_swapped", False),
                        }
                        for kf in keyframes_data
                    ],
                },
                error=None if identify_result.get("enabled") else identify_result.get("reason"),
            ))
        except Exception as e:
            logger.exception("face_identify 실패")
            stages.append(StageInfo(
                stage="face_identify",
                label="인재 얼굴 식별",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"{type(e).__name__}: {e}",
            ))

        # ─────── 단계 4: audio extract + Whisper STT ───────
        begin("audio_stt", "음성 추출 · 대사 인식")
        t0 = _now_ms()
        config = get_settings()
        try:
            audio_meta = await _run_sync(extract_audio, analysis_target, audio_path)
        except subprocess.CalledProcessError as e:
            stages.append(StageInfo(
                stage="audio_stt",
                label="음성 추출 · 대사 인식",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"AUDIO_EXTRACT_FAILED: {e.stderr.decode('utf-8', errors='ignore')[:300] if e.stderr else str(e)}",
            ))
        else:
            try:
                stt = await _run_sync(
                    transcribe_whisper, audio_path, config.OPENAI_API_KEY, "ko"
                )
                stages.append(StageInfo(
                    stage="audio_stt",
                    label="음성 추출 · 대사 인식",
                    success="error" not in stt,
                    elapsed_ms=_now_ms() - t0,
                    data={
                        "audio": audio_meta,
                        "stt": stt,
                    },
                    error=stt.get("error"),
                ))
            except Exception as e:
                stages.append(StageInfo(
                    stage="audio_stt",
                    label="음성 추출 · 대사 인식",
                    success=False,
                    elapsed_ms=_now_ms() - t0,
                    data={"audio": audio_meta},
                    error=f"{type(e).__name__}: {e}",
                ))

        # 단계 4 결과에서 STT segments 추출 (단계 5/6 입력)
        stt_segments: list[dict[str, Any]] = []
        for st in stages:
            if st.stage == "audio_stt" and st.success and st.data:
                stt_data = (st.data or {}).get("stt") if isinstance(st.data, dict) else None
                if isinstance(stt_data, dict):
                    stt_segments = stt_data.get("segments") or []
                break

        # ─────── 단계 5: 음성 특징 (scene 별) ───────
        begin("audio_features", "음성 특징 분석")
        t0 = _now_ms()
        audio_features_by_scene: dict[str, dict[str, Any]] = {}
        if scenes and audio_path.exists():
            try:
                feats = await _run_sync(
                    extract_audio_features_per_scene, audio_path, scenes, stt_segments,
                )
                audio_features_by_scene = {f["scene_id"]: f for f in feats}
                stages.append(StageInfo(
                    stage="audio_features",
                    label="음성 특징 분석",
                    success=True,
                    elapsed_ms=_now_ms() - t0,
                    data={"per_scene": feats},
                ))
            except Exception as e:
                stages.append(StageInfo(
                    stage="audio_features",
                    label="음성 특징 분석",
                    success=False,
                    elapsed_ms=_now_ms() - t0,
                    error=f"{type(e).__name__}: {e}",
                ))
        else:
            stages.append(StageInfo(
                stage="audio_features",
                label="음성 특징 분석",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error="NO_SCENES_OR_AUDIO",
            ))

        # ─────── 영구 저장 (무결성): media_id flush → 단계6 RAG → Qdrant 적재 성공 시에만 commit ───────
        # 원칙: RAG 가 Qdrant 에 성공 적재(>=1건)되어야 DB·영상 파일을 확정한다.
        #       하나라도 실패하면 rollback + Qdrant 보상삭제 (+ 임시영상은 finally 폐기) → 아무것도 남기지 않음.
        #       → "검색 안 되는 유령 영상" 이 구조적으로 생기지 않는다.
        persisted_media_id: int | None = None
        persisted_path: str | None = None
        persisted_size: int | None = None
        rag_scenes: list[dict[str, Any]] = []

        if not (normalized_ok and normalized_path.exists()):
            stages.append(StageInfo(
                stage="rag_json",
                label="장면 분석 · 검색 색인 · 저장",
                success=False,
                elapsed_ms=0,
                error="SKIPPED_NORMALIZE_FAILED",
            ))
        elif not (scenes and keyframes_data):
            stages.append(StageInfo(
                stage="rag_json",
                label="장면 분석 · 검색 색인 · 저장",
                success=False,
                elapsed_ms=0,
                error="SKIPPED_NO_SCENES_OR_KEYFRAMES",
            ))
        else:
            begin("rag_json", "장면 분석 · 검색 색인 · 저장")
            t0 = _now_ms()
            keyframe_by_scene = {kf["scene_id"]: kf for kf in keyframes_data}
            errors: list[str] = []
            media_id: int | None = None
            indexed_count = 0
            ai_summary: str | None = None
            try:
                # 1) talent_media flush 로 media_id 만 발급 (commit 은 Qdrant 성공 후)
                cur_max = (
                    await db.execute(
                        select(TalentMedia.sort_order)
                        .where(TalentMedia.account_id == target_account_id)
                        .order_by(TalentMedia.sort_order.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                next_order = (cur_max or 0) + 100

                row = TalentMedia(
                    account_id=target_account_id,
                    media_type="MOVIE",
                    media_path="__pending__",
                    original_file_name=filename,
                    stored_file_name="__pending__",
                    file_size=normalized_path.stat().st_size,
                    mime_type="video/mp4",
                    sort_order=next_order,
                    is_main=False,
                    is_public=True,
                )
                db.add(row)
                await db.flush()  # media_id 발급 (commit 안 함)
                media_id = row.talent_media_id

                # 2) 단계 6 — 장면별 GPT 분석 (병렬)
                #
                # 각 호출은 대부분 **응답 대기** 라 순차로 돌리면 장면 수 × 응답시간이
                # 그대로 총 시간이 된다 (70장면이면 수 분). 동시에 여러 개를 던지면
                # 대기 시간이 겹쳐 그만큼 줄어든다 — CPU 사양과 무관한 개선이다.
                # 동시 실행 수는 OpenAI 레이트리밋을 고려해 제한한다.
                sem = asyncio.Semaphore(SCENE_CONCURRENCY)
                done_count = 0

                async def analyze_one(idx: int, sc: dict[str, Any]):
                    nonlocal done_count
                    async with sem:
                        if emit:
                            emit({
                                "type": "scene_start",
                                "index": idx,
                                "total": len(scenes),
                                "scene_id": sc["scene_id"],
                                "start_sec": sc.get("start_sec"),
                                "end_sec": sc.get("end_sec"),
                            })
                        try:
                            scene_json = await _run_sync(
                                analyze_scene_with_gpt,
                                account_id=target_account_id,
                                talent_media_id=media_id,
                                scene=sc,
                                keyframe=keyframe_by_scene.get(sc["scene_id"]),
                                stt_segments=stt_segments,
                                audio_features=audio_features_by_scene.get(sc["scene_id"]),
                                openai_api_key=config.OPENAI_API_KEY,
                                main_category=talent.main_category,
                            )
                        except Exception as e:
                            errors.append(f"{sc['scene_id']}: {type(e).__name__}: {e}")
                            scene_json = {
                                "scene_id": sc["scene_id"],
                                "error": f"{type(e).__name__}: {e}",
                            }

                        # 완료 순서는 뒤섞이므로 "몇 개 끝났는지" 로 진행률을 센다
                        done_count += 1
                        if done_count % 10 == 0 or done_count == len(scenes):
                            logger.info(
                                f"[rag_json] 장면 분석 {done_count}/{len(scenes)}"
                            )
                        if emit:
                            emit({
                                "type": "scene",
                                "index": idx,
                                "total": len(scenes),
                                "scene_id": sc["scene_id"],
                                "start_sec": sc.get("start_sec"),
                                "end_sec": sc.get("end_sec"),
                                "summary": scene_json.get("scene_summary"),
                                # analyze_scene_with_gpt 는 실패를 예외가 아니라
                                # {"error": ...} dict 로 돌려주기도 한다 — 그 경우도 알린다
                                "error": scene_json.get("error"),
                                "target_identified": scene_json.get("target_identified"),
                                "target_similarity": scene_json.get("target_similarity"),
                            })
                        return idx, scene_json

                analyzed = await asyncio.gather(
                    *(analyze_one(i, sc) for i, sc in enumerate(scenes, start=1))
                )
                # 장면 순서대로 되돌린다 — RAG 저장·요약은 시간순이어야 읽힌다
                rag_scenes.extend(js for _, js in sorted(analyzed, key=lambda x: x[0]))

                # 3) Qdrant 적재 — 무결성 핵심. 성공(>=1건)해야 이후 DB·영상 확정.
                indexed_count = await index_scenes(
                    account_id=target_account_id,
                    talent_media_id=media_id,
                    rag_scenes=rag_scenes,
                    openai_api_key=config.OPENAI_API_KEY,
                )
                logger.info(
                    f"[rag_json] Qdrant 적재 {indexed_count}건 "
                    f"(분석 {len(rag_scenes)}장면, 오류 {len(errors)}건)"
                )
                if indexed_count == 0:
                    raise RuntimeError(
                        "QDRANT_INDEX_EMPTY: 적재 가능한 scene 0건 — 검색 불가하므로 저장 취소"
                    )

                # 4) 여기 도달 = Qdrant 적재 성공 → 영상 영구화 + DB 확정
                relative_key = _portfolio_relative_key(target_account_id, media_id)
                stored_name = f"{target_account_id}_{media_id}.mp4"
                # 저장소로 옮긴다 (성공하면 임시파일은 정리된다)
                file_size = get_storage().put_file(
                    Path(normalized_path), relative_key, content_type="video/mp4"
                )

                row.media_path = relative_key
                row.stored_file_name = stored_name
                row.file_size = file_size

                # 카드 목록용 포스터 — 얼굴이 가장 잘 잡힌 대표 프레임을 쓴다.
                # 실패해도 화면이 아이콘으로 폴백하므로 분석을 막지 않는다.
                poster = _poster_frame_path(keyframes_data)
                if poster:
                    row.thumbnail_path = await _run_sync(
                        save_portfolio_thumbnail, poster, target_account_id, media_id
                    )
                else:
                    logger.warning(
                        f"영상 포스터를 만들 대표 프레임이 없다 (media={media_id})"
                    )
                ai_summary = await _run_sync(
                    _build_ai_summary,
                    rag_scenes,
                    openai_api_key=config.OPENAI_API_KEY,
                    main_category=talent.main_category,
                )
                if ai_summary:
                    row.ai_summary = ai_summary
                    logger.info(f"대표 요약 생성: {len(ai_summary)}자")
                    if emit:
                        emit({"type": "summary", "summary": ai_summary})

                # RAG .txt 저장 (디버그용 — 추후 관리자 Qdrant 조회로 대체 예정)
                rag_relative = f"rag/{target_account_id}_{media_id}.txt"
                import json as _json
                get_storage().put_bytes(
                    _json.dumps(rag_scenes, ensure_ascii=False, indent=2).encode("utf-8"),
                    rag_relative,
                    content_type="application/json; charset=utf-8",
                )

                await db.commit()  # ← Qdrant 성공 후에야 DB 확정
                persisted_media_id = media_id
                persisted_path = relative_key
                persisted_size = row.file_size

                stages.append(StageInfo(
                    stage="rag_json",
                    label="장면 분석 · 검색 색인 · 저장",
                    success=len(errors) == 0,
                    elapsed_ms=_now_ms() - t0,
                    data={
                        "talent_media_id": persisted_media_id,
                        "media_path": persisted_path,
                        "file_size_bytes": persisted_size,
                        "scene_count": len(rag_scenes),
                        "qdrant_indexed": indexed_count,
                        "ai_summary_saved": bool(ai_summary),
                        "rag_file_path": rag_relative,
                        "errors": errors,
                    },
                    error="; ".join(errors) if errors else None,
                ))
            except Exception as e:
                # 무결성: 무엇이든 실패하면 전부 원복 — DB rollback + Qdrant 보상삭제 (임시영상은 finally 폐기)
                await db.rollback()
                if media_id is not None:
                    try:
                        await delete_media_points(media_id)
                    except Exception as ce:
                        logger.warning(f"qdrant compensating delete failed: {ce}")
                persisted_media_id = None
                logger.exception(f"persist+rag+index failed (rolled back): {e}")
                stages.append(StageInfo(
                    stage="rag_json",
                    label="장면 분석 · 검색 색인 · 저장",
                    success=False,
                    elapsed_ms=_now_ms() - t0,
                    data={
                        "qdrant_indexed": indexed_count,
                        "scene_count": len(rag_scenes),
                        "rolled_back": True,
                        "errors": errors,
                    },
                    error=f"{type(e).__name__}: {e}",
                ))

        return AnalyzeDebugResponse(
            job_id=job_id,
            original_filename=filename,
            upload_size_bytes=upload_size_bytes,
            total_elapsed_ms=_now_ms() - started_total,
            stages=stages,
            talent_media_id=persisted_media_id,
            persisted_path=persisted_path,
            persisted_size_bytes=persisted_size,
            rag_scenes=rag_scenes if rag_scenes else None,
        )

    finally:
        # 임시 디렉토리 정리.
        #   성공 시: 정규화본은 영구 경로로 이동됨 → work_dir 에는 잔여물만 남아 안전.
        #   실패 시: 정규화본이 work_dir 에 그대로 → 여기서 함께 폐기 (무결성: 흔적 안 남김).
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"cleanup failed for {work_dir}: {e}")


# ─────────────────────────────────────────────────────────
# 엔드포인트 — 동기 / 스트리밍 두 가지로 같은 분석 본체를 공유
# ─────────────────────────────────────────────────────────
@analysis_router.post("/portfolio/analyze-debug", response_model=AnalyzeDebugResponse)
async def analyze_debug(
    file: UploadFile = File(...),
    account_id: int | None = Form(default=None),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """분석이 모두 끝난 뒤 전체 결과를 한 번에 반환 (기존 동작)."""
    target_account_id, talent = await _resolve_target(
        account_id=account_id, current=current, db=db, content_type=file.content_type
    )
    job_id, work_dir, original_path, size = await _spool_upload(file)
    return await _analyze(
        filename=file.filename or "upload.mp4",
        job_id=job_id,
        work_dir=work_dir,
        original_path=original_path,
        upload_size_bytes=size,
        target_account_id=target_account_id,
        talent=talent,
        db=db,
    )


@analysis_router.post("/portfolio/analyze-stream")
async def analyze_stream(
    file: UploadFile = File(...),
    account_id: int | None = Form(default=None),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """진행 상황을 NDJSON 한 줄씩 흘려보내며 분석.

    줄마다 하나의 이벤트:
        {"type":"stage",       ...}  단계 완료 (data 제외 — 가볍게)
        {"type":"scene_start", ...}  scene N 분석 시작
        {"type":"scene",       ...}  scene N 결과 (scene_summary 포함)
        {"type":"summary",     ...}  영상 대표 요약
        {"type":"result",      ...}  최종 전체 결과 (마지막 줄)
        {"type":"error",       ...}  실패
    """
    # 검증과 업로드 저장은 응답을 열기 전에 끝낸다.
    #  - 검증: 스트림이 시작되면 403/400 같은 상태 코드를 더 이상 줄 수 없다
    #  - 저장: 제너레이터가 도는 시점엔 UploadFile 이 이미 닫혀 있다
    target_account_id, talent = await _resolve_target(
        account_id=account_id, current=current, db=db, content_type=file.content_type
    )
    job_id, work_dir, original_path, size = await _spool_upload(file)
    filename = file.filename or "upload.mp4"

    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: dict) -> None:
        queue.put_nowait(event)

    async def run() -> None:
        try:
            result = await _analyze(
                filename=filename,
                job_id=job_id,
                work_dir=work_dir,
                original_path=original_path,
                upload_size_bytes=size,
                target_account_id=target_account_id,
                talent=talent,
                db=db,
                emit=emit,
            )
            queue.put_nowait({"type": "result", "result": result.model_dump(mode="json")})
        except HTTPException as e:
            queue.put_nowait({"type": "error", "status": e.status_code, "error": str(e.detail)})
        except Exception as e:
            logger.exception("analyze-stream 실패")
            queue.put_nowait({"type": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            queue.put_nowait(None)  # 종료 신호

    # 프록시(nginx·로드밸런서)는 데이터가 흐르지 않는 연결을 끊는다.
    # 분석은 단계 사이(업로드 수신·ffmpeg 정규화·STT)에 수십 초 침묵할 수 있어,
    # 그 사이 keep-alive 를 흘려보내 연결이 유지되게 한다.
    HEARTBEAT_SEC = 15

    async def gen():
        task = asyncio.create_task(run())
        # 첫 바이트를 즉시 보낸다 — 첫 단계가 끝날 때까지 기다리면
        # 그 침묵만으로 프록시 타임아웃(기본 60초)에 걸린다.
        yield json.dumps({"type": "start"}, ensure_ascii=False) + "\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SEC)
                except asyncio.TimeoutError:
                    yield json.dumps({"type": "ping"}, ensure_ascii=False) + "\n"
                    continue
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        # nginx 등 프록시가 응답을 모아두면 스트리밍이 무의미해진다
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
