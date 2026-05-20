# A2A Local - Current Status

**Last Updated:** 2026-05-20 (after reliable `a2a-consult` direct-call work)

## Project Overview

This repository implements a **C2 (Command & Control) multi-agent council** for AI coding agents (Codex, Claude Code, Grok, and others) over NATS using the Synadia Agent Protocol.

Key components:
- Lightweight protocol for safe agent handoff (`protocol.py`)
- Reference CLI adapters (`*_agent.py`)
- Council orchestrator (`c2_council_runner.py`)
- Auto-discovery + health check tool (`scripts/discover_agents.py`)
- Grok skill / CLI wrapper for direct cross-agent consultation (`skills/a2a-consult/`)
- Docker support for reproducibility + host CLI access

## Recent Major Changes

- **Reliable `a2a-consult` Direct Consultation**
  - Commit: `4986fa3 Make a2a-consult reliable for direct agent calls`
  - Default behavior is now direct single-target consultation instead of council rotation
  - Added explicit `--council` mode for multi-agent runner usage
  - Fixed default session alignment (`collab`) and forwards `--nats-url`, `--timeout`, and `--discover-wait`
  - Added preflight checks for workspace, dependencies, NATS connectivity, and target discovery
  - Added `--json` output for machine-readable Grok/CLI integration
  - Workspace is included in the remote prompt; council runner is no longer called with unsupported `--workspace`
  - Added unit tests in `test_a2a_consult.py`

- **Install + Packaging Fixes**
  - Added `scripts/install-a2a-consult.sh`, `Makefile`, and install guide
  - Fixed CLI wrapper path to prefer `~/.grok/skills/a2a-consult/...` and fall back to `$A2A_LOCAL_ROOT/skills/...`
  - Updated Python requirement to `>=3.11` because `synadia-ai-agents` requires Python 3.11+

- **Docker Support (Option A - Host .venv Mount)**
  - `docker/` folder with Dockerfile, docker-compose.yml, entrypoint.sh
  - NATS exposed on host port **4223** (to avoid conflict)
  - Mounts host `.venv` so `synadia-ai-agents` and `nats-py` work immediately
  - Volume mounts for host home + binaries so `claude`, `codex`, `grok` on the host can be called from inside the container

- **Agent Discovery & Health Check**
  - `scripts/discover_agents.py` with `--ping-pong`, `--json`, `--only-healthy` flags
  - Can auto-detect which agents are live and verify they respond

- **Project Structure Cleanup**
  - Moved research docs to `docs/research/`
  - Design notes to `docs/guides/`
  - `scripts/` folder for launcher and tools
  - Clean `docs/PROTOCOL.md` as the canonical spec

- **Getting Started Guide**
  - `docs/guides/getting-started.md` with clear instructions for running with 1, 2, or 3 agents

- **Script Fixes**
  - `run_c2_council.sh` now correctly handles paths and Python selection (including `uv run python`)

## Current Recommended Ways to Run

### Local (Fastest for development)
```bash
uv sync

PYTHON_BIN=python3 ./scripts/run_c2_council.sh "Your topic" --max-rounds 6
```

### Direct A2A Consultation
```bash
# Start an adapter in the same owner/session/workspace first.
.venv/bin/python codex_agent.py --owner "$USER" --session-name collab --workspace "$PWD"

# Then call the target directly.
.venv/bin/python skills/a2a-consult/scripts/a2a_consult.py \
  codex "Review this repo and suggest the next implementation step" \
  --workspace "$PWD" \
  --json
```

### Docker (Reproducible + Host CLI support)
```bash
# 1. Prepare host venv
python3 -m venv .venv
source .venv/bin/activate
pip install nats-py synadia-ai-agents

# 2. Run Docker
cd docker
docker compose up --build
```

NATS on host → `localhost:4223`

## Key Files

- `protocol.py` — Core handoff & violation logic (zero dependencies)
- `scripts/discover_agents.py` — Live agent discovery + ping-pong test
- `docker/docker-compose.yml` — Current Docker setup (host venv mount)
- `docs/PROTOCOL.md` — Emerging specification
- `skills/a2a-consult/scripts/a2a_consult.py` — Direct consult CLI / Grok skill entrypoint
- `scripts/install-a2a-consult.sh` — Skill and CLI installer
- `docs/guides/getting-started.md` — Best starting point for new users
- `docs/guides/install-a2a-consult-skill.md` — Grok skill install guide

## Known Limitations / Next Steps

- `synadia-ai-agents` is required at runtime (not optional)
- Current council runner is still 3-agent oriented; use `a2a-consult` default direct mode for single-agent work
- Docker host CLI calling works via volume mounts but may need PATH tweaks per macOS setup
- Adapters must be started in the correct workspace for real file edits; `a2a-consult` passes workspace context but cannot relocate an already-running adapter process

## Memory Notes

- This project started as internal debugging for Grok ↔ Claude ↔ Codex over NATS
- Evolved into a reusable "Agent Community Protocol" reference implementation
- Focus areas: safe handoff, partial agent support, discoverability, Docker reproducibility
- Live verification on 2026-05-20 found `codex` and `grok` healthy in session `collab`; direct JSON consult and council smoke tests passed before push

---
*Keep this file updated after major changes.*
