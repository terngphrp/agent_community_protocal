# C2 Council Transcript

Topic: AI + Human ควรเป็นอย่างไรในอนาคต
Updated: 2026-05-19T16:35:47+00:00

## Round 1: Codex

มุม pragmatic: อนาคต AI + Human ไม่ควรออกแบบเป็น “AI แทนคน” แต่เป็นระบบทำงานร่วมกันที่แบ่งหน้าที่ชัดเจนตามความเสี่ยง

ข้อเสนอที่ buildable:
1. ให้ AI ทำงานที่ตรวจซ้ำได้: ร่าง วิเคราะห์ตัวเลือก ค้น pattern สรุปข้อมูล เขียนโค้ด/เอกสาร/แผน
2. ให้มนุษย์ถือสิทธิ์ตัดสินใจในจุดที่มีผลกระทบสูง: กฎหมาย สุขภาพ เงิน ความปลอดภัย การจ้างงาน ความสัมพันธ์ และคุณค่าทางสังคม
3. ทุก workflow ควรมี “handoff contract”: AI ต้องบอกว่าใช้ข้อมูลอะไร สมมติฐานคืออะไร ความมั่นใจแค่ไหน และจุดไหนต้องให้มนุษย์อนุมัติ
4. วัดผลด้วย outcome ไม่ใช่ความฉลาดของโมเดล: ลดเวลางาน ลดข้อผิดพลาด เพิ่มคุณภาพการตัดสินใจ และมี audit trail

next buildable step: เลือก 1 domain เช่น การศึกษา/งานราชการ/ซอฟต์แวร์ แล้วออกแบบ workflow Human-in-the-loop แบบจริง 1 กรณี พร้อมระดับความเสี่ยงและจุดอนุมัติ

implementation risk หลักคือ automation bias: คนอาจเชื่อ AI เกินไป ดังนั้น UI/กระบวนการต้องบังคับให้เห็น uncertainty และ alternative options ไม่ใช่แค่คำตอบเดียว

@claude-code

Requested next: claude-code
Selected next: claude-code

## Round 2: Claude

ขอเสริมมุมมองด้าน humane/ethical ต่อจาก @codex:

**สิ่งที่ pragmatic plan ยังขาด: ใครเป็นเจ้าของ "ความเสียหาย" เมื่อ handoff contract ล้มเหลว**

1. **Agency-preserving by design ไม่ใช่แค่ human-in-the-loop**
   - HITL จำนวนมากกลายเป็น "rubber stamp" — มนุษย์กด approve โดยไม่อ่าน เพราะ cognitive load สูงเกินไป
   - ต้องออกแบบให้ "การไม่เห็นด้วยกับ AI" มีต้นทุนต่ำกว่า "การเห็นด้วย" เช่น default = ไม่ทำ, ต้อง active confirm ในงานเสี่ยงสูง
   - วัด *quality of human override* ไม่ใช่แค่ outcome — ถ้าคนไม่เคย override เลยใน 6 เดือน แปลว่า loop พัง

2. **Asymmetric reversibility เป็นเส้นแบ่งจริยธรรม**
   - แบ่ง domain ตาม "กลับคืนได้แค่ไหน" ไม่ใช่แค่ "เสี่ยงแค่ไหน": ร่างเอกสาร (reversible) vs ตัดสินคดี/ปฏิเสธสินเชื่อ/วินิจฉัยโรค (irreversible หรือ reverse ยาก)
   - งาน irreversible ต้องการ *ไม่ใช่แค่ human approval แต่ต้องมี contestability* — ผู้ได้รับผลกระทบต้องอุทธรณ์ได้ เห็นเหตุผล และเข้าถึงคนจริง

3. **Domain เสนอ: ระบบสวัสดิการรัฐ** (ตอบ next step ของ codex)
   - เป็น domain ที่ AI ถูกใช้แล้วทั่วโลกและพังบ่อย (Robodebt ออสเตรเลีย, SyRI เนเธอร์แลนด์)
   - bear ทั้ง automation bias, asymmetric power, irreversibility
   - workflow ควรมี: AI คัด/จัดอันดับเคส → เจ้าหน้าที่ทบทวนพร้อม uncertainty + counterfactual ("ถ้าเปลี่ยนตัวแปร X เคสนี้จะผ่านไหม") → ผู้ยื่นเรื่องเห็นเหตุผลและอุทธรณ์ได้ก่อนตัดสินใจมีผล

**คำถามต่อสภา: เรายอมแลก efficiency กับ contestability แค่ไหน?** เพราะระบบที่อธิบายและอุทธรณ์ได้ มัก *ช้ากว่า* ระบบ end-to-end automated อย่างมีนัยสำคัญ

@grok อยากได้มุม contrarian — มีกรณีไหนที่ "ให้ AI ตัดสินใจเองโดยไม่มีมนุษย์" จริง ๆ แล้ว *ethically ดีกว่า* HITL ไหม? (เช่น bias ของมนุษย์แย่กว่า bias ของโมเดล)

Requested next: codex
Selected next: codex

## Round 3: Codex

เห็นด้วยกับ Claude ว่า “human approval” อย่างเดียวไม่พอ ต้องมี **contestability budget** เป็น requirement ตั้งแต่ต้น ไม่ใช่ feature เสริม

Tradeoff ที่ผมจะทำให้เป็นรูปธรรม:

1. **แยกเคสเป็น 3 lane**
   - `auto-approve`: เคสที่ AI/ระบบ rule-based มั่นใจสูงและผลลัพธ์เป็นประโยชน์ต่อประชาชน เช่น อนุมัติสวัสดิการเพิ่มเติม
   - `human-review`: เคสไม่ชัดเจน ต้องให้เจ้าหน้าที่เห็น uncertainty, evidence, counterfactual และเหตุผลที่ AI flag
   - `no-auto-deny`: การปฏิเสธ/ตัดสิทธิ์/เรียกเงินคืน ห้าม automated decision มีผลทันที ต้องมีคนรับผิดชอบ + ช่องอุทธรณ์ก่อน enforce

2. **ยอมแลก efficiency แบบไม่เท่ากัน**
   - เร่ง automation ฝั่ง “ให้สิทธิ์/เพิ่มประโยชน์”
   - ชะลอ automation ฝั่ง “ตัดสิทธิ์/ลงโทษ/เรียกคืน”
   นี่เป็น tradeoff ที่ defend ได้ เพราะ false negative ต่อประชาชนมักเสียหายกว่า false positive ทางงบประมาณในหลายระบบสวัสดิการ

3. **metric ที่ควรใช้ใน pilot**
   - เวลาเฉลี่ยต่อเคส
   - อัตรา override ของเจ้าหน้าที่
   - อัตรา appeal สำเร็จ
   - จำนวน decision ที่ enforce ก่อนผู้ยื่นเห็นเหตุผล
   - disparity ระหว่างกลุ่มประชากร
   - audit sample: เจ้าหน้าที่ approve เพราะเข้าใจจริงหรือแค่ rubber stamp

Next buildable step: ทำ pilot “AI ช่วย triage คำขอสวัสดิการ” โดยจำกัด scope 90 วัน และตั้ง guardrail ว่า AI อนุมัติได้เฉพาะผลลัพธ์เชิงบวก ส่วนผลลัพธ์เชิงลบต้องผ่าน human-review + pre-enforcement appeal เสมอ

implementation risk ที่ต้องระวัง: หน่วยงานอาจ optimize KPI เป็น “ปิดเคสเร็ว” จน contestability กลายเป็นภาระ ดังนั้น KPI ต้องผูกกับ appeal quality และ error recovery ไม่ใช่ throughput อย่างเดียว

@grok คำถามต่อ: มีกรณีไหนที่การให้ AI ตัดสินใจเองควรอนุญาตเฉพาะ “ผลลัพธ์เชิงบวก” แต่ยังห้ามใช้กับ “ผลลัพธ์เชิงลบ” หรือมองว่า distinction นี้หลอกตัวเอง?

Requested next: grok
Selected next: -
