# Grok NATS Integration Guide

**วันที่:** 19 พฤษภาคม 2026
**วัตถุประสงค์:** อธิบายวิธีทำให้ Grok (ผ่าน Hermes Agent) เชื่อมต่อกับ NATS เพื่อคุยกับ Claude Code

---

## 1. Grok ผ่าน Hermes Agent คืออะไร

**Hermes Agent** เป็น CLI AI Agent ที่คุณกำลังใช้อยู่ตอนนี้ โดยมีคุณสมบัติ:

- รองรับหลายโมเดล (Grok, Gemini, Claude, etc.)
- มี tools และ skills มากมาย
- สามารถรันคำสั่ง terminal, เขียนไฟล์, ค้นหาข้อมูล
- ใช้ profile ต่าง ๆ (`local`, `alice`)
- ปัจจุบันใช้ `gemini-flash-latest` เป็น default model

**การทำให้ Grok คุยกับ Claude Code ผ่าน NATS:**

เนื่องจาก Hermes Agent เป็น Python-based CLI เราสามารถเพิ่ม NATS integration ได้หลายวิธี

---

## 2. แนวทางการ Integrate Hermes กับ NATS

### 2.1 วิธีที่ 1: สร้าง Skill สำหรับ NATS (แนะนำ)

สร้าง skill ใหม่ใน Hermes ที่ให้ Hermes สามารถ:
- เชื่อมต่อ NATS
- ส่งข้อความไปยัง Claude Code
- รับข้อความจาก Claude Code

**โครงสร้าง skill:**

```
~/.hermes/profiles/alice/skills/
├── nats-agent/
│   ├── SKILL.md
│   ├── nats_client.py
│   └── agent_wrapper.py
```

### 2.2 วิธีที่ 2: สร้าง MCP Server สำหรับ Hermes

เนื่องจาก Hermes รองรับ MCP อยู่แล้ว เราสามารถ:
- สร้าง MCP Server ที่เชื่อม NATS
- ให้ Hermes โหลด MCP Server นี้
- Hermes สามารถเรียก tools ผ่าน MCP เพื่อส่งข้อความ

### 2.3 วิธีที่ 3: Wrapper Script แยก

เขียน Python script แยกที่:
- ทำงานเป็น daemon หรือ background process
- เชื่อมต่อ NATS
- รับข้อความและส่งต่อให้ Hermes ประมวลผล
- ส่งผลลัพธ์กลับผ่าน NATS

---

## 3. วิธีที่ 1: สร้าง NATS Skill สำหรับ Hermes (แนะนำที่สุด)

### 3.1 สร้างไฟล์ Skill

**ไฟล์:** `~/.hermes/profiles/alice/skills/nats-agent/SKILL.md`

```yaml
---
name: nats-agent
description: NATS messaging for Agent-to-Agent communication
category: messaging
---

# NATS Agent Skill

This skill enables Hermes Agent to communicate with other AI agents via NATS messaging system.

## Usage

```python
from nats_agent import NATSAgent

# Create agent
agent = NATSAgent("grok")

# Connect to NATS
await agent.connect()

# Send message to Claude
response = await agent.send_to("claude", "ช่วยวิเคราะห์โค้ดนี้ให้หน่อย")

# Broadcast to all agents
await agent.broadcast("Hello everyone!")
```

## Configuration

Set environment variables:
- `NATS_URL`: NATS server URL (default: nats://localhost:4222)
```

### 3.2 โค้ด Implementation

**ไฟล์:** `nats_client.py`

```python
import asyncio
import json
import os
from typing import Optional, Callable
from nats.aio.client import Client as NATS

class NATSAgent:
    def __init__(self, name: str, nats_url: str = None):
        self.name = name
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
        self.nc: Optional[NATS] = None
        self.message_handlers = {}
        
    async def connect(self):
        """เชื่อมต่อกับ NATS"""
        self.nc = NATS()
        await self.nc.connect(self.nats_url)
        print(f"[{self.name}] Connected to NATS at {self.nats_url}")
        
        # Subscribe ไปที่ inbox ของตัวเอง
        inbox = f"agent.{self.name}.inbox"
        await self.nc.subscribe(inbox, cb=self._handle_message)
        print(f"[{self.name}] Listening on {inbox}")
    
    async def _handle_message(self, msg):
        """จัดการข้อความที่เข้ามา"""
        try:
            data = json.loads(msg.data.decode())
        except:
            data = {"content": msg.data.decode(), "type": "text"}
        
        from_agent = data.get("from", "unknown")
        content = data.get("content", "")
        msg_type = data.get("type", "query")
        session_id = data.get("session_id")
        
        print(f"[{self.name}] Received from {from_agent}: {content[:100]}...")
        
        # เรียก handler
        if msg_type in self.message_handlers:
            response = await self.message_handlers[msg_type](content, session_id, from_agent)
        else:
            response = await self.default_handler(content, session_id, from_agent)
        
        # ส่งตอบกลับ
        if msg.reply:
            reply_data = {
                "from": self.name,
                "to": from_agent,
                "session_id": session_id,
                "content": response,
                "type": "response"
            }
            await msg.respond(json.dumps(reply_data).encode())
    
    async def default_handler(self, content: str, session_id: str, from_agent: str) -> str:
        """Handler เริ่มต้น - ให้ override หรือ register handler"""
        return f"[{self.name}] Received your message: {content}"
    
    def register_handler(self, msg_type: str, handler: Callable):
        """ลงทะเบียน handler สำหรับ message type"""
        self.message_handlers[msg_type] = handler
    
    async def send_to(self, target: str, content: str, session_id: str = None, timeout: float = 30.0) -> Optional[str]:
        """ส่งข้อความไปยัง agent อื่น"""
        subject = f"agent.{target}.inbox"
        
        message = {
            "from": self.name,
            "to": target,
            "session_id": session_id,
            "content": content,
            "type": "query"
        }
        
        try:
            response = await self.nc.request(
                subject,
                json.dumps(message).encode(),
                timeout=timeout
            )
            reply_data = json.loads(response.data.decode())
            return reply_data.get("content")
        except Exception as e:
            print(f"[{self.name}] Error: {e}")
            return None
    
    async def broadcast(self, content: str, session_id: str = None):
        """ส่งข้อความถึงทุก agent"""
        message = {
            "from": self.name,
            "to": "all",
            "session_id": session_id,
            "content": content,
            "type": "broadcast"
        }
        await self.nc.publish("agent.broadcast", json.dumps(message).encode())
    
    async def close(self):
        """ปิดการเชื่อมต่อ"""
        if self.nc:
            await self.nc.close()
```

### 3.3 วิธีใช้งานใน Hermes

**ใน Hermes Agent:**

```python
# Load skill
from skills.nats_agent import NATSAgent

# สร้าง agent
grok = NATSAgent("grok")

# เชื่อมต่อ
await grok.connect()

# ส่งข้อความหา Claude
response = await grok.send_to(
    target="claude",
    content="ช่วยวิเคราะห์โค้ดนี้ให้หน่อย",
    session_id="sess_001"
)

print(f"Claude ตอบ: {response}")

# ปิดการเชื่อมต่อ
await grok.close()
```

---

## 4. วิธีที่ 2: ใช้ MCP Server

### 4.1 สร้าง MCP Server สำหรับ NATS

เนื่องจาก Hermes รองรับ MCP เราสามารถสร้าง MCP Server ที่ให้ Hermes เรียกใช้ NATS ได้

**ข้อดี:**
- ใช้มาตรฐาน MCP
- Hermes สามารถโหลด MCP Server ได้โดยอัตโนมัติ
- สามารถใช้ร่วมกับ Claude Code ได้

**วิธีสร้าง:**
- ใช้ MCP Python SDK หรือ TypeScript SDK
- Register tools: `send_to_agent`, `broadcast_message`, `get_agent_status`

---

## 5. วิธีที่ 3: Background Daemon

### 5.1 สร้าง Daemon Script

**ไฟล์:** `nats_daemon.py`

```python
import asyncio
import sys
from nats_client import NATSAgent

class GrokNATSDaemon:
    def __init__(self):
        self.agent = NATSAgent("grok")
        
    async def start(self):
        await self.agent.connect()
        
        # Register custom handlers
        self.agent.register_handler("query", self.handle_query)
        self.agent.register_handler("code_review", self.handle_code_review)
        
        # รอ forever
        await asyncio.Event().wait()
    
    async def handle_query(self, content, session_id, from_agent):
        # เรียก Hermes/Grok เพื่อประมวลผล
        # สามารถใช้ Hermes tools หรือเรียก LLM API
        response = f"Grok processed: {content}"
        return response
    
    async def handle_code_review(self, content, session_id, from_agent):
        # Logic สำหรับ code review
        return f"Code review result for: {content}"

if __name__ == "__main__":
    daemon = GrokNATSDaemon()
    asyncio.run(daemon.start())
```

### 5.2 รันเป็น Background Process

```bash
# รัน daemon ใน background
python nats_daemon.py &

# หรือใช้ nohup
nohup python nats_daemon.py > nats_daemon.log 2>&1 &
```

---

## 6. การกำหนดค่า (Configuration)

### 6.1 Environment Variables

```bash
# NATS Server URL
export NATS_URL="nats://localhost:4222"

# Agent Name
export AGENT_NAME="grok"

# Session Timeout (seconds)
export SESSION_TIMEOUT="30"

# Log Level
export LOG_LEVEL="INFO"
```

### 6.2 Hermes Config

เพิ่มใน Hermes config:

```yaml
# ~/.hermes/config.yaml
nats:
  url: "nats://localhost:4222"
  agent_name: "grok"
  auto_connect: true
  timeout: 30
```

---

## 7. ขั้นตอนการ Implement

### Phase 1: ทดสอบพื้นฐาน
1. ติดตั้ง NATS Server
2. สร้าง `nats_client.py`
3. ทดสอบส่ง/รับข้อความระหว่าง 2 Python scripts

### Phase 2: Integrate กับ Hermes
1. สร้าง skill `nats-agent`
2. ทดสอบจากภายใน Hermes
3. ส่งข้อความหา Claude Code (ที่รันผ่าน MCP)

### Phase 3: Production Ready
1. เพิ่ม error handling และ reconnect
2. เพิ่ม logging และ monitoring
3. เพิ่ม session management
4. ทดสอบการทำงานแบบ end-to-end

---

## 8. ตัวอย่างการใช้งาน End-to-End

```python
# ตัวอย่างการใช้งานใน Hermes

from skills.nats_agent import NATSAgent
import asyncio

async def main():
    # สร้าง Grok agent
    grok = NATSAgent("grok")
    await grok.connect()
    
    # ส่งข้อความหา Claude
    print("Grok: ส่งข้อความหา Claude...")
    response = await grok.send_to(
        target="claude",
        content="ช่วยเขียน unit test สำหรับฟังก์ชันนี้ให้หน่อย",
        session_id="code_review_001"
    )
    
    print(f"Claude ตอบกลับ: {response}")
    
    # Broadcast ไปทุก agent
    await grok.broadcast("Grok กำลังทำงานอยู่")
    
    await grok.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 9. Troubleshooting

| ปัญหา | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| ไม่สามารถเชื่อมต่อ NATS | Server ไม่รัน | รัน `nats-server -js` |
| Timeout เมื่อส่งข้อความ | Claude ไม่ตอบกลับ | เพิ่ม timeout หรือตรวจสอบ Claude |
| ข้อความไม่ถึง | Subject ผิด | ตรวจสอบ subject pattern |
| Reconnect บ่อย | Network ไม่เสถียร | เพิ่ม reconnect logic |

---

## 10. สรุป

**วิธีที่ดีที่สุดสำหรับ Grok (Hermes):**

1. **สร้าง NATS Skill** สำหรับ Hermes (วิธีที่ 1)
2. Skill นี้ให้ Hermes สามารถส่ง/รับข้อความผ่าน NATS
3. ใช้ร่วมกับ MCP Server ที่ Claude Code โหลดได้
4. หรือรันเป็น background daemon

**ข้อดีของวิธีนี้:**
- ใช้ Hermes tools และ skills ที่มีอยู่แล้ว
- สามารถขยายได้ง่าย
- ใช้มาตรฐานเดียวกับ Claude Code (MCP)

---

*เอกสารนี้จัดทำขึ้นเพื่ออธิบายวิธีทำให้ Grok ผ่าน Hermes Agent เชื่อมต่อกับ NATS*