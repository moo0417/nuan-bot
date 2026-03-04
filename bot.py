import os
import logging
from openai import OpenAI
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ─── CONFIG ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
KIMI_KEY       = os.environ.get("KIMI_API_KEY", "")
BOSS_CHAT_ID   = int(os.environ.get("BOSS_CHAT_ID", "0"))

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

client = OpenAI(
    api_key=KIMI_KEY,
    base_url="https://api.moonshot.cn/v1"
)

SYSTEM_PROMPT = """คุณชื่อ "นุ่น" เป็น AI เลขาและที่ปรึกษาส่วนตัวของ "คุณหมู" (บอส) ทำงานผ่าน Telegram

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

chat_histories: dict = {}

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

async def ask_nuan(uid, text):
    if uid not in chat_histories:
        chat_histories[uid] = []
    chat_histories[uid].append({"role": "user", "content": text})
    if len(chat_histories[uid]) > 20:
        chat_histories[uid] = chat_histories[uid][-20:]
    try:
        resp = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + chat_histories[uid],
            temperature=0.7,
        )
        reply = resp.choices[0].message.content
        chat_histories[uid].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        log.error(f"Kimi error: {e}")
        return "ขออภัยค่ะ เกิดข้อผิดพลาด กรุณาลองใหม่นะคะ 🙏"

async def cmd_start(update, context):
    name = update.effective_user.first_name or "คุณ"
    await update.message.reply_text(
        f"สวัสดีค่ะ คุณ{name}! 🌸\n\nหนูชื่อ *นุ่น* AI เลขาและที่ปรึกษาค่ะ\nพร้อมช่วยงานและติดตามข่าว AI & ธุรกิจโลกค่ะ 😊",
        parse_mode="Markdown", reply_markup=MAIN_MENU
    )

async def cmd_reset(update, context):
    chat_histories.pop(update.effective_user.id, None)
    await update.message.reply_text("เริ่มใหม่แล้วค่ะ 🔄 ถามมาได้เลยนะคะ! 🌸", reply_markup=MAIN_MENU)

async def cmd_faq(update, context):
    await update.message.reply_text(
        "❓ *FAQ ค่ะ*\n\n🕐 เวลาทำการ → ทุกวัน 9:00–18:00 น.\n💰 ราคา → ติดต่อสอบถามได้เลยค่ะ\n📦 สั่งซื้อ → กดเมนู 'สั่งสินค้า' ค่ะ\n\nมีคำถามอื่นอีกไหมคะ? 😊",
        parse_mode="Markdown", reply_markup=MAIN_MENU
    )

async def cmd_contact(update, context):
    user = update.effective_user
    await update.message.reply_text("📞 หนูแจ้งบอสให้แล้วนะคะ ฝากข้อความไว้ได้เลยค่ะ 😊", reply_markup=MAIN_MENU)
    await notify_boss(context, f"👤 {user.first_name} (@{user.username or '-'}) ต้องการติดต่อคุณหมูค่ะ")

async def cmd_news(update, context):
    await update.message.reply_text("📰 กำลังสรุปข่าว AI & ธุรกิจให้ค่ะ รอซักครู่นะคะ... 🌸")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    news = await ask_nuan(update.effective_user.id,
        "สรุปข่าว AI และธุรกิจสำคัญล่าสุดในปี 2025 ที่น่าสนใจ 5 เรื่อง พร้อมวิเคราะห์ผลกระทบต่อธุรกิจ ตอบเป็นภาษาไทยกระชับค่ะ"
    )
    await update.message.reply_text(f"📰 *ข่าว AI & ธุรกิจล่าสุดค่ะ*\n\n{news}", parse_mode="Markdown", reply_markup=MAIN_MENU)

async def cmd_aitrend(update, context):
    await update.message.reply_text("🤖 กำลังวิเคราะห์เทรนด์ AI วันนี้ค่ะ รอซักครู่นะคะ... 🌸")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    trend = await ask_nuan(update.effective_user.id,
        "วิเคราะห์เทรนด์ AI ที่กำลังมาแรงในปี 2025 ที่ธุรกิจควรรู้ 5 เรื่อง พร้อมบอกว่าแต่ละเรื่องมีผลต่อธุรกิจยังไง ตอบเป็นภาษาไทยกระชับค่ะ"
    )
    await update.message.reply_text(f"🤖 *เทรนด์ AI ที่น่าจับตาค่ะ*\n\n{trend}", parse_mode="Markdown", reply_markup=MAIN_MENU)

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

    is_order = any(kw in text.lower() for kw in ["สั่ง","ซื้อ","order","จอง"])
    news_kw = ["ข่าว","news","เทรนด์","trend","ai","openai","google","meta","ธุรกิจ","เศรษฐกิจ","หุ้น","ลงทุน"]
    is_news = any(kw in text.lower() for kw in news_kw)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    if is_news:
        enriched = f"[คำถามเกี่ยวกับข่าว/ธุรกิจ/AI]: {text}\nกรุณาตอบพร้อมข้อมูลล่าสุดที่มี วิเคราะห์ผลกระทบ และให้คำแนะนำเชิงกลยุทธ์ด้วยค่ะ"
        reply = await ask_nuan(uid, enriched)
    else:
        reply = await ask_nuan(uid, text)

    await update.message.reply_text(reply, reply_markup=MAIN_MENU)

    if is_order:
        await notify_boss(context, f"📦 *ออเดอร์ใหม่!*\n👤 {user.first_name} (@{user.username or '-'})\n💬 {text}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("reset",   cmd_reset))
    app.add_handler(CommandHandler("faq",     cmd_faq))
    app.add_handler(CommandHandler("contact", cmd_contact))
    app.add_handler(CommandHandler("news",    cmd_news))
    app.add_handler(CommandHandler("aitrend", cmd_aitrend))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("🌸 นุ่น Bot (Kimi) เริ่มทำงานแล้วค่ะ!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
