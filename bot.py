import os, re, json, html, tempfile, asyncio, logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DEFAULT_COOKIE = "_fbp=fb.2.1769418438923.721603587251513545; Authorization=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjQwNDA0IiwiZW1haWwiOiJhbnlAZGlwZXNoY2hhdWRoYXJ5LmluIiwibmFtZSI6ImRpcHUiLCJ0aW1lc3RhbXAiOjE3NzAxMDkxNzMsInRlbmFudFR5cGUiOiJ1c2VyIiwidGVuYW50TmFtZSI6InN1cGVyMTAwYWRpdHlhc2luZ2hfZGIiLCJ0ZW5hbnRJZCI6IiIsImRpc3Bvc2FibGUiOmZhbHNlfQ.2GKID033W7UYcKb18k8DQBeoIRuw8xvZwG2JycIK1c8; User-ID=40404; base_url=https%3A%2F%super100byadityasingh.akamai.net.in%2F"
MAX_TESTS = 5000
DELAY = 1.5

logging.basicConfig(level=logging.INFO)

# ---------------- HELPERS ----------------

def parse_attempt_url(url):
    m = re.search(r'test-series/(\d+)/tests/(\d+)/attempt', url)
    return (m.group(1), int(m.group(2))) if m else (None, None)

def clean_html_tags(text):
    if not text: return ""
    text = re.sub(r'<(script|style).*?>.*?</\1>', ' ', text, flags=re.S)
    text = re.sub(r'<.*?>', ' ', text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()

def contains_images(text):
    return any(x in (text or "").lower() for x in ['<img', '.jpg', '.png', '.jpeg'])

def process_questions(data):
    out, qn = [], 0
    for q in data:
        if contains_images(q.get("question")):
            continue
        q_clean = clean_html_tags(q.get("question"))
        if not q_clean:
            continue

        qn += 1
        out.append(f"{qn}. {q_clean}")

        ans = int(q.get("answer", 0)) - 1
        for i in range(1, 11):
            opt = clean_html_tags(q.get(f"option_{i}", ""))
            if opt:
                mark = " ✅" if (i-1) == ans else ""
                out.append(f"({chr(96+i)}) {opt}{mark}")
        out.append("")
    return "\n".join(out)

def extract_test_data(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")

    q_url, title = None, "test"
    if script:
        data = json.loads(script.string)

        def walk(o):
            nonlocal q_url, title
            if isinstance(o, dict):
                if "test_questions_url" in o:
                    q_url = o["test_questions_url"]
                if "title" in o and title == "test":
                    title = o["title"]
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for i in o:
                    walk(i)

        walk(data)

    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    return q_url, safe_title

# ---------------- BOT COMMAND ----------------

async def smokey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage:\n/smokey <attempt_url>")
        return

    ts, start_test = parse_attempt_url(context.args[0])
    if not ts:
        await update.message.reply_text("❌ Invalid attempt URL")
        return

    await update.message.reply_text(
        f"🔥 Extraction started\nSeries: {ts}\nFrom test: {start_test}"
    )

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Cookie": DEFAULT_COOKIE
    })

    for test_no in range(start_test, start_test + MAX_TESTS):
        try:
            attempt_url = (
                f"https://super100byadityasingh.akamai.net.in/"
                f"test-series/{ts}/tests/{test_no}/attempt?testPassUrl="
            )

            r = session.get(attempt_url, timeout=20)
            q_url, title = extract_test_data(r.text)

            if not q_url:
                await update.message.reply_text("🏁 Finished or cookie expired")
                break

            q_data = session.get(q_url, timeout=20).json()
            txt_data = process_questions(q_data)

            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".txt", mode="w", encoding="utf-8"
            )
            tmp.write(txt_data)
            tmp.close()

            await update.message.reply_document(
                document=open(tmp.name, "rb"),
                filename=f"{title}.txt"
            )

            os.unlink(tmp.name)
            await asyncio.sleep(DELAY)

        except Exception as e:
            await update.message.reply_text(f"⚠️ Error at test {test_no}:\n{e}")
            break

# ---------------- RUN ----------------

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("smokey", smokey))

print("🤖 Bot running...")
app.run_polling()
