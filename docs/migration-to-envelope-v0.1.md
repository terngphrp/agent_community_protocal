# Migration Guide: From Mention-Based Handoff to a2a-envelope v0.1

**Status**: Work in progress (dual-mode support added in protocol.py + runner)

## Why we are migrating

The original mention-based protocol (`@codex`, `[DONE]`, regex in `protocol.py`) is extremely brittle in real usage:

- LLMs frequently violate "exactly one mention" rule
- `max_edge_repeat` cap causes unwanted third agents to be injected (real bug observed in ping-pong transcripts)
- `[DONE]` is a fragile last-line heuristic
- No self-correction possible — one violation = permanent loss of steering
- No machine-readable audit trail

`a2a-envelope v0.1` makes handoff, termination, correction, and violations **first-class and enforceable**.

## Current State (Dual-Mode)

- `protocol.py` now exports `parse_turn()` — tries structured envelope first, falls back to legacy mention parsing.
- `c2_council_runner.py` stores `envelope` (dict) in every `Turn` when available.
- All existing councils, transcripts, and direct `a2a-consult` calls continue to work unchanged.

## How to use the new envelope (recommended for new councils)

### 1. Instruct agents (add to your system prompt or topic)

At the very end of the response, output:

```a2a-envelope v0.1
{
  "version": "0.1",
  "from": "grok",
  "content": "...your normal answer...",
  "handoff": {"to": "codex", "reason": "needs implementation details"},
  "done": false,
  "correction_attempt": 0
}
```

### 2. Runner will automatically:
- Prefer the structured envelope
- Fall back to legacy behavior if the agent still uses old `@mention` style
- Record the full envelope in `*_history.json` and show it in transcripts

## Migration Phases

**Phase 0 (Current)** — Dual support (what we just implemented)
- Both legacy and envelope councils work
- Good for testing

**Phase 1** — Encourage envelope
- Update agent system prompts / role descriptions to prefer envelope output
- Start new long-running councils with envelope

**Phase 2** — Deprecate pure legacy for new councils
- Default `allow_envelope=True` and warn on pure legacy usage
- Keep legacy parser only for old transcripts

**Phase 3 (optional)** — Remove legacy parser (after all active councils migrated)

## Files Changed / Added

- `envelope.py` (new) — core Envelope class, parser, helpers
- `protocol.py` — added `parse_turn()`, dual-mode wrappers
- `c2_council_runner.py` — stores envelope in Turn, uses new parser
- `docs/migration-to-envelope-v0.1.md` (this file)

## Testing the migration

You can test with existing transcripts:

```bash
python -m pytest test_c2_council_runner.py -k envelope -s
```

Or run a council and inspect the new `envelope` field in the generated `_history.json`.

## Questions / Edge Cases Handled in v0.1

- Self-handoff → violation
- Multiple handoffs → violation
- Both `done` + `handoff` → violation
- `correction_attempt` support (agent can fix its own mistake once)
- Full backward compatibility for all current 2-agent and 3-agent councils

---

**Next steps after this PR**:
- Update agent adapters (`*_cli_agent.py`) to understand the new prompt instruction
- Add richer envelope fields (cost, confidence, structured decisions)
- Build proper self-correction loop in the runner

This migration keeps the spirit of lightweight councils while finally giving us reliability and auditability.