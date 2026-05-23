#!/bin/bash
# Manual full-screen recording for 9-Points / Angela framework demos.
# You control start/stop. Requires macOS Screen Recording permission for Terminal/Cursor.

set -euo pipefail

OUT_DIR="$HOME/Documents/framework-demos"
PID_FILE="$OUT_DIR/.recording.pid"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="$OUT_DIR/framework-demo-$STAMP.mov"

mkdir -p "$OUT_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Recording already running (PID $(cat "$PID_FILE"))."
  echo "Stop it first: ./scripts/stop_framework_recording.sh"
  exit 1
fi

echo "Starting full-screen recording..."
echo "Output: $OUT_FILE"
echo "Stop with: ./scripts/stop_framework_recording.sh"
echo ""

# screencapture -v blocks until interrupted; run in background
screencapture -v "$OUT_FILE" &
echo $! > "$PID_FILE"

sleep 1
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Recording (PID $(cat "$PID_FILE"))."
else
  rm -f "$PID_FILE"
  echo "Failed to start. Grant Screen Recording to Terminal/Cursor:"
  echo "  System Settings → Privacy & Security → Screen Recording"
  exit 1
fi
