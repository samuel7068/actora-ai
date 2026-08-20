"""영상 분석 파이프라인 — 1~6 단계.

- (1) 원본 메타데이터 + ffmpeg 정규화 (fps/해상도)
- (2) PySceneDetect — 장면 분리
- (3) OpenCV — 장면별 keyframe 추출
- (4) ffmpeg 로 오디오 추출 + OpenAI Whisper API STT
- (5) librosa 로 scene 별 음성 특징 (pause/energy/pitch/speech_rate)
- (6) GPT-4 Vision 으로 scene 별 RAG JSON 산출 (전략 B)

모든 함수는 동기. 호출하는 라우터에서 BackgroundTask 또는 동기 응답으로 사용.
"""
from __future__ import annotations

import base64
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import cv2
from scenedetect import ContentDetector, detect as detect_scenes_fn

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# (1) 원본 정보 + 정규화
# ─────────────────────────────────────────────────────────
def probe_video(path: Path) -> dict[str, Any]:
    """ffprobe 로 비디오 메타데이터 추출."""
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    raw = json.loads(result.stdout)

    streams = raw.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = raw.get("format", {})

    def _parse_fps(rate: str | None) -> float | None:
        if not rate or "/" not in rate:
            return None
        try:
            num, den = rate.split("/")
            d = float(den)
            return float(num) / d if d else None
        except (ValueError, ZeroDivisionError):
            return None

    return {
        "file_size_bytes": int(fmt.get("size", 0)) or None,
        "duration_sec": float(fmt.get("duration", 0)) or None,
        "format_name": fmt.get("format_name"),
        "video": {
            "codec": v.get("codec_name") if v else None,
            "width": v.get("width") if v else None,
            "height": v.get("height") if v else None,
            "fps_avg": _parse_fps(v.get("avg_frame_rate")) if v else None,
            "fps_r": _parse_fps(v.get("r_frame_rate")) if v else None,
            "pix_fmt": v.get("pix_fmt") if v else None,
        },
        "audio": {
            "codec": a.get("codec_name") if a else None,
            "sample_rate": int(a.get("sample_rate", 0)) if a and a.get("sample_rate") else None,
            "channels": a.get("channels") if a else None,
        } if a else None,
    }


def normalize_video(
    src: Path,
    dst: Path,
    target_fps: int = 30,
    max_height: int = 1080,
    crf: int = 21,
    preset: str = "veryfast",
) -> dict[str, Any]:
    """ffmpeg 로 fps/해상도/코덱 정규화 (영구 저장본).

    - 가로 비율 유지하며 높이를 max_height 로 제한 (작으면 그대로, 짝수 강제)
    - target_fps 초과면 다운샘플, 미만이면 유지
    - H.264 + AAC 128k + faststart, 결과 컨테이너 MP4

    **이미 조건을 만족하는 영상은 재인코딩하지 않고 영상 스트림을 그대로 복사한다.**
    소프트웨어 인코딩(libx264)은 이 파이프라인에서 가장 무거운 작업이라,
    코어가 적은 서버에서는 이 한 가지로 수십 초가 줄어든다.
    오디오만 aac 로 맞추는데, 오디오 인코딩은 영상에 비해 거의 공짜다.

    preset 은 veryfast — medium 대비 2~3배 빠르고 용량만 조금 늘어난다.
    캐스팅 영상 품질에는 영향이 없다.

    반환값에 `reencoded` 를 담아 어느 경로를 탔는지 알 수 있게 한다.
    """
    info = probe_video(src)
    v = info.get("video") or {}
    height = v.get("height") or 0
    fps = v.get("fps_avg") or v.get("fps_r") or 0.0
    codec = (v.get("codec") or "").lower()
    container = (info.get("format_name") or "").lower()

    # 재인코딩 없이 넘어갈 수 있는 조건 — 하나라도 어긋나면 다시 인코딩한다
    can_copy = (
        codec == "h264"
        and 0 < height <= max_height
        and 0 < fps <= target_fps + 0.5
        and "mp4" in container
    )

    if can_copy:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-c:v", "copy",          # 영상은 그대로 — 여기서 시간을 아낀다
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(dst),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            # min(현재높이, max_height) 로 다운스케일, 가로는 짝수 강제 (-2)
            "-vf", f"scale=-2:'min({max_height},ih)',fps='min({target_fps},source_fps)'",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(dst),
        ]

    subprocess.run(cmd, capture_output=True, check=True)
    logger.info(
        f"정규화: {'스트림 복사' if can_copy else f'재인코딩(preset={preset})'} "
        f"— 원본 {height}p/{fps:.1f}fps/{codec or '?'}"
    )
    out = probe_video(dst)
    out["reencoded"] = not can_copy
    return out


# ─────────────────────────────────────────────────────────
# (2) Scene Split
# ─────────────────────────────────────────────────────────
def detect_scenes(video_path: Path, threshold: float = 27.0) -> list[dict[str, Any]]:
    """PySceneDetect ContentDetector. threshold 기본 27 (콘텐츠 차이 민감도)."""
    scenes = detect_scenes_fn(str(video_path), ContentDetector(threshold=threshold))
    result = []
    for i, (start, end) in enumerate(scenes):
        start_s = float(start.get_seconds())
        end_s = float(end.get_seconds())
        result.append({
            "scene_id": f"scene_{i + 1:03d}",
            "start_sec": round(start_s, 3),
            "end_sec": round(end_s, 3),
            "duration_sec": round(end_s - start_s, 3),
        })
    # PySceneDetect 는 장면이 1개일 때(=전체 컷 없음) 빈 list 를 줄 수 있음 → fallback
    if not result:
        info = probe_video(video_path)
        dur = float(info.get("duration_sec") or 0)
        result.append({
            "scene_id": "scene_001",
            "start_sec": 0.0,
            "end_sec": round(dur, 3),
            "duration_sec": round(dur, 3),
        })
    return result


# ─────────────────────────────────────────────────────────
# (3) Keyframe Extraction (장면 중간 프레임)
# ─────────────────────────────────────────────────────────
def extract_keyframes(
    video_path: Path,
    scenes: list[dict[str, Any]],
    out_dir: Path,
    thumbnail_max_size: int = 320,
    samples_per_scene: int = 1,
) -> list[dict[str, Any]]:
    """각 장면의 대표 프레임을 jpg 로 저장 + base64 썸네일 반환.

    samples_per_scene 이 2 이상이면 장면을 균등 분할한 여러 시점에서 후보 프레임을
    추가로 뽑아 `candidates` 에 담는다. 단계 3.5(얼굴 식별)가 이 후보들 중
    인재가 가장 잘 잡힌 프레임을 대표로 승격시킨다 — 장면 중앙에서 인재가
    뒤돌아 있거나 화면 밖이면 그 장면 전체를 놓치기 때문.

    대표 프레임은 항상 장면 중앙 시점이며 파일명은 `{scene_id}.jpg`
    (samples_per_scene=1 이면 기존 동작과 완전히 동일).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    keyframes: list[dict[str, Any]] = []

    n = max(1, samples_per_scene)
    # 균등 내부 지점 — n=1 → [0.5], n=3 → [0.25, 0.5, 0.75]
    fractions = [(i + 1) / (n + 1) for i in range(n)]
    # 중앙에 가장 가까운 시점이 대표
    center_idx = min(range(n), key=lambda i: abs(fractions[i] - 0.5))

    try:
        for scene in scenes:
            sid = scene["scene_id"]
            start, end = scene["start_sec"], scene["end_sec"]
            candidates: list[dict[str, Any]] = []
            frames_by_idx: dict[int, Any] = {}

            for i, frac in enumerate(fractions):
                t_sec = start + (end - start) * frac
                frame_idx = max(0, int(t_sec * fps))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()
                if not ok or frame is None:
                    logger.warning(f"keyframe miss: {sid} @ {t_sec:.2f}s")
                    continue

                name = f"{sid}.jpg" if i == center_idx else f"{sid}_c{i}.jpg"
                path = out_dir / name
                cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                candidates.append({
                    "sample_index": i,
                    "timestamp_sec": round(t_sec, 3),
                    "frame_index": frame_idx,
                    "file_path": str(path),
                })
                frames_by_idx[i] = frame

            if not candidates:
                continue

            # 대표 = 중앙 시점. 중앙 읽기가 실패했으면 첫 후보로 대체.
            rep_i = center_idx if center_idx in frames_by_idx else min(frames_by_idx)
            rep_frame = frames_by_idx[rep_i]
            rep_meta = next(c for c in candidates if c["sample_index"] == rep_i)

            h, w = rep_frame.shape[:2]
            scale = thumbnail_max_size / max(w, h)
            thumb = cv2.resize(rep_frame, (int(w * scale), int(h * scale))) if scale < 1.0 else rep_frame
            _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")

            kf: dict[str, Any] = {
                "scene_id": sid,
                "timestamp_sec": rep_meta["timestamp_sec"],
                "frame_index": rep_meta["frame_index"],
                "width": w,
                "height": h,
                "file_path": rep_meta["file_path"],
                "thumbnail_data_uri": f"data:image/jpeg;base64,{b64}",
            }
            if n > 1:
                kf["candidates"] = candidates
            keyframes.append(kf)
    finally:
        cap.release()

    return keyframes


# ─────────────────────────────────────────────────────────
# (4) Audio Extract + Whisper STT
# ─────────────────────────────────────────────────────────
def extract_audio(video_path: Path, audio_path: Path) -> dict[str, Any]:
    """ffmpeg 로 m4a(aac) 오디오 추출 (Whisper API 권장 포맷)."""
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-vn",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(audio_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    size = audio_path.stat().st_size if audio_path.exists() else 0
    return {
        "path": str(audio_path),
        "size_bytes": size,
        "format": "aac/m4a",
    }


def extract_audio_features_per_scene(
    audio_path: Path,
    scenes: list[dict[str, Any]],
    stt_segments: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """librosa 로 scene 별 음성 특징 (pause/energy/pitch/speech_rate).

    - pause: scene 내 무성구간(에너지 임계 이하) 비율 및 총 길이
    - energy: RMS 평균/표준편차
    - pitch: pyin F0 추정 — 평균 Hz, 변동성
    - speech_rate: STT segment 의 글자 수 / scene 길이 (chars/sec)
    """
    import librosa
    import numpy as np

    # soundfile 이 m4a/aac 를 못 읽음 → ffmpeg 로 wav 변환 후 로드 (audioread fallback 회피)
    wav_path = audio_path.with_suffix(".librosa.wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(audio_path),
            "-vn", "-ac", "1", "-ar", "22050",
            "-c:a", "pcm_s16le",
            str(wav_path),
        ],
        capture_output=True, check=True,
    )

    # 전체 오디오 로드 (모노, 22050 Hz)
    y, sr = librosa.load(str(wav_path), sr=22050, mono=True)

    results: list[dict[str, Any]] = []
    for scene in scenes:
        start = max(0, float(scene["start_sec"]))
        end = float(scene["end_sec"])
        s_idx = int(start * sr)
        e_idx = min(len(y), int(end * sr))
        segment = y[s_idx:e_idx]
        if len(segment) < sr * 0.2:  # 0.2초 미만은 건너뜀
            results.append({
                "scene_id": scene["scene_id"],
                "skipped": True,
                "reason": "too_short",
            })
            continue

        # RMS energy
        rms = librosa.feature.rms(y=segment, frame_length=2048, hop_length=512)[0]
        energy_mean = float(np.mean(rms))
        energy_std = float(np.std(rms))

        # Pause detection — RMS < threshold 인 프레임 비율 (전체 평균의 20% 임계)
        rms_threshold = max(0.01, energy_mean * 0.2)
        silent_frames = (rms < rms_threshold).sum()
        total_frames = len(rms)
        pause_ratio = float(silent_frames / total_frames) if total_frames else 0.0
        hop_sec = 512 / sr
        pause_total_sec = float(silent_frames * hop_sec)

        # Pitch (F0) via pyin — 음성 범위 50~400 Hz
        try:
            f0, _, _ = librosa.pyin(
                segment, fmin=50, fmax=400, sr=sr, frame_length=2048,
            )
            f0_valid = f0[~np.isnan(f0)]
            pitch_mean = float(np.mean(f0_valid)) if f0_valid.size else None
            pitch_std = float(np.std(f0_valid)) if f0_valid.size else None
        except Exception:
            pitch_mean = pitch_std = None

        # Speech rate — STT segment 의 글자수를 scene 길이로 나눔
        chars_in_scene = 0
        if stt_segments:
            for seg in stt_segments:
                seg_mid = (seg["start"] + seg["end"]) / 2
                if start <= seg_mid <= end:
                    chars_in_scene += len((seg.get("text") or "").strip())
        scene_dur = max(0.1, end - start)
        speech_rate_cps = chars_in_scene / scene_dur if scene_dur else 0.0

        results.append({
            "scene_id": scene["scene_id"],
            "energy": {"mean": round(energy_mean, 4), "std": round(energy_std, 4)},
            "pause": {
                "ratio": round(pause_ratio, 3),
                "total_sec": round(pause_total_sec, 2),
            },
            "pitch_hz": {
                "mean": round(pitch_mean, 1) if pitch_mean is not None else None,
                "std": round(pitch_std, 1) if pitch_std is not None else None,
            },
            "speech_rate": {
                "chars_per_sec": round(speech_rate_cps, 2),
                "chars_in_scene": chars_in_scene,
                "scene_duration_sec": round(scene_dur, 2),
            },
        })
    return results


# 인재 카테고리(main_category) → scene_analysis 프롬프트 파일 매핑.
# 카테고리마다 분석 관점이 달라 프롬프트를 분리한다. 미설정/미지원이면 연기자(actor)로 fallback.
_PROMPT_FILE_BY_CATEGORY = {
    "ACTOR": "portfolio_video_analysis_actor.toml",
    "MODEL": "portfolio_video_analysis_model.toml",
    "INFLUENCER": "portfolio_video_analysis_influencer.toml",
    "VOCAL": "portfolio_video_analysis_vocal.toml",
    "DANCER": "portfolio_video_analysis_dancer.toml",
    "MC": "portfolio_video_analysis_mc.toml",
    "CREATOR": "portfolio_video_analysis_creator.toml",
}
_DEFAULT_PROMPT_FILE = "portfolio_video_analysis_actor.toml"  # fallback = 연기자


def _prompt_file_for_category(main_category: str | None) -> str:
    """main_category(예: 'MC')에 맞는 프롬프트 파일명 반환. 없으면 연기자 디폴트."""
    return _PROMPT_FILE_BY_CATEGORY.get((main_category or "").upper(), _DEFAULT_PROMPT_FILE)


def analyze_scene_with_gpt(
    *,
    account_id: int,
    talent_media_id: int,
    scene: dict[str, Any],
    keyframe: dict[str, Any] | None,
    stt_segments: list[dict[str, Any]] | None,
    audio_features: dict[str, Any] | None,
    openai_api_key: str,
    main_category: str | None = None,
) -> dict[str, Any]:
    """GPT-4 Vision 으로 scene JSON 산출 (단계 6).

    프롬프트는 인재의 main_category 에 맞는 backend/prompts/portfolio_video_analysis_*.toml 의
    [scene_analysis] 에서 로드 (미설정 시 연기자 프롬프트로 fallback).
    입력: keyframe(base64) + scene 시간 + STT 텍스트 + 음성 특징
    출력: RAG 용 scene JSON
    """
    if not openai_api_key:
        return {"error": "OPENAI_API_KEY_MISSING"}

    from openai import OpenAI
    from src.analysis.prompts import get_prompt
    client = OpenAI(api_key=openai_api_key)

    prompt = get_prompt("scene_analysis", file=_prompt_file_for_category(main_category))

    # scene 에 해당하는 STT 텍스트만 합치기
    start, end = float(scene["start_sec"]), float(scene["end_sec"])
    scene_text_parts: list[str] = []
    if stt_segments:
        for seg in stt_segments:
            seg_mid = (seg["start"] + seg["end"]) / 2
            if start <= seg_mid <= end:
                txt = (seg.get("text") or "").strip()
                if txt:
                    scene_text_parts.append(txt)
    scene_text = " ".join(scene_text_parts).strip() or "(음성 없음)"

    user_prompt = prompt["user_template"].format(
        scene_id=scene["scene_id"],
        start_sec=start,
        end_sec=end,
        duration_sec=end - start,
        scene_text=scene_text,
        audio_features=audio_features if audio_features else "(없음)",
    )

    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    if keyframe and keyframe.get("thumbnail_data_uri"):
        content.append({
            "type": "image_url",
            "image_url": {"url": keyframe["thumbnail_data_uri"], "detail": "low"},
        })

    # ── 단계 3.5(얼굴 식별) 결과를 반영 — 여러 인물이 나올 때 평가 대상을 못 박는다.
    #    target_present 가 None 이면 식별을 수행하지 않은 것 → 기존 동작 유지.
    target_present = keyframe.get("target_present") if keyframe else None
    face_count = int((keyframe or {}).get("face_count") or 0)
    crop_uri = (keyframe or {}).get("target_crop_data_uri")

    if crop_uri:
        content.append({"type": "text", "text": (
            f"[평가 대상 지정] 이 장면에는 인물이 {face_count}명 등장합니다. "
            "바로 아래 이미지는 그중 **평가 대상 인재의 얼굴만 잘라낸 것**입니다. "
            "반드시 이 인물만 분석하세요. 다른 등장인물의 외모·표정·의상·연기는 "
            "분석에 포함하지 마세요. 장면 전체 이미지는 배경·장소·상황 파악에만 사용하세요."
        )})
        content.append({
            "type": "image_url",
            # 얼굴 crop 만 high — low(85토큰)로 보내면 미간·입꼬리·눈물 같은
            # 미세한 표정이 뭉개져 감정 분석이 두루뭉술해진다.
            # 장면 전체 이미지는 배경·상황 파악용이라 low 로 충분하다.
            "image_url": {"url": crop_uri, "detail": "high"},
        })
    elif target_present is False:
        content.append({"type": "text", "text": (
            f"[주의] 이 장면에서는 평가 대상 인재의 얼굴이 확인되지 않았습니다"
            f"(검출된 얼굴 {face_count}명). 화면 속 인물이 대상 인재가 아닐 수 있으므로 "
            "외모·표정에 근거한 항목(hair/eye/image_type 등)은 비워 두고, "
            "장소·상황과 음성·대사에 근거해 채울 수 있는 항목만 채우세요."
        )})

    res = client.chat.completions.create(
        model=prompt.get("model", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": content},
        ],
        temperature=prompt.get("temperature", 0.3),
    )
    raw = res.choices[0].message.content or "{}"
    import json as _json
    try:
        parsed = _json.loads(raw)
    except _json.JSONDecodeError as e:
        return {"error": f"JSON_PARSE_FAILED: {e}", "raw": raw}

    # 식별자 강제 주입 (GPT 응답이 누락/오기 했을 수 있음)
    parsed["account_id"] = str(account_id)
    parsed["talent_media_id"] = str(talent_media_id)
    parsed["scene_id"] = scene["scene_id"]
    parsed["scene_start_sec"] = round(start, 3)
    parsed["scene_end_sec"] = round(end, 3)

    # 얼굴 식별 메타 — RAG 검색 시 신뢰도 필터링에 사용
    if keyframe is not None and target_present is not None:
        parsed["target_identified"] = bool(target_present)
        parsed["target_similarity"] = keyframe.get("target_similarity")
        parsed["target_confident"] = bool(keyframe.get("target_confident"))
        parsed["scene_face_count"] = face_count
    return parsed


# 인재 카테고리 → 종합 요약 프롬프트에 넣을 한글 라벨
_CATEGORY_LABELS = {
    "ACTOR": "연기자(배우)",
    "MODEL": "모델",
    "INFLUENCER": "인플루언서",
    "VOCAL": "보컬",
    "DANCER": "댄서",
    "MC": "MC(진행자)",
    "CREATOR": "크리에이터",
}

# 종합 요약에 넣을 최대 scene 수. 초과하면 균등 간격으로 추려
# 영상 앞뒤의 서로 다른 상황이 골고루 반영되게 한다 (앞부분만 자르면 뒷 상황이 통째로 사라짐).
_SUMMARY_MAX_SCENES = 80


def summarize_media_scenes(
    *,
    rag_scenes: list[dict[str, Any]],
    openai_api_key: str,
    main_category: str | None = None,
) -> str | None:
    """단계 6.5 — scene 요약들을 영상 1편의 대표 서술로 종합.

    scene_summary 를 그대로 이어 붙이면 scene 70개에 8,000자가 되고 같은 표현이
    수십 번 반복된다. 그렇다고 앞부분만 자르면 뒤쪽의 다른 상황이 사라지므로,
    GPT 로 **중복만 걷어내고 서로 다른 정보는 살리는** 서술을 만든다.

    실패하면 None 을 반환 — 호출 측에서 기존 이어붙이기로 fallback 한다.
    """
    if not openai_api_key:
        return None

    # 인재로 특정되지 않은 scene 은 다른 등장인물을 묘사한 것일 수 있어 제외.
    # (target_identified 가 None 이면 얼굴 식별을 수행하지 않은 영상 → 그대로 사용)
    usable = [
        sc for sc in rag_scenes
        if isinstance(sc, dict) and not sc.get("error")
        and (sc.get("scene_summary") or "").strip()
    ]
    identified = [sc for sc in usable if sc.get("target_identified") is not False]
    if identified:
        usable = identified

    if not usable:
        return None

    if len(usable) > _SUMMARY_MAX_SCENES:
        step = len(usable) / _SUMMARY_MAX_SCENES
        usable = [usable[int(i * step)] for i in range(_SUMMARY_MAX_SCENES)]

    lines = []
    for sc in usable:
        start = sc.get("scene_start_sec")
        end = sc.get("scene_end_sec")
        when = f" ({start}~{end}초)" if start is not None and end is not None else ""

        # 요약이 "무슨 역·무슨 사건" 을 담으려면 role 정보도 같이 줘야 한다.
        # scene_summary 만 넘기면 외형·감정만 남고 상황이 사라진다.
        role = sc.get("role") or {}
        tags = [
            role.get("role_label"),
            role.get("situation"),
            role.get("character_type"),
            role.get("occupation"),
            role.get("action"),
        ]
        tag = " / ".join(t.strip() for t in tags if isinstance(t, str) and t.strip())
        prefix = f"[{tag}] " if tag else ""
        lines.append(
            f"- {sc.get('scene_id')}{when}: {prefix}{sc['scene_summary'].strip()}"
        )

    from openai import OpenAI
    from src.analysis.prompts import get_prompt

    prompt = get_prompt("media_summary", file="portfolio_video_summary.toml")
    user_prompt = prompt["user_template"].format(
        category_label=_CATEGORY_LABELS.get((main_category or "").upper(), "인재"),
        scene_count=len(usable),
        scene_lines="\n".join(lines),
    )

    client = OpenAI(api_key=openai_api_key)
    res = client.chat.completions.create(
        model=prompt.get("model", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": user_prompt},
        ],
        temperature=prompt.get("temperature", 0.2),
    )

    import json as _json
    try:
        parsed = _json.loads(res.choices[0].message.content or "{}")
    except _json.JSONDecodeError:
        return None

    summary = (parsed.get("summary") or "").strip()
    return summary or None


def transcribe_whisper(audio_path: Path, openai_api_key: str, language: str | None = "ko") -> dict[str, Any]:
    """OpenAI Whisper API 로 STT (segment 타임스탬프 포함)."""
    if not openai_api_key:
        return {"error": "OPENAI_API_KEY_MISSING"}

    from openai import OpenAI
    client = OpenAI(api_key=openai_api_key)

    with audio_path.open("rb") as f:
        kwargs: dict[str, Any] = {
            "model": "whisper-1",
            "file": f,
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
        }
        if language:
            kwargs["language"] = language
        res = client.audio.transcriptions.create(**kwargs)

    # res 는 pydantic-like 객체 — dict 로 직렬화
    raw = res.model_dump() if hasattr(res, "model_dump") else dict(res)
    segments = []
    for seg in raw.get("segments") or []:
        segments.append({
            "id": seg.get("id"),
            "start": seg.get("start"),
            "end": seg.get("end"),
            "text": seg.get("text"),
        })
    return {
        "text": raw.get("text"),
        "language": raw.get("language"),
        "duration": raw.get("duration"),
        "segments": segments,
    }
