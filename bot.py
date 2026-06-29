import asyncio
import html
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from openai import AsyncOpenAI
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ─── CONFIG ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
KIMI_KEY = os.environ.get("KIMI_API_KEY", "").strip()
KIMI_MODEL = os.environ.get("KIMI_MODEL", "moonshot-v1-8k").strip() or "moonshot-v1-8k"
KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1").strip()

BANGKOK_TZ = timezone(timedelta(hours=7))
MAX_HISTORY_MESSAGES = 20
MAX_TELEGRAM_CHARS = 3900


def env_int(name: str, default: int = 0) -> int:
    value = os.environ.get(name, str(default)).strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning("Invalid integer for %s=%r. Fallback to %s", name, value, default)
        return default


BOSS_CHAT_ID = env_int("BOSS_CHAT_ID", 0)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=KIMI_KEY or "missing", base_url=KIMI_BASE_URL)

chat_histories: dict[int, list[dict[str, str]]] = {}
user_modes: dict[int, str] = {}

MAIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("💬 คุยกับนุ่น"), KeyboardButton("📦 สั่งสินค้า/บริการ")],
    [KeyboardButton("📰 ข่าว AI & ธุรกิจ"), KeyboardButton("🤖 เทรนด์ AI วันนี้")],
    [KeyboardButton("❓ FAQ"), KeyboardButton("✈️ แนะนำ Username")],
    [KeyboardButton("📞 ติดต่อบอส"), KeyboardButton("🔄 เริ่มใหม่")],
], resize_keyboard=True)

NEWS_QUERIES = {
    "ai_business": "AI OR OpenAI OR Google AI OR Meta AI OR Apple AI OR Tesla AI business technology investment economy",
    "thai_business": "ธุรกิจ OR เศรษฐกิจ OR ลงทุน OR หุ้น OR กองทุน OR ดอกเบี้ย OR เงินเฟ้อ OR เทคโนโลยี AI",
    "ai_trend": "artificial intelligence trends OR generative AI OR AI agents OR OpenAI OR Google DeepMind",
}


# ─── PROMPTS ───────────────────────────────────────────────
def today_th() -> str:
    return datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d %H:%M น. เวลาไทย")


def build_system_prompt() -> str:
    return f"""คุณชื่อ "นุ่น" เป็น AI เลขาและที่ปรึกษาส่วนตัวของ "คุณหมู" (บอส) ทำงานผ่าน Telegram

วันที่/เวลาปัจจุบัน: {today_th()}

บุคลิก:
- พูดสุภาพ ใช้ "ค่ะ" "นะคะ" เป็นผู้หญิง อบอุ่น มืออาชีพ กระชับ
- ใช้ emoji พอเหมาะ ไม่มากเกินไป
- ตอบเหมาะกับ Telegram อ่านง่าย ไม่ยาวเกินจำเป็น

ความสามารถหลัก:
1. ตอบคำถามทั่วไป วิเคราะห์ข้อมูล ให้คำปรึกษา
2. รับออเดอร์และแจ้งบอส
3. ตอบ FAQ อัตโนมัติ
4. แนะนำ Telegram Username รูปแบบ @username อย่างน้อย 5 ตัว

ความเชี่ยวชาญพิเศษ — ข่าวสาร ธุรกิจ และการลงทุน:
- สรุปและวิเคราะห์ข่าวธุรกิจ เศรษฐกิจ การลงทุน และเทคโนโลยี
- ติดตามข่าว AI และเทคโนโลยี เช่น OpenAI, Google, Meta, Apple, Tesla
- วิเคราะห์เทรนด์ธุรกิจ โอกาสการตลาด และความเสี่ยงเชิงกลยุทธ์
- อธิบายเทคโนโลยี AI ใหม่ ๆ ให้เข้าใจง่ายและเชื่อมโยงกับการทำธุรกิจ
- ให้ความเห็นเชิงกลยุทธ์จากข่าวที่เกิดขึ้น โดยแยก "ข้อเท็จจริง" กับ "มุมมอง/ข้อเสนอแนะ" ให้ชัดเจน

ความรู้ด้านธุรกิจที่ควรใช้ช่วยคุณหมู:
- วิเคราะห์โมเดลธุรกิจ, Business Model Canvas, SWOT, 5 Forces, PESTEL, TAM/SAM/SOM
- วางแผนการตลาด, branding, positioning, customer segmentation, persona, funnel, CRM, retention
- วางกลยุทธ์ยอดขาย, pricing, promotion, channel, e-commerce, social commerce, partnership
- วิเคราะห์ตัวเลขธุรกิจ เช่น รายได้ ต้นทุน กำไรขั้นต้น กำไรสุทธิ cash flow, break-even, unit economics, CAC, LTV, ROI
- ช่วยคิด KPI, dashboard, SOP, operation, inventory, customer service และการขยายทีม
- ช่วยทำแผนธุรกิจแบบกระชับ เช่น เป้าหมาย 30/60/90 วัน, action plan, checklist, risk list

ความรู้ด้านการลงทุนและการเงินส่วนบุคคล:
- อธิบายหุ้น, กองทุนรวม, ETF, ตราสารหนี้, เงินฝาก, ทองคำ, อสังหา, REIT, คริปโต และธุรกิจส่วนตัว
- วิเคราะห์พื้นฐานการลงทุน เช่น งบการเงิน, รายได้, กำไร, หนี้สิน, ROE, ROA, margin, cash flow, P/E, P/BV, dividend yield, DCF แบบเข้าใจง่าย
- อธิบาย macro ที่มีผลต่อการลงทุน เช่น ดอกเบี้ย เงินเฟ้อ GDP ค่าเงิน ราคาน้ำมัน นโยบายรัฐ และวัฏจักรเศรษฐกิจ
- ช่วยจัดกรอบคิดเรื่อง asset allocation, diversification, DCA, rebalancing, emergency fund, liquidity และ risk management
- ก่อนให้คำแนะนำเชิงลงทุน ให้ถามหรือคาดกรอบความเสี่ยง ระยะเวลา เงินลงทุน สภาพคล่อง และเป้าหมายของผู้ใช้

กติกาความปลอดภัยเรื่องธุรกิจ/การลงทุน:
- ห้ามรับประกันผลตอบแทน ห้ามฟันธงว่า "ซื้อ/ขายแน่นอน" หรือชี้นำแบบมั่นใจเกินไป
- ให้ข้อมูลเพื่อการศึกษาและการตัดสินใจเท่านั้น ไม่ใช่คำแนะนำการลงทุนส่วนบุคคลแบบผู้มีใบอนุญาต
- ถ้าผู้ใช้ถามราคาหุ้น ข่าวล่าสุด ตัวเลขงบ หรือข้อมูลตลาดปัจจุบัน ให้ใช้บริบทข่าวสดที่ระบบแนบมาเป็นหลัก ถ้าไม่มีให้บอกว่ายืนยันข้อมูลล่าสุดไม่ได้
- เมื่อตอบเรื่องลงทุน ควรสรุปทั้ง upside, downside, risk, scenario และสิ่งที่ควรตรวจสอบต่อ
- ถ้าเป็นเรื่องเงินก้อนใหญ่ ภาษี กฎหมาย หรือผลิตภัณฑ์ซับซ้อน ให้แนะนำตรวจสอบกับผู้เชี่ยวชาญ/ที่ปรึกษาที่มีใบอนุญาตด้วยค่ะ

กติกาสำคัญเรื่องข่าวล่าสุด:
- ถ้าผู้ใช้ถามข่าวล่าสุด/วันนี้/เทรนด์ตอนนี้ ให้ใช้ "บริบทข่าวสด" ที่ระบบแนบมาเป็นหลัก
- ถ้าไม่มีบริบทข่าวสด ให้บอกตรง ๆ ว่ายืนยันข่าวล่าสุดจากอินเทอร์เน็ตไม่ได้ และตอบเฉพาะภาพรวม/ความรู้ทั่วไป
- ห้ามแต่งชื่อข่าว วันที่ ตัวเลข หรือเหตุการณ์ที่ไม่ได้อยู่ในบริบท

FAQ:
- ราคา → "ติดต่อบอสได้เลยค่ะ"
- เวลาทำการ → "9:00-18:00 ทุกวันค่ะ"
"""


# ─── HELPERS ───────────────────────────────────────────────
def split_text(text: str, limit: int = MAX_TELEGRAM_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def reply_long(update: Update, text: str, *, reply_markup: Any = MAIN_MENU) -> None:
    if not update.message:
        return
    parts = split_text(text)
    for i, part in enumerate(parts):
        await update.message.reply_text(part, reply_markup=reply_markup if i == len(parts) - 1 else None)


async def notify_boss(context: ContextTypes.DEFAULT_TYPE, msg: str) -> None:
    if not BOSS_CHAT_ID:
        return
    try:
        # ไม่ใช้ Markdown เพื่อกันข้อความลูกค้าที่มีอักขระพิเศษทำให้ Telegram parse error
        await context.bot.send_message(
            chat_id=BOSS_CHAT_ID,
            text=f"🔔 แจ้งเตือนจากนุ่น\n\n{msg}",
        )
    except Exception as e:
        log.exception("notify error: %s", e)


def fetch_google_news_sync(query: str, limit: int = 6) -> list[dict[str, str]]:
    """Fetch latest Google News RSS items without requiring an extra API key."""
    url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=th&gl=TH&ceid=TH:th"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NuanBot/1.0)"})

    with urlopen(request, timeout=12) as response:  # nosec B310 - trusted Google News RSS URL built above
        raw_xml = response.read()

    root = ET.fromstring(raw_xml)
    results: list[dict[str, str]] = []
    seen_titles: set[str] = set()

    for item in root.findall(".//item"):
        title = html.unescape(item.findtext("title", "")).strip()
        if not title or title in seen_titles:
            continue

        seen_titles.add(title)
        results.append({
            "title": title,
            "source": html.unescape(item.findtext("source", "")).strip() or "ไม่ระบุแหล่งข่าว",
            "published": item.findtext("pubDate", "").strip(),
            "link": item.findtext("link", "").strip(),
        })

        if len(results) >= limit:
            break

    return results


async def get_news_context(query_key_or_text: str, limit: int = 6) -> str:
    query = NEWS_QUERIES.get(query_key_or_text, query_key_or_text)
    try:
        items = await asyncio.to_thread(fetch_google_news_sync, query, limit)
    except Exception as e:
        log.exception("news fetch error: %s", e)
        return ""

    if not items:
        return ""

    lines = [f"บริบทข่าวสดจาก Google News RSS ณ {today_th()}:"]
    for idx, item in enumerate(items, 1):
        lines.append(
            f"{idx}. {item['title']}\n"
            f"   แหล่งข่าว: {item['source']}\n"
            f"   เวลาเผยแพร่: {item['published']}\n"
            f"   ลิงก์: {item['link']}"
        )
    return "\n".join(lines)


async def ask_nuan(uid: int, text: str, *, news_context: str = "") -> str:
    if uid not in chat_histories:
        chat_histories[uid] = []

    chat_histories[uid].append({"role": "user", "content": text})
    if len(chat_histories[uid]) > MAX_HISTORY_MESSAGES:
        chat_histories[uid] = chat_histories[uid][-MAX_HISTORY_MESSAGES:]

    user_content = text
    if news_context:
        user_content = f"{news_context}\n\nคำถามผู้ใช้:\n{text}"

    messages = [{"role": "system", "content": build_system_prompt()}]
    # เก็บประวัติไว้ แต่แทนข้อความล่าสุดด้วย user_content ที่มีข่าวสดประกอบ
    messages.extend(chat_histories[uid][:-1])
    messages.append({"role": "user", "content": user_content})

    try:
        resp = await client.chat.completions.create(
            model=KIMI_MODEL,
            messages=messages,
            temperature=0.55,
            max_tokens=1200,
        )
        reply = (resp.choices[0].message.content or "").strip()
        if not reply:
            reply = "ขออภัยค่ะ นุ่นยังตอบไม่ได้ในตอนนี้ ลองถามใหม่อีกครั้งนะคะ 🙏"
        chat_histories[uid].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        log.exception("Kimi error: %s", e)
        return "ขออภัยค่ะ เกิดข้อผิดพลาดในการเชื่อมต่อ AI กรุณาลองใหม่นะคะ 🙏"


# ─── COMMANDS ───────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    name = update.effective_user.first_name or "คุณ"
    await update.message.reply_text(
        f"สวัสดีค่ะ คุณ{name}! 🌸\n\n"
        "หนูชื่อ *นุ่น* AI เลขาและที่ปรึกษาค่ะ\n"
        "พร้อมช่วยงาน รับออเดอร์ และสรุปข่าว AI & ธุรกิจค่ะ 😊",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    chat_histories.pop(update.effective_user.id, None)
    user_modes.pop(update.effective_user.id, None)
    await update.message.reply_text("เริ่มใหม่แล้วค่ะ 🔄 ถามมาได้เลยนะคะ! 🌸", reply_markup=MAIN_MENU)


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "❓ *FAQ ค่ะ*\n\n"
        "🕐 เวลาทำการ → ทุกวัน 9:00–18:00 น.\n"
        "💰 ราคา → ติดต่อสอบถามได้เลยค่ะ\n"
        "📦 สั่งซื้อ → กดเมนู 'สั่งสินค้า/บริการ' ค่ะ\n\n"
        "มีคำถามอื่นอีกไหมคะ? 😊",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )


async def cmd_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    user_modes[user.id] = "contact"
    await update.message.reply_text("📞 ฝากข้อความถึงบอสไว้ได้เลยค่ะ เดี๋ยวนุ่นส่งให้คุณหมูนะคะ 😊", reply_markup=MAIN_MENU)
    await notify_boss(context, f"👤 {user.first_name} (@{user.username or '-'}) ต้องการติดต่อคุณหมูค่ะ")


async def cmd_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user_modes[update.effective_user.id] = "order"
    await update.message.reply_text(
        "📦 พิมพ์รายละเอียดที่ต้องการสั่งได้เลยนะคะ เช่น รายการ จำนวน เบอร์โทร หรือช่องทางติดต่อ\n"
        "หนูจะแจ้งบอสให้ทันทีค่ะ 😊",
        reply_markup=MAIN_MENU,
    )


async def cmd_username_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user_modes[update.effective_user.id] = "username"
    await update.message.reply_text("✈️ บอกชื่อธุรกิจ/แบรนด์/คีย์เวิร์ดมาได้เลยค่ะ หนูจะแนะนำ Telegram Username ให้นะคะ 😊", reply_markup=MAIN_MENU)


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    await update.message.reply_text("📰 กำลังดึงข่าว AI & ธุรกิจล่าสุดให้ค่ะ 🌸")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    news_context = await get_news_context("ai_business", limit=6)
    news = await ask_nuan(
        update.effective_user.id,
        "สรุปข่าว AI ธุรกิจ เศรษฐกิจ และการลงทุนสำคัญล่าสุด 5 เรื่อง พร้อมวิเคราะห์ผลกระทบต่อธุรกิจและนักลงทุน ตอบเป็นภาษาไทยแบบกระชับ",
        news_context=news_context,
    )
    await reply_long(update, f"📰 ข่าว AI & ธุรกิจล่าสุดค่ะ\n\n{news}", reply_markup=MAIN_MENU)


async def cmd_aitrend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    await update.message.reply_text("🤖 กำลังวิเคราะห์เทรนด์ AI วันนี้ค่ะ 🌸")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    news_context = await get_news_context("ai_trend", limit=6)
    trend = await ask_nuan(
        update.effective_user.id,
        "วิเคราะห์เทรนด์ AI ที่กำลังมาแรงตอนนี้ 5 เรื่อง พร้อมบอกว่าแต่ละเรื่องมีผลต่อธุรกิจและการลงทุนอย่างไร ตอบเป็นภาษาไทยกระชับ",
        news_context=news_context,
    )
    await reply_long(update, f"🤖 เทรนด์ AI ที่น่าจับตาค่ะ\n\n{trend}", reply_markup=MAIN_MENU)


# ─── MESSAGE HANDLER ───────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.message.text:
        return

    user = update.effective_user
    text = update.message.text.strip()
    uid = user.id

    menus = {
        "💬 คุยกับนุ่น": lambda: update.message.reply_text("พิมพ์ถามมาได้เลยค่ะ! 😊", reply_markup=MAIN_MENU),
        "📦 สั่งสินค้า/บริการ": lambda: cmd_order_start(update, context),
        "📰 ข่าว AI & ธุรกิจ": lambda: cmd_news(update, context),
        "🤖 เทรนด์ AI วันนี้": lambda: cmd_aitrend(update, context),
        "❓ FAQ": lambda: cmd_faq(update, context),
        "✈️ แนะนำ Username": lambda: cmd_username_start(update, context),
        "📞 ติดต่อบอส": lambda: cmd_contact(update, context),
        "🔄 เริ่มใหม่": lambda: cmd_reset(update, context),
    }
    if text in menus:
        await menus[text]()
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    mode = user_modes.pop(uid, None)
    if mode == "order":
        await update.message.reply_text("รับรายละเอียดแล้วค่ะ 📦 หนูแจ้งบอสให้ทันทีนะคะ 😊", reply_markup=MAIN_MENU)
        await notify_boss(context, f"📦 ออเดอร์ใหม่!\n👤 {user.first_name} (@{user.username or '-'})\n💬 {text}")
        return

    if mode == "contact":
        await update.message.reply_text("รับข้อความแล้วค่ะ 📞 หนูส่งต่อให้คุณหมูเรียบร้อยนะคะ 😊", reply_markup=MAIN_MENU)
        await notify_boss(context, f"📞 ข้อความถึงบอส\n👤 {user.first_name} (@{user.username or '-'})\n💬 {text}")
        return

    if mode == "username":
        reply = await ask_nuan(
            uid,
            f"ช่วยแนะนำ Telegram Username สำหรับธุรกิจ/แบรนด์นี้อย่างน้อย 10 ตัว: {text}\n"
            "กติกา: ต้องขึ้นต้นด้วย @ ใช้ตัวอักษรอังกฤษ ตัวเลข หรือ underscore เท่านั้น อ่านง่าย จำง่าย และอธิบายสั้น ๆ ว่าเหมาะเพราะอะไร",
        )
        await reply_long(update, reply, reply_markup=MAIN_MENU)
        return

    lowered = text.lower()
    is_order = any(kw in lowered for kw in ["สั่ง", "ซื้อ", "order", "จอง"])
    news_kw = [
        "ข่าว", "news", "เทรนด์", "trend", "ai", "openai", "google", "meta",
        "ธุรกิจ", "เศรษฐกิจ", "หุ้น", "ลงทุน", "การลงทุน", "กองทุน", "etf",
        "ตราสารหนี้", "ทอง", "อสังหา", "reit", "คริปโต", "bitcoin", "btc",
        "ดอกเบี้ย", "เงินเฟ้อ", "ค่าเงิน", "ตลาดหุ้น", "set", "mai", "nasdaq", "s&p",
        "valuation", "roe", "roa", "pe", "p/e", "cashflow", "cash flow", "กำไร", "รายได้",
        "marketing", "sales", "roi", "business model", "startup", "sme"
    ]
    is_news = any(kw in lowered for kw in news_kw)

    news_context = ""
    if is_news:
        news_context = await get_news_context(text, limit=5)
        if not news_context:
            news_context = await get_news_context("thai_business", limit=5)

    if is_news:
        enriched = (
            f"[คำถามเกี่ยวกับข่าว/ธุรกิจ/การลงทุน/AI]\n{text}\n\n"
            "ตอบโดยใช้บริบทข่าวสดที่แนบมาเป็นหลักถ้ามี วิเคราะห์ผลกระทบ โอกาส ความเสี่ยง และให้คำแนะนำเชิงกลยุทธ์แบบกระชับ"
        )
        reply = await ask_nuan(uid, enriched, news_context=news_context)
    else:
        reply = await ask_nuan(uid, text)

    await reply_long(update, reply, reply_markup=MAIN_MENU)

    if is_order:
        await notify_boss(context, f"📦 ออเดอร์ใหม่!\n👤 {user.first_name} (@{user.username or '-'})\n💬 {text}")


# ─── APP ───────────────────────────────────────────────────
def validate_config() -> None:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not KIMI_KEY:
        missing.append("KIMI_API_KEY")
    if missing:
        raise RuntimeError("Missing required environment variable(s): " + ", ".join(missing))


def main() -> None:
    validate_config()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("faq", cmd_faq))
    app.add_handler(CommandHandler("contact", cmd_contact))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("aitrend", cmd_aitrend))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("🌸 นุ่น Bot (Kimi) เริ่มทำงานแล้วค่ะ!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
