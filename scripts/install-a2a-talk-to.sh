#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_SOURCE_DIR="$PROJECT_ROOT/skills/a2a-talk-to"

INSTALL_CLI=false
INSTALL_GROK=true
INSTALL_CODEX=true
INSTALL_CLAUDE=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cli)
      INSTALL_CLI=true
      shift
      ;;
    --no-grok)
      INSTALL_GROK=false
      shift
      ;;
    --no-codex)
      INSTALL_CODEX=false
      shift
      ;;
    --no-claude)
      INSTALL_CLAUDE=false
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--cli] [--no-grok] [--no-codex] [--no-claude]"
      exit 0
      ;;
    *)
      echo "Error: Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -d "$SKILL_SOURCE_DIR" ]]; then
  echo "Error: skill source not found: $SKILL_SOURCE_DIR" >&2
  exit 1
fi

install_skill_dir() {
  local root="$1"
  local label="$2"
  local target="$root/a2a-talk-to"

  mkdir -p "$target"
  cp -R "$SKILL_SOURCE_DIR/"* "$target/"
  chmod +x "$target/scripts/a2a_talk_to.py"
  chmod +x "$target/scripts/a2a-talk-to"
  echo "Installed $label skill: $target"
}

echo "=== Installing a2a-talk-to user skill ==="

if [[ "$INSTALL_GROK" == true ]]; then
  install_skill_dir "$HOME/.grok/skills" "Grok"
fi

if [[ "$INSTALL_CODEX" == true ]]; then
  install_skill_dir "$HOME/.codex/skills" "Codex"
fi

if [[ "$INSTALL_CLAUDE" == true ]]; then
  install_skill_dir "$HOME/.claude/skills" "Claude"
fi

if ! grep -q "A2A_LOCAL_ROOT" "$HOME/.zshrc" 2>/dev/null && ! grep -q "A2A_LOCAL_ROOT" "$HOME/.bashrc" 2>/dev/null; then
  echo 'export A2A_LOCAL_ROOT="'"$PROJECT_ROOT"'"' >> "$HOME/.zshrc"
  echo "Added A2A_LOCAL_ROOT to ~/.zshrc"
else
  echo "A2A_LOCAL_ROOT is already configured or will be provided by your shell."
fi

if [[ "$INSTALL_CLI" == true ]]; then
  mkdir -p "$HOME/.local/bin"
  CLI_WRAPPER="$HOME/.local/bin/a2a-talk-to"
  cat > "$CLI_WRAPPER" << EOF
#!/usr/bin/env bash
set -euo pipefail

A2A_LOCAL_ROOT="\${A2A_LOCAL_ROOT:-$PROJECT_ROOT}"
cd "\$A2A_LOCAL_ROOT"
exec uv run python "\$A2A_LOCAL_ROOT/skills/a2a-talk-to/scripts/a2a_talk_to.py" "\$@"
EOF
  chmod +x "$CLI_WRAPPER"
  echo "Installed CLI: $CLI_WRAPPER"
fi

echo
echo "Done. Restart agent sessions so they reload user skills."
