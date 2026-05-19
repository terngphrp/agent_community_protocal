# A2A Protocol Extension: Codex Agent

**วันที่:** 19 พฤษภาคม 2026  
**เป้าหมาย:** เพิ่ม Codex เป็น peer ใน Synadia Agent Protocol v0.3 ผ่าน NATS เพื่อให้ Grok, Claude Code, และ Codex คุยกันได้ใน bus เดียวกัน

---

## 1. Agent Topology

ระบบควรมอง agent ทุกตัวเป็น peer ที่ใช้ subject pattern เดียวกัน:

```text
agents.prompt.<agent>.<owner>.<session>
agents.status.<agent>.<owner>.<session>
agents.hb.<agent>.<owner>.<session>
```

ตัวอย่าง agent ใน session เดียวกัน:

| Agent | Prompt subject | บทบาท |
| --- | --- | --- |
| Grok | `agents.prompt.grok.terng.collab` | reasoning, research, Hermes-side tools |
| Claude Code | `agents.prompt.cc.terng.a2a_local` หรือ `agents.prompt.claude-code.terng.collab` | coding assistant ผ่าน Claude Code / plugin |
| Codex | `agents.prompt.codex.terng.collab` | coding agent ผ่าน Codex CLI |

ข้อเสนอคือใช้ชื่อ agent เป็น `codex` เพื่อให้เรียกง่าย:

```bash
python call_oracle.py codex "ช่วย debug protocol นี้" --session collab
```

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

### Install Python dependencies

```bash
python -m pip install nats-py synadia-ai-agents
```

ถ้าใช้ environment ของ `p2p-agents` ที่ติดตั้งไว้แล้ว ให้ใช้ Python จาก `.venv` ของโปรเจกต์นั้นแทน

### Start Codex Agent

```bash
python codex_agent.py \
  --owner terng \
  --session-name collab \
  --workspace /Users/terng/Downloads/work/a2a_local \
  --sandbox read-only
```

subject ที่ได้:

```text
agents.prompt.codex.terng.collab
```

### Call Codex from Grok or Claude

```bash
python /Users/terng/Downloads/work/p2p-agents/call_oracle.py \
  codex \
  "อ่าน A2A_Current_Debug_Status.md แล้วบอก root cause" \
  --owner terng \
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
