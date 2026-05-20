#!/usr/bin/env bash
set -euo pipefail

# Portable launcher for the C2 council (Codex + Claude + Grok over NATS)
# Usage examples:
#   ./scripts/run_c2_council.sh "Your topic here" --max-rounds 6
#   PYTHON_BIN=python3 OWNER=alice SESSION=demo ./scripts/run_c2_council.sh "..."
#
#   # Force using uv
#   PYTHON_BIN="uv run python" ./scripts/run_c2_council.sh "..."

# Get directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Project root is one level above the scripts/ directory
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Resolve Python command (use array to handle "uv run python" correctly)
if [[ -n "${PYTHON_BIN:-}" ]]; then
  PY_CMD=($PYTHON_BIN)
elif command -v uv >/dev/null 2>&1 && [[ -f "$PROJECT_ROOT/pyproject.toml" || -f "$PROJECT_ROOT/uv.lock" ]]; then
  PY_CMD=(uv run python)
elif command -v python3 >/dev/null 2>&1; then
  PY_CMD=(python3)
else
  PY_CMD=(python)
fi

OWNER="${OWNER:-${USER:-local}}"
SESSION="${SESSION:-collab}"
URL="${NATS_URL:-nats://localhost:4222}"

# Optional: auto-discover before launching
if [[ "${1:-}" == "--discover" ]]; then
  shift
  echo "=== Auto-discovering live agents ==="
  "${PY_CMD[@]}" "$PROJECT_ROOT/scripts/discover_agents.py" --owner "$OWNER" --session "$SESSION" --url "$URL" || true
  echo "===================================="
fi

PIDS=()

cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

# All Python files live in the project root, not inside scripts/
"${PY_CMD[@]}" "$PROJECT_ROOT/codex_agent.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session-name "$SESSION" \
  --workspace "$PROJECT_ROOT" \
  --sandbox read-only \
  --timeout 300 &
PIDS+=("$!")

"${PY_CMD[@]}" "$PROJECT_ROOT/claude_cli_agent.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session-name "$SESSION" \
  --workspace "$PROJECT_ROOT" \
  --timeout 300 &
PIDS+=("$!")

"${PY_CMD[@]}" "$PROJECT_ROOT/grok_cli_agent.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session-name "$SESSION" \
  --workspace "$PROJECT_ROOT" \
  --timeout 300 &
PIDS+=("$!")

sleep 3

"${PY_CMD[@]}" "$PROJECT_ROOT/c2_council_runner.py" \
  --url "$URL" \
  --owner "$OWNER" \
  --session "$SESSION" \
  "$@"
