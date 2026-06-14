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
import logging
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.pipeline import (
    analyze_scene_with_gpt,
    detect_scenes,
    extract_audio,
    extract_audio_features_per_scene,
    extract_keyframes,
    normalize_video,
    probe_video,
    transcribe_whisper,
)
from src.analysis.rag_index import delete_media_points, index_scenes
from src.analysis.schemas import AnalyzeDebugResponse, StageInfo
from src.auth.deps import get_current_account
from src.config import get_settings
from src.database import get_db
from src.media.service import absolute_path
from src.talent.models import TalentMaster, TalentMedia

logger = logging.getLogger(__name__)

analysis_router = APIRouter()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _portfolio_relative_key(account_id: int, media_id: int) -> str:
    """체계적 파일명: talent/{account_id}/portfolio/{account_id}_{media_id}.mp4"""
    return f"talent/{account_id}/portfolio/{account_id}_{media_id}.mp4"


def _build_ai_summary(rag_scenes: list[dict[str, Any]]) -> str | None:
    """scene 별 scene_summary 들을 합쳐 talent_media.ai_summary 용 대표 요약 생성."""
    parts: list[str] = []
    for s in rag_scenes:
        if isinstance(s, dict):
            summ = s.get("scene_summary")
            if isinstance(summ, str) and summ.strip():
                parts.append(summ.strip())
    return " ".join(parts) if parts else None


async def _run_sync(func, *args, **kwargs):
    """블로킹 함수를 thread pool 에서 실행 (event loop 보호)."""
    return await asyncio.to_thread(func, *args, **kwargs)


@analysis_router.post("/portfolio/analyze-debug", response_model=AnalyzeDebugResponse)
async def analyze_debug(
    file: UploadFile = File(...),
    account_id: int | None = Form(default=None),
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """업로드된 영상을 분석 파이프라인 실행 + 영구 저장.

    - 본인 업로드: TALENT 가 자기 영상 (account_id 미지정)
    - 관리자 대행 업로드: ADMIN 이 시드 인재의 영상 (account_id 지정)
    - 정규화/RAG/Qdrant 적재 성공 시에만 talent_media 확정 (무결성)
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
        target_account_id = current[0].account_id

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400, detail=f"NOT_A_VIDEO:{file.content_type}"
        )

    # talent_master 행 존재 확인 (가입 미완 방지)
    talent = (
        await db.execute(
            select(TalentMaster).where(TalentMaster.account_id == target_account_id)
        )
    ).scalar_one_or_none()
    if not talent:
        raise HTTPException(status_code=404, detail="TALENT_PROFILE_NOT_FOUND")

    job_id = uuid.uuid4().hex
    work_dir = Path(tempfile.gettempdir()) / "actora-analyze" / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    started_total = _now_ms()
    original_path = work_dir / f"original_{file.filename or 'upload.mp4'}"
    normalized_path = work_dir / "normalized.mp4"
    keyframes_dir = work_dir / "keyframes"
    audio_path = work_dir / "audio.m4a"

    stages: list[StageInfo] = []
    upload_size_bytes = 0
    scenes: list[dict[str, Any]] = []
    normalized_ok = False

    try:
        # 0. 업로드 저장
        CHUNK = 1024 * 1024
        with original_path.open("wb") as fp:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                upload_size_bytes += len(chunk)
                fp.write(chunk)

        # ─────── 단계 1: probe + normalize ───────
        t0 = _now_ms()
        try:
            probe_orig = await _run_sync(probe_video, original_path)
            probe_norm = await _run_sync(normalize_video, original_path, normalized_path)
            normalized_ok = True
            stages.append(StageInfo(
                stage="probe_normalize",
                label="원본 메타데이터 + ffmpeg 정규화",
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
                label="원본 메타데이터 + ffmpeg 정규화",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"FFMPEG_ERROR: {e.stderr.decode('utf-8', errors='ignore')[:500] if e.stderr else str(e)}",
            ))
        except Exception as e:
            stages.append(StageInfo(
                stage="probe_normalize",
                label="원본 메타데이터 + ffmpeg 정규화",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"{type(e).__name__}: {e}",
            ))

        analysis_target = normalized_path if normalized_ok else original_path

        # ─────── 단계 2: scene split ───────
        t0 = _now_ms()
        try:
            scenes = await _run_sync(detect_scenes, analysis_target)
            stages.append(StageInfo(
                stage="scene_split",
                label="장면 분리 (PySceneDetect)",
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
                label="장면 분리 (PySceneDetect)",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error=f"{type(e).__name__}: {e}",
            ))

        # ─────── 단계 3: keyframe extraction ───────
        t0 = _now_ms()
        keyframes_data: list[dict[str, Any]] = []
        if scenes:
            try:
                keyframes_data = await _run_sync(
                    extract_keyframes, analysis_target, scenes, keyframes_dir
                )
                stages.append(StageInfo(
                    stage="keyframes",
                    label="대표 프레임 추출 (OpenCV)",
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
                    label="대표 프레임 추출 (OpenCV)",
                    success=False,
                    elapsed_ms=_now_ms() - t0,
                    error=f"{type(e).__name__}: {e}",
                ))
        else:
            stages.append(StageInfo(
                stage="keyframes",
                label="대표 프레임 추출 (OpenCV)",
                success=False,
                elapsed_ms=_now_ms() - t0,
                error="NO_SCENES",
            ))

        # ─────── 단계 4: audio extract + Whisper STT ───────
        t0 = _now_ms()
        config = get_settings()
        try:
            audio_meta = await _run_sync(extract_audio, analysis_target, audio_path)
        except subprocess.CalledProcessError as e:
            stages.append(StageInfo(
                stage="audio_stt",
                label="오디오 추출 + Whisper STT",
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
                    label="오디오 추출 + Whisper STT",
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
                    label="오디오 추출 + Whisper STT",
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
                    label="음성 특징 (librosa)",
                    success=True,
                    elapsed_ms=_now_ms() - t0,
                    data={"per_scene": feats},
                ))
            except Exception as e:
                stages.append(StageInfo(
                    stage="audio_features",
                    label="음성 특징 (librosa)",
                    success=False,
                    elapsed_ms=_now_ms() - t0,
                    error=f"{type(e).__name__}: {e}",
                ))
        else:
            stages.append(StageInfo(
                stage="audio_features",
                label="음성 특징 (librosa)",
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
                label="RAG 분석 + Qdrant 적재 + 영구 저장",
                success=False,
                elapsed_ms=0,
                error="SKIPPED_NORMALIZE_FAILED",
            ))
        elif not (scenes and keyframes_data):
            stages.append(StageInfo(
                stage="rag_json",
                label="RAG 분석 + Qdrant 적재 + 영구 저장",
                success=False,
                elapsed_ms=0,
                error="SKIPPED_NO_SCENES_OR_KEYFRAMES",
            ))
        else:
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
                    original_file_name=file.filename or "upload.mp4",
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

                # 2) 단계 6 — GPT-4V scene 분석
                for sc in scenes:
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
                        rag_scenes.append(scene_json)
                    except Exception as e:
                        errors.append(f"{sc['scene_id']}: {type(e).__name__}: {e}")
                        rag_scenes.append({
                            "scene_id": sc["scene_id"],
                            "error": f"{type(e).__name__}: {e}",
                        })

                # 3) Qdrant 적재 — 무결성 핵심. 성공(>=1건)해야 이후 DB·영상 확정.
                indexed_count = await index_scenes(
                    account_id=target_account_id,
                    talent_media_id=media_id,
                    rag_scenes=rag_scenes,
                    openai_api_key=config.OPENAI_API_KEY,
                )
                if indexed_count == 0:
                    raise RuntimeError(
                        "QDRANT_INDEX_EMPTY: 적재 가능한 scene 0건 — 검색 불가하므로 저장 취소"
                    )

                # 4) 여기 도달 = Qdrant 적재 성공 → 영상 영구화 + DB 확정
                relative_key = _portfolio_relative_key(target_account_id, media_id)
                stored_name = f"{target_account_id}_{media_id}.mp4"
                final_path = absolute_path(relative_key)
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(normalized_path), str(final_path))

                row.media_path = relative_key
                row.stored_file_name = stored_name
                row.file_size = final_path.stat().st_size
                ai_summary = _build_ai_summary(rag_scenes)
                if ai_summary:
                    row.ai_summary = ai_summary

                # RAG .txt 저장 (디버그용 — 추후 관리자 Qdrant 조회로 대체 예정)
                rag_relative = f"rag/{target_account_id}_{media_id}.txt"
                rag_path = absolute_path(rag_relative)
                rag_path.parent.mkdir(parents=True, exist_ok=True)
                import json as _json
                rag_path.write_text(
                    _json.dumps(rag_scenes, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                await db.commit()  # ← Qdrant 성공 후에야 DB 확정
                persisted_media_id = media_id
                persisted_path = relative_key
                persisted_size = row.file_size

                stages.append(StageInfo(
                    stage="rag_json",
                    label="RAG 분석 + Qdrant 적재 + 영구 저장",
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
                    label="RAG 분석 + Qdrant 적재 + 영구 저장",
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
            original_filename=file.filename or "upload.mp4",
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
