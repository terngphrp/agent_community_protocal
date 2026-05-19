#!/usr/bin/env bash
set -euo pipefail

# Portable launcher for the C2 council (Codex + Claude + Grok over NATS)
# Usage examples:
#   ./scripts/run_c2_council.sh "Your topic here" --max-rounds 6
#   PYTHON_BIN=python3 OWNER=alice SESSION=demo ./scripts/run_c2_council.sh "..."

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve Python interpreter (order: env var > uv > python3 > python)
if [[ -n "${PYTHON_BIN:-}" ]]; then
  PY="$PYTHON_BIN"
elif command -v uv >/dev/null 2>&1 && [[ -f "pyproject.toml" || -f "uv.lock" ]]; then
  PY="uv run python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

OWNER="${OWNER:-${USER:-local}}"
SESSION="${SESSION:-collab}"
URL="${NATS_URL:-nats://localhost:4222}"

# Optional: auto-discover before launching (pass --discover as first arg or use env)
if [[ "${1:-}" == "--discover" ]]; then
  shift
  echo "=== Auto-discovering live agents ==="
  "$PY" "$ROOT/discover_agents.py" --owner "$OWNER" --session "$SESSION" --url "$URL" || true
  echo "===================================="
fi

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
