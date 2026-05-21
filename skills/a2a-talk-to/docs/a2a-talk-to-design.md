# a2a-talk-to — Near-Automatic Cross-Session & Cross-Agent Design

**Version:** 0.2 (Multi-Agent Support)  
**Date:** 2026-05  
**Status:** Design Phase — Updated for Codex + Claude + Grok

---

## 1. Problem Statement

ปัจจุบันการสื่อสารระหว่าง AI agents ข้าม A2A session ยังต้องระบุชื่อ agent และ session แบบ hardcode ทุกครั้ง (เช่น `grok@session-x`, `codex@session-y`)

ปัญหาหลัก:
- ผู้ใช้และ agent ต้องจำชื่อ session และประเภทของ agent เป้าหมายล่วงหน้า
- ไม่มีขั้นตอนการค้นหา (discover) agents ที่กำลัง active อยู่
- การเลือกเป้าหมายยังไม่เป็นระบบและไม่เหมาะกับการใช้งานแบบ agentic
- Tool ยังจำกัดอยู่ที่ Grok เป็นหลัก ทำให้ Codex และ Claude Code ใช้ cross-session ได้ยาก

**เป้าหมายใหม่**: ทำให้ `a2a-talk-to` เป็น **general-purpose cross-session และ cross-agent relay tool** ที่รองรับทั้ง 3 agents หลักในระบบ ได้แก่:
- `grok`
- `claude-code` (รวม Claude)
- `codex`

---

## 2. Goals (Phase 1)

- **ทุกครั้ง** ที่เรียก tool ต้องเริ่มด้วย **Discover** agents ที่ active อยู่ (ข้ามทุก session และทุกประเภท agent)
- หลังจาก discover แล้ว ต้องมีขั้นตอน **เลือกเป้าหมาย** (Target Selection)
- รองรับการใช้งาน 2 แบบหลัก:
  - **Human Interactive** — มนุษย์เห็นรายชื่อและเลือก
  - **Agentic** — Tool คืนค่า list เป็น JSON เพื่อให้ Grok / Claude / Codex เลือกเอง
- ต่อยอดจากโค้ด `a2a-talk-to` เดิม (ไม่สร้างไฟล์ใหม่)
- ใช้ชื่อ tool เดิมคือ **`a2a-talk-to`** ต่อไป
- ทำให้ tool นี้เป็นช่องทางหลักสำหรับการ "consult" ข้าม session ระหว่างสาม agents

---

## 3. Supported Agents

Tool นี้จะรองรับ agents ต่อไปนี้ (และจะ normalize ชื่อให้อัตโนมัติ):

| ชื่อภายใน (Normalized) | ชื่อที่ยอมรับได้ในคำสั่ง          | หมายเหตุ |
|-------------------------|------------------------------------|----------|
| `grok`                  | grok                               | - |
| `claude-code`           | claude, claude-code                | Claude Code |
| `codex`                 | codex                              | - |

---

## 4. Proposed User Flows

### Flow A: Human Interactive (แนะนำสำหรับเริ่มต้น)

```
เรียก: a2a-talk-to "ข้อความ..." --workspace .
          ↓
Tool ทำ Discovery (ทุก agent + ทุก session)
          ↓
แสดงรายชื่อ agents ที่ active (จัดกลุ่มตามประเภท)
          ↓
ผู้ใช้เลือก Source (ถ้ายังไม่ระบุ) และ Target
          ↓
ยืนยัน + ส่งข้อความ
          ↓
แสดงผลลัพธ์
```

### Flow B: Agentic (Grok / Claude / Codex เรียกเอง)

```
Agent เรียก: a2a-talk-to "..." --json --yes
          ↓
Tool ทำ Discovery
          ↓
คืนค่า JSON รายชื่อ agents ทั้งหมดที่ active
          ↓
Agent อ่านรายชื่อแล้วตัดสินใจเลือกเป้าหมาย
          ↓
Agent เรียก tool อีกรอบด้วยข้อมูลที่เลือก (หรือพัฒนาให้ทำในคำสั่งเดียวใน Phase 2)
```

---

## 5. Command Line Interface (Phase 1)

### โหมดสำคัญที่เพิ่ม/ปรับ

| Flag                  | วัตถุประสงค์ |
|-----------------------|--------------|
| `--list` หรือ `--discover` | แสดง/คืนค่ารายชื่อ agents ที่ active ทั้งหมด (แนะนำใช้ `--json`) |
| (ไม่มี flag)           | เริ่มด้วยการ discover อัตโนมัติ แล้วให้เลือกเป้าหมาย |
| `--from` / `--to`     | ยังคงรองรับสำหรับกรณีที่ต้องการข้ามขั้นตอน discovery |
| `--json`              | สำคัญสำหรับ Agentic use |
| `--yes`               | ข้าม confirmation (เหมาะกับการเรียกจาก agent) |

### ตัวอย่างการใช้งาน

**มนุษย์ใช้ (Interactive):**
```bash
a2a-talk-to "ช่วยรีวิวโค้ดส่วนนี้" --workspace .
```

**Agent ใช้ (Agentic):**
```bash
a2a-talk-to "สรุปงานวันนี้" --json --yes
# ได้ JSON กลับมา → เลือกเป้าหมาย → เรียกใหม่
```

**ข้ามไปยัง Codex โดยตรง (ถ้ารู้ session):**
```bash
a2a-talk-to "เขียน unit test ให้ฟังก์ชันนี้" \
  --from grok@feature-x \
  --to codex@unit-test-session \
  --workspace . \
  --yes
```

---

## 6. JSON Output Format (สำคัญสำหรับ Agentic Use)

### ตัวอย่าง Discovery Result

```json
{
  "ok": true,
  "mode": "discovery",
  "endpoints": [
    {
      "name": "grok",
      "session": "feature-x",
      "spec": "grok@feature-x",
      "owner": "terng"
    },
    {
      "name": "claude-code",
      "session": "daily-review",
      "spec": "claude-code@daily-review",
      "owner": "terng"
    },
    {
      "name": "codex",
      "session": "refactor-branch",
      "spec": "codex@refactor-branch",
      "owner": "terng"
    }
  ]
}
```

### ตัวอย่างเมื่อส่งงานสำเร็จ

```json
{
  "ok": true,
  "from": "grok@feature-x",
  "to": "codex@refactor-branch",
  "response": "ได้เลย ผมช่วยเขียน test ให้..."
}
```

---

## 7. ขอบเขตของ Phase 1

**ทำใน Phase 1:**
- ปรับ `a2a_talk_to.py` ให้รองรับ discovery แบบ multi-agent
- แสดงและคืนค่ารายชื่อ agents ทั้ง 3 ประเภท
- รองรับการเลือกเป้าหมายทั้งแบบ interactive และแบบ JSON
- Normalize ชื่อ agent (เช่น `claude` → `claude-code`)
- อัปเดต documentation และตัวอย่างการใช้งานกับ Codex/Claude

**ยังไม่ทำใน Phase 1:**
- Single-call automatic relay (Grok/Claude/Codex เรียกครั้งเดียวจบ)
- Automatic target selection ด้วย logic
- Persistent memory ระหว่างการส่งหลายรอบ
- การจัดการ error แบบอัตโนมัติหลายรอบ

---

## 8. ตัวอย่าง Use Case ที่รองรับได้หลัง Phase 1

- Grok ส่งงานไปให้ Codex ในอีก session เพื่อเขียนโค้ด
- Claude ส่งงานไปให้ Grok เพื่อขอความเห็นเชิงปรัชญา/เทรดออฟ
- Codex ส่งงานไปให้ Claude เพื่อขอรีวิวความปลอดภัย
- มนุษย์ใช้ tool เดียวเพื่อ consult กับทั้ง 3 ตัว โดยไม่ต้องจำ session

---

## 9. Non-Goals

- ยังไม่เปลี่ยนชื่อ tool (คงใช้ `a2a-talk-to` ต่อไป)
- ยังไม่ทำ full automatic loop ข้าม session ใน Phase 1
- ยังไม่เพิ่ม dependency ใหม่
- ยังไม่เปลี่ยน backend (ยังใช้ `a2a-consult` ภายใน)

---

## 10. ขั้นตอนการพัฒนาที่แนะนำ

1. ปรับฟังก์ชัน discovery ให้รองรับหลายประเภทของ agent
2. ปรับการแสดงผลและ JSON output ให้มีข้อมูล `name` ชัดเจน
3. เพิ่มการ normalize ชื่อ agent
4. ปรับ flow หลักให้เริ่มด้วย discovery เสมอ (ถ้าไม่ได้ระบุ `--from`/`--to`)
5. เขียนตัวอย่างการใช้งานกับ Codex และ Claude
6. อัปเดต `SKILL.md` และ `GROK_INSTRUCTIONS.md` (และเพิ่ม Claude/Codex instructions ถ้าจำเป็น)

---

## 11. คำถามเปิด (สำหรับ Phase 2 เป็นต้นไป)

- อยากมีโหมด `--auto-select` ที่ให้ tool เลือกเป้าหมายอัตโนมัติตามเงื่อนไข (เช่น เลือกตัวที่ว่างที่สุด หรือตามชื่อ pattern) หรือไม่?
- อยากพัฒนาให้ `a2a-talk-to` สามารถทำหลายรอบในคำสั่งเดียว (เช่น สำหรับ ping-pong หรือ consultation แบบต่อเนื่อง) ใน Phase 2 หรือไม่?
- ควรมี "preferred agent" หรือ "last used session" เก็บไว้เพื่อลดขั้นตอนการเลือกซ้ำหรือไม่?

---

**เอกสารนี้เป็นเวอร์ชันที่ปรับปรุงใหม่เพื่อรองรับการ consult กับ Codex และ Claude อย่างเต็มรูปแบบ**

พร้อมสำหรับการ review และเริ่มพัฒนา Phase 1

---

**ผู้เขียน:** Grok  
**ไฟล์ที่เกี่ยวข้อง:**
- `skills/a2a-talk-to/scripts/a2a_talk_to.py`
- `skills/a2a-talk-to/SKILL.md`