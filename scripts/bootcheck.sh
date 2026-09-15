#!/bin/bash
# 재부팅 후 자동 기동을 증명하기 위한 1회성 기록기.
# LaunchAgent(RunAtLoad, KeepAlive 없음)로 로그인마다 한 번 실행된다.
#
# 기록: 실제 부팅 시각, 이 스크립트 실행 시각, Tailscale이 올라온 시각,
#       /health가 처음 성공한 시각, 그때의 PID/RSS.
set -uo pipefail

LOG="$HOME/Library/Logs/BlockTroll/bootcheck.log"
API="http://100.96.86.10:8787"
TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
mkdir -p "$(dirname "$LOG")"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# 형식: { sec = 1787417465, usec = 86257 } Sun Aug 23 01:51:05 2026
# ".*sec = " 는 greedy라 usec 값을 잡으므로 앞을 고정해서 매칭한다.
BOOT_EPOCH=$(sysctl -n kern.boottime | sed -n 's/^{ sec = \([0-9][0-9]*\).*/\1/p')
BOOT_HUMAN=$(date -r "$BOOT_EPOCH" '+%Y-%m-%d %H:%M:%S')
START_EPOCH=$(date +%s)

log "===== bootcheck 시작 ====="
log "실제 부팅 시각      : $BOOT_HUMAN"
log "bootcheck 실행 시각 : $(date '+%Y-%m-%d %H:%M:%S')  (부팅 +$((START_EPOCH - BOOT_EPOCH))초)"

# Tailscale 인터페이스가 올라올 때까지
TS_OK=""
for i in $(seq 1 120); do
  if ifconfig 2>/dev/null | grep -q "inet 100.96.86.10"; then
    TS_OK=$i
    log "Tailscale 인터페이스: 부팅 +$(( $(date +%s) - BOOT_EPOCH ))초 (대기 ${i}초)"
    break
  fi
  sleep 1
done
[ -z "$TS_OK" ] && log "Tailscale 인터페이스: 120초 내 미확인 (실패)"

# /health가 처음 성공할 때까지
HEALTH_OK=""
for i in $(seq 1 180); do
  if curl -sf --max-time 2 "$API/health" >/dev/null 2>&1; then
    HEALTH_OK=$i
    log "서버 최초 응답      : 부팅 +$(( $(date +%s) - BOOT_EPOCH ))초 (대기 ${i}초)"
    break
  fi
  sleep 1
done

if [ -z "$HEALTH_OK" ]; then
  log "결과: 실패 — 180초 내 서버가 응답하지 않음"
  log "launchd 상태: $(launchctl print gui/$(id -u)/com.blocktroll.agent 2>&1 | grep -E 'state =|last exit' | tr '\n' ' ')"
  log "===== bootcheck 끝 ====="
  exit 1
fi

PID=$(pgrep -f "uvicorn blocktroll_agent" | head -1)
RSS_KB=$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ')
log "uvicorn PID         : $PID"
log "RSS                 : $(( ${RSS_KB:-0} / 1024 )) MB"
log "바인딩              : $(lsof -nP -iTCP:8787 -sTCP:LISTEN 2>/dev/null | tail -1 | awk '{print $9}')"
log "launchd 속성        : $(launchctl print gui/$(id -u)/com.blocktroll.agent 2>&1 | grep 'properties' | tr -s ' ')"
log "health              : $(curl -s --max-time 3 "$API/health")"
log "classify 테스트     : $(curl -s --max-time 5 -X POST "$API/classify" -H 'Content-Type: application/json' -d '{"texts":["꺼져 이 병신아"],"platform":"bootcheck"}')"
log "결과: 성공 — 재부팅 후 자동 기동 확인됨"
log "===== bootcheck 끝 ====="
