# Getting Started

This guide will help you get the Agent Community Protocol running — whether you have all three agents (Claude, Codex, Grok) or just one or two.

## Prerequisites

- A running **NATS server** (usually `nats://localhost:4222`)
- At least **one** of the following CLIs installed and authenticated:
  - `claude` (Claude Code)
  - `codex` (OpenAI Codex / compatible)
  - `grok` (xAI Grok CLI)
- Python 3.10+

You do **not** need all three agents to use the system.

## Quick Start (All 3 Agents)

If you have Claude, Codex, and Grok:

```bash
# Make sure NATS is running
nats-server -js

# Run a full 3-agent council
./scripts/run_c2_council.sh "Design a better agent handoff protocol" --max-rounds 8
```

The launcher will start all three adapters in the background and run the council.

## Running with Fewer Agents

The protocol is designed to be flexible. You can run councils with just the agents you have.

### 2 Agents (Recommended Approach)

Example: Only **Claude + Grok**

1. Start only the agents you have:

```bash
python claude_cli_agent.py --owner $USER --session demo --workspace "$PWD" &
python grok_cli_agent.py   --owner $USER --session demo --workspace "$PWD" &
```

2. Run the council, choosing a valid starting agent:

```bash
python c2_council_runner.py \
  "Review the current protocol and suggest improvements" \
  --owner $USER \
  --session demo \
  --start grok \
  --max-rounds 6
```

**Current Limitation**:
The runner still uses a fixed rotation (`codex → claude-code → grok`). If it tries to hand off to an agent you didn't start, it will fail with a discovery error.

**Workarounds**:
- Keep `--max-rounds` reasonable
- Manually steer the conversation using `@claude-code` or `@grok` in responses
- For production 2-agent use, you can temporarily edit `AGENT_ORDER` in `c2_council_runner.py`

### Single Agent

You can still use the system productively with just one agent:

```bash
# Start only the agent you have
python claude_cli_agent.py --owner $USER --session solo --workspace "$PWD"

# Run the runner (it will mostly stay on the same agent)
python c2_council_runner.py \
  "Help me design a new feature" \
  --owner $USER \
  --session solo \
  --start claude-code \
  --max-rounds 10
```

This is useful for:
- Testing a new adapter
- Focused work with one strong model
- Development and debugging

## Running the Runner Directly (Most Flexible)

For full control, start adapters manually and run the runner with specific options:

```bash
# Example: Only Codex + Claude
python codex_agent.py   --owner alice --session review --workspace "$PWD" --sandbox read-only &
python claude_cli_agent.py --owner alice --session review --workspace "$PWD" &

# Run council
python c2_council_runner.py \
  "Perform a thorough code review of this repository" \
  --owner alice \
  --session review \
  --start codex \
  --max-rounds 8 \
  --history-window 4
```

### Useful Flags

| Flag                  | Description                              | Example                     |
|-----------------------|------------------------------------------|-----------------------------|
| `--start`             | Which agent speaks first                 | `--start grok`              |
| `--max-rounds`        | Maximum number of turns                  | `--max-rounds 6`            |
| `--owner` / `--session` | Namespace for agents on NATS           | `--owner alice --session feature-x` |
| `--history-window`    | How many previous turns to include       | `--history-window 4`        |

## Environment Variables

You can control behavior without changing code:

```bash
export OWNER=alice
export SESSION=feature-review
export NATS_URL=nats://localhost:4222

./scripts/run_c2_council.sh "Your topic"
```

## Next Steps

- Read the **[Protocol Specification](PROTOCOL.md)** to understand the rules
- Look at **[Codex Adapter Design Notes](guides/codex-adapter.md)** for how adapters work
- Try writing your own adapter (see `*_agent.py` as reference)
- Join the discussion on how to better support 1–2 agent councils

## Discovering Live Agents

Before running a council, you can **automatically detect** which agents are currently available on the bus and even test if they respond:

```bash
python scripts/discover_agents.py --owner $USER --session collab
```

Example output:

```
Discovered agents (owner=alice, session=collab)

Agent             Status        Time   Response / Error
--------------------------------------------------------------------------------
codex             ✅ HEALTHY     87ms   AGENT-OK
claude-code       ✅ HEALTHY    142ms   AGENT-OK
grok              ❌ UNHEALTHY   30000ms Timeout
```

This is extremely useful when you only have 1 or 2 agents running.

You can disable the health check (faster, just discovery):

```bash
python scripts/discover_agents.py --owner $USER --session collab --no-health-check
```

## Tips for Partial Agent Usage

- The **protocol layer** (`protocol.py`) is completely agent-agnostic.
- The **runner** (`c2_council_runner.py`) is currently 3-agent oriented.
- Use `discover_agents.py` to know exactly which agents are live before starting a council.
- Many people successfully use 2-agent setups (Claude + Grok or Codex + Claude) for daily work.

Would you like a guide on **creating your own adapter** next?