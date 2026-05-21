# Grok Instructions for a2a-talk-to

**Purpose**: ให้ Grok สามารถใช้ skill `a2a-talk-to` เพื่อสื่อสารกับ Grok (หรือ agent) อื่นที่กำลังรันอยู่ใน A2A session ต่างกันได้

---

## Core Principle

เมื่อคุณ (Grok) รู้สึกว่าตัวเองต้องการข้อมูล ความเห็น หรือต้องการมอบหมายงานบางอย่างให้กับ Grok ตัวอื่นที่กำลังทำงานใน session ต่างกัน คุณควรใช้ `a2a-talk-to` แทนการพยายามทำเองทั้งหมด

---

## เมื่อไหร่ควรใช้ a2a-talk-to

- คุณกำลังทำงานอยู่ session หนึ่ง (เช่น `feature-auth`) และรู้ว่ามี Grok อีกตัวกำลังทำงานใน session `daily-review` หรือ `refactor-pipeline`
- งานที่ต้องการทำจะดีขึ้นถ้าได้ความเห็นจากอีก session
- คุณต้องการอัพเดทสถานะ หรือขอให้อีกตัวช่วยทำบางอย่างต่อ
- คุณไม่อยากรบกวน human ด้วยงานเล็ก ๆ น้อย ๆ ที่อีก Grok สามารถช่วยได้

---

## วิธีเรียกใช้ (สำหรับ Grok)

### วิธีที่แนะนำที่สุด (Non-interactive + JSON)

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py \
  "สรุปสถานะงานวันนี้แล้วส่งไปให้ Grok ตัวที่ session daily-review ด้วย" \
  --from grok@CURRENT_SESSION \
  --to grok@TARGET_SESSION \
  --workspace . \
  --json \
  --yes
```

### วิธีเรียกแบบยืดหยุ่น (ให้ระบบช่วยค้นหา)

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py \
  "ช่วยรีวิวแผนงาน feature ใหม่ให้หน่อย" \
  --workspace . \
  --json \
  --yes
```

(ในกรณีนี้ Grok อาจต้อง parse ผลลัพธ์และเลือก target เอง หรือขอให้ human ช่วยเลือก)

---

## วิธีที่ดีที่สุดในการใช้จากภายใน Grok

### 1. รู้จัก session ของตัวเองก่อน

ก่อนจะส่งข้อความ คุณควรรู้ว่า **session ปัจจุบันของคุณคืออะไร**

ตัวอย่าง:
- ถ้าคุณถูกเปิดด้วย `--session feature-auth` → คุณคือ `grok@feature-auth`
- คุณสามารถบอก human ว่า "ฉันคือ grok@feature-auth"

### 2. ค้นหาว่ามี session อื่น active อยู่หรือไม่

ก่อนส่งงานจริง ควรเรียกก่อน:

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py --list --json
```

แล้ว parse ผลลัพธ์เพื่อดูว่า session ไหนกำลัง active อยู่

### 3. ส่งข้อความ

ใช้รูปแบบคำสั่งที่ชัดเจน:

```bash
python skills/a2a-talk-to/scripts/a2a_talk_to.py \
  "<ข้อความหรืองานที่ต้องการส่ง>" \
  --from grok@<session-ปัจจุบันของคุณ> \
  --to grok@<session-เป้าหมาย> \
  --workspace <path> \
  --json \
  --yes
```

### 4. รับผลลัพธ์และนำไปใช้ต่อ

สคริปต์จะคืนค่าเป็น JSON แบบนี้:

```json
{
  "ok": true,
  "response": "...คำตอบจาก Grok ตัวอื่น..."
}
```

คุณสามารถนำ `response` ไปใช้ต่อได้ทันที

---

## ตัวอย่าง Prompt ที่ดี (ที่ Grok สามารถใช้เองได้)

### ตัวอย่างที่ 1: ส่งงานแบบตรง

> "ฉันต้องการให้ Grok ตัวที่ session daily-review ช่วยสรุปสถานะงานวันนี้ให้มนุษย์ด้วย ช่วยส่งข้อความนี้ไปให้หน่อย:
> 'วันนี้ฉันทำ feature login เสร็จแล้ว และเจอปัญหาเรื่อง rate limiting ช่วยสรุปสถานะให้มนุษย์ด้วยนะ'"

จากนั้นคุณเรียกสคริปต์ตามรูปแบบด้านบน

### ตัวอย่างที่ 2: ขอความเห็น

> "ฉันกำลังออกแบบ architecture ใหม่ อยากได้ความเห็นจาก Grok ตัวที่ session architecture-review ช่วยส่งสเปกคร่าว ๆ ไปให้และขอความเห็นหน่อย"

---

## ข้อควรระวัง

- อย่า spam การส่งข้าม session บ่อยเกินไป
- ใช้ `--workspace` ให้ถูกต้องเสมอ (โดยเฉพาะถ้าต้องการให้อีกตัวแก้ไขไฟล์)
- ถ้าไม่แน่ใจว่า session เป้าหมายคืออะไร ให้เรียก `--list` ก่อน
- ใช้ `--yes` เมื่อคุณมั่นใจว่าต้องการส่งจริง (เหมาะกับการเรียกอัตโนมัติ)

---

## ตัวอย่างคำสั่งที่แนะนำให้ Grok ใช้บ่อย

```bash
# ดู sessions ที่ active
python skills/a2a-talk-to/scripts/a2a_talk_to.py --list --json

# ส่งงานตรง ๆ
python skills/a2a-talk-to/scripts/a2a_talk_to.py "..." \
  --from "grok@<your-session>" \
  --to "grok@<target-session>" \
  --workspace . \
  --json --yes
```

---

**สรุป**: คุณ (Grok) สามารถและควรใช้ `a2a-talk-to` เป็นเครื่องมือสื่อสารกับ Grok ตัวอื่นในระบบได้อย่างเต็มที่ เช่นเดียวกับที่คุณใช้ tool อื่น ๆ

เป้าหมายคือให้หลาย ๆ Grok instances สามารถทำงานร่วมกันได้ดี โดยไม่ต้องให้มนุษย์เป็นคนประสานงานทุกครั้ง