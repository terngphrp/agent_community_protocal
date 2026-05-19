# Project Structure

## Source Files

- `c2_council_runner.py` — Council orchestrator: turn loop, prompt construction, NATS discovery, transcript writing.
- `protocol.py` — Pure-Python protocol helpers (handoff parsing, `[DONE]` detection, violation rules). No NATS dependency.
- `codex_agent.py` — NATS adapter for the Codex CLI.
- `claude_cli_agent.py` — NATS adapter for the Claude CLI (`claude -p`).
- `grok_cli_agent.py` — NATS adapter for the Grok CLI.
- `scripts/run_c2_council.sh` — One-command launcher that starts all three adapters + the council runner.
- `test_c2_council_runner.py` — Unit tests for the protocol layer (runs without NATS).

## Documentation

- `README.md` — Main project documentation and quick start.
- `docs/PROTOCOL.md` — Core specification (work in progress)
- `docs/guides/` — Implementation and design notes
- `docs/research/` — Early exploration notes on NATS and MCP integration
- `docs/archive/` — Historical internal documents

## Generated / Runtime

- `logs/council/` — Council run transcripts and history (gitignored except README).
- `__pycache__/`, `.ruff_cache/` — Local caches (gitignored).

## Requirements

- NATS server (`nats://localhost:4222` by default)
- Python 3.10+
- `nats` + `synadia_ai` packages (only needed for runtime adapters)
- Local authenticated CLIs (`claude`, `codex`, `grok`, etc.)

## Protocol Rules (Summary)

- Agents hand off using exactly one of: `@codex`, `@claude-code`, `@grok`
- `@claude` is accepted as an alias for `@claude-code`
- Only a standalone final line `[DONE]` terminates the council
- Self-handoff and multi-target mentions are protocol violations
- Violations cause the turn to lose steering rights (fallback rotation is used)
