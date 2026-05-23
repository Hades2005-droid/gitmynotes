#!/bin/bash
# Unattended automation loop for notes + agent bundle refresh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RUNTIME_DIR="$HOME/.gitmynotes-automation"
LOG_DIR="$HOME/Documents/framework-demos/automation-logs"
PID_FILE="$RUNTIME_DIR/away_mode.pid"
LOG_FILE="$LOG_DIR/away_mode.log"

INTERVAL_SECONDS="${ECHO_AWAY_INTERVAL_SECONDS:-900}" # default: 15 minutes

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

run_tick() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] [tick] starting"
  (
    cd "$REPO_ROOT"
    python3 export_notes_for_gemini.py
    python3 scripts/build_echo_agent_bundle.py
  )
  echo "[$ts] [tick] complete"
}

run_loop() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] away mode loop active (interval=${INTERVAL_SECONDS}s)"
  while true; do
    run_tick
    sleep "$INTERVAL_SECONDS"
  done
}

start_loop() {
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Away mode already running (PID $(cat "$PID_FILE"))."
    echo "Log: $LOG_FILE"
    exit 0
  fi

  echo "Starting away mode..."
  nohup "$SCRIPT_DIR/away_mode.sh" run-loop >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 1

  if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Away mode started (PID $(cat "$PID_FILE"))."
    echo "Interval: ${INTERVAL_SECONDS}s"
    echo "Log: $LOG_FILE"
  else
    rm -f "$PID_FILE"
    echo "Failed to start away mode."
    exit 1
  fi
}

stop_loop() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "Away mode is not running."
    exit 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    echo "Away mode stopped (PID $pid)."
  else
    echo "Away mode process was not running."
  fi
  rm -f "$PID_FILE"
}

status_loop() {
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Away mode: running (PID $(cat "$PID_FILE"))"
  else
    echo "Away mode: stopped"
  fi
  echo "Interval: ${INTERVAL_SECONDS}s"
  echo "Log: $LOG_FILE"
  if [[ -f "$LOG_FILE" ]]; then
    echo "--- recent log ---"
    tail -n 20 "$LOG_FILE"
  fi
}

usage() {
  cat <<'EOF'
Usage: ./scripts/away_mode.sh <command>

Commands:
  start      Start unattended loop (export notes + refresh bundle)
  stop       Stop unattended loop
  status     Show status and recent log
  run-once   Run one automation cycle now
  run-loop   Internal loop command (used by start)
EOF
}

cmd="${1:-}"
case "$cmd" in
  start)
    start_loop
    ;;
  stop)
    stop_loop
    ;;
  status)
    status_loop
    ;;
  run-once)
    run_tick
    ;;
  run-loop)
    run_loop
    ;;
  *)
    usage
    exit 1
    ;;
esac

