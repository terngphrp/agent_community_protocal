#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PY="/Users/terng/Downloads/work/p2p-agents/.venv/bin/python"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  PY="$PYTHON_BIN"
elif [[ -x "$DEFAULT_PY" ]]; then
  PY="$DEFAULT_PY"
else
  PY="python3"
fi
OWNER="${OWNER:-terng}"
SESSION="${SESSION:-collab}"
URL="${NATS_URL:-nats://localhost:4222}"

PIDS=()

cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

"$PY" "$ROOT/codex_agent.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session-name "$SESSION" \
  --workspace "$ROOT" \
  --sandbox read-only \
  --timeout 300 &
PIDS+=("$!")

"$PY" "$ROOT/claude_cli_agent.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session-name "$SESSION" \
  --workspace "$ROOT" \
  --timeout 300 &
PIDS+=("$!")

"$PY" "$ROOT/grok_cli_agent.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session-name "$SESSION" \
  --workspace "$ROOT" \
  --timeout 300 &
PIDS+=("$!")

sleep 3

"$PY" "$ROOT/c2_council_runner.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session "$SESSION" \
  "$@"
