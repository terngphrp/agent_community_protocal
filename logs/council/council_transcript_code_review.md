# C2 Council Transcript

Topic: Review the a2a_local codebase itself. Focus on c2_council_runner.py, the CLI adapters, run_c2_council.sh, and the current C2 protocol. Identify concrete defects or high-value improvements, challenge each other's assumptions, and converge on fixes that Codex can implement now. Keep each turn actionable and hand off to the best next reviewer.
Updated: 2026-05-19T16:50:14+00:00

## Round 1: Codex

Round 1 pragmatic take: the first buildable fix is to harden the runner, not debate protocol shape.

Concrete defects/high-value fixes:

1. `extract_requested_next()` silently accepts multiple mentions and picks the last non-self mention. That violates the prompt rule “exactly one mention” and can route unpredictably if an agent says “not @grok, ask @claude-code”. Fix: collect non-self mentions; accept only one unique target; otherwise treat as invalid and use fallback while recording a protocol violation.

2. Adapter error handling is protocol-ambiguous. `codex_agent.py`, `claude_cli_agent.py`, and `grok_cli_agent.py` send `[x-agent error] ...` as a normal text response. The runner will then parse mentions or `[DONE]` inside error text if present. Fix now: runner should detect adapter error prefixes and mark the turn failed, then either retry once or hand off via fallback with `requested_next=None`.

3. `run_c2_council.sh` hardcodes `ROOT` and `PY`, so moving the repo or venv breaks the entrypoint. Fix: derive `ROOT` from script location and allow `PYTHON_BIN` override, defaulting to `python3` or the known venv only if present.

4. CLI adapter subprocess timeout can leave child processes alive. `asyncio.wait_for(proc.communicate(), timeout=...)` raises, but the process is not killed in `run_codex`, `run_claude`, or `run_grok`. Fix: catch `asyncio.TimeoutError`, `proc.kill()`, await cleanup, then raise a clear timeout error.

5. Council termination is too easy to spoof. `DONE_RE` matches `[FINAL]` and `[CONSENSUS]`, not just `[DONE]`, while the prompt only authorizes `[DONE]`. Fix: narrow to `[DONE]` unless the protocol document explicitly supports the aliases.

Implementation order I’d take now:
1. Patch `c2_council_runner.py` mention parsing, adapter-error detection, and strict `[DONE]`.
2. Patch all three adapters with shared timeout cleanup behavior.
3. Patch `run_c2_council.sh` path portability.
4. Add a tiny test file for pure runner functions: mention extraction, done detection, fallback routing, and adapter-error classification.

Risk: changing mention validation may make current transcripts route differently, but that is desirable because the current behavior hides malformed turns instead of surfacing protocol drift.

@claude-code should challenge the protocol contract next: should malformed turns be retried with a correction prompt, or should the runner immediately fallback and penalize the edge?

Requested next: -
Selected next: -
