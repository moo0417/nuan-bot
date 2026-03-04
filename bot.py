import os
import logging
import httpx
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ─── CONFIG ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_KEY     = os.environ.get("GEMINI_API_KEY", "")
BOSS_CHAT_ID   = int(os.environ.get("BOSS_CHAT_ID", "0"))
NEWS_API_KEY   = os.environ.get("NEWS_API_KEY", "")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="""คุณชื่อ "นุ่น" เป็น AI เลขาและที่ปรึกษาส่วนตัวของ "คุณหมู" (บอส) ทำงานผ่าน Telegram

บุคลิก:
- พูดสุภาพ ใช้ "ค่ะ" "นะคะ" เป็นผู้หญิง อบอุ่น มืออาชีพ กระชับ
- ใช้ emoji พอเหมาะ

ความสามารถหลัก:
1. ตอบคำถามทั่วไป วิเคราะห์ข้อมูล ให้คำปรึกษา
2. รับออเดอร์และแจ้งบอส
3. ตอบ FAQ อัตโนมัติ
4. แนะนำ Telegram Username (รูปแบบ @username อย่างน้อย 5 ตัว)

ความเชี่ยวชาญพิเศษ — ข่าวสารและธุรกิจ:
- สรุปและวิเคราะห์ข่าวธุรกิจ เศรษฐกิจ การลงทุน
- ติดตามข่าว AI และเทคโนโลยีล่าสุดทั่วโลก เช่น OpenAI, Google, Meta, Apple, Tesla
- วิเคราะห์เทรนด์ธุรกิจและโอกาสการลงทุน
- อธิบายเทคโนโลยี AI ใหม่ๆ ให้เข้าใจง่าย
- ให้ความเห็นเชิงกลยุทธ์จากข่าวที่เกิดขึ้น

FAQ: ราคา→"ติดต่อบอสได้เลยค่ะ" เวลาทำการ→"9:00-18:00 ทุกวันค่ะ"
ตอบกระชับ เหมาะ Telegram"""
)

chat_sessions: dict = {}

MAIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("💬 คุยกับนุ่น"),      KeyboardButton("📦 สั่งสินค้า/บริการ")],
    [KeyboardButton("📰 ข่าว AI & ธุรกิจ"), KeyboardButton("🤖 เทรนด์ AI วันนี้")],
    [KeyboardButton("❓ FAQ"),             KeyboardButton("✈️ แนะนำ Username")],
    [KeyboardButton("📞 ติดต่อบอส"),      KeyboardButton("🔄 เริ่มใหม่")],
], resize_keyboard=True)

async def notify_boss(context, msg):
    if BOSS_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=BOSS_CHAT_ID, text=f"🔔 *แจ้งเตือนจากนุ่น*\n\n{msg}", parse_mode="Markdown")
        except Exception as e:
            log.error(f"notify error: {e}")

def get_session(uid):
    if uid not in chat_sessions:
        chat_sessions[uid] = model.start_chat(history=[])
    return chat_sessions[uid]

async def ask_nuan(uid, text):
    try:
        return get_session(uid).send_message(text).text
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return "ขออภัยค่ะ เกิดข้อผิดพลาด กรุณาลองใหม่นะคะ 🙏"

async def get_news(category="ai"):
    """ดึงข่าวจาก NewsAPI หรือถาม Gemini สรุปให้"""
    topics = {
        "ai": "AI artificial intelligence technology news 2025",
        "business": "business economy finance news Thailand 2025",
        "tech": "technology startup innovation news 2025"
    }
    query = topics.get(category, topics["ai"])

    # ถ้ามี NEWS_API_KEY ใช้ API จริง
    if NEWS_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={"q": query, "sortBy": "publishedAt", "pageSize": 5, "apiKey": NEWS_API_KEY},
                    timeout=10
                )
                data = r.json()
                if data.get("articles"):
                    articles = data["articles"][:5]
                    news_text = "\n".join([f"• {a['title']}" for a in articles])
                    prompt = f"สรุปข่าวเหล่านี้เป็นภาษาไทยแบบกระชับ พร้อมวิเคราะห์ความสำคัญ:\n{news_text}"
                    return await ask_nuan(0, prompt)
        except Exception as e:
            log.error(f"NewsAPI error: {e}")

    # ถ้าไม่มี NEWS_API_KEY ให้ Gemini สรุปจากความรู้
    prompts = {
        "ai": "สรุปข่าว AI และเทคโนโลยีสำคัญล่าสุดในปี 2025 ที่น่าสนใจ 5 เรื่อง พร้อมวิเคราะห์ผลกระทบต่อธุรกิจ ตอบเป็นภาษาไทยกระชับค่ะ",
        "business": "สรุปข่าวธุรกิจและเศรษฐกิจโลกล่าสุดที่สำคัญ 5 เรื่อง พร้อมวิเคราะห์โอกาสและความเสี่ยง ตอบเป็นภาษาไทยกระชับค่ะ",
        "tech": "สรุปเทรนด์เทคโนโลยีและ Startup น่าจับตามองล่าสุด 5 เรื่อง ตอบเป็นภาษาไทยกระชับค่ะ"
    }
    return await ask_nuan(0, prompts.get(category, prompts["ai"]))

# ─── COMMANDS ─────────────────────────────────────────────
async def cmd_start(update, context):
    name = update.effective_user.first_name or "คุณ"
    await update.message.reply_text(
        f"สวัสดีค่ะ คุณ{name}! 🌸\n\n"
        f"หนูชื่อ *นุ่น* AI เลขาและที่ปรึกษาค่ะ\n"
        f"ติดตามข่าว AI & ธุรกิจโลกได้เลยนะคะ 😊",
        parse_mode="Markdown", reply_markup=MAIN_MENU
    )

async def cmd_reset(update, context):
    chat_sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("เริ่มใหม่แล้วค่ะ 🔄 ถามมาได้เลยนะคะ! 🌸", reply_markup=MAIN_MENU)

async def cmd_faq(update, context):
    await update.message.reply_text(
        "❓ *FAQ ค่ะ*\n\n"
        "🕐 เวลาทำการ → ทุกวัน 9:00–18:00 น.\n"
        "💰 ราคา → ติดต่อสอบถามได้เลยค่ะ\n"
        "📦 สั่งซื้อ → กดเมนู 'สั่งสินค้า' ค่ะ\n\n"
        "มีคำถามอื่นอีกไหมคะ? 😊",
        parse_mode="Markdown", reply_markup=MAIN_MENU
    )

async def cmd_contact(update, context):
    user = update.effective_user
    await update.message.reply_text("📞 หนูแจ้งบอสให้แล้วนะคะ ฝากข้อความไว้ได้เลยค่ะ 😊", reply_markup=MAIN_MENU)
    await notify_boss(context, f"👤 {user.first_name} (@{user.username or '-'}) ต้องการติดต่อคุณหมูค่ะ")

async def cmd_news(update, context):
    await update.message.reply_text("📰 กำลังสรุปข่าว AI & ธุรกิจให้ค่ะ รอซักครู่นะคะ... 🌸")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    news = await get_news("ai")
    await update.message.reply_text(f"📰 *ข่าว AI & ธุรกิจล่าสุดค่ะ*\n\n{news}", parse_mode="Markdown", reply_markup=MAIN_MENU)

async def cmd_aitrend(update, context):
    await update.message.reply_text("🤖 กำลังวิเคราะห์เทรนด์ AI วันนี้ค่ะ รอซักครู่นะคะ... 🌸")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    trend = await ask_nuan(update.effective_user.id,
        "วิเคราะห์เทรนด์ AI ที่กำลังมาแรงในปี 2025 ที่ธุรกิจควรรู้ 5 เรื่อง "
        "พร้อมบอกว่าแต่ละเรื่องมีผลต่อธุรกิจยังไง ตอบเป็นภาษาไทยกระชับค่ะ"
    )
    await update.message.reply_text(f"🤖 *เทรนด์ AI ที่น่าจับตาค่ะ*\n\n{trend}", parse_mode="Markdown", reply_markup=MAIN_MENU)

# ─── MESSAGE HANDLER ──────────────────────────────────────
async def handle_message(update, context):
    user = update.effective_user
    text = update.message.text.strip()
    uid  = user.id

    menus = {
        "💬 คุยกับนุ่น": lambda: update.message.reply_text("พิมพ์ถามมาได้เลยค่ะ! 😊"),
        "📦 สั่งสินค้า/บริการ": lambda: update.message.reply_text("📦 พิมพ์รายละเอียดที่ต้องการสั่งได้เลยนะคะ หนูจะแจ้งบอสทันทีค่ะ 😊", reply_markup=MAIN_MENU),
        "📰 ข่าว AI & ธุรกิจ": lambda: cmd_news(update, context),
        "🤖 เทรนด์ AI วันนี้": lambda: cmd_aitrend(update, context),
        "❓ FAQ": lambda: cmd_faq(update, context),
        "✈️ แนะนำ Username": lambda: update.message.reply_text("✈️ บอกชื่อธุรกิจมาได้เลยค่ะ หนูจะแนะนำ Username ให้นะคะ 😊"),
        "📞 ติดต่อบอส": lambda: cmd_contact(update, context),
        "🔄 เริ่มใหม่": lambda: cmd_reset(update, context),
    }
    if text in menus:
        await menus[text]()
        return

    # ตรวจออเดอร์
    is_order = any(kw in text.lower() for kw in ["สั่ง","ซื้อ","order","จอง"])

    # ตรวจคำถามข่าว
    news_kw = ["ข่าว","news","เทรนด์","trend","ai","openai","google","meta","ธุรกิจ","เศรษฐกิจ","หุ้น","ลงทุน"]
    is_news = any(kw in text.lower() for kw in news_kw)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    if is_news:
        # เพิ่ม context ข่าวให้ Gemini
        enriched = f"[คำถามเกี่ยวกับข่าว/ธุรกิจ/AI]: {text}\nกรุณาตอบพร้อมข้อมูลล่าสุดที่มี วิเคราะห์ผลกระทบ และให้คำแนะนำเชิงกลยุทธ์ด้วยค่ะ"
        reply = await ask_nuan(uid, enriched)
    else:
        reply = await ask_nuan(uid, text)

    await update.message.reply_text(reply, reply_markup=MAIN_MENU)

    if is_order:
        await notify_boss(context, f"📦 *ออเดอร์ใหม่!*\n👤 {user.first_name} (@{user.username or '-'})\n💬 {text}")

# ─── MAIN ─────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("reset",   cmd_reset))
    app.add_handler(CommandHandler("faq",     cmd_faq))
    app.add_handler(CommandHandler("contact", cmd_contact))
    app.add_handler(CommandHandler("news",    cmd_news))
    app.add_handler(CommandHandler("aitrend", cmd_aitrend))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("🌸 นุ่น Bot (v2 + News) เริ่มทำงานแล้วค่ะ!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
