#!/usr/bin/env python
"""이미 분석된 영상에 포스터(카드 목록용 대표 이미지)를 만들어 넣는다.

왜 필요한가
─────────────────────────────────────────────────────────────
포스터 기능을 나중에 붙였으므로 그 전에 올린 영상은 thumbnail_path 가 비어 있고,
목록에서 회색 필름 아이콘만 보인다. 영상을 다시 분석할 필요는 없다 —
프레임만 뽑으면 되므로 GPT·Whisper 호출이 없고 비용도 들지 않는다.

어떻게 고르나
─────────────────────────────────────────────────────────────
영상에서 여러 시점의 프레임을 뽑고, InsightFace 로 **인재 얼굴이 가장 잘 잡힌
프레임**을 고른다 (분석 파이프라인과 같은 기준). 얼굴 임베딩이 없는 계정은
프로필 사진으로 즉석에서 계산한다 — 그러지 않으면 같은 영상에 나오는 다른
배우가 포스터로 잡힌다. 검은 화면·타이틀이 흔한 앞부분(15%)은 피한다.

계산한 임베딩은 DB 에 캐시되므로 이후 영상 분석도 그만큼 빨라진다.

사용법 (backend 디렉토리에서)
─────────────────────────────────────────────────────────────
    .venv/bin/python ../scripts/backfill_video_thumbnails.py --dry-run
    .venv/bin/python ../scripts/backfill_video_thumbnails.py
    .venv/bin/python ../scripts/backfill_video_thumbnails.py --force
    .venv/bin/python ../scripts/backfill_video_thumbnails.py --media-id 48

옵션
    --dry-run     대상만 출력
    --force       이미 포스터가 있어도 다시 만든다
    --media-id N  특정 영상 하나만 (반복 지정 가능)
    --no-face     얼굴 식별을 건너뛰고 중간 프레임을 쓴다 (빠르다)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import asyncio  # noqa: E402

from sqlalchemy import select  # noqa: E402

from src.analysis.face import identify_talent_in_keyframes  # noqa: E402
from src.analysis.router import _ensure_face_embeddings  # noqa: E402
from src.database import _get_async_session_local  # noqa: E402
from src.media.service import (portfolio_thumb_key,  # noqa: E402
                               save_portfolio_thumbnail)
from src.storage import StorageError, get_storage  # noqa: E402
from src.talent.models import TalentMaster, TalentMedia  # noqa: E402

# 프레임을 뽑을 지점 (영상 길이 대비 비율).
# 앞 15% 는 검은 화면·타이틀·로고가 흔해 제외한다.
SAMPLE_RATIOS = (0.20, 0.35, 0.50, 0.65, 0.80)


def probe_duration(path: Path) -> float:
    """영상 길이(초). 실패하면 0."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        return float((out.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def extract_frames(video: Path, out_dir: Path, duration: float) -> list[Path]:
    """여러 시점에서 프레임을 뽑는다. 실패한 시점은 건너뛴다."""
    frames: list[Path] = []
    # 길이를 못 구했으면 고정 시점이라도 시도한다
    points = ([duration * r for r in SAMPLE_RATIOS] if duration > 0
              else [2.0, 5.0, 10.0])
    for i, t in enumerate(points):
        dest = out_dir / f"frame_{i}.jpg"
        try:
            subprocess.run(
                # -ss 를 -i 앞에 두면 키프레임 단위로 빨리 seek 한다
                ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.3f}",
                 "-i", str(video), "-frames:v", "1", "-q:v", "2", "-y", str(dest)],
                capture_output=True, timeout=120,
            )
        except Exception:
            continue
        if dest.exists() and dest.stat().st_size > 0:
            frames.append(dest)
    return frames


def pick_frame(frames: list[Path], face_embeddings, use_face: bool) -> tuple[Path, str]:
    """포스터로 쓸 프레임과 선정 근거를 돌려준다."""
    if not frames:
        raise ValueError("추출된 프레임 없음")

    middle = frames[len(frames) // 2]
    if not use_face or not face_embeddings:
        return middle, "중간 프레임 (얼굴 임베딩 없음)"

    # 분석 파이프라인과 같은 판정을 재사용한다
    kfs = [{"scene_id": i, "file_path": str(p)} for i, p in enumerate(frames)]
    try:
        identify_talent_in_keyframes(kfs, face_embeddings)
    except Exception as e:
        return middle, f"중간 프레임 (얼굴 식별 실패: {e})"

    def sim(kf) -> float:
        try:
            return float(kf.get("target_similarity") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    for pick, why in (
        ([k for k in kfs if k.get("target_confident")], "얼굴 확신"),
        ([k for k in kfs if k.get("target_present")], "얼굴 일치"),
    ):
        if pick:
            best = max(pick, key=sim)
            return Path(best["file_path"]), f"{why} (유사도 {sim(best):.3f})"
    return middle, "중간 프레임 (인재 얼굴 미검출)"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--media-id", type=int, action="append", default=[])
    ap.add_argument("--no-face", action="store_true")
    args = ap.parse_args()

    store = get_storage()

    async with _get_async_session_local()() as db:
        q = select(TalentMedia).where(TalentMedia.media_type == "MOVIE")
        if args.media_id:
            q = q.where(TalentMedia.talent_media_id.in_(args.media_id))
        rows = list((await db.execute(q)).scalars().all())

        targets = [r for r in rows if args.force or not r.thumbnail_path]
        print(f"영상 {len(rows)}건 중 대상 {len(targets)}건"
              + (" (--force: 전부 다시 만든다)" if args.force else ""))
        if not targets:
            print("모든 영상에 포스터가 있습니다.")
            return 0

        # 얼굴 임베딩을 계정별로 한 번만 준비한다.
        # 없으면 프로필 사진으로 지금 계산한다 — 얼굴이 없으면 엉뚱한 인물이
        # 포스터로 잡히기 때문이다(다른 배우가 나오는 장면). 계산 결과는 DB 에
        # 캐시되므로 다음 영상 분석도 그만큼 빨라진다.
        emb: dict[int, object] = {}
        if not args.no_face:
            ids = {r.account_id for r in targets}
            talents = (await db.execute(
                select(TalentMaster).where(TalentMaster.account_id.in_(ids))
            )).scalars().all()
            had = computed = 0
            for t in talents:
                if t.face_embeddings and (t.face_embeddings or {}).get("items"):
                    emb[t.account_id] = t.face_embeddings
                    had += 1
                    continue
                result, meta = await _ensure_face_embeddings(t, db)
                if result and result.get("items"):
                    emb[t.account_id] = result
                    computed += 1
                    print(f"  얼굴 임베딩 계산: account {t.account_id} "
                          f"(사진 {meta.get('profile_image_count')}장 → "
                          f"참조 {meta.get('reference_count')}개)")
                else:
                    print(f"  얼굴 임베딩 없음: account {t.account_id} "
                          f"({meta.get('reason', '?')}) — 중간 프레임을 쓴다")
            print(f"얼굴 임베딩: 기존 {had}건 + 새로 계산 {computed}건 "
                  f"/ 계정 {len(ids)}개")
        print()

        done = failed = 0
        for r in targets:
            mid, aid = r.talent_media_id, r.account_id
            label = f"media {mid} (account {aid}) {r.original_file_name or ''}"[:60]
            if args.dry_run:
                print(f"  [dry-run] {label}")
                done += 1
                continue

            with tempfile.TemporaryDirectory(prefix="actora_poster_") as tmp:
                tmpd = Path(tmp)
                video = tmpd / "video.mp4"
                try:
                    store.download_to(r.media_path, video)
                except StorageError as e:
                    print(f"  ✗ {label}: 영상 다운로드 실패 {e}")
                    failed += 1
                    continue

                dur = probe_duration(video)
                frames = extract_frames(video, tmpd, dur)
                if not frames:
                    print(f"  ✗ {label}: 프레임 추출 실패 (길이 {dur:.1f}s)")
                    failed += 1
                    continue

                try:
                    frame, why = pick_frame(frames, emb.get(aid), not args.no_face)
                except ValueError as e:
                    print(f"  ✗ {label}: {e}")
                    failed += 1
                    continue

                key = save_portfolio_thumbnail(frame, aid, mid)
                if not key:
                    print(f"  ✗ {label}: 포스터 저장 실패")
                    failed += 1
                    continue
                r.thumbnail_path = key
                size = store.size(key)
                print(f"  ✓ {label}\n      {why} · {size / 1024:,.0f}KB · "
                      f"프레임 {len(frames)}개 검사 · 길이 {dur:.0f}s")
                done += 1

        if not args.dry_run:
            await db.commit()

    print(f"\n완료: {done}건" + (f" / 실패 {failed}건" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
