import os
import logging
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

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="""คุณชื่อ "นุ่น" เป็น AI เลขาและที่ปรึกษาส่วนตัวของ "คุณหมู" (บอส) ทำงานผ่าน Telegram
- พูดสุภาพ ใช้ "ค่ะ" "นะคะ" เป็นผู้หญิง อบอุ่น มืออาชีพ กระชับ
- ตอบคำถาม วิเคราะห์ข้อมูล ให้คำปรึกษา แนะนำ Telegram Username (รูปแบบ @username อย่างน้อย 5 ตัว)
- FAQ: ราคา→"ติดต่อบอสได้เลยค่ะ" เวลาทำการ→"9:00-18:00 ทุกวันค่ะ"
- ตอบกระชับ เหมาะ Telegram ใช้ emoji พอเหมาะ"""
)

chat_sessions: dict = {}

MAIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("💬 คุยกับนุ่น"),     KeyboardButton("📦 สั่งสินค้า/บริการ")],
    [KeyboardButton("❓ FAQ"),            KeyboardButton("✈️ แนะนำ Username")],
    [KeyboardButton("📞 ติดต่อบอส"),     KeyboardButton("🔄 เริ่มใหม่")],
], resize_keyboard=True)

async def notify_boss(context, msg):
    if BOSS_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=BOSS_CHAT_ID, text=f"🔔 *แจ้งเตือนจากนุ่น*\n\n{msg}", parse_mode="Markdown")
        except Exception as e:
            log.error(f"notify error: {e}")

async def ask_nuan(uid, text):
    if uid not in chat_sessions:
        chat_sessions[uid] = model.start_chat(history=[])
    try:
        return chat_sessions[uid].send_message(text).text
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return "ขออภัยค่ะ เกิดข้อผิดพลาด กรุณาลองใหม่นะคะ 🙏"

async def cmd_start(update, context):
    name = update.effective_user.first_name or "คุณ"
    await update.message.reply_text(f"สวัสดีค่ะ คุณ{name}! 🌸\n\nหนูชื่อ *นุ่น* AI เลขาส่วนตัวค่ะ พร้อมช่วยเหลือทุกอย่างเลยนะคะ 😊", parse_mode="Markdown", reply_markup=MAIN_MENU)

async def cmd_reset(update, context):
    chat_sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("เริ่มใหม่แล้วค่ะ 🔄 ถามมาได้เลยนะคะ! 🌸", reply_markup=MAIN_MENU)

async def cmd_faq(update, context):
    await update.message.reply_text("❓ *FAQ ค่ะ*\n\n🕐 เวลาทำการ → ทุกวัน 9:00–18:00 น.\n💰 ราคา → ติดต่อสอบถามได้เลยค่ะ\n📦 สั่งซื้อ → กดเมนู 'สั่งสินค้า' ค่ะ\n\nมีคำถามอื่นอีกไหมคะ? 😊", parse_mode="Markdown", reply_markup=MAIN_MENU)

async def cmd_contact(update, context):
    user = update.effective_user
    await update.message.reply_text("📞 หนูแจ้งบอสให้แล้วนะคะ ฝากข้อความไว้ได้เลยค่ะ 😊", reply_markup=MAIN_MENU)
    await notify_boss(context, f"👤 {user.first_name} (@{user.username or '-'}) ต้องการติดต่อคุณหมูค่ะ")

async def handle_message(update, context):
    user = update.effective_user
    text = update.message.text.strip()

    menus = {
        "💬 คุยกับนุ่น": lambda: update.message.reply_text("พิมพ์ถามมาได้เลยค่ะ! 😊"),
        "📦 สั่งสินค้า/บริการ": lambda: update.message.reply_text("📦 พิมพ์รายละเอียดที่ต้องการสั่งได้เลยนะคะ หนูจะแจ้งบอสทันทีค่ะ 😊", reply_markup=MAIN_MENU),
        "❓ FAQ": lambda: cmd_faq(update, context),
        "✈️ แนะนำ Username": lambda: update.message.reply_text("✈️ บอกชื่อธุรกิจมาได้เลยค่ะ หนูจะแนะนำ Username ให้นะคะ 😊"),
        "📞 ติดต่อบอส": lambda: cmd_contact(update, context),
        "🔄 เริ่มใหม่": lambda: cmd_reset(update, context),
    }
    if text in menus:
        await menus[text]()
        return

    is_order = any(kw in text.lower() for kw in ["สั่ง","ซื้อ","order","จอง"])
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = await ask_nuan(user.id, text)
    await update.message.reply_text(reply, reply_markup=MAIN_MENU)

    if is_order:
        await notify_boss(context, f"📦 *ออเดอร์ใหม่!*\n👤 {user.first_name} (@{user.username or '-'})\n💬 {text}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("faq", cmd_faq))
    app.add_handler(CommandHandler("contact", cmd_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("🌸 นุ่น Bot พร้อมทำงานแล้วค่ะ!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
