import os
import re
import json
import asyncio
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

API_URL = "http://localhost:5000/api/get-txt"
SAVE_DIR = "bot_downloads"
os.makedirs(SAVE_DIR, exist_ok=True)

def parse_attempt_url(url):
    pattern = r'test-series/(\d+)/tests/(\d+)/attempt'
    match = re.search(pattern, url)
    if not match:
        return None, None
    return match.group(1), int(match.group(2))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Use /smokey <attempt_url> to extract tests.")

async def smokey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage:\n/smokey <attempt_url>")
        return

    url = context.args[0]
    ts, start_tn = parse_attempt_url(url)

    if not ts:
        await update.message.reply_text("❌ Invalid attempt URL")
        return

    await update.message.reply_text(
        f"🔥 Starting extraction\nSeries: {ts}\nFrom Test: {start_tn}"
    )

    for tn in range(start_tn, start_tn + 5000):
        try:
            r = requests.post(
                API_URL,
                json={"test_series": ts, "test_number": tn},
                timeout=120
            )

            if r.status_code != 200:
                await update.message.reply_text(f"🏁 Reached end of tests or error at {tn} (Status: {r.status_code})")
                break

            filename = f"{ts}_{tn}.txt"
            path = os.path.join(SAVE_DIR, filename)

            with open(path, "wb") as f:
                f.write(r.content)

            await update.message.reply_document(
                document=open(path, "rb"),
                filename=filename
            )

            await asyncio.sleep(1.5)

        except Exception as e:
            await update.message.reply_text(f"⚠️ Error at test {tn}: {str(e)}")
            break

if __name__ == '__main__':
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN not found in environment variables.")
        exit(1)
        
    application = ApplicationBuilder().token(token).build()
    
    start_handler = CommandHandler('start', start)
    smokey_handler = CommandHandler('smokey', smokey)
    
    application.add_handler(start_handler)
    application.add_handler(smokey_handler)
    
    print("Bot is running...")
    application.run_polling()
