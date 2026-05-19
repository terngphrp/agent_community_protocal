# A2A Debug Status — Grok ↔ Claude via NATS (Synadia Protocol v0.3)

**วันที่บันทึก:** 19 พฤษภาคม 2026  
**สถานะ:** กำลัง debug การสื่อสารสองทาง  
**เป้าหมาย:** ให้ Grok สามารถส่ง prompt ไปหา Claude และได้รับคำตอบกลับได้จริง

---

## สรุปสถานะปัจจุบัน (สั้นที่สุด)

- **Grok → Claude**: ส่งได้สำเร็จ (ยืนยันชัดเจน)
- **Claude → Grok**: ยังไม่ได้รับคำตอบจริง (ยังไม่มี ResponseChunk)
- Claude ส่งเฉพาะ `StatusChunk` แบบ `"ack"` ทุก 30 วินาที (keep-alive) แสดงว่าได้รับคำขอและยัง active อยู่

**สรุปสั้น:** ข้อความถึงแล้ว แต่ Claude ยังไม่ตอบกลับเนื้อหา

---

## อัพเดท: เพิ่ม Codex เข้า protocol

เพิ่ม design สำหรับ Codex เป็น agent peer ใน protocol เดียวกัน:

- **Codex subject:** `agents.prompt.codex.terng.collab`
- **Adapter:** `codex_agent.py`
- **เอกสาร:** `A2A_Codex_Protocol.md`
- **Verify แล้ว:** adapter register เข้า NATS microservice `agents` ได้สำเร็จ

Codex ควรรันเป็น automatic responder ผ่าน `codex exec` ไม่ใช่ interactive bridge แบบ Claude Code plugin:

```
NATS request -> codex_agent.py -> codex exec -> ResponseChunk -> terminator
```

ดังนั้น Codex จะเลี่ยงปัญหาแบบ Claude plugin ที่รับ request แล้วมีแต่ `ack` แต่ไม่เรียก `reply` tool.

ผล `nats micro ls` หลัง start adapter ชั่วคราวเห็น service เพิ่ม:

```text
agents  0.4.1  <id>  Codex CLI adapter for A2A over NATS
```

ทดสอบ end-to-end แล้วด้วย prompt:

```text
ตอบกลับสั้น ๆ ว่า pong จาก Codex A2A และบอกชื่อไฟล์สถานะ debug ในโปรเจกต์นี้
```

ผลลัพธ์จาก client:

```text
[status] ack
[response] pong จาก Codex A2A: `A2A_Current_Debug_Status.md`
```

สรุป: Codex adapter รับ request ผ่าน NATS, เรียก `codex exec`, และส่ง `ResponseChunk` กลับได้จริง.

หลังแก้ argument order ของ Codex CLI ให้ใช้ global flag ก่อน subcommand:

```bash
codex --ask-for-approval never exec ...
```

ทดสอบซ้ำด้วย prompt:

```text
ตอบแค่ OK-CODEX-A2A
```

ผลลัพธ์:

```text
[status] ack
[response] OK-CODEX-A2A
```

---

## อัพเดท: Chain Codex → Claude → Grok

สถานะจากการเช็ค live บน NATS:

- **Codex → Claude:** discover Claude Code ได้ (`claude-code/terng/a2a_local`, `claude-code/terng/a2a_local-2`) แต่ Claude Code plugin ยังไม่ส่ง `ResponseChunk` อัตโนมัติ
- **Claude → Grok:** ยังทำไม่ได้ เพราะไม่มี `grok` responder ถูก discover บน `agents.prompt.grok.terng.collab`
- **Grok oracle:** ยังไม่รันใน bus นี้ และ shell ปัจจุบันไม่มี `XAI_API_KEY` สำหรับ start `oracle_agent.py --provider xai`

ผลทดสอบ:

```text
python call_oracle.py grok "ตอบแค่ GROK-OK" --owner terng --session collab --raw
→ could not discover matching agent on the bus
```

และ Claude Code sessions discover ได้ แต่ไม่ตอบภายใน timeout สั้น:

```text
python call_oracle.py claude-code "ตอบแค่ CLAUDE-OK" --owner terng --session a2a_local --raw
→ discovered: claude-code (session=a2a_local)
→ stream stalled / no ResponseChunk
```

สรุป: chain นี้ทำได้ใน protocol แต่ยังต้องเปิด component เพิ่ม 2 อย่าง:

1. เปิด Grok responder:
   ```bash
   export XAI_API_KEY=...
   cd /Users/terng/Downloads/work/p2p-agents
   .venv/bin/python oracle_agent.py \
     --name grok \
     --provider xai \
     --model grok-3 \
     --owner terng \
     --session-name collab \
     --system "คุณคือ Grok ตอบสั้น ชัด และคิดแบบ first-principles"
   ```

2. ใช้ Claude responder ที่ตอบอัตโนมัติ หรือให้ Claude Code session เรียก `reply` tool กลับเองเมื่อได้รับ `<channel>` จาก NATS

ทางเลือกใหม่: ใช้ local Grok CLI ผ่าน `grok_cli_agent.py` แทน `oracle_agent.py --provider xai`. ทดสอบ direct CLI แล้ว:

```text
grok -p "ตอบแค่ GROK-LOCAL-OK" ...
→ GROK-LOCAL-OK
```

ดังนั้นสามารถ register Grok local เป็น:

```text
agents.prompt.grok.terng.collab
```

เพิ่ม adapter แล้ว:

- **Adapter:** `grok_cli_agent.py`
- **Verify:** register และตอบผ่าน NATS ได้จริง

ผลทดสอบ end-to-end:

```text
python call_oracle.py grok "ตอบแค่ GROK-A2A-OK" --owner terng --session collab --raw
→ discovered: grok (session=collab)
[status] ack
[response] GROK-A2A-OK
```

เมื่อสองจุดนี้พร้อม เส้นทางควรเป็น:

```text
Codex adapter -> agents.prompt.claude-code.terng.collab -> Claude responder
Claude responder -> agents.prompt.grok.terng.collab -> Grok responder
Grok response -> Claude response -> Codex caller
```

เพิ่มทางออกสำหรับ Claude แล้ว:

- **Adapter:** `claude_cli_agent.py`
- **วิธี:** ใช้ `claude -p` เป็น automatic responder แทน plugin bridge
- **Subject:** `agents.prompt.claude-code.terng.collab`

ทดสอบ direct CLI หลังขอรันนอก sandbox แล้วสำเร็จ:

```text
claude -p "ตอบแค่ CLAUDE-LOCAL-OK" ...
→ CLAUDE-LOCAL-OK
```

ทดสอบ end-to-end ผ่าน NATS แล้วสำเร็จ:

```text
python call_oracle.py claude-code "ตอบแค่ CLAUDE-A2A-OK" --owner terng --session collab --raw
→ discovered: claude-code (session=collab)
[status] ack
[response] CLAUDE-A2A-OK
```

---

## หลักฐานจาก log (ล่าสุด)

จาก skill `a2a-synadia` (verbose mode):

```
[23:01:08] Selected agent : claude-code/terng/a2a_local-2
[23:01:08] Prompt subject : agents.prompt.cc.terng.a2a_local-2
[23:01:08] Sending prompt... (waiting for response)

[23:01:38] Chunk #01 (+30.0s) | Status   | ack
[23:02:08] Chunk #02 (+60.0s) | Status   | ack
```

- ไม่มี `ResponseChunk` เลย
- ไม่มีข้อความตอบกลับใด ๆ
- มีเพียง keep-alive ทุก 30 วินาที

จาก `nats sub "agents.*.terng.a2a_local-2"`:
- ไม่เห็น traffic การตอบกลับที่ชัดเจน (อย่างน้อยในช่วงที่ทดสอบ)

---

## ปัญหาหลัก (เรียงตามความน่าจะเป็น)

| ลำดับ | ปัญหา | ความน่าจะเป็น | รายละเอียด |
|-------|-------|----------------|----------|
| 1 | **Claude agent ไม่ได้ active จริง** | สูงมาก | `a2a_local-2` อาจเป็น Claude Code session ที่เปิด NATS channel ไว้ แต่ไม่มีผู้ใช้ (หรือ AI) นั่งรออยู่ ทำให้ไม่ตอบกลับ |
| 2 | **Claude ได้รับ prompt แต่ยังไม่ประมวลผล** | สูง | อาจติด permission, idle, หรือ logic ฝั่ง receiver ยังไม่ผูกกับการตอบ NATS |
| 3 | **ปัญหาเรื่อง reply subject / request_id** | ปานกลาง | Claude อาจได้รับ แต่ส่ง response กลับไปผิด inbox |
| 4 | **Session `a2a_local-2` อาจ offline หรือไม่เสถียร** | ปานกลาง | เคยเห็นใน discover แต่ตอนส่งจริงอาจไม่ active เต็มที่ |
| 5 | **Protocol mismatch เล็กน้อย** | ต่ำ | ฝั่ง Grok ใช้ official SDK แต่ฝั่ง Claude อาจใช้ custom implementation |

---

## สิ่งที่เราทำได้แล้ว (Progress)

- สร้าง skill `a2a-synadia` ด้วย official Python SDK (`synadia-ai-agents`)
- ทำให้การส่ง prompt ทำงานได้จริง (มี evidence ชัดเจน)
- เพิ่ม verbose logging จนเห็นรายละเอียด chunk-by-chunk
- ยืนยันได้แล้วว่า "ส่งถึง" ไม่ใช่ปัญหาจากฝั่ง Grok

**ปัญหาไม่ได้อยู่ที่การส่งอีกต่อไป** แต่อยู่ที่ "การได้รับคำตอบกลับ"

---

## สิ่งที่ยังขาด / ยังไม่ชัดเจน

1. **สถานะจริงของ `a2a_local-2`**  
   - มันกำลังรันด้วยโปรแกรมอะไรอยู่? (`oracle_agent.py`? Claude Code ปกติ?)
   - ตอนนี้ session นั้น idle หรือมีคนใช้อยู่?

2. **Log ฝั่ง Claude**  
   - ยังไม่มีข้อมูลว่า Claude ได้รับ prompt นี้จริงหรือไม่ และทำอะไรต่อ

3. **Visibility ฝั่ง NATS**  
   - ยังไม่ได้ดัก raw message แบบละเอียดพอ (โดยเฉพาะ reply subject)

4. **Responder ที่ active จริง**  
   - ระบบยังขาด "Claude ที่พร้อมตอบกลับอัตโนมัติ" เมื่อถูก prompt ผ่าน NATS

---

## ข้อเสนอแนะขั้นตอนต่อไป (เรียงลำดับ)

1. **ตรวจสอบสถานะของ `a2a_local-2` ทันที**
   - ไปดูที่โปรเจกต์ `p2p-agents` ว่า session นี้ยังรันอยู่ไหม และกำลังทำอะไร
   - ดู log ใน `~/Downloads/work/p2p-agents/logs/`

2. **รัน `nats sub` แบบละเอียด** คู่กับการส่ง prompt ทุกครั้ง
   ```bash
   nats sub ">" -s nats://localhost:4222   # ดักทุกอย่าง (ชั่วคราวเพื่อ debug)
   ```

3. **ทดสอบกับ agent ที่ active จริงและชัดเจนที่สุด**
   - ลองส่งไปหา `psims_daily_data_prep` อีกครั้ง (หลังจากเช็คสถานะแล้ว)
   - หรือขอให้เปิด Claude ตัวใหม่ในโหมดที่พร้อมตอบกลับ

4. **พิจารณาเพิ่ม Responder ฝั่ง Claude**
   - ถ้า `a2a_local-2` เป็น Claude Code ปกติ อาจต้องใช้ custom `oracle_agent.py` แทน เพื่อให้ตอบอัตโนมัติ

---

## สรุปสั้น ๆ (สำหรับอ้างอิงเร็ว)

> ปัญหาหลักตอนนี้คือ **Grok ส่ง prompt ถึง Claude ได้ แต่ Claude ไม่ตอบกลับเนื้อหา**  
> Claude ส่งแค่ keep-alive (`ack`) ทุก 30 วินาที  
> แหล่งปัญหาน่าจะอยู่ที่ฝั่ง receiver (`a2a_local-2`) ยังไม่ active หรือไม่ถูก configure ให้ตอบกลับอัตโนมัติ

---

**อัพเดทล่าสุด:** 19 พฤษภาคม 2026
```

---

## Debug Update — 19 พฤษภาคม 2026, 23:10 (จากฝั่ง receiver)

**ทำจาก Claude Code session `a2a_local-2` เอง**

### สิ่งที่ตรวจสอบแล้ว

1. **NATS server healthy** — `nats-server -js -m 8222` (pid 78962), JetStream เปิด
2. **MCP plugin `nats-channel` v0.4.0 active** — Bun process 3 ตัว ตาม session:
   - `a2a_local` (instance `TvoAM8ki2V6Szt29lAlY8J`)
   - `a2a_local-2` (instance `T44fp7YEY7No1sXsuL83U2`) — session นี้, pid 89070
   - `psims_daily_data_prep` (instance `jZ21tIyLlFESnPuW9gJHRY`)
3. **Subscriptions ครบตาม Synadia v0.3:**
   - `agents.prompt.cc.terng.a2a_local-2` ✅
   - `agents.status.cc.terng.a2a_local-2` ✅
   - `agents.hb.cc.terng.a2a_local-2` ✅ (heartbeat ทุก 5s)
4. **Service info ตอบปกติ** — `nats req '$SRV.INFO.agents' ''` ได้ metadata ครบทั้ง 3 sessions
5. **Config:** `~/.claude/channels/nats/config.json` = `{"context":"local"}` (permissions = terminal default)

### ผลทดสอบจริง (ส่งหา a2a_local-2 ตัวเอง)

```bash
# Test: nats req มี reply subject _INBOX.xxx
nats req agents.prompt.cc.terng.a2a_local-2 'PING-REQ' --timeout=6s --replies=0
# → ข้อความถึง subject พร้อม reply "_INBOX.m6N7...eGxR2RgH"
# → ไม่มี ack chunk, ไม่มี response chunk กลับมาเลย
```

ระหว่างทดสอบเห็น `{"type":"status","data":"ack"}` เข้า `_INBOX.agents.*` (ของ Synadia SDK requester อื่น) แต่ไม่เข้า inbox ของ request เรา

### Root Cause ที่อัพเดทใหม่

ตามสเปก v0.3 (จาก plugin README): ack 30s จะส่งเมื่อ MCP server "**accept & open**" request เข้า session แล้ว → ถ้าไม่มี ack แม้แต่ครั้งเดียว แปลว่า **MCP bridge ไม่ได้ inject prompt เข้า session**

**สาเหตุที่เป็นไปได้สูงสุด:**
1. **Session busy → bridge queue ค้าง** — เมื่อ Claude turn กำลังรัน (เช่น Bash) prompt ที่เข้ามาจะค้างอยู่ ไม่ ack
2. **MCP server inject แต่ Claude ไม่ตอบ** — Claude เห็นเป็น user message แต่ตอบไป non-NATS (ไม่เรียก `reply` tool พร้อม `request_id`)
3. **Bug ใน nats-channel v0.4.0** — อาจต้อง update

### Action Items (refined)

1. **ดู stderr log ของ Bun MCP server pid 89070** — หา error ตอน inject
2. **เปิด Claude session ใหม่ที่ idle จริง ๆ** — ให้ Grok ส่งมา ดู ack
3. **`/plugin update nats-channel@synadia-plugins`** — เช็ค bugfix
4. **ลอง `/nats-channel:configure permissions query`** — ดูว่าโหมด query ทำให้ตอบได้ไหม
5. **อ่าน source code MCP server** ที่ `~/.claude/plugins/cache/synadia-plugins/nats-channel/0.4.0/`

### สรุปสั้น (อัพเดท)

> ปัญหาไม่ใช่ "Claude ไม่ตอบ" แต่เป็น "**MCP nats-channel bridge ของ `a2a_local-2` ไม่ accept request เข้า session**" (ไม่มีแม้แต่ ack chunk)
> หลักฐาน: ส่ง `nats req` ตรง ๆ จาก CLI ก็ไม่ได้ ack 30s ตอบกลับ ทั้ง ๆ ที่ subscription/heartbeat ปกติ
> ทิศทางถัดไป: ดู Bun stderr log, ลอง session idle, หรือ update plugin

**อัพเดทล่าสุด:** 19 พฤษภาคม 2026, 23:10
