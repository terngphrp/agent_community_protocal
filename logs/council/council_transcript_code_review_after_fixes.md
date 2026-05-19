# C2 Council Transcript

Topic: Review the updated a2a_local code after the first fixes. Focus on whether the strict final-line DONE signal, handoff violation recording, adapter timeout cleanup, portable run script, and unittest coverage are enough. Identify any remaining concrete bug that Codex should fix now. Hand off among all three reviewers.
Updated: 2026-05-19T16:55:52+00:00

## Round 1: Codex

The fixes are directionally enough for a usable loop, but I would not call this done yet.

Concrete bug Codex should fix now: `analyze_handoff()` silently ignores self-mentions. In [c2_council_runner.py](/Users/terng/Downloads/work/a2a_local/c2_council_runner.py:204), a Codex response containing only `@codex` returns `(None, None)`, so the runner records no protocol violation even though the prompt explicitly forbids naming yourself as next speaker. If the response says `@codex @grok`, it also records no violation because self-mentions are filtered before violation analysis. Fix: collect all mentions first, record `self handoff target mentioned: codex` when present, then separately choose the last valid non-self target or fallback.

Secondary risk: the unit tests did not run under system `python3` because importing `c2_council_runner` requires `nats`. That means the “unittest coverage” is only useful inside the project venv, not as a portable smoke test. Either document the venv runner or split pure protocol helpers into a dependency-free module.

The strict final-line `[DONE]` check looks correct. Adapter timeout cleanup is acceptable for direct child processes, though it may not clean grandchildren if a CLI spawns them. The run script is improved, but still has local defaults (`DEFAULT_PY`, `OWNER=terng`) that make it less portable than it looks.

@claude-code should review the human/protocol side next: whether violations should merely be recorded or should alter turn selection/reporting semantics.

Requested next: claude-code
Selected next: claude-code
Protocol violation: multiple handoff targets mentioned: grok, claude-code

## Round 2: Claude

Round 2 — Claude:

Codex is right that the self-mention bug is the load-bearing fix, but the deeper issue is what we *do* with violations. Recording-only is the wrong default for a semi-autonomous council: a silent log lets one agent quietly steer turn order by always naming itself, and the human supervisor only notices in postmortem. That undermines the whole point of having an explicit handoff protocol.

Concrete things Codex should fix in this pass, beyond the self-mention parsing:

1. **Violations must alter selection, not just be recorded.** When `analyze_handoff()` detects a self-handoff or no valid mention, the runner should override with deterministic round-robin and tag the round header with `PROTOCOL_VIOLATION: <reason>` so the human reading the transcript sees it inline, not in a side log. Today (per Codex's read) the offender effectively gets a free pass.

2. **`[DONE]` must be invalid in any response that also commits a handoff violation.** Otherwise an agent can end the debate prematurely while breaking the rules — the protocol failure should void the termination signal, not coexist with it. This matters ethically: a misbehaving model shouldn't be able to unilaterally close discussion.

3. **The pure protocol helpers (`analyze_handoff`, `[DONE]` check, mention parsing) should be extracted into a `nats`-free module** so the unittests run under system `python3`. Codex's portability point is real; right now "we have tests" is misleading if they only pass in one venv.

Adapter grandchild cleanup (Codex's secondary concern) is worth a TODO but not a blocker — none of the current CLIs (`codex`, `claude`, `grok`) fork detached children in practice.

Net: directional progress is real, but "enough" requires violations to be load-bearing in turn selection, not decorative. Grok, you have the systems/perf lens — does enforcing round-robin override on violation create any race or starvation pattern I'm missing in the runner's state machine?

@grok

Requested next: grok
Selected next: grok
Protocol violation: -

## Round 3: Grok

The code on disk still contains the self-mention bug Codex identified: analyze_handoff filters the current speaker before collecting targets, so a turn that names only itself returns (None, None) and never populates protocol_violation. The first fixes did not close the loop between council diagnosis and source change.

Answering the systems question directly: overriding to round-robin on violation adds no races or starvation. choose_next already protects against ping-pong via edge_counts; forcing the fallback path simply increases rotation frequency for misbehaving agents. Termination remains bounded by max_rounds or max_edge_repeat. The loop is strictly sequential.

Real constraint: the protocol's correctness depends on the three external CLIs emitting parseable directives from stochastic models. Runner enforcement can only make violations visible and neutralize their steering effect; it cannot make the models obedient. That is the limit of "enough".

Codex should now: (1) rewrite analyze_handoff to surface self-mentions as violation strings, (2) move the four pure helpers to a new protocol.py with no nats imports, (3) make run_turn compute violation before the done gate so a violating [DONE] is treated as continuation with forced next, (4) stamp "PROTOCOL_VIOLATION: ..." into the round header in the transcript when present, and (5) update tests and run script for clean-system execution.

@codex

Requested next: codex
Selected next: codex
Protocol violation: -

## Round 4: Codex

I verified the current files. The remaining bug is still concrete and fixable: `analyze_handoff()` drops self-mentions before deciding whether a violation occurred, so `@codex` from Codex becomes “no requested target, no violation” instead of “self handoff target mentioned.” That means the runner cannot enforce the rule it prompts agents to follow.

The buildable fix is the five-step patch Grok listed, with one implementation detail: make violation state part of selection semantics, not just transcript metadata. `run_turn()` should always analyze handoff before accepting `[DONE]`; if there is any protocol violation, ignore the done signal, set `requested_next = None`, and force `choose_next()` down the deterministic fallback path. The transcript header should show `PROTOCOL_VIOLATION: <reason>` inline so a human reviewing the council sees the breach where it happened.

The tests are not enough until pure protocol helpers move out of `c2_council_runner.py` into a dependency-free module. Current `test_c2_council_runner.py` still imports the NATS-bound runner, so it is not a portable smoke test. Add explicit unit cases for self-only mention, self-plus-valid mention, violating `[DONE]`, and no valid handoff.

Adapter cleanup and the run script are acceptable as secondary hardening items. The blocker is protocol enforcement.

[DONE]

Requested next: -
Selected next: -
Protocol violation: -
