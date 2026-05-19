# A2A Local

Local C2 multi-agent council for Codex, Claude, and Grok over NATS using the
Synadia Agent Protocol.

This project exposes local CLI tools as A2A peers, then runs a lightweight
council loop where agents hand off turns with mentions such as `@grok` or
`@claude-code`.

## What It Does

- Registers Codex, Claude, and Grok as local NATS prompt agents.
- Runs a semi-autonomous C2 council with bounded turns and light memory.
- Keeps transcript and JSON history files for each council run.
- Enforces a small protocol for handoffs, termination, and violations.
- Provides dependency-light unit tests for the protocol layer.

## Architecture

There are two layers:

1. CLI-backed NATS adapters
2. C2 council runner

Adapters:

- `codex_agent.py` registers `agents.prompt.codex.<owner>.<session>`.
- `claude_cli_agent.py` registers `agents.prompt.claude-code.<owner>.<session>`.
- `grok_cli_agent.py` registers `agents.prompt.grok.<owner>.<session>`.

Runner:

- `c2_council_runner.py` discovers agents on NATS.
- It sends role-aware prompts with recent history.
- It reads handoff intent from mentions.
- It writes logs to `logs/council/`.
- It stops on max rounds or a valid final-line `[DONE]`.

Protocol helpers live in `protocol.py` so they can be tested without importing
NATS or Synadia dependencies.

## Requirements

- NATS running at `nats://localhost:4222`
- Python with `nats` and `synadia_ai`
- Authenticated local CLIs:
  - `codex`
  - `claude`
  - `grok`

The known working Python runtime is:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python
```

System Python can run the protocol tests, but not the NATS runner unless the
required packages are installed.

## Quick Start

Run the full council stack:

```bash
./run_c2_council.sh "AI + Human ควรเป็นอย่างไรในอนาคต" --max-rounds 8
```

The script starts all three adapters, waits briefly, then launches the runner.
It also stops the adapters when the runner exits.

Useful environment overrides:

```bash
OWNER=terng SESSION=collab NATS_URL=nats://localhost:4222 ./run_c2_council.sh
PYTHON_BIN=/path/to/python ./run_c2_council.sh
```

## Manual Run

Start adapters in separate terminals:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python codex_agent.py --owner terng --session-name collab --workspace "$PWD" --sandbox read-only
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python claude_cli_agent.py --owner terng --session-name collab --workspace "$PWD"
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python grok_cli_agent.py --owner terng --session-name collab --workspace "$PWD"
```

Then run the council:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python c2_council_runner.py \
  "Review this codebase and propose concrete fixes" \
  --owner terng \
  --session collab \
  --max-rounds 6
```

## Protocol Contract

- Valid handoff mentions: `@codex`, `@claude-code`, `@grok`
- Alias: `@claude` maps to `@claude-code`
- A council may end only when `[DONE]` is the final standalone line.
- Adapter error responses are protocol violations.
- Self-handoff mentions are protocol violations.
- Multiple unique handoff targets are protocol violations.
- A violating turn cannot steer the next speaker.
- Violations are written inline in transcript round headers.

## Logs And Memory

Generated council artifacts are stored under:

```text
logs/council/
```

Default runner output uses timestamped files:

```text
<run-id>_history.json
<run-id>_transcript.md
```

Use a stable run id:

```bash
./run_c2_council.sh "topic" --run-id code-review-001
```

Local project memory lives in:

```text
memory/a2a_local_status.md
```

## Tests

Run protocol tests with system Python:

```bash
python3 -m unittest -v test_c2_council_runner.py
```

Run with the project runtime:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python -m unittest -v test_c2_council_runner.py
```

Compile all main files:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python -m py_compile \
  protocol.py \
  c2_council_runner.py \
  codex_agent.py \
  claude_cli_agent.py \
  grok_cli_agent.py \
  test_c2_council_runner.py
```

## Project Map

- `protocol.py` — dependency-free handoff and protocol helpers.
- `c2_council_runner.py` — C2 turn loop, NATS discovery, prompt construction, log writing.
- `codex_agent.py` — Codex CLI adapter.
- `claude_cli_agent.py` — Claude CLI adapter.
- `grok_cli_agent.py` — Grok CLI adapter.
- `run_c2_council.sh` — convenience launcher.
- `test_c2_council_runner.py` — protocol unit tests.
- `A2A_Project_Structure.md` — detailed file map.
- `A2A_C2_Autonomous_Council_Plan.md` — design plan.

## Current Status

The system has passed live local tests with the flow:

```text
Codex -> Claude -> Grok
```

Recent hardening added:

- Strict final-line `[DONE]` handling.
- Structured `HandoffResult`.
- Self-mention and multiple-target violation detection.
- Dependency-free protocol tests.
- Timestamped council logs.

Known next improvements:

- Add a structured handoff footer or metadata channel.
- Move durable memory to NATS KV or SQLite.
- Consider process-group cleanup for CLI adapters if a CLI starts detached child processes.
