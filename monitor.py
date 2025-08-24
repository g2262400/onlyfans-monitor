import os
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

# Config
TARGET_URL = os.getenv("TARGET_URL", "https://onlyfans.com/horvthnorbert15")
CHECK_PATTERNS = ["Available now", "Seen seconds ago"]
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "5"))
PORT = int(os.getenv("PORT", "8080"))  # Koyeb expects a web port
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# Tiny HTTP server to satisfy Koyeb Web Service
class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def start_http():
    HTTPServer(("0.0.0.0", PORT), Ping).serve_forever()

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
        print(f"[{now_iso()}] Discord status {r.status_code}")
    except Exception as e:
        print(f"[{now_iso()}] Discord error: {e}")

def monitor():
    available = False
    start_ts = None

    send_discord_message(
        f"Monitoring started for {urlparse(TARGET_URL).netloc}\nURL: {TARGET_URL}\nTime: {now_iso()}"
    )

    with sync_playwright() as p:
        # Headless Chromium with minimal flags
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print(f"[{now_iso()}] Opening {TARGET_URL}...")
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[{now_iso()}] First navigation error: {e}")

        print(f"[{now_iso()}] Watching live DOM updates...")

        try:
            while True:
                try:
                    html = page.content()
                except Exception as e:
                    print(f"[{now_iso()}] Read content error: {e}")
                    time.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                present = any(pat in html for pat in CHECK_PATTERNS)

                if present and not available:
                    available = True
                    start_ts = datetime.now(timezone.utc).astimezone()
                    print(f"[{now_iso()}] Online detected.")
                    send_discord_message(
                        f"Online at {start_ts.isoformat(timespec='seconds')}\nURL: {TARGET_URL}"
                    )

                elif present and available:
                    elapsed = int((datetime.now(timezone.utc).astimezone() - start_ts).total_seconds())
                    print(f"[{now_iso()}] Online for {format_duration(elapsed)}")

                elif not present and available:
                    end_ts = datetime.now(timezone.utc).astimezone()
                    duration_sec = int((end_ts - start_ts).total_seconds())
                    duration_str = format_duration(duration_sec)
                    print(f"[{now_iso()}] Went offline. Online for {duration_str}.")
                    send_discord_message(
                        f"Went offline at {end_ts.isoformat(timespec='seconds')}\n"
                        f"Online duration: {duration_str}\n"
                        f"URL: {TARGET_URL}"
                    )
                    available = False
                    start_ts = None
                else:
                    print(f"[{now_iso()}] Not available.")

                time.sleep(CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print(f"[{now_iso()}] Stopped by user.")
        finally:
            try:
                browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    # Start the tiny HTTP server for Koyeb Web Service health
    threading.Thread(target=start_http, daemon=True).start()
    # Start the monitor
    monitor()
