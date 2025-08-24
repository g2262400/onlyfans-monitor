import os
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

TARGET_URL = os.getenv("TARGET_URL", "https://onlyfans.com/horvthnorbert15")
CHECK_PATTERNS = ["available now", "seen seconds ago"]
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "5"))
PORT = int(os.getenv("PORT", "8080"))
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

def log(msg):
    print(f"[{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}] {msg}", flush=True)

class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def start_http():
    log(f"http server starting on :{PORT}")
    HTTPServer(("0.0.0.0", PORT), Ping).serve_forever()

def heartbeat():
    while True:
        log("heartbeat")
        time.sleep(15)

def format_duration(total_sec: int) -> str:
    if total_sec < 60:
        return f"{total_sec} second(s)"
    m, s = divmod(total_sec, 60)
    return f"{m} minute(s)" if s == 0 else f"{m} minute(s) {s} second(s)"

def send_discord_message(content: str):
    if not DISCORD_WEBHOOK_URL:
        log(f"Webhook not set. Message: {content}")
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
        log(f"discord status {r.status_code}")
    except Exception as e:
        log(f"discord error: {e}")

def page_inner_text(page):
    try:
        return page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception as e:
        log(f"innerText error: {e}")
        return ""

def monitor():
    available = False
    start_ts = None
    send_discord_message(
        f"Monitoring started for {urlparse(TARGET_URL).netloc}\nURL: {TARGET_URL}\nTime: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}"
    )

    with sync_playwright() as p:
        args = ["--no-sandbox", "--disable-dev-shm-usage"]
        log("launching chromium")
        browser = p.chromium.launch(headless=True, args=args)

        context = browser.new_context(locale="en-US")
        page = context.new_page()

        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ("image","media","font") else route.continue_())

        log(f"opening {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until="networkidle", timeout=45000)
        except Exception as e:
            log(f"navigation warn: {e}")
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception as e2:
                log(f"navigation fail: {e2}")

        log("watching live DOM")

        try:
            while True:
                try:
                    page.evaluate("() => void 0")
                except Exception:
                    pass

                txt = page_inner_text(page).lower()
                present = any(pat in txt for pat in CHECK_PATTERNS)

                if present and not available:
                    available = True
                    start_ts = datetime.now(timezone.utc).astimezone()
                    log("online detected")
                    send_discord_message(f"Online at {start_ts.isoformat(timespec='seconds')}\nURL: {TARGET_URL}")
                elif present and available:
                    elapsed = int((datetime.now(timezone.utc).astimezone() - start_ts).total_seconds())
                    log(f"online for {format_duration(elapsed)}")
                elif not present and available:
                    end_ts = datetime.now(timezone.utc).astimezone()
                    dur = int((end_ts - start_ts).total_seconds())
                    log(f"went offline. online for {format_duration(dur)}")
                    send_discord_message(
                        f"Went offline at {end_ts.isoformat(timespec='seconds')}\n"
                        f"Online duration: {format_duration(dur)}\n"
                        f"URL: {TARGET_URL}"
                    )
                    available = False
                    start_ts = None
                else:
                    log("not available")

                time.sleep(CHECK_INTERVAL_SECONDS)
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    if os.getenv("PORT"):  # only start HTTP server on Koyeb
        threading.Thread(target=start_http, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()
    monitor()
