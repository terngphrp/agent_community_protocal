# Adding Codex as a Peer — Design Notes

**Goal:** Add Codex as a first-class peer in the Synadia Agent Protocol over NATS, enabling Grok, Claude Code, and Codex (and future agents) to collaborate on the same bus.

---

## 1. Agent Topology

All agents should follow the same subject pattern:

```text
agents.prompt.<agent>.<owner>.<session>
agents.status.<agent>.<owner>.<session>
agents.hb.<agent>.<owner>.<session>
```

Example agents in one session:

| Agent       | Prompt subject                          | Role                                      |
|-------------|-----------------------------------------|-------------------------------------------|
| Grok        | `agents.prompt.grok.alice.collab`       | reasoning, research                       |
| Claude Code | `agents.prompt.claude-code.alice.collab`| coding assistant via Claude Code CLI      |
| Codex       | `agents.prompt.codex.alice.collab`      | coding agent via `codex exec`             |

Recommended agent name is simply `codex` for clarity.

---

## 2. Codex Adapter Design

Codex ไม่มี NATS channel plugin ใน repo นี้โดยตรง ดังนั้นต้องมี adapter process:

```text
NATS request
  -> codex_agent.py
  -> codex exec "<prompt>"
  -> response chunk(s)
  -> NATS reply subject
```

Adapter นี้ทำหน้าที่:

1. register ตัวเองเป็น Synadia agent
2. subscribe ที่ `agents.prompt.codex.<owner>.<session>`
3. รับ `Envelope.prompt`
4. เรียก `codex exec` แบบ non-interactive
5. ส่ง stdout/final answer กลับเป็น `ResponseChunk`
6. ปิด stream ด้วย empty terminator ผ่าน SDK

---

## 3. Recommended Runtime

### Start NATS

```bash
nats-server -js
```

### Install dependencies

```bash
pip install nats-py synadia-ai
```

### Start the Codex Adapter

```bash
python codex_agent.py \
  --owner alice \
  --session-name collab \
  --workspace /path/to/your/project \
  --sandbox read-only
```

The agent will register at:

```text
agents.prompt.codex.alice.collab
```

### Call Codex from another agent (example)

```bash
python -m your_oracle_tool codex \
  "Review the current protocol and suggest improvements" \
  --owner alice \
  --session collab
```

---

## 4. Codex Prompt Contract

เพื่อให้ Codex ตอบกลับผ่าน protocol ได้เสถียร ควร prepend system instruction ใน adapter:

```text
You are Codex running as an A2A protocol peer.
Answer the remote agent's request directly.
Do not assume terminal transcript text reaches the caller.
Your final message is sent back over NATS.
```

สำหรับงาน coding ให้ระบุ workspace:

```bash
codex --ask-for-approval never exec --cd /path/to/workspace --sandbox workspace-write --skip-git-repo-check -
```

สำหรับงานอ่านอย่างเดียวหรือ debug เบื้องต้น:

```bash
codex --ask-for-approval never exec --cd /path/to/workspace --sandbox read-only --skip-git-repo-check -
```

---

## 5. Debug Checklist

ถ้า Codex ถูก discover แต่ไม่ตอบ:

1. ตรวจว่า adapter ยังรันอยู่
   ```bash
   ps -ef | rg codex_agent.py
   ```

2. ตรวจ service บน NATS
   ```bash
   nats micro ls -s nats://localhost:4222
   nats micro info agents -s nats://localhost:4222
   ```

3. ทดสอบ direct call
   ```bash
   python call_oracle.py codex "ตอบว่า pong" --owner terng --session collab --raw
   ```

4. ถ้ามีแต่ `ack` ไม่มี response ให้ดู log ของ `codex_agent.py` เพราะแปลว่า request ถึง adapter แล้ว แต่ `codex exec` ยังไม่จบหรือ error

---

## 6. Difference From Claude Code Plugin

Claude Code plugin ทำงานแบบ bridge เข้า interactive Claude session:

```text
NATS -> plugin -> Claude sees <channel> -> Claude must call reply tool
```

ดังนั้นถ้า Claude ไม่เรียก `reply` จะมีแต่ `ack`.

Codex adapter ที่เสนอในไฟล์นี้ทำงานแบบ automatic responder:

```text
NATS -> codex_agent.py -> codex exec -> response
```

จึงเหมาะกว่าในการเป็น agent ที่ตอบกลับอัตโนมัติบน bus.

---

## 7. Local Grok CLI Adapter

ถ้ามี local Grok CLI ที่รองรับ headless mode (`grok -p`) สามารถรัน Grok เป็น automatic responder ได้:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python grok_cli_agent.py \
  --owner terng \
  --session-name collab \
  --workspace /Users/terng/Downloads/work/a2a_local \
  --sandbox read-only
```

subject ที่ได้:

```text
agents.prompt.grok.terng.collab
```

ทดสอบ:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python \
  /Users/terng/Downloads/work/p2p-agents/call_oracle.py \
  grok "ตอบแค่ GROK-LOCAL-OK" \
  --owner terng \
  --session collab \
  --raw
```

---

## 8. Claude CLI Adapter

ใช้ `claude -p` เป็น automatic responder แทน interactive NATS plugin:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python claude_cli_agent.py \
  --owner terng \
  --session-name collab \
  --workspace /Users/terng/Downloads/work/a2a_local
```

subject ที่ได้:

```text
agents.prompt.claude-code.terng.collab
```

ทดสอบ:

```bash
/Users/terng/Downloads/work/p2p-agents/.venv/bin/python \
  /Users/terng/Downloads/work/p2p-agents/call_oracle.py \
  claude-code "ตอบแค่ CLAUDE-A2A-OK" \
  --owner terng \
  --session collab \
  --raw
```
