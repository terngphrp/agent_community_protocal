"""
a2a-envelope v0.1 — Structured Handoff Envelope for Agent Community Protocol

This module replaces the fragile mention-based handoff system with a
machine-enforceable, versioned envelope while maintaining backward
compatibility with existing free-text + @mention councils.

Design goals (based on real failure analysis from protocol.py + logs):
- Eliminate regex parsing of handoffs
- Make [DONE] and handoff first-class and explicit
- Support self-correction (1 retry before forfeit)
- Support audit (turn_id, correlation_id, violations)
- Easy embedding in normal agent responses (human + machine readable)
- Dual-mode parser (envelope first → legacy mention fallback)

Recommended embedding format (agents output this at the very end):

    ...normal response text here...

    ```a2a-envelope v0.1
    {
      "version": "0.1",
      "turn_id": "...",
      "from": "grok",
      "content": "...",
      "handoff": {"to": "codex", "reason": "..."},
      "done": false,
      "correction_attempt": 0,
      ...
    }
    ```
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Literal

# =============================================================================
# Core Data Structures
# =============================================================================

AgentName = Literal["codex", "claude-code", "grok"]


@dataclass
class Handoff:
    to: AgentName
    reason: str | None = None


@dataclass
class Envelope:
    """a2a-envelope v0.1"""

    version: str = "0.1"
    turn_id: str = ""                    # UUID4 for this logical turn
    from_agent: AgentName = "grok"       # who produced this turn
    content: str = ""                    # the actual reasoning / answer (human readable)

    # Control fields (exactly one of handoff or done should be meaningful)
    handoff: Handoff | None = None
    done: bool = False

    # Reliability & correction
    correction_attempt: int = 0          # 0 = first try, 1 = after self-correction
    violations: list[str] | None = None  # self-reported by the agent

    # Optional rich metadata
    metadata: dict[str, Any] | None = None

    # Internal: correlation across retries / sub-councils
    correlation_id: str | None = None

    def __post_init__(self):
        if not self.turn_id:
            self.turn_id = str(uuid.uuid4())

        if self.violations is None:
            self.violations = []

        if self.metadata is None:
            self.metadata = {}

        # Normalize handoff to Handoff instance (accept both dict and Handoff)
        if self.handoff is not None and isinstance(self.handoff, dict):
            self.handoff = Handoff(
                to=self.handoff.get("to"),
                reason=self.handoff.get("reason"),
            )

    @property
    def is_valid_handoff(self) -> bool:
        return self.handoff is not None and not self.done

    @property
    def is_done(self) -> bool:
        return self.done and self.handoff is None

    def to_json(self, indent: int | None = None) -> str:
        """Serialize to clean JSON (ready to embed)."""
        if self.handoff is None:
            handoff_data = None
        elif isinstance(self.handoff, Handoff):
            handoff_data = asdict(self.handoff)
        else:
            # already a dict (defensive)
            handoff_data = self.handoff

        data = {
            "version": self.version,
            "turn_id": self.turn_id,
            "from": self.from_agent,
            "content": self.content,
            "handoff": handoff_data,
            "done": self.done,
            "correction_attempt": self.correction_attempt,
            "violations": self.violations or [],
            "metadata": self.metadata or {},
        }
        if self.correlation_id:
            data["correlation_id"] = self.correlation_id

        return json.dumps(data, indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "Envelope":
        data = json.loads(json_str)

        handoff = None
        if data.get("handoff"):
            handoff = Handoff(
                to=data["handoff"]["to"],
                reason=data["handoff"].get("reason")
            )

        return cls(
            version=data.get("version", "0.1"),
            turn_id=data.get("turn_id", ""),
            from_agent=data.get("from") or data.get("from_agent", "grok"),
            content=data.get("content", ""),
            handoff=handoff,
            done=data.get("done", False),
            correction_attempt=data.get("correction_attempt", 0),
            violations=data.get("violations"),
            metadata=data.get("metadata"),
            correlation_id=data.get("correlation_id"),
        )


# =============================================================================
# Dual-Mode Parser (Envelope first, then legacy mention fallback)
# =============================================================================

# Legacy mention patterns (kept for backward compat during migration)
LEGACY_MENTION_RE = re.compile(r"@(?P<name>codex|claude-code|claude|grok)\b", re.IGNORECASE)
LEGACY_DONE_RE = re.compile(r"^\[DONE\]$", re.IGNORECASE)

ENVELOPE_BLOCK_RE = re.compile(
    r"```a2a-envelope\s+v?(?P<version>0\.\d+)\s*\n(?P<json>[\s\S]+?)\n```",
    re.MULTILINE
)


def parse_response(
    text: str,
    current_agent: AgentName,
    allow_legacy: bool = True
) -> tuple[Envelope | None, str | None, list[str]]:
    """
    Parse agent response.

    Returns:
        (envelope_or_none, legacy_requested_next_or_none, violations)

    Strategy:
    1. Try to find and parse a2a-envelope block first (preferred)
    2. If no envelope and legacy allowed → fall back to old mention + [DONE] logic
    3. Collect violations (self-reported + detected)
    """
    violations: list[str] = []

    # --- Try structured envelope first ---
    envelope_match = ENVELOPE_BLOCK_RE.search(text)
    if envelope_match:
        try:
            json_str = envelope_match.group("json").strip()
            env = Envelope.from_json(json_str)

            # Basic semantic validation
            if env.from_agent != current_agent:
                violations.append(f"envelope 'from' ({env.from_agent}) does not match speaker ({current_agent})")

            if env.handoff and env.handoff.to == current_agent:
                violations.append("agent tried to hand off to itself")

            if env.done and env.handoff is not None:
                violations.append("both 'done' and 'handoff' are set")

            # Strip the envelope block from content for cleanliness
            clean_content = ENVELOPE_BLOCK_RE.sub("", text).strip()
            env.content = clean_content or env.content

            return env, None, violations

        except Exception as e:
            violations.append(f"failed to parse a2a-envelope block: {e}")

    # --- Legacy fallback (mention-based) ---
    if not allow_legacy:
        violations.append("no valid a2a-envelope found and legacy mode disabled")
        return None, None, violations

    # Reuse the old logic (imported or duplicated here for now)
    # In real integration we will call protocol.analyze_handoff + is_done_signal
    targets = [m.group("name").lower() for m in LEGACY_MENTION_RE.finditer(text)]
    non_self = [t for t in targets if t != current_agent]

    if current_agent in targets:
        violations.append(f"{current_agent} tried to hand off to itself")

    if len(set(non_self)) > 1:
        violations.append(f"multiple handoff targets: {', '.join(set(non_self))}")

    requested = non_self[-1] if non_self else None

    # Check for legacy [DONE]
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    is_done = bool(lines) and bool(LEGACY_DONE_RE.match(lines[-1]))

    if is_done:
        requested = None

    # Legacy path: do NOT create Envelope here.
    # Let protocol.parse_turn decide. Return None for envelope so dual-mode can detect "legacy".
    if requested or is_done:
        return None, requested, violations

    violations.append("missing handoff mention (legacy mode)")
    return None, None, violations


# =============================================================================
# Embedding Helper (for prompts / adapters)
# =============================================================================

def format_envelope_block(env: Envelope) -> str:
    """Returns the exact markdown block agents should append at the end of their response."""
    return f"```a2a-envelope v{env.version}\n{env.to_json(indent=2)}\n```"


def build_envelope_instructions(current: AgentName, valid_targets: list[AgentName]) -> str:
    """
    Instructions to inject into agent prompts during the migration period.
    """
    targets = ", ".join(f"@{t}" for t in valid_targets if t != current)
    return f"""\
At the very end of your response, you MUST output a machine-readable envelope in the following format (do NOT escape it):

```a2a-envelope v0.1
{{
  "version": "0.1",
  "from": "{current}",
  "content": "...your normal reasoning...",
  "handoff": {{"to": "<one of {targets}>", "reason": "short reason"}} OR null,
  "done": true/false,
  "correction_attempt": 0,
  "metadata": {{ "confidence": 0.0-1.0 }}
}}
```

Rules:
- Exactly one of "handoff" or "done": true must be present.
- Never hand off to yourself.
- If you made a mistake in the previous turn, you may set "correction_attempt": 1 and try again.
- The JSON must be inside a fenced code block with language "a2a-envelope v0.1".
"""


# =============================================================================
# Convenience: Create a new envelope for the current turn
# =============================================================================

def new_envelope(
    from_agent: AgentName,
    content: str,
    handoff_to: AgentName | None = None,
    done: bool = False,
    correlation_id: str | None = None,
    correction_attempt: int = 0,
) -> Envelope:
    return Envelope(
        from_agent=from_agent,
        content=content,
        handoff=Handoff(to=handoff_to) if handoff_to else None,
        done=done,
        correlation_id=correlation_id or str(uuid.uuid4()),
        correction_attempt=correction_attempt,
    )


# =============================================================================
# Validation (can be extended later)
# =============================================================================

def validate_envelope(env: Envelope, active_agents: list[AgentName]) -> list[str]:
    """Returns list of violations (empty = valid)."""
    errs: list[str] = []

    if env.handoff and env.handoff.to not in active_agents:
        errs.append(f"handoff target '{env.handoff.to}' is not an active agent")

    if env.handoff and env.handoff.to == env.from_agent:
        errs.append("self-handoff is not allowed")

    if env.done and env.handoff is not None:
        errs.append("cannot be both done and handing off")

    if env.correction_attempt > 1:
        errs.append("correction_attempt > 1 not allowed in v0.1")

    return errs


if __name__ == "__main__":
    # Quick smoke test
    env = new_envelope("grok", "I think codex should continue the implementation.", "codex")
    print("=== Envelope JSON ===")
    print(env.to_json(indent=2))
    print("\n=== Embedded block ===")
    print(format_envelope_block(env))

    print("\n=== Parse test (envelope) ===")
    block = format_envelope_block(env)
    parsed, _, _ = parse_response("Some reasoning...\n\n" + block, "grok")
    print("Parsed handoff.to:", parsed.handoff.to if parsed and parsed.handoff else None)