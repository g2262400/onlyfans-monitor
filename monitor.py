import os
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

TARGET_URL = os.getenv("TARGET_URL", "https://onlyfans.com/horvthnorbert15")
CHECK_PATTERNS = ["available now", "seen seconds ago"]  # case-insensitive
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "5"))
PORT = int(os.getenv("PORT", "8080"))
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

def start_http():
    HTTPServer(("0.0.0.0", PORT), Ping).serve_forever()

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def format_duration(total_sec: int) -> str:
    if total_sec < 60: return f"{total_sec} second(s)"
    m, s = divmod(total_sec, 60)
    return f"{m} minute(s)" if s == 0 else f"{m} minute(s) {s} second(s)"

def send_discord_message(content: str):
    if not DISCORD_WEBHOOK_URL:
        print(f"[{now_iso()}] Webhook not set. Message: {content}"); return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
        print(f"[{now_iso()}] Discord status {r.status_code}")
    except Exception as e:
        print(f"[{now_iso()}] Discord error: {e}")

def page_inner_text(page):
    try:
        return page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception as e:
        print(f"[{now_iso()}] innerText error: {e}")
        return ""

def accept_cookies_if_any(page):
    try:
        candidates = [
            "button:has-text('Accept')",
            "button:has-text('I agree')",
            "button:has-text('Allow all')",
            "[aria-label='Accept']",
        ]
        for sel in candidates:
            el = page.locator(sel)
            if el.first.is_visible(timeout=1000):
                el.first.click(timeout=1000)
                time.sleep(0.5)
                break
    except Exception:
        pass

def monitor():
    available = False
    start_ts = None
    send_discord_message(f"Monitoring started for {urlparse(TARGET_URL).netloc}\nURL: {TARGET_URL}\nTime: {now_iso()}")

    with sync_playwright() as p:
        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-blink-features=AutomationControlled",
        ]
        browser = p.chromium.launch(headless=True, args=args)

        context = browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'language', {get: () => 'en-US'});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        """)

        page = context.new_page()

        # Block heavy assets to reduce memory and speed up
        def route_handler(route):
            rt = route.request.resource_type
            if rt in ("image", "media", "font"):
                return route.abort()
            return route.continue_()
        page.route("**/*", route_handler)

        print(f"[{now_iso()}] Opening {TARGET_URL}...")
        try:
            page.goto(TARGET_URL, wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"[{now_iso()}] Navigation warning: {e}")
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception as e2:
                print(f"[{now_iso()}] Second navigation failed: {e2}")

        accept_cookies_if_any(page)
        print(f"[{now_iso()}] Watching live DOM updates...")

        try:
            while True:
                # Nudge page periodically so scripts keep running
                try:
                    page.evaluate("() => void 0")
                except Exception:
                    pass

                text = page_inner_text(page).lower()
                present = any(pat in text for pat in CHECK_PATTERNS)

                if present and not available:
                    available = True
                    start_ts = datetime.now(timezone.utc).astimezone()
                    print(f"[{now_iso()}] Online detected.")
                    send_discord_message(f"Online at {start_ts.isoformat(timespec='seconds')}\nURL: {TARGET_URL}")

                elif present and available:
                    elapsed = int((datetime.now(timezone.utc).astimezone() - start_ts).total_seconds())
                    print(f"[{now_iso()}] Online for {format_duration(elapsed)}")

                elif not present and available:
                    end_ts = datetime.now(timezone.utc).astimezone()
                    dur_sec = int((end_ts - start_ts).total_seconds())
                    dur_str = format_duration(dur_sec)
                    print(f"[{now_iso()}] Went offline. Online for {dur_str}.")
                    send_discord_message(
                        f"Went offline at {end_ts.isoformat(timespec='seconds')}\n"
                        f"Online duration: {dur_str}\n"
                        f"URL: {TARGET_URL}"
                    )
                    available = False
                    start_ts = None
                else:
                    print(f"[{now_iso()}] Not available.")

                time.sleep(CHECK_INTERVAL_SECONDS)
        finally:
            try:
                context.close(); browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    threading.Thread(target=start_http, daemon=True).start()
    monitor()
