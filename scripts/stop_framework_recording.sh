#!/bin/bash
# Stop manual framework demo recording started by start_framework_recording.sh

set -euo pipefail

OUT_DIR="$HOME/Documents/framework-demos"
PID_FILE="$OUT_DIR/.recording.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No recording in progress."
  exit 1
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill -INT "$PID" 2>/dev/null || kill "$PID" 2>/dev/null || true
  sleep 2
  echo "Stopped recording (PID $PID)."
else
  echo "Recording process not found."
fi

rm -f "$PID_FILE"

LATEST="$(ls -t "$OUT_DIR"/framework-demo-*.mov 2>/dev/null | head -1 || true)"
if [[ -n "$LATEST" ]]; then
  SIZE="$(du -h "$LATEST" | cut -f1)"
  echo "Saved: $LATEST ($SIZE)"
  open -R "$LATEST"
fi
