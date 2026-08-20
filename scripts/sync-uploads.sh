#!/usr/bin/env bash
#
# 개발 PC ↔ 운영 서버 업로드 파일 동기화 (양방향)
#
# 왜 필요한가:
#   두 환경은 DB 와 Qdrant 를 공유하지만 파일(영상·프로필 사진)은 각자 디스크에 있다.
#   그래서 한쪽에서 등록·분석하면 반대쪽 검색에는 바로 나타나지만 재생은 404 가 된다.
#
# 이 스크립트가 처리하는 것:
#   1) 서버 파일 소유권 정리
#      서버에서 등록한 파일은 컨테이너(root)가 만들어 ubuntu 가 덮어쓸 수 없다.
#      (테스트하는 사람이 서버에서 직접 등록해도 문제가 없게 한다)
#   2) 양쪽 삭제 전파
#      rsync 는 삭제를 옮기지 않는다. --delete 를 쓰면 반대로 "저쪽에서만 등록한
#      파일" 이 지워진다. 그래서 백엔드가 남긴 삭제 대장(.deleted.log)만 지운다.
#      삭제를 전송보다 **먼저** 처리해야 지운 파일이 되돌아오지 않는다.
#   3) 파일 전송 (방향은 아래 옵션)
#   4) 양쪽 개수 검증
#
# 사용법:
#   scripts/sync-uploads.sh                 로컬 → 서버 (기본)
#   scripts/sync-uploads.sh --pull          서버 → 로컬
#   scripts/sync-uploads.sh --both          양방향 (합집합)
#   scripts/sync-uploads.sh --both --dry-run   무엇이 오갈지만 확인
#
# 서버·키를 바꾸려면 환경변수로:
#   ACTORA_SERVER=ubuntu@1.2.3.4 ACTORA_SSH_KEY=~/.ssh/other.pem scripts/sync-uploads.sh
#
set -euo pipefail

SERVER="${ACTORA_SERVER:-ubuntu@3.35.101.121}"
KEY="${ACTORA_SSH_KEY:-$HOME/.ssh/lightsail-seoul.pem}"
REMOTE="/app/actora/backend/uploads"
LOCAL="backend/uploads"
LOG_NAME=".deleted.log"

MODE="push"
DRY=""

usage() {
  sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY="--dry-run" ;;
    --push)    MODE="push" ;;
    --pull)    MODE="pull" ;;
    --both)    MODE="both" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "알 수 없는 옵션: $arg (--help 로 사용법 확인)" >&2; exit 1 ;;
  esac
done

# ── 사전 확인 ────────────────────────────────────────────────
[ -d "$LOCAL" ] || { echo "✗ $LOCAL 이 없습니다. 프로젝트 루트에서 실행하세요." >&2; exit 1; }
[ -f "$KEY" ]   || { echo "✗ SSH 키가 없습니다: $KEY" >&2; exit 1; }
SSH="ssh -i $KEY"

case "$MODE" in
  push) DIR_LABEL="로컬 → 서버" ;;
  pull) DIR_LABEL="서버 → 로컬" ;;
  both) DIR_LABEL="양방향" ;;
esac
echo "동기화: $DIR_LABEL${DRY:+  (dry-run — 아무것도 변경하지 않습니다)}"

# ── 경로 안전성 검사 ────────────────────────────────────────
# 대장에는 uploads 기준 상대 경로만 들어와야 한다
safe_key() {
  case "$1" in
    "" | *..* | /*) return 1 ;;
    *) return 0 ;;
  esac
}

# ── 1) 서버 파일 소유권 정리 ─────────────────────────────────
echo
echo "▶ 1/4  서버 파일 소유권 정리"
if [ -n "$DRY" ]; then
  echo "  [dry-run] sudo chown -R ubuntu:ubuntu $REMOTE"
elif $SSH "$SERVER" "sudo chown -R ubuntu:ubuntu $REMOTE" 2>/dev/null; then
  echo "  완료"
else
  echo "  ! 실패 (sudo 권한 없음?) — Permission denied 가 나면 서버에서 직접 실행하세요:"
  echo "      sudo chown -R ubuntu:ubuntu $REMOTE"
fi

# ── 2) 삭제 전파 (전송보다 먼저) ─────────────────────────────
echo
echo "▶ 2/4  삭제 반영"

# 2-a) 서버에서 지운 것 → 로컬에서 삭제
if [ "$MODE" = "pull" ] || [ "$MODE" = "both" ]; then
  remote_log="$($SSH "$SERVER" "cat '$REMOTE/$LOG_NAME' 2>/dev/null || true")"
  if [ -n "$remote_log" ]; then
    n=0
    while IFS= read -r key; do
      safe_key "$key" || { [ -n "$key" ] && echo "  건너뜀(경로 이상): $key"; continue; }
      if [ -n "$DRY" ]; then
        echo "  [dry-run] 로컬에서 삭제: $key"
      else
        rm -rf -- "$LOCAL/$key"
        echo "  로컬 삭제: $key"
      fi
      n=$((n + 1))
    done <<< "$(printf '%s\n' "$remote_log" | sort -u)"
    echo "  서버→로컬 $n 건"
    [ -z "$DRY" ] && $SSH "$SERVER" ": > '$REMOTE/$LOG_NAME'"
  else
    echo "  서버에서 지운 파일 없음"
  fi
fi

# 2-b) 로컬에서 지운 것 → 서버에서 삭제
if [ "$MODE" = "push" ] || [ "$MODE" = "both" ]; then
  if [ -s "$LOCAL/$LOG_NAME" ]; then
    n=0
    while IFS= read -r key; do
      safe_key "$key" || { [ -n "$key" ] && echo "  건너뜀(경로 이상): $key"; continue; }
      if [ -n "$DRY" ]; then
        echo "  [dry-run] 서버에서 삭제: $key"
      else
        $SSH "$SERVER" "rm -rf -- '$REMOTE/$key'"
        echo "  서버 삭제: $key"
      fi
      n=$((n + 1))
    done < <(sort -u "$LOCAL/$LOG_NAME")
    echo "  로컬→서버 $n 건"
    [ -z "$DRY" ] && : > "$LOCAL/$LOG_NAME"
  else
    echo "  로컬에서 지운 파일 없음"
  fi
fi

# ── 3) 전송 ──────────────────────────────────────────────────
echo
echo "▶ 3/4  파일 전송"
# .deleted.log 는 전송하지 않는다 — 넘어가면 양쪽 삭제 이력이 뒤섞인다
RSYNC_OPTS=(-avzh --progress --exclude "$LOG_NAME" -e "$SSH")
[ -n "$DRY" ] && RSYNC_OPTS+=("$DRY")

if [ "$MODE" = "pull" ] || [ "$MODE" = "both" ]; then
  echo "  ← 서버에서 가져오기"
  rsync "${RSYNC_OPTS[@]}" "$SERVER:$REMOTE/" "$LOCAL/"
fi
if [ "$MODE" = "push" ] || [ "$MODE" = "both" ]; then
  echo "  → 서버로 보내기"
  rsync "${RSYNC_OPTS[@]}" "$LOCAL/" "$SERVER:$REMOTE/"
fi

# ── 4) 검증 ──────────────────────────────────────────────────
echo
echo "▶ 4/4  개수 확인"
lm=$(find "$LOCAL/talent" -name '*.mp4' 2>/dev/null | wc -l | tr -d ' ')
li=$(find "$LOCAL/talent" -path '*/profile/*' -type f 2>/dev/null | wc -l | tr -d ' ')
echo "  로컬  영상 $lm 개 / 프로필 사진 $li 개"
if [ -z "$DRY" ]; then
  $SSH "$SERVER" "
    m=\$(find $REMOTE/talent -name '*.mp4' 2>/dev/null | wc -l | tr -d ' ')
    i=\$(find $REMOTE/talent -path '*/profile/*' -type f 2>/dev/null | wc -l | tr -d ' ')
    echo \"  서버  영상 \$m 개 / 프로필 사진 \$i 개\"
  "
  if [ "$MODE" = "both" ]; then
    echo
    echo "※ --both 이후에는 양쪽 개수가 같아야 합니다. 다르면 전송이 덜 끝난 것입니다."
  else
    echo
    echo "※ 한 방향만 보냈으므로 반대편이 더 많을 수 있습니다 (그쪽에서만 등록한 파일)."
  fi
fi
echo
echo "완료."
