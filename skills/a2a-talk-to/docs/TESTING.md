# Testing Guide for a2a-talk-to (End-to-End)

## Prerequisites

- NATS server running (`nats-server -js`)
- อย่างน้อย 2 Grok (หรือ agent) instances ที่รันอยู่คนละ session
- Python dependencies ครบ (จาก a2a_local)

ตัวอย่างการรัน Grok สองตัวในสอง session:

```bash
# Terminal 1 - Session A
grok --session feature-x

# Terminal 2 - Session B
grok --session daily-review
```

---

## Test Cases

### 1. Basic Discovery (`--list`)

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py --list
```

**Expected:**
- เห็น agents จากทั้งสอง session
- แสดงเป็นตารางชัดเจน

### 2. Interactive Flow (Human)

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py "ทดสอบส่งข้อความข้าม session" --workspace .
```

**Expected Flow:**
1. แสดงรายชื่อ agents
2. ให้เลือก source
3. ให้เลือก target
4. แสดงสรุปชัดเจน
5. ขอ approve
6. ส่งงานและได้คำตอบกลับ

### 3. Direct Non-Interactive (สำคัญสำหรับ Grok)

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py \
  "ช่วยสรุปงานวันนี้ให้หน่อย" \
  --from grok@feature-x \
  --to grok@daily-review \
  --workspace . \
  --json \
  --yes
```

**Expected:**
- ส่งงานได้โดยไม่ต้อง interactive
- คืนค่าเป็น JSON ที่อ่านง่าย

### 4. Back / Cancel Flow

ในโหมด interactive ให้ทดสอบ:
- พิมพ์ `back` ตอนเลือก target → ควรย้อนกลับไปเลือก source ใหม่
- พิมพ์ `cancel` → ควรยกเลิกการทำงาน

### 5. JSON Mode

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py --list --json
```

ควรได้ output เป็น JSON ที่ parse ได้

---

## End-to-End Scenario (แนะนำ)

1. เปิด Grok 2 ตัวใน 2 session ต่างกัน
2. ใน session A ให้ Grok พิมพ์ว่า:
   > "ช่วยส่งข้อความไปให้ Grok ตัวที่ session daily-review ว่า 'วันนี้ฉันทำ feature login เสร็จแล้ว' ด้วย"

3. Grok ควรเรียก `a2a-talk-to` ด้วยพารามิเตอร์ที่เหมาะสม
4. ตรวจสอบว่า Grok ใน session B ได้รับข้อความ
5. ตรวจสอบ log / transcript ว่ามีการสื่อสารข้าม session เกิดขึ้น

---

## Known Limitations (MVP)

- ยังต้องระบุ `--from` ด้วยตัวเอง (Grok ควรรู้ session ของตัวเอง)
- ยังไม่มี persistent memory ระหว่างการเรียกหลายครั้ง
- ยังไม่มี human approval บังคับสำหรับทุกการส่ง (ยกเว้น interactive mode)

---

## Tips สำหรับการทดสอบ

- ใช้ `--yes` เมื่อทดสอบซ้ำบ่อย ๆ เพื่อไม่ให้ติดขัดที่ approve
- ใช้ `--json` + pipe ไป `jq` เพื่อ debug
- เปิดหลาย terminal พร้อมกันเพื่อจำลองหลาย session

ตัวอย่างคำสั่ง debug:

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py --list --json | jq .
```