#!/usr/bin/env bash
#
# 개발 서버 기동 래퍼 — 포트를 확실히 비우고 하나만 띄운다.
#
# 왜 필요한가
# ─────────────────────────────────────────────────────────────
# `[Errno 48] Address already in use` 가 반복해서 났다. 원인이 두 겹이다.
#
#  1) uvicorn --reload 는 포트를 잡는 프로세스가 **두 개**다
#     (reloader 부모 + 워커 자식). 하나만 죽이면 남은 쪽이 포트를 계속 잡는다.
#     pkill -f 'uvicorn src.main:app' 은 더 나쁘다 — -f 는 명령줄 문자열로 찾으므로
#     이 스크립트를 실행한 쉘까지 죽인다.
#
#  2) 태스크가 **동시에 두 번** 시작될 수 있다 (VS Code 의 folderOpen 자동 실행 +
#     사용자의 수동 실행). 둘 다 "포트 비었음" 을 확인하고 통과한 뒤 거의 같은 순간에
#     bind 하면 하나가 Errno 48 을 받는다. 포트 확인만으로는 막을 수 없다.
#
# 그래서 기동 구간을 잠금(mkdir 은 원자적)으로 감싸고, 잠금 안에서 포트를 비운 뒤
# 실제로 풀렸는지 확인하고 exec 한다. exec 로 쉘을 대체하므로 VS Code 가 태스크를
# 멈출 때 시그널이 서버에 직접 간다 (중간 쉘만 죽고 서버가 남는 일을 막는다).
# 잠금 해제는 곁가지 서브셸이 "포트가 잡혔는지" 를 보고 처리한다.
#
# 사용법:
#   scripts/dev-serve.sh <포트> <실행할 명령...>
#
#   scripts/dev-serve.sh 8000 ./backend/.venv/bin/python -m uvicorn src.main:app --reload ...
#   scripts/dev-serve.sh 3000 npm run dev
#
set -uo pipefail

PORT="${1:?사용법: dev-serve.sh <포트> <명령...>}"
shift
[ "$#" -gt 0 ] || { echo "✗ 실행할 명령이 없습니다" >&2; exit 1; }

LOCK="${TMPDIR:-/tmp}/actora-dev-$PORT.lock"
LOCK_WAIT=60      # 0.25초 × 60 = 최대 15초 대기
PORT_WAIT=40      # 0.25초 × 40 = 최대 10초 대기
STALE_MIN=2       # 이 시간(분)보다 오래된 잠금은 버려진 것으로 본다

listeners() { lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null; }

# ── 1) 버려진 잠금 정리 ──────────────────────────────────────
# 기동 도중 프로세스가 죽으면 잠금이 남는다. 시간으로 판단해 치운다.
# (없으면 매번 15초를 헛되게 기다린다)
if [ -d "$LOCK" ] && [ -n "$(find "$LOCK" -maxdepth 0 -mmin +$STALE_MIN 2>/dev/null)" ]; then
  echo "· 오래된 잠금 제거: $LOCK"
  rmdir "$LOCK" 2>/dev/null || true
fi

# ── 2) 잠금 획득 ────────────────────────────────────────────
# mkdir 은 원자적이라 두 프로세스가 동시에 성공할 수 없다.
locked=0
for _ in $(seq $LOCK_WAIT); do
  if mkdir "$LOCK" 2>/dev/null; then locked=1; break; fi
  sleep 0.25
done
if [ "$locked" = 0 ]; then
  # 잠금을 못 얻어도 진행한다 — 영구 대기보다 낫다
  echo "! 잠금 대기 시간 초과 — 그대로 진행합니다 ($LOCK)"
fi
# 아래 어디서 끝나든 잠금을 놓는다 (exec 전에 직접 지우지만, 중간에 죽는 경우 대비)
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT INT TERM

# ── 3) 포트 비우기 ──────────────────────────────────────────
pids="$(listeners)"
if [ -n "$pids" ]; then
  echo "· 포트 $PORT 사용 중 → 종료: $(echo "$pids" | tr '\n' ' ')"
  # SIGKILL — uvicorn --reload 의 부모·자식이 graceful shutdown 하는 동안
  # 포트를 계속 잡고 있어 다음 기동이 실패한다
  echo "$pids" | xargs kill -9 2>/dev/null || true
fi

# 실제로 풀렸는지 확인한다 (고정 sleep 은 짧으면 실패, 길면 낭비)
for _ in $(seq $PORT_WAIT); do
  [ -z "$(listeners)" ] && break
  sleep 0.25
done
if [ -n "$(listeners)" ]; then
  echo "✗ 포트 $PORT 를 비우지 못했습니다: $(listeners | tr '\n' ' ')" >&2
  echo "  다른 사용자나 프로세스가 잡고 있는지 확인하세요: lsof -iTCP:$PORT -sTCP:LISTEN" >&2
  exit 1
fi

# ── 4) 기동 ────────────────────────────────────────────────
# 잠금은 **서버가 실제로 포트를 잡은 뒤에** 놓아야 한다.
#
# 여기서 먼저 놓으면 안 된다. 뒤이어 시작한 인스턴스가 잠금을 얻는 순간
# 이 서버는 아직 bind 하기 전이라 "포트 비었음" 으로 보이고, 그대로 통과해
# 같은 포트에 bind 를 시도한다 — 그게 Errno 48 의 실제 원인이었다.
# (실측으로 확인: 잠금을 exec 앞에서 놓았을 때 경쟁이 그대로 재현됐다)
#
# 그래서 잠금 해제를 **곁가지 서브셸**에 맡기고 본체는 exec 로 넘어간다.
# 이렇게 하면
#   - 잠금은 서버가 포트를 잡은 뒤에 풀린다 (경쟁 방지)
#   - 이 쉘이 서버로 대체되므로 시그널이 서버에 직접 간다
#   - 쉘이 남지 않아 서버가 죽을 때 'Killed: 9 "$@"' 같은 잡 제어 메시지가
#     터미널에 찍히지 않는다
(
  for _ in $(seq $PORT_WAIT); do
    [ -n "$(listeners)" ] && break
    sleep 0.25
  done
  rmdir "$LOCK" 2>/dev/null || true
) &

trap - EXIT INT TERM
echo "· 기동: $*"
exec "$@"
