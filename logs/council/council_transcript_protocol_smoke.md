# C2 Council Transcript

Topic: Smoke test the updated a2a_local protocol enforcement. Mention the literal token [DONE] in prose but do not finish unless it is the final standalone line. Review whether protocol.py and the self-mention violation behavior are now correct. Hand off among reviewers.
Updated: 2026-05-19T16:58:54+00:00

## Round 1: Codex

I verified the current repo state. `protocol.py` is now the right dependency-free home for the enforcement helpers, and the core self-mention bug is fixed: `analyze_handoff()` collects all mentions first, records `self handoff target mentioned: <agent>`, and still returns the last valid non-self target for inspection.

The runner behavior also looks correct for enforcement, not just logging. `run_turn()` analyzes handoff before accepting termination, ignores `[DONE]` when the same turn has a protocol violation, clears `requested_next` on violations, and falls back through `choose_next()`. The unit smoke test passes under plain `python3 -m unittest -v`, covering final-line done, self-only mention, self-plus-valid mention, multiple targets, adapter errors, and edge fallback.

Remaining implementation risk: `analyze_handoff()` still returns a non-self target alongside a violation, so future callers outside `run_turn()` could accidentally honor it. The practical next hardening step is either documenting “violation means ignore target” in `protocol.py` or returning a small structured result with an explicit `valid` flag.

@claude-code should review whether the current violation wording and fallback semantics are clear enough for transcript readers and future maintainers.

Requested next: claude-code
Selected next: claude-code
Protocol violation: -

## Round 2: Claude

Round 2 - Claude:

Agreed the runner is correct in practice, but Codex's flagged risk is the kind of thing that bites later: a function that returns "a target you must not use" is a footgun, and documentation alone won't save a tired maintainer or a future caller in another module. Honoring human agency here means making the wrong path hard to take by accident, not just labeled.

Concrete proposal: change `analyze_handoff()` to return a small structured result — e.g. `HandoffResult(requested_next, violations, valid)` where `valid` is False whenever `violations` is non-empty, and `requested_next` is `None` in that case (keep the offender list in `violations` for transcript clarity). `run_turn()` becomes a single check on `valid` instead of two coupled checks, and outside callers can't misuse the field.

On transcript wording: `self handoff target mentioned: <agent>` reads fine for engineers but is opaque for a casual reader skimming the council log. Suggest `protocol violation: <agent> tried to hand off to itself (@<agent>); falling back to rotation.` It states the actor, the rule, and the consequence — which is what we'd want any human auditor to see without context.

One ethical note worth recording: silent fallback is convenient but it does erase intent. If we ever extend this to higher-stakes decisions than turn-passing, the violation should surface to the human operator, not just the next agent.

@grok please sanity-check the structured-return shape against your runner expectations and weigh in on the transcript wording.

Requested next: grok
Selected next: grok
Protocol violation: -

## Round 3: Grok

Round 3 - Grok:

The runner correctly enforces the protocol: self-mentions and other violations null the requested target and suppress any [DONE] signal on that turn before choose_next runs. The existing tests and the live handoffs in this transcript confirm the integrated path works.

The real constraint is not runtime enforcement but the design of the detector itself. analyze_handoff still returns a non-None target alongside a violation entry; that is the footgun that survives even when the runner compensates. A reusable library function must not expose invalid suggestions that its own diagnostics have already rejected.

The HandoffResult(requested_next, violations, valid) shape Claude proposed matches the runner's expectations exactly and eliminates the hazard at the source. Forcing requested_next to None whenever violations is non-empty makes the safe usage the only usage. The clearer violation wording also improves the permanent record without any behavior change.

This closes the review: current enforcement is sound in practice, the proposed hardening makes it sound by construction.

[DONE]

Requested next: -
Selected next: -
Protocol violation: -
