import json
import requests
import re
from bs4 import BeautifulSoup
from flask import Flask, request, send_file, jsonify
import html
import tempfile
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# 🔐 YOUR COOKIE
DEFAULT_COOKIE = "_fbp=fb.2.1769418438923.721603587251513545; Authorization=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjQwNDA0IiwiZW1haWwiOiJhbnlAZGlwZXNoY2hhdWRoYXJ5LmluIiwibmFtZSI6ImRpcHUiLCJ0aW1lc3RhbXAiOjE3NzAxMDkxNzMsInRlbmFudFR5cGUiOiJ1c2VyIiwidGVuYW50TmFtZSI6InN1cGVyMTAwYWRpdHlhc2luZ2hfZGIiLCJ0ZW5hbnRJZCI6IiIsImRpc3Bvc2FibGUiOmZhbHNlfQ.2GKID033W7UYcKb18k8DQBeoIRuw8xvZwG2JycIK1c8; User-ID=40404; base_url=https%3A%2F%super100byadityasingh.akamai.net.in%2F"

def clean_html_tags(text):
    """Aggressively removes HTML, CSS attributes, and forces single-line text."""
    if not text:
        return ""

    # 1. Remove obvious script and style blocks
    text = re.sub(r'<(script|style).*?>.*?</\1>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 2. Remove CSS property-value pairs (e.g., "orphans:0; widows:0; border:none;")
    # This looks for words followed by a colon and ending in a semicolon or quote
    text = re.sub(r'[a-zA-Z-]+\s*:\s*[^;>"]+(;|$|")', ' ', text)
    
    # 3. Remove leftover tag fragments like "> or ">
    text = re.sub(r'[^>]*">', ' ', text)
    text = re.sub(r'^[">]+', ' ', text)

    # 4. Remove all standard HTML tags <...>
    text = re.sub(r'<.*?>', ' ', text)

    # 5. Decode HTML entities (&nbsp;, &amp;, etc.)
    text = html.unescape(text)

    # 6. FORCE SINGLE LINE and remove extra whitespace
    # .split() handles all newlines (\n), tabs (\t), and spaces
    text = " ".join(text.split())

    # 7. Final trim of any stray symbols left at the start
    text = re.sub(r'^[\s\.\*@:;>"}]+', '', text)

    return text.strip()

def contains_images(text):
    if not text: return False
    return any(p in text.lower() for p in ['<img', '.jpg', '.png', '.jpeg', '.gif', 'image_link'])

def process_questions(data):
    output = []
    qn = 0
    skipped = 0

    for q in data:
        q_raw = q.get('question', '')
        
        # Skip image questions
        if contains_images(q_raw) or any(contains_images(q.get(f'option_{i}', '')) for i in range(1, 11)):
            skipped += 1
            continue

        q_clean = clean_html_tags(q_raw)
        if not q_clean:
            skipped += 1
            continue

        qn += 1
        # Each question is now strictly on one line
        output.append(f"{qn}. {q_clean}")

        # Correct answer index
        ans_val = q.get("answer")
        try:
            correct_index = int(ans_val) - 1 if ans_val else -1
        except:
            correct_index = -1

        # Options
        for i in range(1, 11):
            opt_raw = q.get(f'option_{i}', '')
            opt_clean = clean_html_tags(opt_raw)
            if opt_clean:
                # Filter out single letters leaked from messy HTML if they aren't the text
                letter = chr(96 + i) # a, b, c...
                mark = " ✅" if (i-1) == correct_index else ""
                output.append(f"({letter}) {opt_clean}{mark}")

        output.append("") # Blank line between questions

    if skipped:
        output.append(f"\nNote: Skipped {skipped} questions containing images or empty text.")
    return "\n".join(output)

# ---------- EXTRACTOR & API ----------

def extract_test_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
    q_url, title = None, None

    if script_tag:
        try:
            data = json.loads(script_tag.string)
            def search(obj):
                nonlocal q_url, title
                if isinstance(obj, dict):
                    if "test_questions_url" in obj: q_url = obj["test_questions_url"]
                    if "title" in obj and not title: title = obj["title"]
                    for v in obj.values(): search(v)
                elif isinstance(obj, list):
                    for i in obj: search(i)
            search(data)
        except: pass

    if not q_url:
        match = re.search(r'https://[^\s"\']+\.json', html_content)
        q_url = match.group(0) if match else None
    
    if not title:
        tm = re.search(r'<h5[^>]*>(.*?)</h5>', html_content)
        title = clean_html_tags(tm.group(1)) if tm else "test_file"

    return q_url, title

@app.route("/api/get-txt", methods=["POST"])
def get_txt():
    body = request.json
    ts, tn = body.get("test_series"), body.get("test_number")
    if not ts or not tn: return jsonify({"error": "Missing data"}), 400

    try:
        url = f"https://super100byadityasingh.akamai.net.in/test-series/{ts}/tests/{tn}/attempt?testPassUrl="
        r = requests.get(url, headers={"cookie": DEFAULT_COOKIE, "user-agent": "Mozilla/5.0"}, timeout=20)
        
        q_url, title = extract_test_data(r.text)
        if not q_url: return jsonify({"error": "Cookie Expired"}), 403

        q_data = requests.get(q_url).json()
        formatted = process_questions(q_data)

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        temp.write(formatted)
        temp.close()

        safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        return send_file(temp.name, as_attachment=True, download_name=f"{safe_title}.txt", mimetype="text/plain")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)