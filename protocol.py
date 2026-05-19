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
