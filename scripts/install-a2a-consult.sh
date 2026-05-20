#!/usr/bin/env bash
set -euo pipefail

# =====================================================
# a2a-consult Skill Auto Installer
# =====================================================
# This script installs the a2a-consult Grok skill and
# optionally sets it up as a CLI command (a2a-consult).
#
# Usage:
#   ./scripts/install-a2a-consult.sh
#   ./scripts/install-a2a-consult.sh --cli
#   ./scripts/install-a2a-consult.sh --docker
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Prefer the skill template inside the repo (skills/a2a-consult)
# Fallback to the one in ~/.grok/skills if not found
if [[ -d "$PROJECT_ROOT/skills/a2a-consult" ]]; then
  SKILL_SOURCE_DIR="$PROJECT_ROOT/skills/a2a-consult"
else
  SKILL_SOURCE_DIR="$HOME/.grok/skills/a2a-consult"
fi

SKILL_TARGET_DIR="$HOME/.grok/skills/a2a-consult"

INSTALL_CLI=false
DOCKER_MODE=false
INSTALL_DEPS=false
USE_UV=false
USE_PIP=false

# Parse arguments
SOURCE_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cli)
            INSTALL_CLI=true
            shift
            ;;
        --docker)
            DOCKER_MODE=true
            shift
            ;;
        --install-deps|--deps)
            INSTALL_DEPS=true
            shift
            ;;
        --uv)
            USE_UV=true
            shift
            ;;
        --pip)
            USE_PIP=true
            shift
            ;;
        --source=*)
            SOURCE_DIR="${1#*=}"
            shift
            ;;
        --source)
            if [[ $# -lt 2 ]]; then
                echo "❌ Error: --source requires a directory"
                exit 1
            fi
            shift
            SOURCE_DIR="$1"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--cli] [--docker] [--install-deps] [--uv|--pip] [--source DIR]"
            exit 0
            ;;
        *)
            echo "❌ Error: Unknown option: $1"
            exit 1
            ;;
    esac
done

# Allow custom source directory
if [[ -n "$SOURCE_DIR" && -d "$SOURCE_DIR" ]]; then
    SKILL_SOURCE_DIR="$SOURCE_DIR"
elif [[ -d "$PROJECT_ROOT/skills/a2a-consult" ]]; then
    SKILL_SOURCE_DIR="$PROJECT_ROOT/skills/a2a-consult"
fi

echo "=== Installing a2a-consult Grok Skill ==="
echo

# 1. Check if skill source exists
if [[ ! -d "$SKILL_SOURCE_DIR" ]]; then
    echo "❌ Error: Skill source directory not found at $SKILL_SOURCE_DIR"
    echo "   Please make sure you are running this from the a2a_local repository."
    exit 1
fi

# 2. Create target directory
echo "→ Creating skill directory at $SKILL_TARGET_DIR"
mkdir -p "$SKILL_TARGET_DIR"

# 3. Copy skill files
echo "→ Copying skill files..."
cp -r "$SKILL_SOURCE_DIR/"* "$SKILL_TARGET_DIR/"

# 4. Make the main script executable
chmod +x "$SKILL_TARGET_DIR/scripts/a2a_consult.py"

echo "✅ Skill files copied successfully."

# 5. Install dependencies if requested
if [[ "$INSTALL_DEPS" == true ]]; then
    echo
    echo "→ Installing required Python dependencies (nats-py, synadia-ai-agents)..."
    
    # Determine which tool to use
    INSTALL_CMD=""
    
    if [[ "$USE_PIP" == true ]]; then
        INSTALL_CMD="pip install"
    elif [[ "$USE_UV" == true ]]; then
        INSTALL_CMD="uv pip install"
    else
        # Auto detect
        if command -v uv >/dev/null 2>&1; then
            INSTALL_CMD="uv pip install"
            echo "   Detected uv → using 'uv pip install'"
        elif command -v pip3 >/dev/null 2>&1; then
            INSTALL_CMD="pip3 install"
        elif command -v pip >/dev/null 2>&1; then
            INSTALL_CMD="pip install"
        else
            echo "❌ Error: Neither pip nor uv found. Please install dependencies manually:"
            echo "   pip install nats-py synadia-ai-agents"
            exit 1
        fi
    fi
    
    echo "   Running: $INSTALL_CMD nats-py synadia-ai-agents"
    if $INSTALL_CMD nats-py synadia-ai-agents; then
        echo "✅ Dependencies installed successfully."
    else
        echo "⚠️  Failed to install some dependencies. You may need to install them manually."
    fi
fi

# 7. Set A2A_LOCAL_ROOT environment variable (if not already set)
if ! grep -q "A2A_LOCAL_ROOT" "$HOME/.zshrc" 2>/dev/null && ! grep -q "A2A_LOCAL_ROOT" "$HOME/.bashrc" 2>/dev/null; then
    echo "→ Adding A2A_LOCAL_ROOT to your shell config..."
    echo 'export A2A_LOCAL_ROOT="'"$PROJECT_ROOT"'"' >> "$HOME/.zshrc"
    echo "   (Added to ~/.zshrc)"
    echo "   Please run: source ~/.zshrc"
else
    echo "→ A2A_LOCAL_ROOT already configured or will be set manually."
fi

# 8. Optional: Install as CLI command
if [[ "$INSTALL_CLI" == true ]]; then
    echo
    echo "→ Installing 'a2a-consult' as a global CLI command..."
    
    mkdir -p "$HOME/.local/bin"
    
    CLI_WRAPPER="$HOME/.local/bin/a2a-consult"
    
    cat > "$CLI_WRAPPER" << EOF
#!/usr/bin/env bash
# Wrapper for a2a-consult Grok skill

A2A_LOCAL_ROOT="\${A2A_LOCAL_ROOT:-$PROJECT_ROOT}"
PYTHON_BIN="\${PYTHON_BIN:-python3}"

if [[ -x "\$HOME/.grok/skills/a2a-consult/scripts/a2a_consult.py" ]]; then
  exec "\$PYTHON_BIN" "\$HOME/.grok/skills/a2a-consult/scripts/a2a_consult.py" "\$@"
fi

exec "\$PYTHON_BIN" "\$A2A_LOCAL_ROOT/skills/a2a-consult/scripts/a2a_consult.py" "\$@"
EOF
    
    chmod +x "$CLI_WRAPPER"
    
    echo "✅ CLI installed at $CLI_WRAPPER"
    echo "   Make sure ~/.local/bin is in your PATH."
    echo
    echo "   You can now run:"
    echo "     a2a-consult claude \"help me with this task\" --workspace ."
fi

# 7. Docker mode notice
if [[ "$DOCKER_MODE" == true ]]; then
    echo
    echo "→ Docker mode detected."
    echo "   When using Docker (with host .venv mounted), you can run the skill from inside the container like this:"
    echo
    echo "   docker compose run --rm app /app/.venv/bin/python /app/.grok/skills/a2a-consult/scripts/a2a_consult.py claude \"...\" --workspace /app"
    echo
    echo "   Or create an alias in your host shell for convenience."
fi

echo
echo "✅ Installation complete!"
echo
echo "Next steps:"
echo "  1. Add this to your ~/.zshrc (or ~/.bashrc):"
echo "     export A2A_LOCAL_ROOT=\"$PROJECT_ROOT\""
echo
echo "  2. Restart your Grok session (quit completely and reopen)."
echo
echo "  3. Test the skill:"
echo "     a2a-consult --help"
echo "     OR from Grok: /a2a-consult claude \"...\""
echo

if [[ "$INSTALL_CLI" == false ]]; then
    echo "Tip: Run with --cli to also install the 'a2a-consult' command globally."
fi

echo "Done."
