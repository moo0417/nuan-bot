# 🌸 วิธี Deploy นุ่น Bot บน Railway.app

## ขั้นตอนที่ 1 — เตรียม Anthropic API Key
1. ไปที่ https://console.anthropic.com
2. กด "Get API Keys" → "Create Key"
3. คัดลอก Key ไว้ค่ะ (หน้าตาแบบ sk-ant-...)

## ขั้นตอนที่ 2 — หา BOSS_CHAT_ID ของคุณหมู
1. เปิด Telegram ค้นหา @userinfobot
2. กด Start → มันจะบอก Chat ID ของคุณหมูค่ะ
3. จดตัวเลขนั้นไว้

## ขั้นตอนที่ 3 — อัปโหลดขึ้น GitHub
1. สมัคร/Login https://github.com
2. กด "New repository" ตั้งชื่อ nuan-bot
3. อัปโหลดไฟล์ทั้ง 3:
   - bot.py
   - requirements.txt
   - railway.toml

## ขั้นตอนที่ 4 — Deploy บน Railway
1. ไปที่ https://railway.app
2. Login ด้วย GitHub
3. กด "New Project" → "Deploy from GitHub repo"
4. เลือก repo "nuan-bot"

## ขั้นตอนที่ 5 — ตั้งค่า Environment Variables
ใน Railway → กด "Variables" แล้วเพิ่ม:

| ชื่อ Variable     | ค่า                              |
|-------------------|----------------------------------|
| TELEGRAM_TOKEN    | Token จาก @BotFather             |
| ANTHROPIC_API_KEY | Key จาก Anthropic                |
| BOSS_CHAT_ID      | Chat ID ของคุณหมู               |

## ขั้นตอนที่ 6 — Deploy!
กด "Deploy" แล้วรอ 2-3 นาที
ถ้าเห็น ✅ Active = นุ่นออนไลน์แล้วค่ะ! 🎉

## ทดสอบ
เปิด Telegram → ค้นหา Bot ของคุณหมู → กด Start
นุ่นจะทักทายทันทีเลยค่ะ! 🌸

---
หากติดปัญหาขั้นตอนไหน ถามนุ่นได้เลยนะคะ 😊
