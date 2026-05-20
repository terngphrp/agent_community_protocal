---
name: a2a-cross-session
description: Discover running A2A agents across sessions, let the user choose source and target agents, then relay a message between Grok, Claude Code, Codex, or other A2A agents without disturbing their main workflow.
argument-hint: "[prompt] [--from agent@session] [--to agent@session] [--workspace path]"
---

# a2a-cross-session

Use this skill when the user wants Grok, Claude Code, Codex, or another A2A agent to talk across different running sessions.

## Workflow

1. Discover all live A2A agents for the owner across all sessions.
2. If the user did not specify endpoints, show a numbered menu and ask which source and target to use.
3. Ask the source agent to prepare an update/message.
4. Relay that source response to the target agent.
5. Return both the source message and target acknowledgement.

## Commands

Interactive selection:

```bash
uv run python skills/a2a-cross-session/scripts/a2a_cross_session.py \
  "Update Claude about the perf/pipeline-speedup branch" \
  --workspace /path/to/project
```

Non-interactive:

```bash
uv run python skills/a2a-cross-session/scripts/a2a_cross_session.py \
  "Update Claude about the perf/pipeline-speedup branch" \
  --workspace /path/to/project \
  --from grok@collab \
  --to claude@psims_daily_data_prep
```

Use `claude`, `claude-code`, `codex`, or `grok` as agent names. `claude` is normalized to `claude-code`.

## Notes

- This is a relay, not a full council. It avoids mutating the main workflow by targeting explicit A2A sessions.
- Discovery defaults to no health check to avoid invoking every agent. Add `--health-check` when the user wants to verify responsiveness.
- The script reuses `a2a-consult` for the actual relay call.
