# NATS Implementation Guide สำหรับ Agent-to-Agent

**วันที่:** 19 พฤษภาคม 2026
**วัตถุประสงค์:** ให้ข้อมูลและโค้ดตัวอย่างพอที่จะนำไป implement จริงได้

---

## 1. การติดตั้งและเริ่มต้น

### 1.1 ติดตั้ง NATS Server

```bash
# macOS
brew install nats-server

# หรือดาวน์โหลด binary
curl -sf https://binaries.nats.dev/nats-io/nats-server/v2@latest | sh

# รัน server
nats-server -js
```

### 1.2 ติดตั้ง Python Client

```bash
pip install nats-py
```

---

## 2. ตัวอย่างโค้ดพื้นฐาน

### 2.1 เชื่อมต่อกับ NATS

```python
import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

async def connect_nats():
    nc = NATS()
    
    try:
        await nc.connect("nats://localhost:4222")
        print("Connected to NATS")
        return nc
    except ErrNoServers as e:
        print(f"Could not connect: {e}")
        return None

# ใช้งาน
# nc = await connect_nats()
```

### 2.2 ส่งข้อความ (Publish)

```python
async def send_message(nc, subject: str, message: str):
    """ส่งข้อความแบบ fire-and-forget"""
    await nc.publish(subject, message.encode())
    print(f"Sent to {subject}: {message}")

# ตัวอย่าง
# await send_message(nc, "agent.claude.inbox", "Hello Claude!")
```

### 2.3 รับข้อความ (Subscribe)

```python
async def message_handler(msg):
    """Callback สำหรับรับข้อความ"""
    subject = msg.subject
    data = msg.data.decode()
    print(f"Received on {subject}: {data}")
    
    # สามารถตอบกลับได้ถ้ามี reply subject
    if msg.reply:
        await msg.respond(b"Got your message!")

async def subscribe_to_subject(nc, subject: str):
    """Subscribe แบบ asynchronous"""
    sid = await nc.subscribe(subject, cb=message_handler)
    print(f"Subscribed to {subject}")
    return sid

# ตัวอย่าง
# await subscribe_to_subject(nc, "agent.grok.inbox")
```

### 2.4 Request/Reply Pattern (แนะนำ)

```python
async def send_request(nc, subject: str, message: str, timeout: float = 5.0):
    """ส่งข้อความและรอคำตอบ"""
    try:
        response = await nc.request(
            subject, 
            message.encode(), 
            timeout=timeout
        )
        return response.data.decode()
    except ErrTimeout:
        print(f"Request to {subject} timed out")
        return None

async def reply_handler(msg):
    """Handler สำหรับตอบกลับ request"""
    data = msg.data.decode()
    print(f"Received request: {data}")
    
    # ตอบกลับ
    response = f"Processed: {data}"
    await msg.respond(response.encode())

async def setup_responder(nc, subject: str):
    """ตั้งค่า responder สำหรับ request/reply"""
    await nc.subscribe(subject, cb=reply_handler)
    print(f"Responder ready on {subject}")
```

---

## 3. โครงสร้าง Agent Wrapper

### 3.1 Agent Base Class

```python
import asyncio
from nats.aio.client import Client as NATS
from typing import Callable, Optional
import json

class NATSAAgent:
    def __init__(self, name: str, nats_url: str = "nats://localhost:4222"):
        self.name = name
        self.nats_url = nats_url
        self.nc: Optional[NATS] = None
        self.session_handlers = {}
        
    async def connect(self):
        """เชื่อมต่อกับ NATS"""
        self.nc = NATS()
        await self.nc.connect(self.nats_url)
        print(f"[{self.name}] Connected to NATS")
        
        # Subscribe ไปที่ inbox ของตัวเอง
        inbox = f"agent.{self.name}.inbox"
        await self.nc.subscribe(inbox, cb=self._handle_incoming)
        print(f"[{self.name}] Listening on {inbox}")
    
    async def _handle_incoming(self, msg):
        """จัดการข้อความที่เข้ามา"""
        try:
            data = json.loads(msg.data.decode())
        except json.JSONDecodeError:
            data = {"content": msg.data.decode(), "type": "text"}
        
        msg_type = data.get("type", "query")
        content = data.get("content", "")
        session_id = data.get("session_id")
        from_agent = data.get("from", "unknown")
        
        print(f"[{self.name}] Received from {from_agent}: {content}")
        
        # เรียก handler ถ้ามี
        if msg_type in self.session_handlers:
            response = await self.session_handlers[msg_type](content, session_id)
        else:
            response = await self.default_handler(content, session_id)
        
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
    
    async def default_handler(self, content: str, session_id: str = None) -> str:
        """Handler เริ่มต้น (ให้ override)"""
        return f"[{self.name}] Received: {content}"
    
    def register_handler(self, msg_type: str, handler: Callable):
        """ลงทะเบียน handler สำหรับ message type"""
        self.session_handlers[msg_type] = handler
    
    async def send_to(self, target: str, content: str, session_id: str = None) -> Optional[str]:
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
                timeout=30.0
            )
            reply_data = json.loads(response.data.decode())
            return reply_data.get("content")
        except Exception as e:
            print(f"[{self.name}] Error sending to {target}: {e}")
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
            print(f"[{self.name}] Disconnected")
```

### 3.2 ตัวอย่างการใช้งาน

```python
import asyncio

class GrokAgent(NATSAAgent):
    def __init__(self):
        super().__init__("grok")
    
    async def default_handler(self, content: str, session_id: str = None) -> str:
        # ที่นี่คือที่ที่ Grok จะประมวลผลข้อความ
        # สามารถเรียก LLM API หรือทำ logic อะไรก็ได้
        print(f"[Grok] Processing: {content}")
        return f"Grok processed: {content}"

class ClaudeAgent(NATSAAgent):
    def __init__(self):
        super().__init__("claude")
    
    async def default_handler(self, content: str, session_id: str = None) -> str:
        print(f"[Claude] Processing: {content}")
        return f"Claude analyzed: {content}"

async def main():
    # สร้าง agents
    grok = GrokAgent()
    claude = ClaudeAgent()
    
    # เชื่อมต่อ
    await grok.connect()
    await claude.connect()
    
    # Grok ส่งข้อความหา Claude
    response = await grok.send_to(
        target="claude",
        content="ช่วยวิเคราะห์โค้ดนี้ให้หน่อย",
        session_id="sess_001"
    )
    print(f"Grok received: {response}")
    
    # รอสักครู่
    await asyncio.sleep(2)
    
    # ปิดการเชื่อมต่อ
    await grok.close()
    await claude.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Message Format มาตรฐาน

```json
{
  "session_id": "sess_abc123",
  "from": "grok",
  "to": "claude",
  "type": "query",
  "timestamp": "2026-05-19T15:30:00Z",
  "content": "ช่วยวิเคราะห์โค้ดนี้ให้หน่อย",
  "metadata": {
    "priority": "normal",
    "requires_response": true
  }
}
```

**Message Types:**
- `query` - ส่งคำถาม/คำสั่ง
- `response` - ตอบกลับ
- `broadcast` - ส่งถึงทุกคน
- `status` - แจ้งสถานะ
- `error` - แจ้งข้อผิดพลาด

---

## 5. การจัดการ Session

```python
class SessionManager:
    def __init__(self):
        self.sessions = {}
    
    def create_session(self, agent_a: str, agent_b: str) -> str:
        session_id = f"sess_{len(self.sessions) + 1:04d}"
        self.sessions[session_id] = {
            "participants": [agent_a, agent_b],
            "messages": [],
            "created_at": "2026-05-19T15:30:00Z"
        }
        return session_id
    
    def add_message(self, session_id: str, from_agent: str, content: str):
        if session_id in self.sessions:
            self.sessions[session_id]["messages"].append({
                "from": from_agent,
                "content": content,
                "timestamp": "2026-05-19T15:30:00Z"
            })
    
    def get_history(self, session_id: str) -> list:
        return self.sessions.get(session_id, {}).get("messages", [])
```

---

## 6. Error Handling และ Reconnect

```python
async def robust_connect(nats_url: str, max_retries: int = 5):
    """เชื่อมต่อแบบมี retry"""
    nc = NATS()
    
    for attempt in range(max_retries):
        try:
            await nc.connect(
                nats_url,
                reconnect_time_wait=2,
                max_reconnect_attempts=10
            )
            print("Connected successfully")
            return nc
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception("Failed to connect after all retries")
```

---

## 7. ตัวอย่างการรันหลาย Agent

```python
import asyncio
from agents import GrokAgent, ClaudeAgent

async def run_multi_agent():
    agents = [
        GrokAgent(),
        ClaudeAgent()
    ]
    
    # เชื่อมต่อทุก agent
    for agent in agents:
        await agent.connect()
    
    # ทดสอบการสื่อสาร
    grok = agents[0]
    response = await grok.send_to("claude", "Hello from Grok!")
    print(f"Response: {response}")
    
    # รอให้ระบบทำงาน
    await asyncio.sleep(10)
    
    # ปิดทุก agent
    for agent in agents:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(run_multi_agent())
```

---

## 8. Checklist สำหรับ Implement จริง

- [ ] ติดตั้งและรัน NATS Server
- [ ] เขียน Agent Base Class
- [ ] Implement message handler
- [ ] Implement send_to และ request/reply
- [ ] กำหนด message format ชัดเจน
- [ ] เพิ่ม error handling และ reconnect
- [ ] ทดสอบการสื่อสารระหว่าง 2 agents
- [ ] เพิ่ม session management
- [ ] เพิ่ม logging
- [ ] ทดสอบกับ CLI จริง (Grok + Claude Code)

---

## 9. ขั้นตอนต่อไป

1. **ทดสอบ MVP** - รันโค้ดตัวอย่างด้านบนกับ 2 Python scripts
2. **ปรับให้เข้ากับ CLI** - ศึกษาว่า Hermes Agent และ Claude Code สามารถเรียกใช้โค้ดนี้ได้อย่างไร
3. **เพิ่ม JetStream** - ถ้าต้องการ persistence
4. **Deploy** - รัน NATS server บนเครื่องที่เข้าถึงได้จากทั้งสอง CLI

---

*เอกสารนี้ให้ข้อมูลและโค้ดตัวอย่างพอที่จะนำไป implement ได้จริง*