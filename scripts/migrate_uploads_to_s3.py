#!/usr/bin/env python
"""로컬 uploads → 오브젝트 스토리지 일회성 이전 + 프로필 사진 썸네일 생성.

왜 필요한가
─────────────────────────────────────────────────────────────
파일을 버킷 한 곳으로 모으면 개발 PC ↔ 운영 서버 동기화가 사라진다.
그 전환을 위해 이미 디스크에 있는 파일을 한 번 올려야 한다.

키는 uploads 기준 상대 경로를 그대로 쓴다 → DB 의 media_path 를 고칠 필요가 없다.

사용법 (backend 디렉토리에서)
─────────────────────────────────────────────────────────────
    .venv/bin/python ../scripts/migrate_uploads_to_s3.py --dry-run
    .venv/bin/python ../scripts/migrate_uploads_to_s3.py
    .venv/bin/python ../scripts/migrate_uploads_to_s3.py --thumbs-only

옵션
    --dry-run      무엇을 올릴지만 출력
    --force        이미 버킷에 있어도 다시 올린다
    --thumbs-only  업로드는 건너뛰고 썸네일만 만든다
    --source DIR   원본 디렉토리 (기본: settings.UPLOAD_DIR)

같은 버킷을 두 환경이 공유하므로 이 스크립트는 **한쪽에서 한 번만** 돌리면 된다.
양쪽에 파일이 나뉘어 있으면 각각 돌린다 — 이미 있는 키는 건너뛰므로 안전하다.
"""
from __future__ import annotations

import argparse
import mimetypes
import sys
from pathlib import Path

# backend 를 import 경로에 넣는다 (스크립트가 repo/scripts 에 있으므로)
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.media.service import make_thumbnail, profile_thumb_key  # noqa: E402
from src.storage import get_storage  # noqa: E402

# 업로드하지 않는 것 — 옛 동기화 대장과 OS 잔재
SKIP_NAMES = {".deleted.log", ".DS_Store", "Thumbs.db"}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:,.1f}{unit}"
        n /= 1024
    return f"{n:,.1f}TB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--thumbs-only", action="store_true")
    ap.add_argument("--source", default="")
    args = ap.parse_args()

    config = get_settings()
    if not config.S3_BUCKET:
        print(
            "✗ S3_BUCKET 이 설정되지 않았습니다.\n"
            f"  backend/.env.{config.ENVIRONMENT} 에 S3_BUCKET 등을 넣어주세요.",
            file=sys.stderr,
        )
        return 1

    root = Path(args.source or config.UPLOAD_DIR).resolve()
    if not root.exists():
        print(f"✗ 원본 디렉토리가 없습니다: {root}", file=sys.stderr)
        return 1

    store = get_storage()
    print(f"원본 : {root}")
    print(f"대상 : s3://{config.S3_BUCKET} ({config.S3_REGION})")
    if args.dry_run:
        print("모드 : dry-run — 아무것도 올리지 않습니다")
    print()

    files = sorted(p for p in root.rglob("*") if p.is_file())
    files = [p for p in files if p.name not in SKIP_NAMES]

    uploaded = skipped = failed = 0
    thumbs_made = thumbs_skipped = 0
    bytes_up = 0

    for path in files:
        key = str(path.relative_to(root))
        size = path.stat().st_size
        is_profile = "/profile/" in f"/{key}" and "/profile/thumb/" not in f"/{key}"

        # ── 원본 업로드 ──
        if not args.thumbs_only:
            if not args.force and store.exists(key):
                skipped += 1
            elif args.dry_run:
                print(f"  [dry-run] 업로드 {key} ({human(size)})")
                uploaded += 1
                bytes_up += size
            else:
                try:
                    ctype = mimetypes.guess_type(key)[0] or "application/octet-stream"
                    # put_file 은 원본을 옮기므로(로컬 파일을 지운다) 바이트로 올린다.
                    # 이전 작업 중에 로컬 파일이 사라지면 되돌릴 수 없다.
                    store.put_bytes(path.read_bytes(), key, content_type=ctype)
                    uploaded += 1
                    bytes_up += size
                    print(f"  ↑ {key} ({human(size)})")
                except Exception as e:
                    failed += 1
                    print(f"  ✗ {key}: {e}", file=sys.stderr)

        # ── 프로필 사진 썸네일 ──
        if is_profile:
            parts = key.split("/")
            # talent/{account_id}/profile/{filename}
            if len(parts) == 4 and parts[0] == "talent":
                account_id, filename = parts[1], parts[3]
                tkey = profile_thumb_key(account_id, filename)
                if not args.force and store.exists(tkey):
                    thumbs_skipped += 1
                elif args.dry_run:
                    print(f"  [dry-run] 썸네일 {tkey}")
                    thumbs_made += 1
                else:
                    data = make_thumbnail(path)
                    if data:
                        try:
                            store.put_bytes(data, tkey, content_type="image/webp")
                            thumbs_made += 1
                            print(
                                f"  ⤓ {tkey} ({human(size)} → {human(len(data))})"
                            )
                        except Exception as e:
                            failed += 1
                            print(f"  ✗ {tkey}: {e}", file=sys.stderr)

    print()
    print(f"파일   : 전체 {len(files)}개")
    if not args.thumbs_only:
        print(f"업로드 : {uploaded}개 ({human(bytes_up)}) / 이미 있어 건너뜀 {skipped}개")
    print(f"썸네일 : 생성 {thumbs_made}개 / 이미 있어 건너뜀 {thumbs_skipped}개")
    if failed:
        print(f"실패   : {failed}개", file=sys.stderr)
        return 1

    if not args.dry_run:
        print()
        print("완료. 확인:")
        print("  - 화면에서 영상 재생과 프로필 사진 표시")
        print("  - 확인이 끝나면 backend/uploads 는 백업으로 두었다가 지우면 됩니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
