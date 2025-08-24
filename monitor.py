import time
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Target settings
TARGET_URL = "https://onlyfans.com/horvthnorbert15"
CHECK_PATTERNS = ["Available now", "Seen seconds ago"]
CHECK_INTERVAL_SECONDS = 5   # loop interval

# Discord webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1408951816875675741/t3HMOIprYOTBBYsWmTEMnOIg4B1EcaEUlT0nCDWc9xl47mlOK-En0GFHqJArrBHMKeNW"

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

def send_discord_message(content):
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=15)
        if resp.status_code >= 300:
            print(f"[{now_iso()}] Discord webhook failed with status {resp.status_code}. Body: {resp.text[:300]}")
        else:
            print(f"[{now_iso()}] Discord message sent.")
    except Exception as e:
        print(f"[{now_iso()}] Discord webhook error: {e}")

def init_browser():
    options = Options()
    # comment this if you want to see the browser
    # options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def monitor_live(url):
    driver = init_browser()
    driver.get(url)
    print(f"[{now_iso()}] Opened {url}. Now watching live DOM updates...")

    available = False
    start_ts = None

    send_discord_message(f"📡 Monitoring has started for {urlparse(url).netloc}\nURL: {url}\nTime: {now_iso()}")

    try:
        while True:
            html = driver.page_source
            present = any(p in html for p in CHECK_PATTERNS)

            if present and not available:
                # first time going online
                available = True
                start_ts = datetime.now(timezone.utc).astimezone()
                print(f"[{now_iso()}] 🟢 First seen available. Online at {start_ts.isoformat(timespec='seconds')}")
                send_discord_message(f"🟢 Online at {start_ts.isoformat(timespec='seconds')}\nURL: {url}")

            elif present and available:
                # live counter in console only
                now = datetime.now(timezone.utc).astimezone()
                elapsed = int((now - start_ts).total_seconds())
                duration_str = format_duration(elapsed)
                print(f"[{now_iso()}] ⏱ Online for {duration_str}")

            elif not present and available:
                # went offline, calculate duration
                end_ts = datetime.now(timezone.utc).astimezone()
                duration_sec = int((end_ts - start_ts).total_seconds())
                duration_str = format_duration(duration_sec)
                print(f"[{now_iso()}] 🔴 No longer available. Online for {duration_str}.")
                send_discord_message(
                    f"🔴 Went offline at {end_ts.isoformat(timespec='seconds')}\n"
                    f"Online duration: {duration_str}\n"
                    f"URL: {url}"
                )
                available = False
                start_ts = None

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print(f"\n[{now_iso()}] Stopped by user.")
        driver.quit()
        if available and start_ts:
            end_ts = datetime.now(timezone.utc).astimezone()
            duration_sec = int((end_ts - start_ts).total_seconds())
            duration_str = format_duration(duration_sec)
            send_discord_message(
                f"❌ Monitoring stopped while user was online.\n"
                f"Online since: {start_ts.isoformat(timespec='seconds')}\n"
                f"Duration so far: {duration_str}\n"
                f"URL: {url}"
            )

if __name__ == "__main__":
    if TARGET_URL.startswith("http"):
        monitor_live(TARGET_URL)
    else:
        raise SystemExit("Set TARGET_URL to the page you want to monitor. Include http or https.")
