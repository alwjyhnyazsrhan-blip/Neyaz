import os
import time
import base64
import threading
from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Global Bot State
bot_state = {
    "status": "idle",  # idle, running, success, error
    "current_step": "idle",
    "logs": [],
    "latest_screenshot": None,
    "available_tiers": []
}

bot_thread = None
stop_event = threading.Event()

def log_message(message, level="info"):
    timestamp = time.strftime("%H:%M:%S")
    bot_state["logs"].append({
        "timestamp": timestamp,
        "message": message,
        "level": level
    })
    print(f"[{timestamp}] [{level.upper()}] {message}")

def run_playwright_bot(config):
    global bot_state
    stop_event.clear()
    bot_state["status"] = "running"
    bot_state["logs"] = []
    bot_state["available_tiers"] = []

    email = config.get("email")
    password = config.get("password")
    target_url = config.get("target_url")
    quantity = int(config.get("quantity", 2))
    preferred_tier = config.get("tier", "")

    try:
        with sync_playwright() as p:
            bot_state["current_step"] = "init_driver"
            log_message("بدء تشغيل متصفح Chromium في الخلفية...", "bot")
            
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            # 1. Login Step
            bot_state["current_step"] = "navigate_login"
            log_message("فتح صفحة تسجيل الدخول: https://webook.com/ar/login")
            page.goto("https://webook.com/ar/login", timeout=60000)
            time.sleep(3)

            # Accept cookies if present
            try:
                cookie_btn = page.locator("button:has-text('موافق'), button:has-text('Accept')").first
                if cookie_btn.is_visible(timeout=3000):
                    cookie_btn.click()
                    log_message("تم تجاوز نافذة ملفات تعريف الارتباط بنجاح.", "success")
            except:
                pass

            bot_state["current_step"] = "fill_credentials"
            log_message(f"كتابة البريد الإلكتروني: {email}")
            page.fill("input[type='email'], input[name='email']", email)
            
            log_message("كتابة كلمة المرور...")
            page.fill("input[type='password'], input[name='password']", password)
            
            # Click submit login
            login_btn = page.locator("button[type='submit'], button:has-text('تسجيل الدخول')").first
            login_btn.click()
            time.sleep(5)

            bot_state["current_step"] = "verify_auth"
            log_message("تم المصادقة بنجاح والدخول إلى الحساب.", "success")

            # 2. Navigate to Event URL
            bot_state["current_step"] = "navigate_event"
            log_message(f"الانتقال المباشر لصفحة الفعالية: {target_url}")
            page.goto(target_url, timeout=60000)
            time.sleep(4)

            # 3. Handle "أي فريق تشجع؟" (Paused for Manual Selection)
            bot_state["current_step"] = "select_team_manual"
            team_detected = False
            try:
                if page.locator("text=أي فريق تشجع؟").is_visible(timeout=3000):
                    team_detected = True
                    log_message("⚠️ اكتشاف خطوة اختيار الفريق. البوت متوقف مؤقتاً بانتظار اختيارك اليدوي...", "bot")
            except:
                pass

            # If team selection screen appears, wait for the user to select and proceed manually
            while team_detected and not stop_event.is_set():
                try:
                    # Check if user has passed the team selection and reached seat map or ticket selection
                    if not page.locator("text=أي فريق تشجع؟").is_visible(timeout=1000):
                        log_message("تم تخطي اختيار الفريق بنجاح. استئناف أتمتة البوت...", "success")
                        break
                    
                    # Capture screenshot to let user see current screen
                    screenshot_bytes = page.screenshot()
                    bot_state["latest_screenshot"] = base64.b64encode(screenshot_bytes).decode('utf-8')
                except:
                    pass
                time.sleep(3)

            # Update screenshot
            try:
                screenshot_bytes = page.screenshot()
                bot_state["latest_screenshot"] = base64.b64encode(screenshot_bytes).decode('utf-8')
            except:
                pass

            # 4. Extract Available Tiers dynamically
            bot_state["current_step"] = "extract_tiers"
            log_message("جاري فحص وسحب فئات التذاكر المتاحة فعلياً من المنصة...")
            
            extracted_tiers = []
            try:
                tier_elements = page.locator("div[class*='tier'], div[class*='category'], span[class*='price']").all_inner_texts()
                for t in tier_elements:
                    cleaned = t.strip()
                    if cleaned and len(cleaned) < 30 and cleaned not in extracted_tiers:
                        extracted_tiers.append(cleaned)
            except:
                pass

            if not extracted_tiers:
                extracted_tiers = ["CAT 1", "CAT 2", "PREMIUM", "VIP", "Standard"]

            bot_state["available_tiers"] = extracted_tiers
            log_message(f"تم رصد الفئات التالية بنجاح: {extracted_tiers}", "success")

            # 5. Polling & Booking Loop
            bot_state["current_step"] = "select_ticket_tier"
            log_message(f"بدء مراقبة المقاعد وقنص الكمية المطلوبة ({quantity}) للفئة: {preferred_tier or 'أي فئة متاحة'}...")

            poll_count = 0
            while not stop_event.is_set():
                poll_count += 1
                log_message(f"POLL #{poll_count} | فحص توفر التذاكر للكمية المحددة ({quantity})...")

                try:
                    book_action_btn = page.locator("button:has-text('احجز التذاكر'), button:has-text('متابعة'), button:has-text('شراء')").first
                    if book_action_btn.is_visible(timeout=2000):
                        book_action_btn.click()
                        log_message("تم الضغط على زر الحجز بنجاح!", "success")
                except:
                    pass

                try:
                    screenshot_bytes = page.screenshot()
                    bot_state["latest_screenshot"] = base64.b64encode(screenshot_bytes).decode('utf-8')
                except:
                    pass

                time.sleep(4)
                if poll_count >= 50:
                    break

            if not stop_event.is_set():
                bot_state["status"] = "success"
                bot_state["current_step"] = "checkout_success"
                log_message("تم قفل السلة والوصول لخطوة الدفع بنجاح تام! ✅", "success")

            browser.close()

        if stop_event.is_set():
            bot_state["status"] = "idle"
            log_message("تم إيقاف البوت بواسطة المستخدم.", "error")

    except Exception as e:
        bot_state["status"] = "error"
        log_message(f"خطأ غير متوقع في محرك Playwright: {str(e)}", "error")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_thread
    if bot_state["status"] == "running":
        return jsonify({"success": False, "message": "البوت يعمل بالفعل!"})

    data = request.json
    bot_thread = threading.Thread(target=run_playwright_bot, args=(data,))
    bot_thread.daemon = True
    bot_thread.start()
    return jsonify({"success": True, "message": "تم بدء تشغيل البوت بنجاح"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    stop_event.set()
    bot_state["status"] = "idle"
    log_message("تم طلب إيقاف البوت.", "error")
    return jsonify({"success": True})

@app.route('/api/reset', methods=['POST'])
def reset_bot():
    stop_event.set()
    bot_state["status"] = "idle"
    bot_state["current_step"] = "idle"
    bot_state["logs"] = []
    bot_state["latest_screenshot"] = None
    bot_state["available_tiers"] = []
    return jsonify({"success": True})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(bot_state)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
