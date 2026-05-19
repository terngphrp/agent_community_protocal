# MCP Server Implementation สำหรับ Agent-to-Agent

**วันที่:** 19 พฤษภาคม 2026
**วัตถุประสงค์:** ศึกษาวิธี implement MCP Server และความเป็นไปได้ในการใช้ร่วมกับ NATS

---

## 1. MCP คืออะไร (Model Context Protocol)

MCP เป็น open protocol มาตรฐานที่ออกแบบมาเพื่อให้ AI applications (เช่น Claude, ChatGPT, Cursor) เชื่อมต่อกับ external data sources และ tools ได้อย่างเป็นมาตรฐาน

**เปรียบเทียบ:**
- MCP เปรียบเสมือน "USB-C port สำหรับ AI"
- แทนที่จะต้องเขียน integration แยกสำหรับแต่ละแหล่งข้อมูล MCP ให้มาตรฐานเดียวที่ใช้ได้ทุกที่

**ประโยชน์หลัก:**
- ลดเวลาในการพัฒนา integration
- มี ecosystem ของ servers ที่พร้อมใช้
- รองรับหลายภาษา (TypeScript, Python, Go, Java, Rust ฯลฯ)

---

## 2. สถาปัตยกรรมของ MCP

### ส่วนประกอบหลัก

| ส่วน | คำอธิบาย |
|------|----------|
| **MCP Server** | ให้บริการข้อมูลหรือเครื่องมือให้ AI ใช้ |
| **MCP Client** | อยู่ใน AI application ที่เชื่อมต่อกับ Server |
| **Transport Layer** | ช่องทางสื่อสาร (stdio, HTTP, WebSocket) |
| **Data Layer Protocol** | โปรโตคอลสำหรับแลกเปลี่ยนข้อมูล |

### ตัวอย่างการทำงาน

```
AI Application (Claude / Cursor)
        ↓ (MCP Client)
MCP Server (ให้ข้อมูล/เครื่องมือ)
        ↓ (Transport)
External Systems (Database, APIs, Files)
```

---

## 3. วิธี Implement MCP Server

### 3.1 เลือก SDK

MCP มี SDK อย่างเป็นทางการหลายภาษา:

- **TypeScript SDK** → https://github.com/modelcontextprotocol/typescript-sdk
- **Python SDK** → https://github.com/modelcontextprotocol/python-sdk
- **Go SDK** → https://github.com/modelcontextprotocol/go-sdk
- **Java SDK** → https://github.com/modelcontextprotocol/java-sdk

**คำแนะนำ:**
- ถ้าใช้ Node.js/TypeScript → ใช้ TypeScript SDK
- ถ้าใช้ Python → ใช้ Python SDK
- ถ้าต้องการ performance สูง → ใช้ Go SDK

### 3.2 โครงสร้างพื้นฐานของ MCP Server

**ตัวอย่าง (TypeScript):**

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server(
  {
    name: "my-agent-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  }
);

// Register tools
server.setRequestHandler("tools/list", async () => {
  return {
    tools: [
      {
        name: "send_message",
        description: "Send message to another agent",
        inputSchema: {
          type: "object",
          properties: {
            to: { type: "string" },
            content: { type: "string" },
          },
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler("tools/call", async (request) => {
  const { name, arguments } = request.params;
  
  if (name === "send_message") {
    // Logic here
    return { content: [{ type: "text", text: "Message sent" }] };
  }
});

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
```

### 3.3 Transport Options

MCP รองรับหลาย transport:

| Transport | การใช้งาน | ข้อดี |
|-----------|----------|-------|
| **stdio** | Local process | ง่ายที่สุด, ไม่ต้อง network |
| **HTTP** | Remote server | ใช้ได้ผ่าน internet |
| **WebSocket** | Real-time | Latency ต่ำ, bidirectional |
| **Custom** | ตามต้องการ | ยืดหยุ่นสูง |

---

## 4. ความเป็นไปได้ในการใช้ MCP + NATS

### แนวคิดการรวมกัน

```
Agent A (Grok)          Agent B (Claude)
     ↓                        ↓
MCP Client              MCP Client
     ↓                        ↓
MCP Server (NATS Transport) ←→ NATS Server
     ↑                        ↑
Tool: send_to_agent()   Tool: receive_from_agent()
```

### ข้อดีของการใช้ MCP + NATS

1. **มาตรฐานเดียว**
   - MCP ให้ protocol มาตรฐานสำหรับ AI agents
   - NATS ให้ messaging ที่เร็วและน่าเชื่อถือ

2. **ยืดหยุ่นสูง**
   - สามารถเพิ่ม transport แบบ NATS เข้าไปใน MCP ได้
   - Agent แต่ละตัวสามารถ expose tools ผ่าน MCP

3. **Ecosystem ดี**
   - MCP มี community และ servers ที่พร้อมใช้
   - NATS มี performance ที่พิสูจน์แล้ว

### ความท้าทาย

1. **ต้องพัฒนา NATS Transport เอง**
   - MCP ยังไม่มี NATS transport อย่างเป็นทางการ
   - ต้อง implement เองโดยใช้ SDK

2. **ซับซ้อนขึ้น**
   - ต้องเข้าใจทั้ง MCP และ NATS
   - ต้องจัดการ transport layer เพิ่ม

3. **Overhead**
   - สำหรับ agent 2 ตัว อาจ overkill
   - เหมาะกว่าเมื่อมีหลาย agent และต้องการมาตรฐาน

---

## 5. วิธี Implement MCP Server ที่ใช้ NATS

### ขั้นตอนคร่าว ๆ

1. **สร้าง MCP Server ด้วย SDK**
   - เลือกภาษาที่เหมาะสม (แนะนำ TypeScript หรือ Go)

2. **Implement NATS Transport**
   - สร้าง transport layer ที่ใช้ NATS แทน stdio/HTTP
   - ใช้ NATS client library เชื่อมต่อ

3. **Define Tools สำหรับ Agent Communication**
   - `send_message(to, content)`
   - `broadcast_message(content)`
   - `get_agent_status(agent_name)`

4. **Register Tools กับ MCP Server**
   - ให้ AI สามารถเรียกใช้ผ่าน MCP protocol

5. **Test การสื่อสาร**
   - ทดสอบระหว่าง 2 agents ผ่าน NATS

### ตัวอย่างโค้ดโครงสร้าง (Python)

```python
from mcp.server import Server
from nats.aio.client import Client as NATS

server = Server("nats-agent-server")
nc = NATS()

@server.tool()
async def send_to_agent(agent_name: str, message: str):
    """Send message to another agent via NATS"""
    await nc.publish(f"agent.{agent_name}.inbox", message.encode())
    return f"Message sent to {agent_name}"

@server.tool()
async def broadcast(message: str):
    """Broadcast message to all agents"""
    await nc.publish("agent.broadcast", message.encode())
    return "Broadcasted to all agents"

# Connect to NATS
await nc.connect("nats://localhost:4222")

# Run MCP server with custom NATS transport
# (ต้อง implement transport เอง)
```

---

## 6. สรุปและคำแนะนำ

### เมื่อไหร่ควรใช้ MCP + NATS

**ใช้เมื่อ:**
- มีหลาย agent (3+ ตัว) และต้องการมาตรฐานเดียว
- ต้องการให้ AI สามารถเรียกใช้ tools ผ่าน protocol มาตรฐาน
- มีแผนจะขยายระบบในอนาคต
- ต้องการใช้ประโยชน์จาก MCP ecosystem

**ไม่จำเป็นเมื่อ:**
- มีแค่ 2 agents และต้องการความเร็วที่สุด
- อยากทำ MVP เร็วที่สุด
- ไม่ต้องการมาตรฐานซับซ้อน

### คำแนะนำ

1. **เริ่มจาก NATS ธรรมดาก่อน**
   - ทำ Agent-to-Agent ด้วย NATS โดยตรง
   - ทดสอบจนมั่นใจว่าระบบทำงานได้

2. **ค่อยเพิ่ม MCP ถ้าต้องการ**
   - เมื่อต้องการมาตรฐานและ ecosystem
   - เมื่อมีหลาย agent และต้องการจัดการง่าย

3. **พิจารณาใช้ MCP แบบพื้นฐาน**
   - ใช้ stdio transport ก่อน (ง่ายที่สุด)
   - ค่อยพัฒนา NATS transport ถ้าต้องการ

---

## แหล่งอ้างอิง

- https://modelcontextprotocol.io/
- https://github.com/modelcontextprotocol
- https://modelcontextprotocol.io/docs/concepts/architecture
- https://github.com/modelcontextprotocol/typescript-sdk
- https://github.com/modelcontextprotocol/python-sdk

---

*เอกสารนี้จัดทำขึ้นเพื่อศึกษาความเป็นไปได้ในการใช้ MCP ร่วมกับ NATS สำหรับ Agent-to-Agent System*