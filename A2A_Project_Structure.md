# A2A Local Project Structure

## Source Files

- `c2_council_runner.py` — C2 runner, turn loop, prompt construction, discovery, transcript writing.
- `protocol.py` — dependency-free protocol helpers for handoff parsing, done detection, adapter-error detection, and routing.
- `codex_agent.py` — Synadia/NATS adapter for Codex CLI.
- `claude_cli_agent.py` — Synadia/NATS adapter for Claude CLI.
- `grok_cli_agent.py` — Synadia/NATS adapter for Grok CLI.
- `run_c2_council.sh` — convenience entrypoint that starts all adapters and then runs the council.
- `test_c2_council_runner.py` — dependency-light unit tests for the protocol layer.

## Docs

- `A2A_C2_Autonomous_Council_Plan.md` — C2 design plan.
- `A2A_Codebase_Brief_For_Agents.md` — briefing used when asking Claude/Grok to explain the codebase.
- `A2A_Codex_Protocol.md` and `A2A_Current_Debug_Status.md` — earlier implementation/debug notes.
- `A2A_Project_Structure.md` — this file.

## Runtime Artifacts

- `logs/council/` — generated council histories and transcripts.
- `memory/` — local project memory summaries intended for future agent handoff.
- `__pycache__/` and `.ruff_cache/` — local tool caches.

## Runtime Requirements

- NATS at `nats://localhost:4222`.
- Python runtime with `nats` and `synadia_ai`, usually:
  `/Users/terng/Downloads/work/p2p-agents/.venv/bin/python`
- Authenticated local CLIs for Codex, Claude, and Grok.

## Current Protocol Contract

- Agents may hand off with exactly one of `@codex`, `@claude-code`, or `@grok`.
- `@claude` is accepted as an alias for `@claude-code`.
- A turn may end the council only by putting `[DONE]` on its own final line.
- Protocol violations are recorded in the transcript header and force fallback routing.
