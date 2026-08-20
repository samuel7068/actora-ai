"""얼굴 기반 인재 식별 — InsightFace(ArcFace) 임베딩 대조.

영상에 여러 인물이 등장할 때, 프로필 사진의 얼굴과 대조해
"어느 얼굴이 이 인재인가" 를 특정한다.

구성:
    (a) 프로필 사진 → 512d 정규화 임베딩  (talent_master.face_embeddings 에 캐시)
    (b) keyframe   → 얼굴 검출 → 코사인 유사도 → 인재 얼굴 bbox / crop

모델은 프로세스당 1회만 로드 (약 325MB, CPU 추론).
모든 함수는 동기 — 호출 측에서 스레드풀로 감쌀 것.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "buffalo_l"
EMBEDDING_DIM = 512
# 모델 저장 위치. Docker 이미지에 미리 내려받아 둘 때 INSIGHTFACE_HOME 으로 지정한다
# (미지정 시 최초 호출에서 약 288MB 를 내려받으므로 첫 분석이 수 분 지연된다).
MODEL_ROOT = os.environ.get("INSIGHTFACE_HOME") or "~/.insightface"

# 코사인 유사도 임계값 — 실측 기반 (buffalo_l / w600k_r50).
#   보유 샘플(프로필 사진 5장 x 포트폴리오 영상 4편) 실측 분포:
#       동일인 0.740 ~ 0.927 / 타인 -0.12 ~ 0.288
#   타인 최대(0.288) 위로 마진을 두되, 프로필 사진과 영상의 촬영 시기·조명·화장이
#   다르면 동일인 유사도가 0.4~0.7 대까지 내려간다.
#   운영 데이터에서 일치 판정의 절반이 0.45~0.50 에 몰려 "본인인데 놓치는" 경우가
#   있어 0.45 → 0.40 으로 낮췄다. 타인 최대 0.288 과는 아직 0.11 의 간격이 있다.
#   반대로 다른 배우를 본인으로 오인하는 일이 늘면 0.45~0.50 으로 되돌린다.
SIM_THRESHOLD = 0.40
SIM_THRESHOLD_STRICT = 0.60

# 얼굴 검출 최소 신뢰도 (RetinaFace det_score)
MIN_DET_SCORE = 0.55
# 프로필 사진에서 임베딩을 뽑을 최소 얼굴 크기 (px)
MIN_PROFILE_FACE_PX = 50

_app = None
_app_lock = threading.Lock()


def get_face_app():
    """FaceAnalysis 싱글톤. 최초 호출 시 모델 로드 (수 초 소요)."""
    global _app
    if _app is not None:
        return _app
    with _app_lock:
        if _app is None:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(
                name=MODEL_NAME,
                root=MODEL_ROOT,
                providers=["CPUExecutionProvider"],
                # 검출 + 인식만 사용 (landmark/genderage 는 불필요 → 로딩·추론 절약)
                allowed_modules=["detection", "recognition"],
            )
            app.prepare(ctx_id=-1, det_size=(640, 640))
            _app = app
            logger.info(f"InsightFace ready: {MODEL_NAME}")
    return _app


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 0 else vec


def _face_embedding(face) -> np.ndarray:
    """Face 객체에서 L2 정규화된 임베딩 추출."""
    emb = getattr(face, "normed_embedding", None)
    if emb is None:
        emb = _normalize(np.asarray(face.embedding, dtype=np.float32))
    return np.asarray(emb, dtype=np.float32)


def _bbox_area(face) -> float:
    x1, y1, x2, y2 = [float(v) for v in face.bbox]
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


# ─────────────────────────────────────────────────────────
# (a) 프로필 사진 → 임베딩
# ─────────────────────────────────────────────────────────
def source_hash(image_paths: list[str]) -> str:
    """프로필 사진 목록의 지문 — 사진이 바뀌면 캐시를 무효화하는 데 사용."""
    joined = "\n".join(sorted(str(p) for p in image_paths))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def embed_profile_images(image_paths: list[Path | str]) -> dict[str, Any]:
    """프로필 사진들에서 인재 얼굴 임베딩을 추출.

    사진 1장당 **가장 큰 얼굴 1개** 만 사용한다 (프로필 사진은 본인이 주피사체라는 전제).
    반환 dict 는 그대로 talent_master.face_embeddings 에 저장 가능.
    """
    app = get_face_app()
    items: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for raw_path in image_paths:
        path = Path(raw_path)
        key = str(raw_path)
        img = cv2.imread(str(path))
        if img is None:
            failed.append({"source": key, "reason": "IMAGE_READ_FAILED"})
            continue

        faces = app.get(img)
        if not faces:
            failed.append({"source": key, "reason": "NO_FACE_DETECTED"})
            continue

        face = max(faces, key=_bbox_area)
        x1, y1, x2, y2 = [float(v) for v in face.bbox]
        if min(x2 - x1, y2 - y1) < MIN_PROFILE_FACE_PX:
            failed.append({"source": key, "reason": "FACE_TOO_SMALL"})
            continue
        if float(face.det_score) < MIN_DET_SCORE:
            failed.append({"source": key, "reason": "LOW_DET_SCORE"})
            continue

        emb = _face_embedding(face)
        items.append({
            "source": key,
            # JSONB 용량 절감 — 소수 6자리면 유사도 오차 1e-6 미만
            "embedding": [round(float(v), 6) for v in emb],
            "det_score": round(float(face.det_score), 4),
            "bbox": [round(v, 1) for v in (x1, y1, x2, y2)],
            "face_count_in_image": len(faces),
        })

    return {
        "model": MODEL_NAME,
        "dim": EMBEDDING_DIM,
        "items": items,
        "failed": failed,
    }


def load_reference_embeddings(face_embeddings: dict[str, Any] | None) -> np.ndarray | None:
    """DB 에 저장된 face_embeddings → (N, 512) 행렬. 없으면 None."""
    if not face_embeddings:
        return None
    items = face_embeddings.get("items") or []
    vectors = [
        np.asarray(it["embedding"], dtype=np.float32)
        for it in items
        if it.get("embedding")
    ]
    if not vectors:
        return None
    return np.vstack(vectors)


# ─────────────────────────────────────────────────────────
# (b) 프레임에서 인재 찾기
# ─────────────────────────────────────────────────────────
def _match_faces(img: np.ndarray, refs: np.ndarray) -> dict[str, Any]:
    """프레임 1장에서 인재 얼굴을 탐색.

    프로필 사진이 여러 장이면 **최댓값** 을 유사도로 삼는다
    (정면/측면 등 각도별 사진 중 하나만 맞아도 동일인).
    """
    app = get_face_app()
    faces = [f for f in app.get(img) if float(f.det_score) >= MIN_DET_SCORE]
    if not faces:
        return {"face_count": 0, "target": None, "best_similarity": None}

    best_face = None
    best_sim = -1.0
    for face in faces:
        sims = refs @ _face_embedding(face)  # refs 는 이미 L2 정규화됨
        sim = float(np.max(sims))
        if sim > best_sim:
            best_sim, best_face = sim, face

    if best_face is None or best_sim < SIM_THRESHOLD:
        return {
            "face_count": len(faces),
            "target": None,
            "best_similarity": round(best_sim, 4) if best_sim >= 0 else None,
        }

    x1, y1, x2, y2 = [float(v) for v in best_face.bbox]
    h, w = img.shape[:2]
    return {
        "face_count": len(faces),
        "best_similarity": round(best_sim, 4),
        "target": {
            "similarity": round(best_sim, 4),
            "confident": best_sim >= SIM_THRESHOLD_STRICT,
            "det_score": round(float(best_face.det_score), 4),
            "bbox": [round(v, 1) for v in (x1, y1, x2, y2)],
            # 얼굴이 화면에서 차지하는 비율 — 클로즈업/롱샷 판별에 사용
            "face_ratio": round(((x2 - x1) * (y2 - y1)) / float(w * h), 5),
        },
    }


def crop_face_data_uri(
    img: np.ndarray,
    bbox: list[float],
    *,
    margin: float = 0.45,
    max_size: int = 448,
    quality: int = 85,
) -> str | None:
    """얼굴 bbox 를 여유 있게 잘라 base64 data URI 로 반환 (GPT 전달용).

    margin 은 표정뿐 아니라 상반신 자세·의상도 함께 보이도록 넉넉히 준다.
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    if bw <= 0 or bh <= 0:
        return None

    mx, my = bw * margin, bh * margin
    cx1 = max(0, int(x1 - mx))
    cy1 = max(0, int(y1 - my))
    cx2 = min(w, int(x2 + mx))
    cy2 = min(h, int(y2 + my))
    crop = img[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return None

    ch, cw = crop.shape[:2]
    scale = max_size / max(ch, cw)
    if scale < 1.0:
        crop = cv2.resize(crop, (int(cw * scale), int(ch * scale)))

    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return None
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def identify_talent_in_keyframes(
    keyframes: list[dict[str, Any]],
    face_embeddings: dict[str, Any] | None,
    *,
    thumbnail_max_size: int = 320,
) -> dict[str, Any]:
    """단계 3.5 — keyframe 별로 인재 얼굴을 특정 (keyframes 를 제자리 수정).

    scene 당 후보 프레임(candidates)이 여러 개면, 인재 얼굴이 **가장 크게 잡힌**
    프레임을 대표 keyframe 으로 승격한다. 중간 프레임에서 인재가 뒤돌아 있거나
    화면 밖이면 그 scene 전체를 놓치는 문제를 막기 위함.

    각 keyframe 에 주입되는 필드:
        target_present     bool   — 인재로 판정된 얼굴 존재 여부
        target_similarity  float  — 코사인 유사도 (미검출 시 None)
        target_confident   bool   — STRICT 임계값 초과 여부
        target_bbox        list   — [x1,y1,x2,y2]
        target_face_ratio  float  — 얼굴 면적 / 프레임 면적
        target_crop_data_uri str  — 얼굴 crop (GPT 전달용)
        face_count         int    — 프레임 내 검출된 총 얼굴 수
    """
    refs = load_reference_embeddings(face_embeddings)
    if refs is None:
        for kf in keyframes:
            kf["target_present"] = None  # 판정 불가 (프로필 임베딩 없음)
        return {
            "enabled": False,
            "reason": "NO_PROFILE_EMBEDDING",
            "scene_total": len(keyframes),
            "scene_with_target": 0,
        }

    scene_with_target = 0
    multi_person_scenes = 0

    for kf in keyframes:
        # 후보 프레임 목록 — 없으면 대표 프레임 1개만 검사
        candidates = kf.get("candidates") or [{
            "file_path": kf.get("file_path"),
            "timestamp_sec": kf.get("timestamp_sec"),
            "frame_index": kf.get("frame_index"),
        }]

        best: dict[str, Any] | None = None
        best_img: np.ndarray | None = None
        max_face_count = 0

        for cand in candidates:
            path = cand.get("file_path")
            if not path:
                continue
            img = cv2.imread(str(path))
            if img is None:
                continue
            res = _match_faces(img, refs)
            max_face_count = max(max_face_count, res["face_count"])
            tgt = res["target"]
            if tgt is None:
                continue
            # 인재 얼굴이 가장 크게 잡힌 후보를 채택
            if best is None or tgt["face_ratio"] > best["target"]["face_ratio"]:
                best = {"cand": cand, "target": tgt, "face_count": res["face_count"]}
                best_img = img

        kf["face_count"] = max_face_count
        if max_face_count > 1:
            multi_person_scenes += 1

        if best is None or best_img is None:
            kf["target_present"] = False
            kf["target_similarity"] = None
            kf["target_confident"] = False
            kf["target_bbox"] = None
            kf["target_face_ratio"] = None
            kf["target_crop_data_uri"] = None
            continue

        scene_with_target += 1
        tgt = best["target"]
        cand = best["cand"]

        # 대표 프레임 승격 — 채택된 후보가 기존 대표와 다르면 교체
        if cand.get("file_path") and cand["file_path"] != kf.get("file_path"):
            kf["file_path"] = cand["file_path"]
            kf["timestamp_sec"] = cand.get("timestamp_sec", kf.get("timestamp_sec"))
            kf["frame_index"] = cand.get("frame_index", kf.get("frame_index"))
            kf["thumbnail_data_uri"] = _thumbnail_data_uri(best_img, thumbnail_max_size)
            kf["representative_swapped"] = True

        kf["target_present"] = True
        kf["target_similarity"] = tgt["similarity"]
        kf["target_confident"] = tgt["confident"]
        kf["target_bbox"] = tgt["bbox"]
        kf["target_face_ratio"] = tgt["face_ratio"]
        kf["target_crop_data_uri"] = crop_face_data_uri(best_img, tgt["bbox"])
        kf["face_count"] = best["face_count"]

    logger.info(
        f"얼굴 식별 완료: {scene_with_target}/{len(keyframes)} scene 에서 인재 확인 "
        f"(2인 이상 등장 {multi_person_scenes} scene, 프로필 참조 {int(refs.shape[0])}장, "
        f"임계값 {SIM_THRESHOLD})"
    )
    return {
        "enabled": True,
        "model": MODEL_NAME,
        "threshold": SIM_THRESHOLD,
        "threshold_strict": SIM_THRESHOLD_STRICT,
        "reference_count": int(refs.shape[0]),
        "scene_total": len(keyframes),
        "scene_with_target": scene_with_target,
        "multi_person_scenes": multi_person_scenes,
    }


def _thumbnail_data_uri(img: np.ndarray, max_size: int) -> str:
    h, w = img.shape[:2]
    scale = max_size / max(w, h)
    thumb = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1.0 else img
    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
