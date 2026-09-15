#!/bin/bash
# BlockTroll 추론 서버 (launchd 진입점)
#
# - uvicorn을 127.0.0.1에만 바인드한다. 외부 노출은 `tailscale serve`가 담당하며
#   이 프로세스 자체는 절대 0.0.0.0을 듣지 않는다.
# - stdout/stderr 전부를 타임스탬프 붙여 로그 파일에 append 한다.
set -uo pipefail

REPO="/Users/jinwoong_kim/Projects/BlockTroll"
VENV_PY="$REPO/.venv/bin/python"
LOG_DIR="$HOME/Library/Logs/BlockTroll"
LOG_FILE="$LOG_DIR/agent.log"
MAX_LOG_BYTES=$((20 * 1024 * 1024))   # 20MB 넘으면 1회 롤오버

# Tailscale 인터페이스 IP에만 바인드한다. 0.0.0.0은 절대 쓰지 않는다 —
# 이 주소는 타일넷 안에서만 도달 가능하고 공개 인터넷에는 노출되지 않는다.
# 부팅 직후 Tailscale이 아직 안 올라왔으면 bind가 실패하는데, launchd KeepAlive가
# ThrottleInterval(10초)마다 재시도하므로 결국 붙는다.
HOST="${BLOCKTROLL_HOST:-100.96.86.10}"
PORT="${BLOCKTROLL_PORT:-8787}"

mkdir -p "$LOG_DIR"

# 단순 사이즈 기반 롤오버 (launchd가 재시작할 때마다 확인)
if [ -f "$LOG_FILE" ]; then
  SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt "$MAX_LOG_BYTES" ]; then
    mv -f "$LOG_FILE" "$LOG_FILE.1"
  fi
fi

# 이 시점 이후의 모든 출력에 타임스탬프를 붙인다.
exec > >("$VENV_PY" -u "$REPO/scripts/ts_log.py" >> "$LOG_FILE") 2>&1

echo "[run_server] starting: host=$HOST port=$PORT repo=$REPO"
echo "[run_server] python: $($VENV_PY -V 2>&1)"

cd "$REPO" || { echo "[run_server] FATAL: cannot cd to $REPO"; exit 1; }

if [ ! -x "$VENV_PY" ]; then
  echo "[run_server] FATAL: venv python not found at $VENV_PY"
  exit 1
fi

exec "$VENV_PY" -u -m uvicorn blocktroll_agent.app:app \
  --host "$HOST" \
  --port "$PORT" \
  --log-level info
