from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

import bot as nuan_core

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()
LINE_BOSS_USER_ID = os.environ.get("LINE_BOSS_USER_ID", "").strip()
MAX_LINE_CHARS = 4900
MAX_LINE_MESSAGES = 5

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

ORDER_KEYWORDS = ["สั่ง", "ซื้อ", "order", "จอง"]
NEWS_KEYWORDS = [
    "ข่าว", "news", "เทรนด์", "trend", "ai", "openai", "google", "meta",
    "ธุรกิจ", "เศรษฐกิจ", "หุ้น", "ลงทุน", "การลงทุน", "กองทุน", "etf",
    "ตราสารหนี้", "ทอง", "อสังหา", "reit", "คริปโต", "bitcoin", "btc",
    "ดอกเบี้ย", "เงินเฟ้อ", "ค่าเงิน", "ตลาดหุ้น", "set", "mai", "nasdaq", "s&p",
    "valuation", "roe", "roa", "pe", "p/e", "cashflow", "cash flow", "กำไร", "รายได้",
    "marketing", "sales", "roi", "business model", "startup", "sme"
]

LINE_MENU_TEXT = """สวัสดีค่ะ 🌸 หนูชื่อ "นุ่น" AI เลขาและที่ปรึกษาค่ะ

พิมพ์เลือกเมนูได้เลยนะคะ:
💬 คุยกับนุ่น
📦 สั่งสินค้า/บริการ
📰 ข่าว AI & ธุรกิจ
🤖 เทรนด์ AI วันนี้
❓ FAQ
✈️ แนะนำ Username
📞 ติดต่อบอส
🔄 เริ่มใหม่

หรือพิมพ์คำถามถึงนุ่นได้เลยค่ะ 😊"""


def build_system_prompt() -> str:
    return f"""คุณชื่อ "นุ่น" เป็น AI เลขาและที่ปรึกษาส่วนตัวของ "คุณหมู" (บอส) ทำงานผ่าน LINE Official Account

วันที่/เวลาปัจจุบัน: {nuan_core.today_th()}

บุคลิก:
- พูดสุภาพ ใช้ "ค่ะ" "นะคะ" เป็นผู้หญิง อบอุ่น มืออาชีพ กระชับ
- ใช้ emoji พอเหมาะ ไม่มากเกินไป
- ตอบเหมาะกับ LINE อ่านง่าย ไม่ยาวเกินจำเป็น

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


# Reuse the same AI/news core, but switch the prompt to LINE wording in this web service process.
nuan_core.build_system_prompt = build_system_prompt


def env_int(name: str, default: int = 0) -> int:
    value = os.environ.get(name, str(default)).strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        log.warning("Invalid integer for %s=%r. Fallback to %s", name, value, default)
        return default


def split_line_text(text: str) -> list[str]:
    return nuan_core.split_text(text or "ค่ะ", MAX_LINE_CHARS)


def to_line_messages(text: str) -> list[dict[str, str]]:
    chunks = split_line_text(text)
    if len(chunks) > MAX_LINE_MESSAGES:
        suffix = "\n\n…ข้อความยาวเกินข้อจำกัดของ LINE จึงตัดบางส่วนออกค่ะ"
        chunks = chunks[:MAX_LINE_MESSAGES]
        chunks[-1] = chunks[-1][:MAX_LINE_CHARS - len(suffix)] + suffix
    return [{"type": "text", "text": chunk or "ค่ะ"} for chunk in chunks]


def is_order_text(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in ORDER_KEYWORDS)


def is_news_text(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in NEWS_KEYWORDS)


def source_label(source: dict[str, Any]) -> str:
    source_type = source.get("type", "unknown")
    user_id = source.get("userId", "-")
    chat_id = source.get("groupId") or source.get("roomId")
    return f"{source_type}:{chat_id} user:{user_id}" if chat_id else f"user:{user_id}"


def session_key(source: dict[str, Any]) -> str:
    if source.get("userId"):
        return f"line:user:{source['userId']}"
    if source.get("groupId"):
        return f"line:group:{source['groupId']}"
    if source.get("roomId"):
        return f"line:room:{source['roomId']}"
    return "line:unknown"


def verify_line_signature(body: bytes, signature: str) -> bool:
    if not LINE_CHANNEL_SECRET or not signature:
        return False
    digest = hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def post_json_sync(url: str, payload: dict[str, Any], headers: dict[str, str]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = UrlRequest(url, data=data, method="POST", headers=headers)
    try:
        with urlopen(request, timeout=12) as response:  # nosec B310 - official API endpoint
            response.read()
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API error {e.code}: {error_body}") from e
    except URLError as e:
        raise RuntimeError(f"API connection error: {e}") from e


def line_api_post_sync(path: str, payload: dict[str, Any]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is not configured")
    post_json_sync(
        "https://api.line.me" + path,
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        },
    )


async def send_line_reply(reply_token: str, text: str) -> None:
    if reply_token:
        await asyncio.to_thread(line_api_post_sync, "/v2/bot/message/reply", {"replyToken": reply_token, "messages": to_line_messages(text)})


async def send_line_push(to: str, text: str) -> None:
    if to:
        await asyncio.to_thread(line_api_post_sync, "/v2/bot/message/push", {"to": to, "messages": to_line_messages(text)})


def telegram_notify_sync(text: str) -> None:
    if not nuan_core.TELEGRAM_TOKEN or not nuan_core.BOSS_CHAT_ID:
        return
    post_json_sync(
        f"https://api.telegram.org/bot{nuan_core.TELEGRAM_TOKEN}/sendMessage",
        {"chat_id": nuan_core.BOSS_CHAT_ID, "text": text},
        {"Content-Type": "application/json"},
    )


async def notify_boss(msg: str) -> None:
    text = f"🔔 แจ้งเตือนจากนุ่น (LINE)\n\n{msg}"
    if LINE_BOSS_USER_ID:
        try:
            await send_line_push(LINE_BOSS_USER_ID, text)
        except Exception as e:
            log.exception("line boss push error: %s", e)
    if nuan_core.TELEGRAM_TOKEN and nuan_core.BOSS_CHAT_ID:
        try:
            await asyncio.to_thread(telegram_notify_sync, text)
        except Exception as e:
            log.exception("telegram boss notify error: %s", e)


async def reply_news(reply_token: str, uid: str, *, trend: bool = False) -> None:
    if trend:
        news_context = await nuan_core.get_news_context("ai_trend", limit=6)
        prompt = "วิเคราะห์เทรนด์ AI ที่กำลังมาแรงตอนนี้ 5 เรื่อง พร้อมบอกว่าแต่ละเรื่องมีผลต่อธุรกิจและการลงทุนอย่างไร ตอบเป็นภาษาไทยกระชับ"
        title = "🤖 เทรนด์ AI ที่น่าจับตาค่ะ"
    else:
        news_context = await nuan_core.get_news_context("ai_business", limit=6)
        prompt = "สรุปข่าว AI ธุรกิจ เศรษฐกิจ และการลงทุนสำคัญล่าสุด 5 เรื่อง พร้อมวิเคราะห์ผลกระทบต่อธุรกิจและนักลงทุน ตอบเป็นภาษาไทยแบบกระชับ"
        title = "📰 ข่าว AI & ธุรกิจล่าสุดค่ะ"
    reply = await nuan_core.ask_nuan(uid, prompt, news_context=news_context)
    await send_line_reply(reply_token, f"{title}\n\n{reply}")


async def handle_text_event(event: dict[str, Any]) -> None:
    reply_token = event.get("replyToken", "")
    source = event.get("source", {}) or {}
    text = ((event.get("message", {}) or {}).get("text") or "").strip()
    uid = session_key(source)

    if not text:
        await send_line_reply(reply_token, "ตอนนี้นุ่นอ่านข้อความชนิดนี้ไม่ได้ค่ะ ส่งเป็นข้อความตัวอักษรได้เลยนะคะ 😊")
        return

    plain_text = text.lower()
    if plain_text in {"/start", "start", "menu", "เมนู", "เริ่ม", "เริ่มต้น"}:
        await send_line_reply(reply_token, LINE_MENU_TEXT)
        return

    if text in {"💬 คุยกับนุ่น", "คุยกับนุ่น"}:
        await send_line_reply(reply_token, "พิมพ์ถามมาได้เลยค่ะ! 😊")
        return
    if text in {"📦 สั่งสินค้า/บริการ", "สั่งสินค้า", "สั่งซื้อ"}:
        nuan_core.user_modes[uid] = "order"
        await send_line_reply(reply_token, "📦 พิมพ์รายละเอียดที่ต้องการสั่งได้เลยนะคะ เช่น รายการ จำนวน เบอร์โทร หรือช่องทางติดต่อ\nหนูจะแจ้งบอสให้ทันทีค่ะ 😊")
        return
    if text in {"📞 ติดต่อบอส", "ติดต่อบอส"}:
        nuan_core.user_modes[uid] = "contact"
        await send_line_reply(reply_token, "📞 ฝากข้อความถึงบอสไว้ได้เลยค่ะ เดี๋ยวนุ่นส่งให้คุณหมูนะคะ 😊")
        await notify_boss(f"👤 ผู้ใช้ LINE ({source_label(source)}) ต้องการติดต่อคุณหมูค่ะ")
        return
    if text in {"✈️ แนะนำ Username", "แนะนำ Username", "username"}:
        nuan_core.user_modes[uid] = "username"
        await send_line_reply(reply_token, "✈️ บอกชื่อธุรกิจ/แบรนด์/คีย์เวิร์ดมาได้เลยค่ะ หนูจะแนะนำ Telegram Username ให้นะคะ 😊")
        return
    if text in {"❓ FAQ", "FAQ", "faq"}:
        await send_line_reply(reply_token, "❓ FAQ ค่ะ\n\n🕐 เวลาทำการ → ทุกวัน 9:00–18:00 น.\n💰 ราคา → ติดต่อสอบถามได้เลยค่ะ\n📦 สั่งซื้อ → พิมพ์ 'สั่งสินค้า' ได้เลยค่ะ\n\nมีคำถามอื่นอีกไหมคะ? 😊")
        return
    if text in {"📰 ข่าว AI & ธุรกิจ", "ข่าว AI", "ข่าวธุรกิจ"}:
        await reply_news(reply_token, uid, trend=False)
        return
    if text in {"🤖 เทรนด์ AI วันนี้", "เทรนด์ AI", "trend ai"}:
        await reply_news(reply_token, uid, trend=True)
        return
    if text in {"🔄 เริ่มใหม่", "reset", "เริ่มใหม่"}:
        nuan_core.chat_histories.pop(uid, None)
        nuan_core.user_modes.pop(uid, None)
        await send_line_reply(reply_token, "เริ่มใหม่แล้วค่ะ 🔄 ถามมาได้เลยนะคะ! 🌸")
        return

    mode = nuan_core.user_modes.pop(uid, None)
    if mode == "order":
        await send_line_reply(reply_token, "รับรายละเอียดแล้วค่ะ 📦 หนูแจ้งบอสให้ทันทีนะคะ 😊")
        await notify_boss(f"📦 ออเดอร์ใหม่จาก LINE!\n👤 {source_label(source)}\n💬 {text}")
        return
    if mode == "contact":
        await send_line_reply(reply_token, "รับข้อความแล้วค่ะ 📞 หนูส่งต่อให้คุณหมูเรียบร้อยนะคะ 😊")
        await notify_boss(f"📞 ข้อความถึงบอสจาก LINE\n👤 {source_label(source)}\n💬 {text}")
        return
    if mode == "username":
        reply = await nuan_core.ask_nuan(
            uid,
            f"ช่วยแนะนำ Telegram Username สำหรับธุรกิจ/แบรนด์นี้อย่างน้อย 10 ตัว: {text}\nกติกา: ต้องขึ้นต้นด้วย @ ใช้ตัวอักษรอังกฤษ ตัวเลข หรือ underscore เท่านั้น อ่านง่าย จำง่าย และอธิบายสั้น ๆ ว่าเหมาะเพราะอะไร",
        )
        await send_line_reply(reply_token, reply)
        return

    news_context = ""
    if is_news_text(text):
        news_context = await nuan_core.get_news_context(text, limit=5) or await nuan_core.get_news_context("thai_business", limit=5)
    if is_news_text(text):
        enriched = f"[คำถามเกี่ยวกับข่าว/ธุรกิจ/การลงทุน/AI]\n{text}\n\nตอบโดยใช้บริบทข่าวสดที่แนบมาเป็นหลักถ้ามี วิเคราะห์ผลกระทบ โอกาส ความเสี่ยง และให้คำแนะนำเชิงกลยุทธ์แบบกระชับ"
        reply = await nuan_core.ask_nuan(uid, enriched, news_context=news_context)
    else:
        reply = await nuan_core.ask_nuan(uid, text)
    await send_line_reply(reply_token, reply)

    if is_order_text(text):
        await notify_boss(f"📦 ออเดอร์ใหม่จาก LINE!\n👤 {source_label(source)}\n💬 {text}")


async def process_events(events: list[dict[str, Any]]) -> None:
    for event in events:
        try:
            event_type = event.get("type")
            if event_type == "message" and (event.get("message") or {}).get("type") == "text":
                await handle_text_event(event)
            elif event_type == "follow":
                await send_line_reply(event.get("replyToken", ""), LINE_MENU_TEXT)
            elif event.get("replyToken"):
                await send_line_reply(event.get("replyToken", ""), "ตอนนี้นุ่นรองรับข้อความตัวอักษรก่อนนะคะ 😊")
        except Exception as e:
            log.exception("line event processing error: %s", e)


def validate_config() -> None:
    missing = []
    if not nuan_core.KIMI_KEY:
        missing.append("KIMI_API_KEY")
    if not LINE_CHANNEL_ACCESS_TOKEN:
        missing.append("LINE_CHANNEL_ACCESS_TOKEN")
    if not LINE_CHANNEL_SECRET:
        missing.append("LINE_CHANNEL_SECRET")
    if missing:
        raise RuntimeError("Missing required environment variable(s): " + ", ".join(missing))


app = FastAPI(title="Nuan LINE Bot", version="1.0.0")


@app.on_event("startup")
async def startup() -> None:
    validate_config()
    log.info("🌸 นุ่น LINE Bot พร้อมรับ webhook ที่ /line/webhook แล้วค่ะ")


@app.get("/")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "nuan-line-bot", "line_configured": bool(LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET)}


@app.get("/healthz")
async def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.post("/line/webhook")
async def line_webhook(request: Request, background_tasks: BackgroundTasks, x_line_signature: str = Header(default="", alias="x-line-signature")) -> JSONResponse:
    body = await request.body()
    if not verify_line_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid LINE signature")
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e
    events = payload.get("events", [])
    if events:
        background_tasks.add_task(process_events, events)
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn

    validate_config()
    uvicorn.run(app, host="0.0.0.0", port=env_int("PORT", 8000))
