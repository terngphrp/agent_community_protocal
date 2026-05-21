---
name: a2a-talk-to
description: Send messages or delegate tasks to another AI agent (Grok, Claude Code, or Codex) running in a different A2A session. Supports both human use and agent-initiated cross-session communication.
argument-hint: "[prompt] [--from agent@session] [--to agent@session] [--list] [--workspace path]"
---

# a2a-talk-to — Cross-Session Communication (Grok / Claude / Codex)

**Goal**: ให้ Grok ที่กำลังรันอยู่ (หรือผู้ใช้) สามารถพูดคุย / ส่งงาน / ขอความช่วยเหลือ กับ Grok อีกตัวที่กำลังรันอยู่ใน session อื่นได้อย่างสะดวกและปลอดภัย ผ่าน CLI

## หลักการออกแบบ (MVP)

- **User tells → Approve → Auto**: ผู้ใช้หรือ Grok บอกเป้าหมาย → ระบบแสดงรายชื่อ session ที่ active → ผู้ใช้ approve → ส่งงาน
- เน้นประสบการณ์ผ่าน **CLI** เป็นหลัก (ทั้งมนุษย์และ Grok สามารถเรียกใช้ได้)
- ใช้โครงสร้าง A2A เดิม (NATS + discovery)
- Default ใช้ sandbox แบบ restrictive
- มี logging ที่ชัดเจน

## เมื่อไหร่ควรใช้

- ต้องการให้ Grok สองตัวที่กำลังทำงานคนละเรื่อง coordinate กัน
- อยากส่งงานจาก session ปัจจุบันไปยัง session อื่น (เช่น daily-review, long-running-task, another feature)
- อยากให้ Grok ตัวหนึ่งอัพเดทหรือขอความเห็นจาก Grok ตัวอื่นโดยไม่รบกวน workflow หลัก

## วิธีใช้

### 1. แบบ Interactive (แนะนำสำหรับมนุษย์)

```bash
a2a-talk-to "ช่วยรีวิวแผนงาน feature ใหม่ให้หน่อย" --workspace .
```

ระบบจะ:
- ค้นหา agents ที่ active อยู่ทุก session
- แสดงรายชื่อ
- ให้เลือก source และ target
- ให้ approve แล้วส่งงาน

### 2. แบบ Non-Interactive (ดีสำหรับ Grok และ scripting)

```bash
a2a-talk-to "ส่งสรุปงานวันนี้ไปให้ตัวที่ session daily-review ด้วย" \
  --from grok@feature-x \
  --to grok@daily-review \
  --workspace /path/to/project \
  --json
```

### 3. ดู sessions ที่กำลัง active อยู่

```bash
a2a-talk-to --list
a2a-talk-to --list --owner terng
```

## พารามิเตอร์สำคัญ

| Parameter       | คำอธิบาย                                      | ตัวอย่าง                     |
|-----------------|-----------------------------------------------|-----------------------------|
| `prompt`        | ข้อความหรืองานที่ต้องการส่ง                   | "ช่วยรีวิวโค้ดส่วนนี้"       |
| `--from`        | ตัวส่ง (agent@session)                        | `grok@feature-auth`         |
| `--to`          | ตัวรับ (agent@session)                        | `grok@daily-review`         |
| `--list`        | แสดงรายชื่อ agents ที่ active อยู่ทุก session | -                           |
| `--workspace`   | โฟลเดอร์โปรเจกต์                             | `.` หรือ path เต็ม          |
| `--json`        | คืนค่าแบบ machine-readable (เหมาะกับ Grok)    | -                           |

## สำหรับ Grok (Agent Use)

Grok สามารถเรียก skill นี้ได้โดยตรง เช่น:

> "ช่วยส่งงาน refactor ไฟล์ `auth.py` ไปให้ Grok ตัวที่ session `refactor-pipeline` ด้วย"

จากนั้น Grok สามารถเรียกสคริปต์แบบ non-interactive พร้อม `--json` และ parse ผลลัพธ์กลับมาใช้ต่อได้

## ความแตกต่างจาก `a2a-cross-session`

| คุณสมบัติ              | a2a-cross-session          | a2a-talk-to (ใหม่)                  |
|------------------------|----------------------------|-------------------------------------|
| เป้าหมายหลัก           | Human interactive          | Human + Grok (CLI-first)           |
| UX                     | Interactive menu หนัก     | เรียบง่าย + ดีสำหรับ agent         |
| Non-interactive        | ทำได้ แต่ไม่ค่อยเน้น      | เน้นและทำให้สะอาด                  |
| การ integrate กับ Grok | ยาก                        | ออกแบบมาเพื่อให้ Grok เรียกได้ง่าย  |
| Logging                | พื้นฐาน                   | ดีขึ้น (มี intent ชัดเจน)           |

## ตัวอย่างการทำงานจริง (MVP)

1. ผู้ใช้รัน Grok ใน session `feature-x`
2. พิมพ์: `ช่วยส่งงานนี้ไปให้ตัวที่ session daily-review ด้วย`
3. Grok เรียก `a2a-talk-to` แบบ non-interactive
4. ระบบค้นหา → พบ `grok@daily-review` → ส่งงาน → ได้คำตอบกลับ
5. Grok นำคำตอบกลับมาใช้ต่อ

---

**สถานะปัจจุบัน**: MVP Core เสร็จสมบูรณ์ (A, B, C, D ครบ)

### เอกสารที่เกี่ยวข้อง

- [GROK_INSTRUCTIONS.md](docs/GROK_INSTRUCTIONS.md) — Instruction สำหรับให้ Grok ใช้ skill นี้
- [TESTING.md](docs/TESTING.md) — คู่มือทดสอบ End-to-End
- Wrapper script: `scripts/a2a-talk-to` (เรียกง่ายขึ้น)

เป้าหมายระยะสั้น: ทำให้การคุยข้าม session ผ่าน Grok CLI เป็นเรื่องปกติและน่าใช้ที่สุดเท่าที่จะทำได้ในโครงสร้างปัจจุบัน

---

Related Skills:
- `a2a-consult` — คุยกับ agent ใน session เดียวกันหรือระบุ target-session
- `a2a-cross-session` — เครื่องมือรุ่นเก่า (legacy)
- `discover_agents` — ใช้ตรวจสอบ agents ที่ active อยู่