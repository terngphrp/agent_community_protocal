# Agent Community Protocol — Specification (Draft)

> **Status:** Early draft. This document is intended to become the canonical specification for interoperable multi-agent councils over NATS.

## 1. Goals

- Enable **reliable, auditable turn-based collaboration** between heterogeneous AI agents.
- Provide **strong safety guarantees** through explicit handoff rules and violation enforcement.
- Remain **transport-friendly** (currently built on Synadia/NATS Agent Protocol).
- Support **incremental adoption** — agents can join without changing their core behavior.

## 2. Core Concepts

### 2.1 Agents

An agent is identified by three parts:

- `agent` — e.g. `claude-code`, `codex`, `grok`, `aider`
- `owner` — human or organization (e.g. `alice`, `terng`, `acme`)
- `session` — collaboration context (e.g. `collab`, `feature-x`, `review-2026`)

### 2.2 Subject Patterns

All communication uses the following NATS subject hierarchy (recommended):

```
agents.prompt.<agent>.<owner>.<session>
agents.status.<agent>.<owner>.<session>
agents.hb.<agent>.<owner>.<session>
```

### 2.3 Council

A council is a sequence of turns where agents collaborate on a shared topic under the supervision of a **runner** (or equivalent orchestrator).

## 3. Handoff Rules (Current Reference)

| Rule                        | Requirement                                      | Violation? |
|----------------------------|--------------------------------------------------|----------|
| Handoff target             | Must mention **exactly one** valid agent         | Yes      |
| Self-handoff               | Forbidden                                        | Yes      |
| Multiple distinct targets  | Forbidden                                        | Yes      |
| Termination signal         | Must be the **final standalone line** `[DONE]`   | Ignored if violation present |
| Adapter error response     | Treated as protocol violation                    | Yes      |

Valid mention forms (case-insensitive):
- `@codex`
- `@claude-code`, `@claude`
- `@grok`

## 4. Message Format

Current reference implementation uses free-form text with embedded mentions.

Future versions should define a structured envelope (proposed):

```json
{
  "role": "claude-code",
  "content": "...",
  "handoff": { "to": "codex" },
  "metadata": { ... }
}
```

## 5. Termination

A council ends successfully only when an agent outputs a message whose **last non-empty line** is exactly `[DONE]` (case-insensitive) **and** the turn contains no protocol violations.

## 6. Violation Handling

When a violation is detected:

1. The violation is recorded in the transcript.
2. The offending turn **loses the right to choose** the next speaker.
3. The runner falls back to a deterministic rotation (with repetition limiting).

## 7. Transport Requirements

The current reference uses the Synadia Agent Protocol (`synadia_ai` + NATS microservices). Any transport that can provide:

- Request / streaming response
- Agent discovery
- Heartbeats / liveness

...is considered compatible in principle.

## 8. Open Questions (for community discussion)

- Should we define a canonical structured handoff format?
- How should durable memory / shared context work across councils?
- What is the minimal set of features an agent must implement to be "protocol compliant"?
- Versioning strategy for the protocol.

---

**Contributions to this spec are very welcome.** Please open issues or PRs against `docs/PROTOCOL.md`.