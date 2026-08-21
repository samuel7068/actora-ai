#!/usr/bin/env python
"""이미 등록된 영상을 프롬프트 최신판으로 다시 분석한다.

왜 필요한가
─────────────────────────────────────────────────────────────
분석 프롬프트를 고쳐도 이미 분석된 영상의 결과는 그대로다. 실제로 카메라 광고
영상의 한 컷이 "부상 장면" 으로 잘못 분석되어, 다친 연기를 찾는 검색에 광고 배우가
올라온 일이 있었다. 프롬프트는 고쳤지만(actor-1.4) 기존 데이터는 재분석해야 바뀐다.

어떻게 하나
─────────────────────────────────────────────────────────────
업로드 때와 **똑같은 파이프라인**을 다시 태운다 (scene 분리 → 대표 프레임 →
얼굴 식별 → STT → 장면별 GPT → Qdrant 적재 → 대표 요약 → 포스터).
그래서 파이프라인이 바뀌어도 이 스크립트를 따라 고칠 필요가 없다.

    버킷에서 영상 내려받기
      → 새로 분석해서 **새 미디어 행**을 만든다
      → 성공하면 옛 행 · 옛 Qdrant 포인트 · 옛 버킷 파일을 지운다
      → 실패하면 옛 것을 그대로 남긴다 (검색이 비는 시간이 없다)

새 행을 만드는 이유: 분석 로직이 "성공했을 때만 저장" 으로 무결성을 지키고 있어,
그 경로를 그대로 쓰는 것이 가장 안전하다. 대신 **talent_media_id 가 바뀐다.**
조회수와 등록일시도 새로 시작한다 (프로토타입이라 실질적인 손실은 없다).

비용
─────────────────────────────────────────────────────────────
영상 26개 · 장면 457개 기준으로 장면마다 GPT 호출이 한 번씩 일어난다.
Whisper STT 도 영상마다 다시 돈다. --dry-run 으로 규모를 먼저 확인할 것.

사용법 (backend 디렉토리에서)
─────────────────────────────────────────────────────────────
    .venv/bin/python ../scripts/reanalyze_videos.py --dry-run
    .venv/bin/python ../scripts/reanalyze_videos.py --media-id 50
    .venv/bin/python ../scripts/reanalyze_videos.py --account-id 16
    .venv/bin/python ../scripts/reanalyze_videos.py --all

옵션
    --dry-run       대상만 출력 (분석하지 않는다)
    --media-id N    특정 영상만 (반복 지정 가능)
    --account-id N  특정 아티스트의 영상 전부 (반복 지정 가능)
    --all           등록된 영상 전부 — 오래 걸리므로 명시적으로 요구한다
    --keep-old      옛 행·파일을 지우지 않는다 (결과를 나란히 비교할 때)
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import asyncio  # noqa: E402

from sqlalchemy import select  # noqa: E402

from src.account.models import AccountMaster  # noqa: E402
from src.analysis.rag_index import delete_media_points, get_media_scenes  # noqa: E402
from src.analysis.router import _analyze  # noqa: E402
from src.database import _get_async_session_local  # noqa: E402
from src.storage import StorageError, get_storage  # noqa: E402
from src.talent.models import TalentMaster, TalentMedia  # noqa: E402


async def collect(db, args) -> list:
    """재분석 대상 목록."""
    q = select(TalentMedia).where(TalentMedia.media_type == "MOVIE")
    if args.media_id:
        q = q.where(TalentMedia.talent_media_id.in_(args.media_id))
    elif args.account_id:
        q = q.where(TalentMedia.account_id.in_(args.account_id))
    q = q.order_by(TalentMedia.talent_media_id)
    return list((await db.execute(q)).scalars().all())


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--media-id", type=int, action="append", default=[])
    ap.add_argument("--account-id", type=int, action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--keep-old", action="store_true")
    args = ap.parse_args()

    if not (args.media_id or args.account_id or args.all or args.dry_run):
        print("✗ 대상을 지정하세요: --media-id / --account-id / --all "
              "(또는 --dry-run 으로 목록만 확인)", file=sys.stderr)
        return 1

    store = get_storage()
    Session = _get_async_session_local()

    async with Session() as db:
        targets = await collect(db, args)
        names = dict((await db.execute(
            select(AccountMaster.account_id, AccountMaster.name))).all())

        total_scenes = 0
        print(f"{'media':>6} {'이름':<5} {'scene':>5}  파일명")
        for r in targets:
            n = len(await get_media_scenes(r.talent_media_id))
            total_scenes += n
            print(f"{r.talent_media_id:>6} {names.get(r.account_id, '?'):<5} "
                  f"{n:>5}  {str(r.original_file_name)[:40]}")
        print(f"\n대상 {len(targets)}개 영상 / 기존 scene {total_scenes}개")
        print(f"장면마다 GPT 호출 1회 + 영상마다 STT 1회가 일어납니다.")
        print(f"예상 소요: 약 {len(targets) * 85 / 60:.0f}분 (영상당 80~90초)")

        if args.dry_run:
            print("\n[dry-run] 아무것도 바꾸지 않았습니다.")
            return 0

    done = failed = 0
    for r in targets:
        mid, aid = r.talent_media_id, r.account_id
        label = f"media {mid} ({names.get(aid, '?')}) {r.original_file_name or ''}"[:56]
        print(f"\n── {label}")

        # 세션은 영상마다 새로 연다 — 하나가 실패해도 다음이 깨끗한 상태로 시작한다
        async with Session() as db:
            talent = (await db.execute(
                select(TalentMaster).where(TalentMaster.account_id == aid)
            )).scalar_one_or_none()
            if talent is None:
                print("   ✗ 아티스트 프로필이 없어 건너뜁니다")
                failed += 1
                continue

            old_path = r.media_path
            # _analyze 는 끝나면서 work_dir 를 통째로 지운다. 그래서 내려받은 원본은
            # work_dir **밖**(임시 디렉토리 직하)에 두고, work_dir 은 그 아래에 따로 만든다.
            with tempfile.TemporaryDirectory(prefix="actora_reanalyze_") as tmp:
                base = Path(tmp)
                src = base / "original.mp4"
                work = base / "work"
                work.mkdir()
                try:
                    store.download_to(old_path, src)
                except StorageError as e:
                    print(f"   ✗ 영상 다운로드 실패: {e}")
                    failed += 1
                    continue

                try:
                    result = await _analyze(
                        filename=r.original_file_name or f"{mid}.mp4",
                        job_id=f"reanalyze-{mid}-{uuid.uuid4().hex[:6]}",
                        work_dir=work,
                        original_path=src,
                        upload_size_bytes=src.stat().st_size,
                        target_account_id=aid,
                        talent=talent,
                        db=db,
                    )
                except Exception as e:
                    print(f"   ✗ 분석 실패: {type(e).__name__}: {e}")
                    print("     옛 데이터는 그대로 남아 있습니다")
                    failed += 1
                    continue

            # _analyze 는 Pydantic 모델(AnalyzeDebugResponse)을 돌려준다
            new_id = getattr(result, "talent_media_id", None)
            if not new_id:
                print("   ✗ 분석이 미디어를 저장하지 못했습니다 (옛 데이터 유지)")
                failed += 1
                continue
            print(f"   ✓ 새 media {new_id} 생성")

            if args.keep_old:
                print(f"   · --keep-old: 옛 media {mid} 를 남겨 둡니다")
                done += 1
                continue

            # 새 분석이 성공한 **뒤에만** 옛 것을 치운다
            try:
                await delete_media_points(mid)
            except Exception as e:
                print(f"   ! 옛 Qdrant 포인트 삭제 실패: {e}")
            store.delete(old_path)
            store.delete(f"rag/{aid}_{mid}.txt")
            old_row = (await db.execute(
                select(TalentMedia).where(TalentMedia.talent_media_id == mid)
            )).scalar_one_or_none()
            if old_row is not None:
                if old_row.thumbnail_path:
                    store.delete(old_row.thumbnail_path)
                await db.delete(old_row)
                await db.commit()
            print(f"   · 옛 media {mid} 정리 완료")
            done += 1

    print(f"\n완료: {done}개" + (f" / 실패 {failed}개" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
