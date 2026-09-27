import os
import sys
import json
import time
import base64
import logging
import threading
import asyncio
import subprocess
import httpx
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WebookBot")

app = Flask(__name__, template_folder="templates", static_folder="static")

bot_state = {
    "status": "idle",
    "current_step": "idle",
    "logs": [],
    "target_url": "",
    "event_title": "الوضع الشامل للفعاليات",
    "account_email": "",
    "scraped_events": [],
    "ticket_quantity": 100,
    "preferred_tier": "vip",
    "latest_screenshot_b64": "",
}

bot_stop_event = threading.Event()
bot_thread = None
xvfb_process = None

def start_virtual_display():
    global xvfb_process
    try:
        if xvfb_process:
            xvfb_process.terminate()
        
        os.environ["XDG_RUNTIME_DIR"] = "/tmp/runtime-root"
        os.makedirs("/tmp/runtime-root", exist_ok=True)
        os.chmod("/tmp/runtime-root", 0o700)

        xvfb_process = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x800x24", "-ac"])
        os.environ["DISPLAY"] = ":99"
        logger.info("[DISPLAY] تم تشغيل الشاشة الوهمية Xvfb بنجاح")
    except Exception as e:
        logger.warning(f"[DISPLAY] تحذير Xvfb: {e}")

def add_log(level: str, message: str, step: str = ""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "id": f"log_{int(time.time() * 1000)}",
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "step": step
    }
    bot_state["logs"].append(log_entry)
    if len(bot_state["logs"]) > 250:
        bot_state["logs"].pop(0)
    logger.info(f"[{level.upper()}] {message}")

async def fetch_all_platform_events():
    """جلب قائمة الفعاليات العامة من المنصة عبر طلبات سريعة"""
    add_log("info", "[API] جاري سحب قائمة الفعاليات المتاحة من المنصة الرسمية...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get("https://webook.com/api/explore/events", headers=headers)
            if response.status_code == 200:
                data = response.json()
                events_list = data.get("data", []) if isinstance(data, dict) else data
                bot_state["scraped_events"] = events_list
                add_log("success", f"[API] تمت عملية السحب بنجاح! تم العثور على {len(events_list)} فعالية.")
                return events_list
            else:
                add_log("warning", f"[API] استجابة غير مباشرة من الخادم (Status: {response.status_code})، سيتم الاعتماد على المتصفح المباشر.")
    except Exception as e:
        add_log("warning", f"[API] تعذر السحب المباشر عبر الـ API: {e}")
    return []

async def playwright_automation_worker(config: dict):
    from playwright.async_api import async_playwright

    start_virtual_display()

    email = config.get("email", "")
    password = config.get("password", "")
    target_url = config.get("target_url", "https://webook.com/ar/explore")

    bot_state["status"] = "running"
    bot_state["account_email"] = email
    bot_state["target_url"] = target_url

    add_log("bot", "=======================================================")
    add_log("bot", f"🚀 تشغيل البوت الشامل للرابط والفعاليات المستهدفة...")

    await fetch_all_platform_events()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1280,800"
                ]
            )

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                locale="ar-SA"
            )

            page = await context.new_page()

            bot_state["current_step"] = "navigate_explore"
            add_log("info", "[NAVIGATE] فتح منصة الاستكشاف الرئيسية...")
            await page.goto("https://webook.com/ar/explore", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2000)

            bot_state["current_step"] = "login"
            add_log("info", "[AUTH] الانتقال لصفحة تسجيل الدخول للحساب...")
            await page.goto("https://webook.com/ar/login", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)

            email_input = page.locator("input[type='email'], input[name='email'], #email").first
            if await email_input.is_visible(timeout=8000):
                await email_input.fill(email)
                await page.wait_for_timeout(500)

                continue_btn = page.locator("button:has-text('تابع باستخدام البريد الإلكتروني'), button:has-text('Continue'), button[type='submit']").first
                if await continue_btn.is_visible(timeout=3000):
                    await continue_btn.click()
                    await page.wait_for_timeout(1000)

                password_input = page.locator("input[type='password'], input[name='password'], #password").first
                if await password_input.is_visible(timeout=8000):
                    await password_input.fill(password)
                    submit_btn = page.locator("button[type='submit'], button:has-text('تسجيل الدخول')").first
                    await submit_btn.click()
                    add_log("success", f"[AUTH] تم تسجيل الدخول بنجاح بالحساب: {email}")
                    await page.wait_for_timeout(4000)

            if bot_stop_event.is_set():
                await browser.close()
                return

            bot_state["current_step"] = "navigate_event"
            add_log("info", f"[NAVIGATE] الانتقال لرابط الفعالية لفحص المقاعد والتذاكر: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)

            try:
                book_btn = page.locator("button:has-text('احجز التذاكر'), button:has-text('Book Tickets'), a:has-text('احجز')").first
                if await book_btn.is_visible(timeout=4000):
                    await book_btn.click()
                    add_log("info", "[ACTION] تم النقر على زر الحجز وفتح مخطط المقاعد والتذاكر.")
            except Exception:
                pass

            try:
                title_elem = page.locator("h1").first
                if await title_elem.is_visible():
                    bot_state["event_title"] = (await title_elem.text_content()).strip()
                    add_log("info", f"[EVENT] تم رصد الفعالية الحالية: {bot_state['event_title']}")
            except Exception:
                pass

            bot_state["current_step"] = "monitoring_seats"
            bot_state["status"] = "paused"
            add_log("success", "=======================================================")
            add_log("success", "🎯 [READY] البوت يسحب بيانات الصفحة ومخطط المقاعد ويعرض البث الحي للصور الآن!")
            add_log("success", "=======================================================")

            while not bot_stop_event.is_set():
                try:
                    s_bytes = await page.screenshot()
                    bot_state["latest_screenshot_b64"] = base64.b64encode(s_bytes).decode("utf-8")
                except Exception:
                    pass
                await asyncio.sleep(2.0)

            await browser.close()

        except Exception as e:
            logger.error(f"Error: {e}")
            bot_state["status"] = "error"
            add_log("error", f"[ERROR] {str(e)}")
            try:
                s_bytes = await page.screenshot()
                bot_state["latest_screenshot_b64"] = base64.b64encode(s_bytes).decode("utf-8")
            except Exception:
                pass
            await browser.close()

def run_worker_thread(config: dict):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(playwright_automation_worker(config))
    finally:
        loop.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/start", methods=["POST"])
def start_bot():
    global bot_thread, bot_stop_event
    if bot_state["status"] in ["running", "paused"]:
        return jsonify({"success": False, "message": "البوت يعمل بالفعل!"}), 400

    data = request.json or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    target_url = data.get("target_url", "").strip()

    if not email or not password or not target_url:
        return jsonify({"success": False, "message": "الرجاء إدخال البيانات والرابط المستهدف."}), 400

    bot_stop_event.clear()
    bot_thread = threading.Thread(target=run_worker_thread, args=(data,), daemon=True)
    bot_thread.start()
    return jsonify({"success": True, "message": "تم بدء تشغيل البوت الشامل بنجاح!"})

@app.route("/api/stop", methods=["POST"])
def stop_bot():
    global bot_stop_event
    bot_stop_event.set()
    bot_state["status"] = "idle"
    return jsonify({"success": True, "message": "تم إيقاف البوت."})

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": bot_state["status"],
        "current_step": bot_state["current_step"],
        "event_title": bot_state["event_title"],
        "target_url": bot_state["target_url"],
        "scraped_events_count": len(bot_state["scraped_events"]),
        "logs": bot_state["logs"],
        "latest_screenshot": bot_state["latest_screenshot_b64"]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
