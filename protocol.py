from __future__ import annotations

from dataclasses import dataclass
import re


AGENT_ORDER = ["codex", "claude-code", "grok"]
VALID_MENTIONS = "@codex, @claude-code, @grok"

MENTION_TO_AGENT = {
    "codex": "codex",
    "claude": "claude-code",
    "claude-code": "claude-code",
    "grok": "grok",
}

MENTION_RE = re.compile(r"@(?P<name>codex|claude-code|claude|grok)\b", re.IGNORECASE)
ADAPTER_ERROR_RE = re.compile(r"^\[(codex|claude|grok)-agent error\]", re.IGNORECASE)


@dataclass(frozen=True)
class HandoffResult:
    requested_next: str | None
    violation: str | None

    @property
    def valid(self) -> bool:
        return self.violation is None


def is_done_signal(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and lines[-1].upper() == "[DONE]"


def is_adapter_error(text: str) -> bool:
    return bool(ADAPTER_ERROR_RE.match(text.strip()))


def analyze_handoff(text: str, current: str) -> HandoffResult:
    targets = [MENTION_TO_AGENT[match.group("name").lower()] for match in MENTION_RE.finditer(text)]
    non_self_targets = [target for target in targets if target != current]
    unique_non_self = list(dict.fromkeys(non_self_targets))

    violations: list[str] = []
    if current in targets:
        violations.append(f"{current} tried to hand off to itself (@{current})")
    if len(unique_non_self) > 1:
        violations.append(f"multiple handoff targets mentioned: {', '.join(unique_non_self)}")

    violation = "; ".join(violations) or None
    requested_next = None if violation else (non_self_targets[-1] if non_self_targets else None)
    return HandoffResult(requested_next=requested_next, violation=violation)


def handoff_candidates(current: str, requested: str | None) -> list[str]:
    candidates: list[str] = []
    if requested and requested != current:
        candidates.append(requested)
    start_idx = AGENT_ORDER.index(current)
    for offset in range(1, len(AGENT_ORDER)):
        candidate = AGENT_ORDER[(start_idx + offset) % len(AGENT_ORDER)]
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def choose_next(
    current: str,
    requested: str | None,
    edge_counts: dict[tuple[str, str], int],
    max_edge_repeat: int,
) -> str:
    candidates = handoff_candidates(current, requested)
    candidate = candidates[-1]
    for option in candidates:
        if edge_counts.get((current, option), 0) < max_edge_repeat:
            candidate = option
            break

    edge_counts[(current, candidate)] = edge_counts.get((current, candidate), 0) + 1
    return candidate


# =============================================================================
# a2a-envelope v0.1 Dual-Mode Support (Migration Layer)
# =============================================================================
#
# This section adds structured envelope support while keeping 100%
# backward compatibility with all existing mention-based councils.
#
# New recommended API: parse_turn()
# Old APIs (analyze_handoff, is_done_signal, etc.) remain unchanged.

try:
    from envelope import (
        Envelope,
        parse_response as _parse_envelope_or_legacy,
        format_envelope_block,
        validate_envelope as _validate_envelope,
    )
    _ENVELOPE_AVAILABLE = True
except Exception:
    _ENVELOPE_AVAILABLE = False
    Envelope = None  # type: ignore


def parse_turn(
    text: str,
    current: str,
    allow_envelope: bool = True,
) -> tuple["Envelope | None", HandoffResult, bool, list[str]]:
    """
    New primary parser for v0.1+ (recommended, improved after review).

    Returns a 4-tuple for clarity:
        (envelope, handoff_result, done, violations)

    - `done` is a clean boolean (True if either envelope.done or legacy [DONE] is present and valid).
    - This removes the need for callers to re-check is_done_signal after parsing.
    """
    violations: list[str] = []

    if allow_envelope and _ENVELOPE_AVAILABLE:
        env, _, env_viols = _parse_envelope_or_legacy(
            text, current, allow_legacy=True
        )
        if env_viols:
            violations.extend(env_viols)

        if env is not None:
            requested = env.handoff.to if env.handoff else None
            viol_str = "; ".join(violations) if violations else None

            # done comes cleanly from the envelope
            done = bool(env.done) and not viol_str
            return env, HandoffResult(requested_next=requested, violation=viol_str), done, violations

    # Legacy path
    legacy = analyze_handoff(text, current)
    if legacy.violation:
        violations.append(legacy.violation)

    done = is_done_signal(text) and not legacy.violation
    if done:
        return None, HandoffResult(requested_next=None, violation=legacy.violation), True, violations

    return None, legacy, False, violations


def format_envelope_for_agent(env: "Envelope") -> str:
    """Convenience wrapper so runner/adapters can easily embed envelopes."""
    if not _ENVELOPE_AVAILABLE or Envelope is None:
        return ""
    return format_envelope_block(env)


def validate_envelope(env: "Envelope", active_agents: list[str] | None = None) -> list[str]:
    """Wrapper around envelope validation."""
    if not _ENVELOPE_AVAILABLE or Envelope is None:
        return ["envelope support not available"]
    return _validate_envelope(env, active_agents or AGENT_ORDER)
