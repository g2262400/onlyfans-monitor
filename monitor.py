import time
import os
import requests
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

TARGET_URL = "https://onlyfans.com/horvthnorbert15"
CHECK_PATTERNS = ["Available now", "Seen seconds ago"]
CHECK_INTERVAL_SECONDS = 5

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def format_duration(seconds_total: int) -> str:
    if seconds_total < 60:
        return f"{seconds_total} second(s)"
    minutes = seconds_total // 60
    seconds = seconds_total % 60
    if seconds == 0:
        return f"{minutes} minute(s)"
    return f"{minutes} minute(s) {seconds} second(s)"

def send_discord_message(content: str):
    if not DISCORD_WEBHOOK_URL:
        print(f"[{now_iso()}] Webhook not set. Message: {content}")
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
        print(f"[{now_iso()}] Discord send status {r.status_code}")
    except Exception as e:
        print(f"[{now_iso()}] Discord error: {e}")

def monitor():
    available = False
    start_ts = None

    send_discord_message(f"📡 Monitoring started for {urlparse(TARGET_URL).netloc}\nURL: {TARGET_URL}\nTime: {now_iso()}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(TARGET_URL)
        print(f"[{now_iso()}] Opened {TARGET_URL}")

        try:
            while True:
                html = page.content()
                present = any(p in html for p in CHECK_PATTERNS)

                if present and not available:
                    available = True
                    start_ts = datetime.now(timezone.utc).astimezone()
                    send_discord_message(f"🟢 Online at {start_ts.isoformat(timespec='seconds')}\nURL: {TARGET_URL}")
                elif present and available:
                    elapsed = int((datetime.now(timezone.utc).astimezone() - start_ts).total_seconds())
                    print(f"[{now_iso()}] ⏱ Online for {format_duration(elapsed)}")
                elif not present and available:
                    end_ts = datetime.now(timezone.utc).astimezone()
                    elapsed = int((end_ts - start_ts).total_seconds())
                    send_discord_message(
                        f"🔴 Went offline at {end_ts.isoformat(timespec='seconds')}\n"
                        f"Online duration: {format_duration(elapsed)}\n"
                        f"URL: {TARGET_URL}"
                    )
                    available = False
                    start_ts = None
                else:
                    print(f"[{now_iso()}] Not available.")

                time.sleep(CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            browser.close()
            print("Stopped.")

if __name__ == "__main__":
    monitor()
