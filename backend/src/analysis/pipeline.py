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
    preset: str = "medium",
) -> dict[str, Any]:
    """ffmpeg 로 fps/해상도/코덱 정규화 (영구 저장본).

    - 가로 비율 유지하며 높이를 max_height 로 제한 (작으면 그대로, 짝수 강제)
    - target_fps 초과면 다운샘플, 미만이면 유지
    - H.264 (CRF 21, preset medium) + AAC 128k + faststart
    - 결과 컨테이너: MP4

    화질/용량 균형: 1080p · CRF 21 · medium 은 캐스팅 영상 품질에 충분.
    """
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
    return probe_video(dst)


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
) -> list[dict[str, Any]]:
    """각 장면의 중간 시점 프레임을 jpg 로 저장 + base64 썸네일 반환."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    keyframes: list[dict[str, Any]] = []

    try:
        for scene in scenes:
            mid_sec = (scene["start_sec"] + scene["end_sec"]) / 2
            frame_idx = max(0, int(mid_sec * fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                logger.warning(f"keyframe miss: {scene['scene_id']} @ {mid_sec:.2f}s")
                continue
            h, w = frame.shape[:2]
            # 원본 jpg 저장
            full_path = out_dir / f"{scene['scene_id']}.jpg"
            cv2.imwrite(str(full_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])

            # 작은 썸네일 → base64
            scale = thumbnail_max_size / max(w, h)
            if scale < 1.0:
                thumb = cv2.resize(frame, (int(w * scale), int(h * scale)))
            else:
                thumb = frame
            _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")

            keyframes.append({
                "scene_id": scene["scene_id"],
                "timestamp_sec": round(mid_sec, 3),
                "frame_index": frame_idx,
                "width": w,
                "height": h,
                "file_path": str(full_path),
                "thumbnail_data_uri": f"data:image/jpeg;base64,{b64}",
            })
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


def analyze_scene_with_gpt(
    *,
    account_id: int,
    talent_media_id: int,
    scene: dict[str, Any],
    keyframe: dict[str, Any] | None,
    stt_segments: list[dict[str, Any]] | None,
    audio_features: dict[str, Any] | None,
    openai_api_key: str,
) -> dict[str, Any]:
    """GPT-4 Vision 으로 scene JSON 산출 (단계 6).

    프롬프트는 backend/prompts/analysis.toml 의 [scene_analysis] 에서 로드.
    입력: keyframe(base64) + scene 시간 + STT 텍스트 + 음성 특징
    출력: RAG 용 scene JSON
    """
    if not openai_api_key:
        return {"error": "OPENAI_API_KEY_MISSING"}

    from openai import OpenAI
    from src.analysis.prompts import get_prompt
    client = OpenAI(api_key=openai_api_key)

    prompt = get_prompt("scene_analysis")

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
    return parsed


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
