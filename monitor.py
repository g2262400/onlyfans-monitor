import os
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

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
        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        log("launching chromium")
        browser = p.chromium.launch(headless=True, args=args)

        # Realistic desktop fingerprint
        context = browser.new_context(
            locale="en-US",
            timezone_id="UTC",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        """)

        page = context.new_page()

        # Block heavy assets
        def route_handler(route):
            rt = route.request.resource_type
            if rt in ("image", "media", "font"):
                return route.abort()
            return route.continue_()
        page.route("**/*", route_handler)

        # Robust navigation with retries
        log(f"opening {TARGET_URL}")
        nav_ok = False
        for attempt in range(1, 4):
            try:
                page.goto(TARGET_URL, wait_until="networkidle", timeout=45000)
                nav_ok = True
                break
            except PWTimeout as e:
                log(f"navigation timeout attempt {attempt}: {e}")
            except Exception as e:
                log(f"navigation error attempt {attempt}: {e}")
            time.sleep(2)
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
                nav_ok = True
                break
            except Exception as e2:
                log(f"fallback nav error attempt {attempt}: {e2}")
                time.sleep(2)

        if not nav_ok:
            log("failed to navigate after retries, exiting")
            try:
                context.close(); browser.close()
            except Exception:
                pass
            return

        # Quick snapshot to verify content
        try:
            html = page.content()
            log(f"page url: {page.url}")
            log(f"html length: {len(html)}")
            log(f"html head: {html[:200].replace(chr(10),' ')}")
            txt = page_inner_text(page)
            log(f"innerText length: {len(txt)}")
            log(f"innerText head: {txt[:200].replace(chr(10),' ')}")
        except Exception as e:
            log(f"snapshot error: {e}")

        log("watching live DOM")

        try:
            while True:
                # keep JS alive
                try:
                    page.evaluate("() => void 0")
                except Exception:
                    pass

                txt = page_inner_text(page).lower()
                # also fallback to html if needed
                if not txt:
                    try:
                        html = page.content().lower()
                    except Exception:
                        html = ""
                else:
                    html = ""

                present = any(pat in txt for pat in CHECK_PATTERNS) or any(pat in html for pat in CHECK_PATTERNS)

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
                context.close(); browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    if os.getenv("PORT"):
        threading.Thread(target=start_http, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()
    monitor()
