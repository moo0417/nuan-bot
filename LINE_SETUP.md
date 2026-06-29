# LINE Messaging API setup for Nuan Bot

This repo now supports LINE through `line_bot.py` while keeping the existing Telegram bot in `bot.py`.

## Environment variables

Required for LINE:

- `KIMI_API_KEY` — same Kimi/Moonshot API key used by the Telegram bot
- `LINE_CHANNEL_ACCESS_TOKEN` — Messaging API channel access token from LINE Developers Console
- `LINE_CHANNEL_SECRET` — Messaging API channel secret from LINE Developers Console

Optional:

- `LINE_BOSS_USER_ID` — LINE user ID, group ID, or room ID to receive boss notifications by LINE push message
- `TELEGRAM_TOKEN` and `BOSS_CHAT_ID` — if set, LINE orders/contact messages will also be forwarded to the Telegram boss chat
- `KIMI_MODEL` — defaults to `moonshot-v1-8k`
- `KIMI_BASE_URL` — defaults to `https://api.moonshot.cn/v1`
- `PORT` — web server port, defaults to `8000`

## Run locally

```bash
pip install -r requirements.txt
uvicorn line_bot:app --host 0.0.0.0 --port 8000
```

Health checks:

- `GET /`
- `GET /healthz`

LINE webhook endpoint:

- `POST /line/webhook`

## LINE Developers Console

1. Create or open a Messaging API channel.
2. Set the webhook URL to:

   ```text
   https://YOUR_PUBLIC_DOMAIN/line/webhook
   ```

3. Enable **Use webhook**.
4. Put the channel access token and channel secret into the deployment environment variables.
5. Verify the webhook URL in the LINE Developers Console.

## Notes

- LINE requires a public HTTPS webhook URL.
- LINE webhook requests are verified with `x-line-signature` before processing.
- Reply messages use `/v2/bot/message/reply`.
- Optional boss notifications by LINE use `/v2/bot/message/push`.
- The existing Telegram bot can keep running separately with `python bot.py`.
