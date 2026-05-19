# Agent Community Protocol

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-early--development-orange)

A lightweight, deterministic **multi-agent council** protocol for AI coding agents
(Codex, Claude Code, Grok, and others) running over NATS using the Synadia Agent Protocol.

This repository contains:

- The core **protocol rules** for safe agent handoff, termination, and violation handling
- Reference **CLI adapters** that turn local agent CLIs into NATS peers
- A **council runner** that orchestrates turn-based collaboration with bounded execution

The goal is to enable reliable, auditable collaboration between heterogeneous AI agents on the same machine or across a local NATS cluster.

## Core Ideas

Agents communicate by sending prompts to each other over NATS using stable subjects:

```
agents.prompt.<agent>.<owner>.<session>
```

A **council** is a turn-based conversation where each agent must explicitly hand off to another agent (or terminate with `[DONE]`). The runner enforces strict rules so the collaboration stays on track.

### Key Guarantees

- Only the **final standalone line** `[DONE]` ends a council
- Self-handoff and mentioning multiple different agents are **protocol violations**
- Violating turns lose the right to choose the next speaker (deterministic fallback rotation kicks in)
- All protocol decisions are logged and auditable

## Architecture

Two clean layers:

| Layer                  | Responsibility                              | Key Files                          |
|------------------------|---------------------------------------------|------------------------------------|
| **Protocol**           | Handoff rules, violation detection, `[DONE]` | `protocol.py`, `test_c2_council_runner.py` |
| **Runtime**            | NATS adapters + council orchestration       | `*_agent.py`, `c2_council_runner.py`, `scripts/run_c2_council.sh` |

**Adapters** turn local CLIs (`claude -p`, `codex exec`, `grok -p`) into proper NATS `AgentService` peers that speak the protocol.

**Runner** handles discovery, prompt construction with rolling history, handoff resolution, and persistent transcripts.

## Installation

```bash
git clone https://github.com/terngphrp/agent_community_protocal.git
cd agent_community_protocal
```

### Protocol-only (no NATS needed)

The core protocol can be used immediately:

```bash
python -m unittest -v test_c2_council_runner.py
```

### Full Runtime (with NATS adapters)

```bash
pip install nats-py synadia-ai
```

> This project uses modern packaging (`pyproject.toml`). A future version may be published on PyPI.

## Dependencies

| Layer              | Dependencies                  | Notes |
|--------------------|-------------------------------|-------|
| **Core Protocol**  | None                          | `protocol.py` + tests run anywhere |
| **Runtime Adapters** | `nats-py`, `synadia-ai`     | Only needed when running agents over NATS |
| **Development**    | `ruff`, `pytest` (optional)   | See `pyproject.toml` |

## Requirements

- NATS server running (`nats://localhost:4222` by default)
- Python 3.10+
- Authenticated local CLIs you want to expose (`claude`, `codex`, `grok`, etc.)

## Quick Start

For a complete walkthrough (including how to run with **only 1 or 2 agents**), see:

→ **[Getting Started Guide](docs/guides/getting-started.md)**

```bash
# Ensure NATS is running and your agent CLIs are authenticated
scripts/run_c2_council.sh "Design a new feature using the agent protocol" --max-rounds 8
```

The script starts the three reference adapters, runs the council, and cleans up on exit.

### Common Environment Overrides

```bash
# Different owner + session (recommended)
OWNER=alice SESSION=feature-review ./scripts/run_c2_council.sh "..." --max-rounds 6

# Use a specific Python interpreter
PYTHON_BIN=python3 ./scripts/run_c2_council.sh "..."

# Custom NATS URL
NATS_URL=nats://192.168.1.50:4222 ./scripts/run_c2_council.sh "..."
```

## Protocol Rules (Contract)

| Rule                        | Behavior                                                                 |
|----------------------------|--------------------------------------------------------------------------|
| **Handoff**                | Must mention exactly one of `@codex`, `@claude-code`, `@grok` (or `@claude`) |
| **Termination**            | Only a standalone final line `[DONE]` ends the council                   |
| **Self-handoff**           | Forbidden — treated as protocol violation                                |
| **Multiple targets**       | Forbidden — violation                                                    |
| **Violation consequence**  | The violating turn loses steering rights; runner falls back to rotation  |
| **Adapter errors**         | Treated as violations and cannot terminate the council                   |

## Running Adapters Manually

If you want to start adapters individually (useful for debugging or custom setups):

```bash
python codex_agent.py   --workspace "$PWD" --sandbox read-only
python claude_cli_agent.py --workspace "$PWD"
python grok_cli_agent.py --workspace "$PWD"
```

Then drive the council yourself:

```bash
python c2_council_runner.py "Your topic here" --max-rounds 6 --owner local --session demo
```

## Development

```bash
# Run the dependency-free protocol tests
python -m unittest -v test_c2_council_runner.py

# Quick syntax check across the project
python -m py_compile protocol.py c2_council_runner.py \
    codex_agent.py claude_cli_agent.py grok_cli_agent.py
```

## Project Layout

```
pyproject.toml              # Modern Python packaging metadata
protocol.py                 # Core protocol (zero dependencies)
c2_council_runner.py        # Council orchestrator + NATS integration
*_agent.py                  # Reference NATS adapters
scripts/run_c2_council.sh   # Launcher script
test_c2_council_runner.py   # Protocol tests
CONTRIBUTING.md
docs/
  PROTOCOL.md               # Core protocol specification (draft)
  guides/
    codex-adapter.md        # Design notes for Codex adapter
    project-structure.md    # Historical project layout
  research/                 # Early NATS/MCP exploration notes
  archive/                  # Old internal documents
```

See:
- `docs/guides/getting-started.md` (including how to run with 1-2 agents)
- `scripts/discover_agents.py --help` (auto-detect + health check live agents)
- `docs/PROTOCOL.md` for the specification

## Roadmap & Community

This is the reference implementation of the **Agent Community Protocol**.

Current strengths:
- Strong, enforceable handoff rules
- Excellent test coverage on the protocol layer
- Works today with real Codex, Claude Code, and Grok CLIs

Areas where we want contributions:
- Structured handoff metadata (reduce reliance on LLM formatting)
- Additional adapters (`aider`, `opencode`, custom agents)
- Durable memory backends (NATS KV, SQLite, etc.)
- Formal protocol specification + interoperability test suite

Pull requests, new adapters, and discussions are extremely welcome.

---

**Ready to collaborate with multiple AI agents in a safe, auditable way?**  
Start a council and let them hand off to each other.
