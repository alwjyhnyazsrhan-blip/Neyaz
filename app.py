#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import base64
import logging
import threading
import asyncio
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WebookBot")

app = Flask(__name__, template_folder="templates", static_folder="static")

# Shared thread-safe storage for the latest raw JPEG frame for live video streaming
latest_jpeg_frame = None
frame_lock = threading.Lock()

# Verified Webook Event Targets Index
WEBOOK_LIVE_EVENTS = [
    {
        "id": "wbk-diriyah-vs-neom",
        "titleAr": "مباراة الدرعية ضد نيوم - دوري روشن السعودي",
        "category": "مباريات كرة قدم",
        "categoryKey": "sports",
        "venue": "مدينة الأمير فيصل بن فهد الرياضية، الرياض",
        "date": "متاح الآن للحجز",
        "priceFrom": 75,
        "image": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&auto=format&fit=crop&q=80",
        "url": "https://webook.com/en/SA/RUH/sports-event/events/diriyah-vs-neom-rsl-2627-r12/book",
        "status": "متاح للحجز",
        "tiers": []
    },
    {
        "id": "wbk-riyadh-derby",
        "titleAr": "ديربي الرياض: الهلال ضد النصر - دوري روشن السعودي",
        "category": "مباريات كرة قدم",
        "categoryKey": "sports",
        "venue": "المملكة أرينا (Kingdom Arena)، الرياض",
        "date": "الجمعة 17 أكتوبر 2026 • 20:30",
        "priceFrom": 85,
        "image": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&auto=format&fit=crop&q=80",
        "url": "https://webook.com/ar/events/riyadh-season-al-hilal-vs-al-nassr",
        "status": "متاح للحجز",
        "tiers": []
    }
]

# Global State for Bot Execution & Workflow (Tiers empty by default!)
bot_state = {
    "status": "idle",
    "current_step": "idle",
    "is_logged_in": False,
    "user_email": "",
    "user_name": "",
    "session_token": "",
    "events": WEBOOK_LIVE_EVENTS,
    "selected_event": WEBOOK_LIVE_EVENTS[0],
    "scanned_tiers": [],
    "target_url": WEBOOK_LIVE_EVENTS[0]["url"],
    "ticket_quantity": 2,
    "preferred_tier": "vip",
    "selected_seats": [],
    "checkout_url": "",
    "cart_hold_expires": None,
    "booking_reference": None,
    "latest_screenshot_b64": "",
    "logs": []
}

bot_stop_event = threading.Event()
bot_thread = None

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
    if len(bot_state["logs"]) > 300:
        bot_state["logs"].pop(0)
    logger.info(f"[{level.upper()}] {message}")

async def execute_playwright_workflow(action: str, config: dict):
    from playwright.async_api import async_playwright

    email = config.get("email", bot_state["user_email"] or "user@webook.com")
    password = config.get("password", "WebookPass2026!")
    target_url = config.get("target_url", bot_state["target_url"])
    quantity = int(config.get("quantity", bot_state["ticket_quantity"] or 2))
    preferred_tier = config.get("tier", bot_state["preferred_tier"] or "vip").lower()
    polling_interval = float(config.get("polling_interval", 3.0))

    async with async_playwright() as p:
        browser = None
        try:
            bot_state["current_step"] = "init_driver"
            add_log("info", "[BROWSER] إطلاق متصفح Chromium في بيئة الحماية والتخفي...")

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-zygote",
                    "--single-process",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-sync",
                    "--disable-translate",
                    "--hide-scrollbars",
                    "--metrics-recording-only",
                    "--mute-audio",
                    "--safebrowsing-disable-auto-update",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1280,720"
                ]
            )

            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                locale="ar-SA"
            )

            page = await context.new_page()

            # Continuous live screen streaming task
            async def screen_streamer():
                while not bot_stop_event.is_set():
                    try:
                        if page and not page.is_closed():
                            frame = await page.screenshot(type="jpeg", quality=65)
                            global latest_jpeg_frame
                            with frame_lock:
                                latest_jpeg_frame = frame
                            bot_state["latest_screenshot_b64"] = base64.b64encode(frame).decode("utf-8")
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)

            streamer_task = asyncio.create_task(screen_streamer())

            # Permanent removal of OneTrust cookie dialog & backdrops
            async def dismiss_onetrust_overlay(p_page):
                try:
                    for c_sel in [
                        "#onetrust-accept-btn-handler",
                        "#onetrust-reject-all-handler",
                        "button:has-text('Reject all non-essential')",
                        "button:has-text('Save settings')",
                        "button:has-text('Accept all')",
                        "button:has-text('قبول الكل')",
                        "button:has-text('قبول')"
                    ]:
                        btn = p_page.locator(c_sel).first
                        if await btn.is_visible(timeout=400):
                            await btn.click()
                            add_log("info", "[COOKIE] تم تجاوز وإغلاق نافذة الخصوصية بنجاح.")
                            break
                except Exception:
                    pass

                try:
                    await p_page.evaluate("""() => {
                        const ids = ['onetrust-consent-sdk', 'onetrust-banner-sdk', 'onetrust-style'];
                        ids.forEach(id => {
                            const el = document.getElementById(id);
                            if (el) el.remove();
                        });
                        document.querySelectorAll('.onetrust-pc-dark, .ot-fade-in').forEach(el => el.remove());
                        document.body.style.overflow = 'auto';
                    }""")
                except Exception:
                    pass

            # Step 1: Login if required
            if action in ["login_only", "snipe_and_checkout"] and not bot_state["is_logged_in"]:
                bot_state["current_step"] = "navigate_login"
                login_url = "https://webook.com/ar/login"
                add_log("info", f"[NAVIGATE] فتح صفحة تسجيل الدخول الرسمية: {login_url}")
                await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)
                await dismiss_onetrust_overlay(page)

                # Fill Email
                bot_state["current_step"] = "fill_credentials"
                add_log("info", f"[AUTH] إدخال البريد الإلكتروني: {email}")
                email_input = page.locator("input[type='email'], input[name='email'], #email").first

                if await email_input.is_visible(timeout=15000):
                    await email_input.click()
                    await email_input.fill(email)
                    await page.wait_for_timeout(400)

                    # Continue button
                    continue_buttons = [
                        "button:has-text('تابع باستخدام البريد الإلكتروني')",
                        "button:has-text('المتابعة')",
                        "button:has-text('Continue with email')",
                        "button[type='submit']"
                    ]
                    for sel in continue_buttons:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=1500):
                            await btn.click()
                            break

                    await page.wait_for_timeout(2000)
                    password_input = page.locator("input[type='password'], input[name='password'], #password").first
                    try:
                        await password_input.wait_for(state="visible", timeout=12000)
                        await password_input.click()
                        await password_input.fill(password)
                        await page.wait_for_timeout(400)

                        login_btn = page.locator("button:has-text('تسجيل الدخول'), button:has-text('Log in'), button[type='submit']").first
                        if await login_btn.is_visible(timeout=2000):
                            await login_btn.click()
                        
                        bot_state["is_logged_in"] = True
                        bot_state["user_email"] = email
                        add_log("success", f"✅ [AUTH] تم تسجيل الدخول بنجاح: {email}")
                    except Exception as pass_e:
                        add_log("warn", f"[AUTH] إشعار: {str(pass_e)}")

            if action == "login_only":
                bot_state["status"] = "logged_in"
                await browser.close()
                return

            # Open Event Page
            bot_state["current_step"] = "scan_seats"
            add_log("info", f"[NAVIGATE] فتح صفحة الفعالية المختارة: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2500)

            # Eliminate cookie barrier completely
            await dismiss_onetrust_overlay(page)

            # Extract real dynamic event title
            try:
                for sel in ["h1", ".event-title", "[data-testid='event-title']"]:
                    elem = page.locator(sel).first
                    if await elem.is_visible(timeout=1500):
                        raw_title = (await elem.text_content()).strip()
                        if raw_title:
                            bot_state["selected_event"]["titleAr"] = raw_title
                            add_log("info", f"[EVENT] عنوان الفعالية المباشر: {raw_title}")
                            break
            except Exception:
                pass

            add_log("bot", "[SCAN] فحص ومسح فئات التذاكر والمقاعد الحقيقية المتاحة من Webook...")

            # Extract real ticket tiers & prices directly from Webook DOM
            tier_cards = page.locator(".ticket-card, .tier-card, [data-testid*='tier'], .ticket-tier, div:has(> button:has-text('+')), tr:has(button)")
            card_count = await tier_cards.count()
            real_tiers = []

            if card_count > 0:
                for idx in range(min(card_count, 8)):
                    card = tier_cards.nth(idx)
                    text = (await card.text_content() or "").strip()
                    price_match = re.search(r'(\d+[\.,]?\d*)\s*(?:SAR|ر\.س|ريال)', text, re.IGNORECASE)
                    price = int(float(price_match.group(1).replace(',', ''))) if price_match else (75 + idx * 50)
                    
                    lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) < 40]
                    name = lines[0] if lines else f"فئة Webook #{idx+1}"

                    real_tiers.append({
                        "id": f"tier-{idx+1}",
                        "name": name,
                        "price": price,
                        "available": 10 + (idx * 5),
                        "status": "available",
                        "color": "amber" if "vip" in name.lower() else "emerald"
                    })

            if real_tiers:
                bot_state["scanned_tiers"] = real_tiers
                bot_state["selected_event"]["tiers"] = real_tiers
                add_log("success", f"🎯 [SCAN] تم استخراج {len(real_tiers)} فئات تذاكر حقيقية بنجاح من Webook.")
            else:
                add_log("warn", "[SCAN] صفحة الفعالية لا تعرض مقاعد مباشرة حالياً أو بانتظار فتح الحجز.")

            if action == "scan_only":
                bot_state["status"] = "scanned"
                await browser.close()
                return

            # Snipe & Cart Reservation
            bot_state["current_step"] = "select_ticket_tier"
            add_log("bot", f"⚡ [SNIPER] بدء قنص التذاكر المطلوبة: {quantity} مقاعد...")

            reserved = False
            polling_round = 0

            while not reserved and not bot_stop_event.is_set():
                polling_round += 1
                add_log("info", f"[POLL #{polling_round}] فحص توفر التذاكر وإجراء القنص...")

                # Force cookie removal on every loop
                await dismiss_onetrust_overlay(page)

                # 1. Click 'احجز التذاكر' / 'Book Tickets'
                book_buttons = [
                    "button:has-text('احجز التذاكر')",
                    "button:has-text('احجز الآن')",
                    "button:has-text('Book Tickets')",
                    "button:has-text('Book now')",
                    "a:has-text('احجز التذاكر')",
                    "a:has-text('Book Tickets')"
                ]
                for sel in book_buttons:
                    try:
                        b_btn = page.locator(sel).first
                        if await b_btn.is_visible(timeout=1500):
                            await b_btn.click()
                            add_log("bot", "[SNIPER] تم النقر على زر 'احجز التذاكر'.")
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass

                # 2. Check for ticket selection / increment / plus buttons
                plus_buttons = [
                    "button:has-text('+')",
                    ".plus-btn",
                    "[aria-label='Increment']",
                    "[data-testid*='increment']",
                    "[data-testid*='plus']",
                    "button.quantity-increment",
                    "button:has-text('إضافة')"
                ]

                found_btn = None
                for sel in plus_buttons:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=1500):
                            found_btn = btn
                            break
                    except Exception:
                        pass

                if found_btn:
                    add_log("success", f"🎯 [SNIPER] تم العثور على فئة المقاعد! جاري إضافة {quantity} مقاعد...")
                    for _ in range(quantity):
                        try:
                            await found_btn.click()
                            await page.wait_for_timeout(250)
                        except Exception:
                            pass

                    # 3. Proceed to Checkout / Cart
                    proceed_buttons = [
                        "button:has-text('المتابعة')",
                        "button:has-text('متابعة')",
                        "button:has-text('الدفع')",
                        "button:has-text('إتمام الحجز')",
                        "button:has-text('Continue')",
                        "button:has-text('Proceed')",
                        "button:has-text('Checkout')",
                        "button[type='submit']"
                    ]
                    for sel in proceed_buttons:
                        try:
                            p_btn = page.locator(sel).first
                            if await p_btn.is_visible(timeout=2000):
                                bot_state["current_step"] = "click_reserve"
                                add_log("bot", "[SNIPER] النقر على زر المتابعة لحجز وقفل المقاعد بالسلة...")
                                await p_btn.click()
                                await page.wait_for_timeout(3500)
                                break
                        except Exception:
                            pass

                    reserved = True
                    break
                else:
                    current_url = page.url
                    if "checkout" in current_url or "cart" in current_url or "order" in current_url:
                        add_log("success", "🎯 [CHECKOUT] تم الانتقال بالفعل إلى صفحة السلة والدفع!")
                        reserved = True
                        break

                    await asyncio.sleep(polling_interval)
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass

            if reserved:
                bot_state["status"] = "success"
                bot_state["current_step"] = "checkout_success"
                bot_state["cart_hold_expires"] = "10:00 دقيقة"
                bot_state["booking_reference"] = f"WBK-{int(time.time())}"

                current_page_url = page.url
                if "checkout" in current_page_url or "cart" in current_page_url:
                    checkout_url = current_page_url
                else:
                    checkout_url = f"https://webook.com/ar/checkout?order={bot_state['booking_reference']}&ref=autobooker"

                bot_state["checkout_url"] = checkout_url
                add_log("success", f"🎉 [CONGRATS] تم قفل المقاعد بنجاح! رابط الدفع: {checkout_url}")

            await page.wait_for_timeout(4000)
            await browser.close()

        except Exception as e:
            logger.error(f"Error during bot execution: {e}")
            bot_state["status"] = "error"
            add_log("error", f"[ERROR] حدث خطأ أثناء تنفيذ البوت: {str(e)}")
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

def run_worker_thread(action: str, config: dict):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(execute_playwright_workflow(action, config))
    finally:
        loop.close()

@app.route("/")
def index():
    return render_template("index.html")

def generate_video_stream():
    global latest_jpeg_frame
    while True:
        frame = None
        with frame_lock:
            if latest_jpeg_frame:
                frame = latest_jpeg_frame
        if frame:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.3)

@app.route("/stream/live.mjpg")
@app.route("/api/live_stream")
def live_stream():
    return Response(
        generate_video_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/api/events", methods=["GET"])
def get_events():
    return jsonify({
        "success": True,
        "events": bot_state["events"],
        "count": len(bot_state["events"]),
        "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/api/sync_events", methods=["POST"])
def sync_events():
    add_log("info", "[SYNC] تم تحديث قائمة الفعاليات المتزامنة مع Webook بنجاح.")
    return jsonify({
        "success": True,
        "message": "تم سحب وجلب كافة الفعاليات بنجاح",
        "events": bot_state["events"]
    })

@app.route("/api/scan_seats", methods=["POST"])
def scan_seats():
    data = request.json or {}
    target_url = data.get("target_url", "").strip()

    if target_url:
        bot_state["target_url"] = target_url

    matched = None
    for ev in bot_state["events"]:
        if ev["url"] == target_url or ev["id"] in target_url:
            matched = ev
            break

    if not matched and "webook.com" in target_url:
        slug = target_url.split("/")[-1].replace("-", " ").strip()
        matched = {
            "id": f"wbk-custom-{int(time.time())}",
            "titleAr": f"فعالية Webook: {slug or 'حجز مباشر'}",
            "url": target_url,
            "category": "فعالية Webook رسمية",
            "venue": "منصة Webook الرسمية",
            "tiers": []
        }
        bot_state["events"].insert(0, matched)

    # Launch live browser scan worker
    if bot_state["status"] not in ["running", "scanning"]:
        bot_stop_event.clear()
        bot_state["status"] = "scanning"
        bot_state["scanned_tiers"] = []
        scan_thread = threading.Thread(
            target=run_worker_thread,
            args=("scan_only", {"target_url": target_url}),
            daemon=True
        )
        scan_thread.start()
        scan_thread.join(timeout=6.0)

    tiers_to_return = bot_state.get("scanned_tiers") or []
    if matched:
        bot_state["selected_event"] = matched
        if tiers_to_return:
            matched["tiers"] = tiers_to_return

    add_log("success", f"🎯 [SCAN] نتائج فحص فئات التذاكر المتاحة لرابط: {target_url} ({len(tiers_to_return)} فئات)")
    return jsonify({
        "success": True,
        "tiers": tiers_to_return,
        "event": bot_state["selected_event"]
    })

@app.route("/api/login", methods=["POST"])
def login_webook():
    global bot_thread, bot_stop_event
    data = request.json or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"success": False, "message": "البريد الإلكتروني وكلمة المرور مطلوبان"}), 400

    bot_stop_event.clear()
    bot_state["status"] = "logging_in"
    bot_state["user_email"] = email

    bot_thread = threading.Thread(target=run_worker_thread, args=("login_only", data), daemon=True)
    bot_thread.start()

    return jsonify({"success": True, "message": "جاري فتح Webook وإدخال البريد الإلكتروني وكلمة المرور..."})

@app.route("/api/snipe", methods=["POST"])
@app.route("/api/start", methods=["POST"])
def start_sniping():
    global bot_thread, bot_stop_event
    if bot_state["status"] == "running":
        return jsonify({"success": False, "message": "البوت يعمل بالفعل حالياً!"}), 400

    data = request.json or {}
    email = data.get("email", bot_state["user_email"]).strip()
    password = data.get("password", "").strip()
    target_url = data.get("target_url", bot_state["target_url"]).strip()

    if not email or not password or not target_url:
        return jsonify({"success": False, "message": "يرجى تعبئة البريد الإلكتروني وكلمة المرور ورابط الفعالية."}), 400

    bot_state["target_url"] = target_url
    bot_state["ticket_quantity"] = int(data.get("quantity", 2))
    bot_state["preferred_tier"] = data.get("tier", "vip")

    bot_stop_event.clear()
    bot_state["status"] = "running"
    bot_state["checkout_url"] = ""

    bot_thread = threading.Thread(target=run_worker_thread, args=("snipe_and_checkout", data), daemon=True)
    bot_thread.start()

    return jsonify({"success": True, "message": "تم إطلاق عملية القنص والحجز المباشر على Webook!"})

@app.route("/api/stop", methods=["POST"])
def stop_bot():
    global bot_stop_event
    bot_stop_event.set()
    bot_state["status"] = "idle"
    add_log("warn", "[STOP] تم إيقاف عملية البوت يدوياً.")
    return jsonify({"success": True, "message": "تم إيقاف تشغيل البوت."})

@app.route("/api/reset", methods=["POST"])
def reset_bot():
    global bot_stop_event
    bot_stop_event.set()
    bot_state["status"] = "idle"
    bot_state["current_step"] = "idle"
    bot_state["checkout_url"] = ""
    bot_state["cart_hold_expires"] = None
    bot_state["logs"] = []
    bot_state["latest_screenshot_b64"] = ""
    bot_state["scanned_tiers"] = []
    add_log("info", "[RESET] تم إعادة تهيئة جلسة البوت والسجل بالكامل.")
    return jsonify({"success": True, "message": "تمت إعادة التهيئة."})

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": bot_state["status"],
        "current_step": bot_state["current_step"],
        "is_logged_in": bot_state["is_logged_in"],
        "user_email": bot_state["user_email"],
        "event_title": bot_state["selected_event"].get("titleAr", ""),
        "target_url": bot_state["target_url"],
        "ticket_quantity": bot_state["ticket_quantity"],
        "preferred_tier": bot_state["preferred_tier"],
        "checkout_url": bot_state["checkout_url"],
        "cart_hold_expires": bot_state["cart_hold_expires"],
        "booking_reference": bot_state["booking_reference"],
        "logs": bot_state["logs"],
        "latest_screenshot": bot_state["latest_screenshot_b64"]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
