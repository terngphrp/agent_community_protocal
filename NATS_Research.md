# NATS Research - Agent-to-Agent Protocol

**วันที่วิจัย:** 19 พฤษภาคม 2026
**วัตถุประสงค์:** ศึกษาความเป็นไปได้ในการใช้ NATS เป็น messaging layer สำหรับ Agent-to-Agent Communication (Grok + Claude Code)

---

## 1. NATS คืออะไร

NATS เป็น open-source messaging system ที่ออกแบบมาเพื่อระบบ distributed และ cloud-native โดยเฉพาะ

**จุดเด่นหลัก:**
- Latency ต่ำมาก (sub-millisecond)
- Binary ขนาดเล็ก รันง่าย
- รองรับหลายรูปแบบการสื่อสารในตัวเดียว
- มี client library มากกว่า 45 ภาษา
- ใช้จริงใน production มาหลายปี (บริษัทใหญ่ เช่น NVIDIA, Replit, Uniphore)

---

## 2. Core NATS vs JetStream

### Core NATS
- Pub/Sub แบบดั้งเดิม
- Request/Reply pattern
- At-most-once delivery
- ไม่มี persistence
- Latency ต่ำที่สุด

### JetStream
- Persistence engine ที่ built-in อยู่ใน nats-server
- รองรับ streaming และ replay
- At-least-once หรือ exactly-once delivery
- มี Streams และ Consumers
- Key/Value Store และ Object Store
- เหมาะสำหรับงานที่ต้องการความน่าเชื่อถือสูง

**คำแนะนำสำหรับ Agent-to-Agent:**
- เริ่มด้วย **Core NATS** ก่อน (ง่ายและเร็ว)
- ค่อยเพิ่ม **JetStream** เมื่อต้องการ persistence หรือ queue

---

## 3. รูปแบบการสื่อสารที่เหมาะกับ Agent

### 3.1 Request/Reply (แนะนำที่สุด)
```python
# Agent A ส่งคำถามและรอคำตอบ
response = await nc.request("agent.claude.inbox", payload, timeout=10)
```

**ข้อดี:**
- ตรงกับการสนทนาแบบสองทาง
- มี timeout และ error handling ง่าย
- Agent ทั้งสองไม่ต้องรู้จักกันโดยตรง

### 3.2 Pub/Sub
```python
# ส่งถึงทุก agent
await nc.publish("agent.broadcast", message)

# แต่ละ agent subscribe
await nc.subscribe("agent.grok.inbox", callback=handler)
```

**เหมาะกับ:**
- Broadcast ข่าวสาร
- ส่งงานไปหลาย agent พร้อมกัน

### 3.3 JetStream (ขั้นสูง)
- ใช้เมื่อต้องการเก็บประวัติการสนทนา
- ทำ queue เมื่อ agent ไม่ว่าง
- Replay ข้อความย้อนหลัง

---

## 4. Client Libraries ที่นิยม

| ภาษา | Library | สถานะ |
|------|---------|--------|
| Go | nats.go | Official, ดีที่สุด |
| Python | nats.py | Official, ใช้งานดี |
| TypeScript/JavaScript | nats.ws, nats.js | Official |
| Rust | nats.rs | Official |
| Java | nats.java | Official |
| .NET | nats.net | Official |

**สำหรับโปรเจกต์นี้:**
- Grok → ใช้ **Python** (nats.py)
- Claude Code → ใช้ **Go** หรือ **TypeScript**

---

## 5. ข้อดีของ NATS สำหรับ Agent-to-Agent

1. **Decoupled Architecture**
   - Agent แต่ละตัวไม่ต้องรู้จักกันโดยตรง
   - เพิ่ม/ลด agent ได้ง่าย

2. **หลายรูปแบบในตัวเดียว**
   - Pub/Sub + Request/Reply + KV + Streaming
   - ไม่ต้องติดตั้งหลายระบบ

3. **Performance ดี**
   - Latency ต่ำ เหมาะกับงาน real-time
   - Binary ขนาดเล็ก ใช้ทรัพยากรน้อย

4. **Scalability**
   - เริ่มจาก 2 agent ก็ได้
   - พอมี 10-20 agent ก็ยังใช้ได้ (แค่เพิ่ม cluster)

5. **Deployment ง่าย**
   - Binary เดียว รันด้วยคำสั่งเดียว
   - มี Docker image อย่างเป็นทางการ

---

## 6. ข้อเสียและข้อจำกัด

1. **ต้องออกแบบ Protocol เอง**
   - NATS เป็นแค่ transport layer
   - ต้องกำหนด message format เอง (เช่น JSON schema)

2. **State Management**
   - NATS ไม่เก็บ state ให้
   - ต้องจัดการ session เอง

3. **Error Handling**
   - ต้องจัดการ reconnect, timeout, retry เอง

4. **Debugging ยากกว่า REST**
   - เป็น async messaging
   - ต้องใช้ tool ช่วย monitor

---

## 7. โครงสร้าง Subject ที่แนะนำ

```
agent.{name}.inbox          # แต่ละ agent ฟังข้อความส่วนตัว
agent.broadcast             # ส่งถึงทุก agent
agent.session.{id}          # session เฉพาะ
agent.{name}.status         # สถานะ (online/offline/busy)
agent.{name}.result         # ผลลัพธ์จาก agent
```

**ตัวอย่าง Message Format:**
```json
{
  "session_id": "sess_abc123",
  "from": "grok",
  "to": "claude",
  "type": "query",
  "timestamp": "2026-05-19T14:30:00Z",
  "content": "ช่วยวิเคราะห์โค้ดนี้ให้หน่อย"
}
```

---

## 8. ขั้นตอนการเริ่มต้น (MVP)

1. **ติดตั้ง NATS Server**
   ```bash
   brew install nats-server
   nats-server -js
   ```

2. **ติดตั้ง Client Library**
   ```bash
   pip install nats-py
   go get github.com/nats-io/nats.go
   ```

3. **เขียน Agent Wrapper**
   - สร้าง class/function สำหรับเชื่อมต่อ NATS
   - จัดการ subscribe และ request/reply

4. **ทดสอบการสื่อสาร**
   - Agent A ส่งข้อความหา Agent B
   - Agent B ตอบกลับ

---

## 9. สรุปและคำแนะนำ

**NATS เป็นตัวเลือกที่เหมาะสมมาก** สำหรับ Agent-to-Agent Protocol เพราะ:

- ใช้งานง่ายและเร็ว
- มีหลายรูปแบบการสื่อสารในตัวเดียว
- Scale ได้ทั้งเล็กและใหญ่
- มี community และเอกสารดี

**คำแนะนำ:**
- เริ่มด้วย **Core NATS + Request/Reply** ก่อน
- ค่อยเพิ่ม **JetStream** เมื่อต้องการ persistence
- ออกแบบ message format ให้ชัดเจนตั้งแต่แรก
- ใช้ subject แบบ hierarchical เพื่อให้ง่ายต่อการจัดการ

---

## แหล่งอ้างอิง

- https://docs.nats.io/
- https://nats.io/
- https://github.com/nats-io/nats.py
- https://github.com/nats-io/nats.go

---

*เอกสารนี้จัดทำขึ้นเพื่อใช้เป็นข้อมูลอ้างอิงในการพัฒนา Agent-to-Agent System ด้วย NATS*