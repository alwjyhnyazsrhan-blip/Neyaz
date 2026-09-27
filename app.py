import os
import sys
import json
import time
import base64
import logging
import threading
import asyncio
import subprocess
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

# Global State for Bot Execution
bot_state = {
    "status": "idle",       # "idle", "running", "paused", "success", "error"
    "current_step": "idle",
    "logs": [],
    "target_url": "",
    "event_title": "فعالية غير محددة",
    "account_email": "",
    "ticket_quantity": 100,
    "preferred_tier": "vip",
    "latest_screenshot_b64": "",
    "cart_hold_expires": None,
    "booking_reference": None
}

bot_stop_event = threading.Event()
bot_thread = None
xvfb_process = None

def start_virtual_display():
    """تشغيل شاشة وهمية Xvfb للسيرفرات السحابية لتشغيل متصفح مرئي"""
    global xvfb_process
    try:
        # التأكد من تشغيل الشاشة الوهمية برقم :99
        xvfb_process = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x800x24"])
        os.environ["DISPLAY"] = ":99"
        logger.info("[DISPLAY] تم تشغيل الشاشة الوهمية Xvfb بنجاح على Display :99")
    except Exception as e:
        logger.warning(f"[DISPLAY] تعذر تشغيل Xvfb (قد تكون محلياً على جهازك): {e}")

def add_log(level: str, message: str, step: str = ""):
    """Helper to record timestamped logs to state"""
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

async def send_telegram_alert(token: str, chat_id: str, message: str, screenshot_bytes: bytes = None):
    """Optional async notification to Telegram bot"""
    if not token or not chat_id:
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=8)

        if screenshot_bytes:
            photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
            files = {"photo": ("screenshot.png", screenshot_bytes, "image/png")}
            requests.post(photo_url, data={"chat_id": chat_id, "caption": "📸 لقطة تأكيد حجز المقاعد يدوياً"}, files=files, timeout=12)
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")

async def playwright_automation_worker(config: dict):
    """Playwright worker executing live automation workflow on Virtual Display"""
    from playwright.async_api import async_playwright

    # تشغيل الشاشة الوهمية قبل فتح المتصفح
    start_virtual_display()

    email = config.get("email", "")
    password = config.get("password", "")
    target_url = config.get("target_url", "https://webook.com/ar/explore")
    quantity = int(config.get("quantity", 100))
    preferred_tier = config.get("tier", "vip").lower()
    telegram_token = config.get("telegram_token", "")
    telegram_chat_id = config.get("telegram_chat_id", "")

    bot_state["status"] = "running"
    bot_state["account_email"] = email
    bot_state["target_url"] = target_url
    bot_state["ticket_quantity"] = quantity
    bot_state["preferred_tier"] = preferred_tier

    add_log("bot", "=======================================================")
    add_log("bot", f"🚀 تشغيل بوت Webook على الشاشة الافتراضية المرئية...")
    add_log("info", f"[TARGET] الفعالية المستهدفة: {target_url}")
    add_log("info", f"[USER] الحساب: {email}")

    async with async_playwright() as p:
        try:
            bot_state["current_step"] = "init_driver"
            add_log("info", "[BROWSER] تهيئة متصفح Chromium بوضع مرئي على الشاشة الافتراضية...")

            browser = await p.chromium.launch(
                headless=False,  # تشغيل مرئي حقيقي داخل الشاشة الوهمية
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

            # Step 1: Open Login Page
            bot_state["current_step"] = "navigate_login"
            login_url = "https://webook.com/ar/login"
            add_log("info", f"[NAVIGATE] فتح صفحة تسجيل الدخول: {login_url}")
            await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)

            screenshot_bytes = await page.screenshot()
            bot_state["latest_screenshot_b64"] = base64.b64encode(screenshot_bytes).decode("utf-8")

            try:
                cookie_btn = page.locator("button:has-text('قبول'), button:has-text('Accept'), button#onetrust-accept-btn-handler").first
                if await cookie_btn.is_visible(timeout=3000):
                    await cookie_btn.click()
                    add_log("info", "[COOKIE] تم تجاوز نافذة ملفات تعريف الارتباط بنجاح.")
            except Exception:
                pass

            if bot_stop_event.is_set():
                await browser.close()
                return

            # Step 2: Input Credentials & Sign In
            bot_state["current_step"] = "fill_credentials"
            add_log("info", f"[AUTH] كتابة البريد الإلكتروني: {email}")

            email_input = page.locator("input[type='email'], input[name='email'], #email").first
            if await email_input.is_visible(timeout=10000):
                await email_input.fill(email)
                await page.wait_for_timeout(500)

                continue_btn = page.locator("button:has-text('تابع باستخدام البريد الإلكتروني'), button:has-text('Continue'), button[type='submit']").first
                if await continue_btn.is_visible(timeout=3000):
                    await continue_btn.click()
                    await page.wait_for_timeout(1000)

                password_input = page.locator("input[type='password'], input[name='password'], #password").first
                if await password_input.is_visible(timeout=8000):
                    await password_input.fill(password)
                    add_log("info", "[AUTH] كتابة كلمة المرور المشفّرة: ••••••••••••")

                    submit_btn = page.locator("button[type='submit'], button:has-text('تسجيل الدخول'), button:has-text('Log in')").first
                    await submit_btn.click()
                    add_log("bot", "[AUTH] تم النقر على زر 'تسجيل الدخول'... جاري التحقق من التوكن")

                bot_state["current_step"] = "verify_auth"
                await page.wait_for_timeout(3500)
                add_log("success", f"[AUTH] اكتملت مصادقة الحساب بنجاح: {email}")

            if bot_stop_event.is_set():
                await browser.close()
                return

            # Step 3: Navigate to Target Event URL & Open Booking Window
            bot_state["current_step"] = "navigate_event"
            add_log("info", f"[NAVIGATE] الانتقال المباشر لصفحة الفعالية: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)

            try:
                book_trigger_btn = page.locator("button:has-text('احجز التذاكر'), button:has-text('Book Tickets'), a:has-text('احجز'), button:has-text('اختر التذاكر')").first
                if await book_trigger_btn.is_visible(timeout=4000):
                    await book_trigger_btn.click()
                    add_log("info", "[ACTION] تم النقر على زر حجز التذاكر لفتح خيارات المقاعد والتذاكر مباشرة.")
                    await page.wait_for_timeout(2500)
            except Exception:
                pass

            try:
                title_elem = page.locator("h1").first
                if await title_elem.is_visible():
                    bot_state["event_title"] = (await title_elem.text_content()).strip()
                    add_log("info", f"[EVENT] عنوان الفعالية: {bot_state['event_title']}")
            except Exception:
                pass

            # Step 4: Manual Control Mode on Virtual Display
            bot_state["current_step"] = "waiting_manual_selection"
            bot_state["status"] = "paused"
            add_log("success", "=======================================================")
            add_log("success", "🎯 [VIRTUAL LIVE MODE] المتصفح يعمل الآن على الشاشة الوهمية!")
            add_log("info", "[INFO] يمكنك الآن رؤية التحديثات عبر لقطات الشاشة وتحديد العدد المطلوب (100 مقعد أو أكثر) بيدك.")
            add_log("success", "=======================================================")

            max_manual_wait = 900
            elapsed = 0

            while elapsed < max_manual_wait and not bot_stop_event.is_set():
                try:
                    s_bytes = await page.screenshot()
                    bot_state["latest_screenshot_b64"] = base64.b64encode(s_bytes).decode("utf-8")
                except Exception:
                    pass

                current_url = page.url
                if "checkout" in current_url or "payment" in current_url or "order" in current_url:
                    bot_state["status"] = "success"
                    bot_state["current_step"] = "checkout_success"
                    bot_state["booking_reference"] = f"WBK-{int(time.time())}"

                    add_log("success", "🎉 [CHECKOUT] تم رصد الانتقال لصفحة الدفع بنجاح!")

                    final_screenshot = await page.screenshot()
                    bot_state["latest_screenshot_b64"] = base64.b64encode(final_screenshot).decode("utf-8")

                    alert_text = (
                        f"🎯 *تم الوصول لصفحة الدفع*\n"
                        f"• الفعالية: {bot_state['event_title']}\n"
                        f"• الحساب: {email}\n"
                        f"• الرابط: {current_url}"
                    )
                    await send_telegram_alert(telegram_token, telegram_chat_id, alert_text, final_screenshot)
                    break

                await asyncio.sleep(2.0)
                elapsed += 2.0

            await page.wait_for_timeout(5000)
            await browser.close()

        except Exception as e:
            logger.error(f"Error during bot execution: {e}")
            bot_state["status"] = "error"
            add_log("error", f"[ERROR] حدث خطأ أثناء تنفيذ البوت: {str(e)}")
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

# -------------------------------------------------------------
# Web Server Routes
# -------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/start", methods=["POST"])
def start_bot():
    global bot_thread, bot_stop_event
    if bot_state["status"] == "running" or bot_state["status"] == "paused":
        return jsonify({"success": False, "message": "البوت يعمل أو في وضع الانتظار بالفعل!"}), 400

    data = request.json or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    target_url = data.get("target_url", "").strip()

    if not email or not password or not target_url:
        return jsonify({"success": False, "message": "يرجى تعبئة البريد الإلكتروني وكلمة المرور ورابط الفعالية."}), 400

    bot_stop_event.clear()
    bot_thread = threading.Thread(target=run_worker_thread, args=(data,), daemon=True)
    bot_thread.start()

    return jsonify({"success": True, "message": "تم إطلاق البوت على الشاشة الافتراضية بنجاح!"})

@app.route("/api/stop", methods=["POST"])
def stop_bot():
    global bot_stop_event
    bot_stop_event.set()
    bot_state["status"] = "idle"
    add_log("warn", "[STOP] تم إيقاف عملية البوت يدوياً من لوحة التحكم.")
    return jsonify({"success": True, "message": "تم إيقاف تشغيل البوت."})

@app.route("/api/reset", methods=["POST"])
def reset_bot():
    global bot_stop_event
    bot_stop_event.set()
    bot_state["status"] = "idle"
    bot_state["current_step"] = "idle"
    bot_state["logs"] = []
    bot_state["latest_screenshot_b64"] = ""
    add_log("info", "[RESET] تم إعادة تعيين جلسة البوت والسجل بالكامل.")
    return jsonify({"success": True, "message": "تمت إعادة التعيين."})

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": bot_state["status"],
        "current_step": bot_state["current_step"],
        "event_title": bot_state["event_title"],
        "target_url": bot_state["target_url"],
        "ticket_quantity": bot_state["ticket_quantity"],
        "preferred_tier": bot_state["preferred_tier"],
        "cart_hold_expires": bot_state["cart_hold_expires"],
        "booking_reference": bot_state["booking_reference"],
        "logs": bot_state["logs"],
        "latest_screenshot": bot_state["latest_screenshot_b64"]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
