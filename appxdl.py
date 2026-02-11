import requests
import os
import time

API_URL = "http://127.0.0.1:5000/api/get-txt"   #change this
TEST_SERIES_ID = 124
START_TEST = 1
END_TEST = 5000

SAVE_DIR = "download"
os.makedirs(SAVE_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

def get_filename_from_headers(response, fallback):
    cd = response.headers.get("Content-Disposition")
    if cd and "filename=" in cd:
        filename = cd.split("filename=")[-1].strip('"')
        return filename
    return fallback

for test_no in range(START_TEST, END_TEST + 1):
    try:
        print(f"⬇ Downloading Test {test_no}...")

        response = session.post(
            API_URL,
            json={
                "test_series": TEST_SERIES_ID,
                "test_number": test_no
            },
            timeout=60
        )

        if response.status_code != 200:
            print(f"❌ Skipped {test_no} (status {response.status_code})")
            continue

        filename = get_filename_from_headers(
            response,
            f"{TEST_SERIES_ID}_{test_no}.txt"
        )

        filepath = os.path.join(SAVE_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        print(f"✅ Saved: {filename}")

        # prevent hammering server

    except Exception as e:
        print(f"⚠ Error in Test {test_no}: {e}")

