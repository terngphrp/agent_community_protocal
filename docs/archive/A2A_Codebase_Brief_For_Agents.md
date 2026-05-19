# A2A Local Codebase Brief

This workspace implements a local three-agent A2A prototype using NATS and the
Synadia Agent Protocol. The goal is to let Codex, Claude, and Grok talk to each
other as peers, then let a lightweight C2 council runner coordinate multi-turn
discussion through mentions.

## Current Architecture

There are two layers:

1. CLI-backed NATS adapters
2. A C2 council runner

The adapters register local CLI tools as Synadia A2A agents on NATS:

- `codex_agent.py` registers `agents.prompt.codex.<owner>.<session>`.
- `claude_cli_agent.py` registers `agents.prompt.claude-code.<owner>.<session>`.
- `grok_cli_agent.py` registers `agents.prompt.grok.<owner>.<session>`.

Each adapter:

- Connects to `nats://localhost:4222`.
- Uses `AgentService` from `synadia_ai.agent_service`.
- Accepts an `Envelope(prompt=...)`.
- Builds a local CLI prompt.
- Runs the matching CLI non-interactively.
- Sends the final answer back as response chunks.

The runner is `c2_council_runner.py`.

It:

- Discovers agents with `synadia_ai.agents.Agents.discover()` and
  `DiscoverFilter(agent=..., owner=..., session_name=...)`.
- Sends prompts with `target.prompt(Envelope(prompt=...), timeout=...)`.
- Keeps an in-memory list of turns.
- Writes `council_history.json` and `council_transcript.md`.
- Extracts handoff mentions from agent responses.
- Supports `@codex`, `@claude-code`, `@claude`, and `@grok`.
- Chooses the last valid mention that is not the current speaker.
- Falls back to a rotation when no valid mention exists.
- Prevents one handoff edge from repeating too many times with
  `--max-edge-repeat`.
- Stops on `[DONE]`, `[FINAL]`, `[CONSENSUS]`, or `--max-rounds`.

## Important Runtime Defaults

- NATS URL: `nats://localhost:4222`
- Owner: usually `terng`
- Session: `collab`
- Agent order: `codex -> claude-code -> grok`
- Default topic: `AI + Human ควรเป็นอย่างไรในอนาคต`
- Python runtime: `/Users/terng/Downloads/work/p2p-agents/.venv/bin/python`

System Python does not have the required `nats` and `synadia_ai` packages, so
the p2p-agents virtual environment must be used.

## Main Files

- `c2_council_runner.py`: C2 orchestrator / light history manager.
- `run_c2_council.sh`: starts all three adapters, then runs the C2 runner.
- `codex_agent.py`: NATS adapter for Codex CLI.
- `claude_cli_agent.py`: NATS adapter for Claude CLI.
- `grok_cli_agent.py`: NATS adapter for Grok CLI.
- `A2A_C2_Autonomous_Council_Plan.md`: original C2 plan.
- `council_transcript_test2.md`: successful live-test transcript.
- `council_history_test2.json`: successful live-test JSON history.

## Live Test Status

The C2 runner has already passed a real three-turn test:

1. Codex answered and handed off to `@claude-code`.
2. Claude answered and handed off to `@grok`.
3. Grok answered and handed off back to `@claude-code`.

The test stopped at `--max-rounds 3`, not because of a failure.

One bug was found and fixed during testing:

- Old behavior: the runner selected the first mention in a response.
- Problem: Claude often says something like "ต่อจาก @codex ..." before asking
  `@grok` to continue.
- Fix: `extract_requested_next()` now selects the last valid mention that is not
  the current speaker.

## Current Design Tradeoffs

This is not a fully autonomous agent society. It is intentionally C2:

- Agents decide what to say and whom to mention next.
- The runner still enforces turn boundaries, history size, max rounds, and loop
  prevention.
- Mention-based handoff is simple and inspectable, but it can be ambiguous.
- The runner writes local files rather than using NATS KV or a database.
- The adapters run local CLIs and return whole answers, not fine-grained
  streaming semantic events.

## Questions For Reviewing Agents

Please respond with:

1. Your understanding of what this codebase does.
2. The strongest part of the design.
3. The weakest or riskiest part of the design.
4. One concrete next improvement you would make.
5. Whether you think the current C2 protocol is good enough for more 8-12 round
   testing.
