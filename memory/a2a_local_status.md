# A2A Local Memory

Current state:

- The workspace implements a local C2 council over NATS for Codex, Claude, and Grok.
- Runtime adapters are `codex_agent.py`, `claude_cli_agent.py`, and `grok_cli_agent.py`.
- The runner is `c2_council_runner.py`.
- Protocol helper logic is now isolated in `protocol.py` so tests can run without NATS.
- Council logs and transcripts live under `logs/council/`.
- The runner now creates timestamped log files by default.

Important protocol decisions:

- `[DONE]` only ends a council turn when it is the final standalone line.
- Adapter error responses are protocol violations and cannot end the council.
- Self-handoff mentions are protocol violations.
- Multiple unique handoff targets are protocol violations.
- A violating turn cannot steer the next speaker; the runner falls back to deterministic rotation.
- Violations are written inline in transcript round headers.

Validation:

- `python3 -m unittest -v test_c2_council_runner.py` passes.
- `/Users/terng/Downloads/work/p2p-agents/.venv/bin/python -m unittest -v test_c2_council_runner.py` passes.

Known next improvements:

- Add a structured handoff footer/channel to reduce free-form mention ambiguity.
- Consider NATS KV or SQLite for durable council memory beyond local transcript files.
- Consider process-group cleanup for CLI adapters if any CLI starts detached child processes.
