#!/bin/bash
set -e

echo "=== Agent Community Protocol Docker Environment ==="

# Add common macOS host binary locations to PATH so we can call claude, codex, grok from host
export PATH="/host-bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Also allow calling binaries from user's home (common for user-installed tools)
if [ -d "/host-home/.local/bin" ]; then
    export PATH="/host-home/.local/bin:$PATH"
fi

echo "PATH configured to prefer host binaries."
echo "You can now call 'claude', 'codex', 'grok' if they exist on the host."

exec "$@"