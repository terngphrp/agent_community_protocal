# Council Logs

This directory stores generated C2 council artifacts.

Default runner output now uses timestamped files:

- `<run-id>_history.json`
- `<run-id>_transcript.md`

Older manually named test outputs are kept here as historical evidence of
protocol debugging and live agent runs.

Use `--run-id <name>` for a stable pair of filenames, or pass
`--history-file` / `--transcript-file` when a specific output path is needed.

## Recent Activity

- `4986fa3 Make a2a-consult reliable for direct agent calls` pushed to `origin/main`
- Live NATS checks on 2026-05-20:
  - Discovered `codex` and `grok` in owner `terng`, session `collab`
  - Health checks passed for both agents
  - Direct `a2a-consult` JSON calls passed for `codex` and `grok`
  - Default-session direct call passed (`collab`)
  - `--council --max-rounds 1` smoke test passed and ended with `[DONE]`
- Verification before commit/push:
  - `.venv/bin/python -m unittest -v test_c2_council_runner.py test_a2a_consult.py`
  - `.venv/bin/python -m py_compile protocol.py c2_council_runner.py codex_agent.py claude_cli_agent.py grok_cli_agent.py skills/a2a-consult/scripts/a2a_consult.py scripts/discover_agents.py test_a2a_consult.py`
  - `bash -n scripts/install-a2a-consult.sh scripts/run_c2_council.sh`
- Major Docker support added (host .venv mount mode for fast testing + host CLI access)
- `discover_agents.py` with `--ping-pong` protocol test
- Project structure reorganized (`docs/`, `scripts/`, `memory/`)
- `memory/a2a_local_status.md` created for ongoing progress tracking

**Note**: Docker-based council runs will also generate logs here when using the mounted project volume.
