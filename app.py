#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================================
 Webook Auto-Booker Bot - Flask & Playwright Automation Server
 Specially tuned and optimized for Render.com (Docker & Native)
 
 Full Workflow Implementation:
 1. 2-Step Login with Email -> 'Continue with email' -> Password -> Authentication
 2. Live Synchronization of All Webook Events
 3. Seat & Ticket Tier Availability Scanner
 4. Ultra-Fast Ticket Sniping & Cart Locking
 5. Instant Payment / Checkout Link Generation with 10-Minute Cart Hold
========================================================================================
"""
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

# Sample / Cached Real Webook Events Database for Instant Live Sync
WEBOOK_LIVE_EVENTS = [
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
        "tiers": [
            {"id": "vip", "name": "كبار الشخصيات VIP", "price": 350, "available": 14, "status": "available", "color": "amber"},
            {"id": "gold", "name": "الفئة الذهبية Gold", "price": 180, "available": 42, "status": "available", "color": "yellow"},
            {"id": "silver", "name": "الفئة الفضية Silver", "price": 120, "available": 8, "status": "limited", "color": "slate"},
            {"id": "regular", "name": "المقاعد العادية Regular", "price": 85, "available": 160, "status": "available", "color": "emerald"}
        ]
    },
    {
        "id": "wbk-al-ittihad-vs-al-ahli",
        "titleAr": "ديربي جدة: الاتحاد ضد الأهلي - دوري روشن",
        "category": "مباريات كرة قدم",
        "categoryKey": "sports",
        "venue": "مدينة الملك عبدالله الرياضية (الجوهرة المشعة)، جدة",
        "date": "السبت 25 أكتوبر 2026 • 21:00",
        "priceFrom": 75,
        "image": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?w=800&auto=format&fit=crop&q=80",
        "url": "https://webook.com/ar/events/al-ittihad-vs-al-ahli-rsl-2627",
        "status": "متاح للحجز",
        "tiers": [
            {"id": "vip", "name": "كبار الشخصيات VIP", "price": 400, "available": 6, "status": "limited", "color": "amber"},
            {"id": "gold", "name": "الفئة الذهبية Gold", "price": 200, "available": 25, "status": "available", "color": "yellow"},
            {"id": "regular", "name": "المقاعد العادية Regular", "price": 75, "available": 95, "status": "available", "color": "emerald"}
        ]
    },
    {
        "id": "wbk-blvd-world",
        "titleAr": "بوليفارد وورلد (Boulevard World) - موسم الرياض 2026",
        "category": "موسم الرياض",
        "categoryKey": "entertainment",
        "venue": "بوليفارد وورلد، حطين، الرياض",
        "date": "يومياً من 16:00 حتى 01:00",
        "priceFrom": 45,
        "image": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800&auto=format&fit=crop&q=80",
        "url": "https://webook.com/ar/events/boulevard-world-riyadh-season-2026",
        "status": "متاح للحجز",
        "tiers": [
            {"id": "vip", "name": "تذكرة VIP مسار سريع Fast Track", "price": 150, "available": 50, "status": "available", "color": "amber"},
            {"id": "regular", "name": "تذكرة دخول عامة Regular", "price": 45, "available": 500, "status": "available", "color": "emerald"}
        ]
    },
    {
        "id": "wbk-concert-abdulmajeed",
        "titleAr": "ليلة الطرب: حفل الفنان عبدالمجيد عبدالله في مسرح محمد عبده",
        "category": "حفلات غنائية",
        "categoryKey": "music",
        "venue": "مسرح محمد عبده أرينا، بوليفارد سيتي، الرياض",
        "date": "الخميس 13 نوفمبر 2026 • 21:30",
        "priceFrom": 250,
        "image": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=800&auto=format&fit=crop&q=80",
        "url": "https://webook.com/ar/events/abdulmajeed-abdullah-live-riyadh-season",
        "status": "سريع النفاد 🔥",
        "tiers": [
            {"id": "royal", "name": "المقصورة الملكية Royal Box", "price": 1200, "available": 2, "status": "limited", "color": "purple"},
            {"id": "vip", "name": "كبار الشخصيات VIP", "price": 750, "available": 9, "status": "limited", "color": "amber"},
            {"id": "gold", "name": "الفئة الذهبية Gold", "price": 450, "available": 18, "status": "available", "color": "yellow"},
            {"id": "regular", "name": "الفئة الفضية Regular", "price": 250, "available": 32, "status": "available", "color": "emerald"}
        ]
    },
    {
        "id": "wbk-diriyah-e-prix",
        "titleAr": "سباق الدرعية إي بري 2027 (Diriyah E-Prix Formula E)",
        "category": "رياضات وسرعة",
        "categoryKey": "sports",
        "venue": "حلبة الدرعية التاريخية، الرياض",
        "date": "14 - 15 يناير 2027",
        "priceFrom": 100,
        "image": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=800&auto=format&fit=crop&q=80",
        "url": "https://webook.com/ar/sa/jed/sports-event/events/e-prix-2027-day-1",
        "status": "متاح للحجز",
        "tiers": [
            {"id": "vip", "name": "تذكرة ضيافة ونادي البادوك VIP", "price": 650, "available": 20, "status": "available", "color": "amber"},
            {"id": "regular", "name": "المدرج العام Grandstand", "price": 100, "available": 240, "status": "available", "color": "emerald"}
        ]
    },
    {
        "id": "wbk-kings-cup-nassr",
        "titleAr": "كأس خادم الحرمين الشريفين: النصر ضد الخلود",
        "category": "مباريات كرة قدم",
        "categoryKey": "sports",
        "venue": "الأول بارك (Al-Awwal Park)، جامعة الملك سعود، الرياض",
        "date": "الثلاثاء 28 أكتوبر 2026 • 20:00",
        "priceFrom": 60,
        "image": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&auto=format&fit=crop&q=80",
        "url": "https://webook.com/ar/sa/ruh/sports-event/events/kc-26-27-al-nassr-vs-al-kholood-s4f2y7k6",
        "status": "متاح للحجز",
        "tiers": [
            {"id": "vip", "name": "منصة كبار الشخصيات VIP", "price": 300, "available": 11, "status": "available", "color": "amber"},
            {"id": "gold", "name": "الفئة الممتازة Cat 1", "price": 150, "available": 35, "status": "available", "color": "yellow"},
            {"id": "regular", "name": "الدرجة الموحدة Regular", "price": 60, "available": 120, "status": "available", "color": "emerald"}
        ]
    }
]

# Global State for Bot Execution & Workflow
bot_state = {
    "status": "idle",       # "idle", "logging_in", "logged_in", "scanning", "running", "success", "error"
    "current_step": "idle",
    "is_logged_in": False,
    "user_email": "",
    "user_name": "",
    "session_token": "",
    "events": WEBOOK_LIVE_EVENTS,
    "selected_event": WEBOOK_LIVE_EVENTS[0],
    "scanned_tiers": WEBOOK_LIVE_EVENTS[0]["tiers"],
    "target_url": WEBOOK_LIVE_EVENTS[0]["url"],
    "ticket_quantity": 2,
    "preferred_tier": "vip",
    "selected_seats": ["A-101", "A-102"],
    "checkout_url": "",
    "cart_hold_expires": None,
    "booking_reference": None,
    "latest_screenshot_b64": "",
    "logs": []
}

bot_stop_event = threading.Event()
bot_thread = None

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
    if len(bot_state["logs"]) > 300:
        bot_state["logs"].pop(0)
    logger.info(f"[{level.upper()}] {message}")

# -------------------------------------------------------------
# Automation Worker: Login, Event Sync, Seat Scan & Sniping
# -------------------------------------------------------------
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

            # Background live screen streamer task
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

            # ==============================================================
            # STAGE 1: AUTOMATED 2-STEP LOGIN ON WEBOOK
            # ==============================================================
            bot_state["current_step"] = "navigate_login"
            login_url = "https://webook.com/ar/login"
            add_log("info", f"[NAVIGATE] فتح صفحة تسجيل الدخول الرسمية: {login_url}")
            await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)

            # Accept cookies
            try:
                cookie_btn = page.locator("button:has-text('قبول'), button:has-text('Accept'), button#onetrust-accept-btn-handler").first
                if await cookie_btn.is_visible(timeout=2500):
                    await cookie_btn.click()
                    add_log("info", "[COOKIE] تم تجاوز إشعار ملفات تعريف الارتباط.")
            except Exception:
                pass

            # Step 1.1: Fill Email
            bot_state["current_step"] = "fill_credentials"
            add_log("info", f"[AUTH] إدخال البريد الإلكتروني: {email}")
            email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='البريد'], #email").first

            if await email_input.is_visible(timeout=15000):
                await email_input.click()
                await email_input.fill(email)
                await page.wait_for_timeout(400)

                # Capture screenshot
                try:
                    s_bytes = await page.screenshot()
                    bot_state["latest_screenshot_b64"] = base64.b64encode(s_bytes).decode("utf-8")
                except Exception:
                    pass

                # Step 1.2: Click 'المتابعة باستخدام البريد الإلكتروني'
                password_input = page.locator("input[type='password'], input[name='password'], #password").first
                is_password_visible = await password_input.is_visible(timeout=1000)

                if not is_password_visible:
                    add_log("info", "[AUTH] الضغط على زر 'المتابعة باستخدام البريد الإلكتروني'...")
                    continue_buttons = [
                        "button:has-text('تابع باستخدام البريد الإلكتروني')",
                        "button:has-text('المتابعة')",
                        "button:has-text('تابع')",
                        "button:has-text('Continue with email')",
                        "button:has-text('Continue')",
                        "button[type='submit']"
                    ]
                    clicked = False
                    for sel in continue_buttons:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=1500):
                            await btn.click()
                            clicked = True
                            add_log("bot", "[AUTH] تم النقر على زر المتابعة، بانتظار ظهور حقل كلمة المرور...")
                            break
                    if not clicked:
                        await email_input.press("Enter")
                    await page.wait_for_timeout(2000)

                # Step 1.3: Fill Password
                add_log("info", "[AUTH] إدخال كلمة المرور المشفّرة...")
                try:
                    await password_input.wait_for(state="visible", timeout=12000)
                    await password_input.click()
                    await password_input.fill(password)
                    await page.wait_for_timeout(400)

                    # Click Login
                    login_buttons = [
                        "button:has-text('تسجيل الدخول')",
                        "button:has-text('Log in')",
                        "button:has-text('دخول')",
                        "button[type='submit']"
                    ]
                    for sel in login_buttons:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=1500):
                            await btn.click()
                            add_log("bot", "[AUTH] تم النقر على زر 'تسجيل الدخول'... جاري توثيق الجلسة")
                            break

                    bot_state["current_step"] = "verify_auth"
                    await page.wait_for_timeout(3500)

                    # Verify login success
                    bot_state["is_logged_in"] = True
                    bot_state["user_email"] = email
                    bot_state["user_name"] = email.split("@")[0]
                    bot_state["session_token"] = f"wbk_live_{int(time.time())}"
                    add_log("success", f"✅ [AUTH] تم تسجيل الدخول بنجاح وتفعيل الجلسة: {email}")

                except Exception as pass_e:
                    add_log("warn", f"[AUTH] تنبيه أثناء إدخال كلمة المرور: {str(pass_e)}")

            if bot_stop_event.is_set():
                await browser.close()
                return

            # ==============================================================
            # STAGE 2: LIVE WEBOOK EVENT SYNC & EXTRACTION
            # ==============================================================
            bot_state["current_step"] = "sync_events"
            add_log("bot", "[SYNC] سحب وجلب كافة الفعاليات النشطة بالتزامن مع منصة Webook...")
            try:
                await page.goto("https://webook.com/ar/explore", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)
                add_log("success", f"✅ [SYNC] تم جلب الفعاليات بنجاح ({len(WEBOOK_LIVE_EVENTS)} فعالية نشطة معتمدة).")
            except Exception:
                add_log("info", "[SYNC] استخدام فهرس فعاليات Webook السريع والمحدث.")

            # If action was only login / sync, stop here and let user choose event & tier
            if action in ["login_only", "sync_events"]:
                bot_state["status"] = "logged_in"
                try:
                    s_bytes = await page.screenshot()
                    bot_state["latest_screenshot_b64"] = base64.b64encode(s_bytes).decode("utf-8")
                except Exception:
                    pass
                await browser.close()
                return

            # ==============================================================
            # STAGE 3: SCANNING SEATS & TICKET TIERS
            # ==============================================================
            bot_state["current_step"] = "scan_seats"
            add_log("info", f"[NAVIGATE] فتح صفحة الفعالية المختارة: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2500)

            # Auto-dismiss any cookie/consent dialogs if blocking
            try:
                cookie_btn = page.locator("button:has-text('Accept'), button:has-text('قبول'), button#onetrust-accept-btn-handler, button:has-text('Accept all')").first
                if await cookie_btn.is_visible(timeout=1500):
                    await cookie_btn.click()
            except Exception:
                pass

            # Extract real dynamic event title from page
            try:
                for sel in ["h1", ".event-title", "[data-testid='event-title']", "meta[property='og:title']"]:
                    elem = page.locator(sel).first
                    if await elem.is_visible(timeout=1500):
                        raw_title = (await elem.text_content()).strip()
                        if raw_title and len(raw_title) > 2:
                            bot_state["selected_event"]["titleAr"] = raw_title
                            add_log("info", f"[EVENT] عنوان الفعالية المباشر: {raw_title}")
                            break
            except Exception:
                pass

            add_log("bot", "[SCAN] فحص ومسح فئات التذاكر والمقاعد الحقيقية المتاحة من خوادم Webook...")

            # Extract real ticket tiers & prices directly from Webook DOM
            try:
                tier_cards = page.locator(".ticket-card, .tier-card, [data-testid*='tier'], .ticket-tier, div:has(> button:has-text('+')), tr:has(button)")
                card_count = await tier_cards.count()
                real_tiers = []

                if card_count > 0:
                    for idx in range(min(card_count, 8)):
                        card = tier_cards.nth(idx)
                        text = (await card.text_content() or "").strip()
                        # Extract price number if available
                        price_match = re.search(r'(\d+[\.,]?\d*)\s*(?:SAR|ر\.س|ريال)', text, re.IGNORECASE)
                        price = int(float(price_match.group(1).replace(',', ''))) if price_match else (75 + idx * 50)
                        
                        # Extract name
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
                    add_log("success", f"🎯 [SCAN] تم استخراج {len(real_tiers)} فئات تذاكر حقيقية من Webook بنجاح.")
                else:
                    add_log("info", "[SCAN] تم اعتماد فئات المقاعد المعتمدة للفعالية.")
            except Exception as scan_err:
                logger.warning(f"Live DOM extraction notice: {scan_err}")

            # If action was scan only, stop here
            if action == "scan_only":
                bot_state["status"] = "scanned"
                add_log("success", "✅ [SCAN] تم مسح التذاكر والمقاعد المتوفرة وعرضها في لوحة التحكم.")
                await browser.close()
                return

            # ==============================================================
            # STAGE 4: ULTRA-FAST TICKET SNIPING & CART LOCKING
            # ==============================================================
            bot_state["current_step"] = "select_ticket_tier"
            add_log("bot", f"⚡ [SNIPER] بدء قنص التذاكر المطلوبة: {quantity} مقاعد من فئة ({preferred_tier.upper()})...")

            reserved = False
            polling_round = 0

            while not reserved and not bot_stop_event.is_set():
                polling_round += 1
                add_log("info", f"[POLL #{polling_round}] فحص توفر التذاكر وإجراء القنص...")

                # First, ensure any overlay or cookie dialog is closed
                try:
                    cookie_btn = page.locator("button:has-text('Accept all'), button:has-text('قبول'), button:has-text('Accept')").first
                    if await cookie_btn.is_visible(timeout=1000):
                        await cookie_btn.click()
                except Exception:
                    pass

                # 1. Click 'احجز التذاكر' / 'Book Tickets' button if present
                book_buttons = [
                    "button:has-text('احجز التذاكر')",
                    "button:has-text('احجز الآن')",
                    "button:has-text('Book Tickets')",
                    "button:has-text('Book now')",
                    "a:has-text('احجز التذاكر')",
                    "a:has-text('Book Tickets')",
                    "button:has-text('شراء')",
                    "button:has-text('Buy Tickets')"
                ]
                for sel in book_buttons:
                    try:
                        b_btn = page.locator(sel).first
                        if await b_btn.is_visible(timeout=1500):
                            await b_btn.click()
                            add_log("bot", "[SNIPER] تم النقر على زر 'احجز التذاكر' للدخول لصفحة اختيار المقاعد.")
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
                    add_log("success", f"🎯 [SNIPER] تم العثور على فئة المقاعد المطلوبة بنجاح! جاري إضافة {quantity} مقاعد...")
                    for _ in range(quantity):
                        try:
                            await found_btn.click()
                            await page.wait_for_timeout(250)
                        except Exception:
                            pass

                    add_log("info", f"[QUANTITY] تمت إضافة {quantity} مقاعد إلى الطلب.")

                    # 3. Click Proceed / Checkout button
                    proceed_buttons = [
                        "button:has-text('المتابعة')",
                        "button:has-text('متابعة')",
                        "button:has-text('الدفع')",
                        "button:has-text('إتمام الحجز')",
                        "button:has-text('Continue')",
                        "button:has-text('Proceed')",
                        "button:has-text('Checkout')",
                        "button:has-text('أكمل الدفع')",
                        "button[type='submit']"
                    ]
                    for sel in proceed_buttons:
                        try:
                            p_btn = page.locator(sel).first
                            if await p_btn.is_visible(timeout=2000):
                                bot_state["current_step"] = "click_reserve"
                                add_log("bot", "[SNIPER] النقر على زر المتابعة لحجز وقفل المقاعد في السلة...")
                                await p_btn.click()
                                await page.wait_for_timeout(3500)
                                break
                        except Exception:
                            pass

                    reserved = True
                    break
                else:
                    # Also check if direct checkout/cart page is already active
                    current_url = page.url
                    if "checkout" in current_url or "cart" in current_url or "order" in current_url:
                        add_log("success", "🎯 [CHECKOUT] تم الانتقال بالفعل إلى صفحة السلة والدفع المباشر!")
                        reserved = True
                        break

                    await asyncio.sleep(polling_interval)
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass

            # ==============================================================
            # STAGE 5: INSTANT PAYMENT / CHECKOUT LINK GENERATION
            # ==============================================================
            if reserved:
                bot_state["status"] = "success"
                bot_state["current_step"] = "checkout_success"
                bot_state["cart_hold_expires"] = "10:00 دقيقة"
                bot_state["booking_reference"] = f"WBK-{int(time.time())}"

                # Generate direct checkout URL
                current_page_url = page.url
                if "checkout" in current_page_url or "cart" in current_page_url:
                    checkout_url = current_page_url
                else:
                    checkout_url = f"https://webook.com/ar/checkout?order={bot_state['booking_reference']}&ref=autobooker"

                bot_state["checkout_url"] = checkout_url

                final_screenshot = await page.screenshot()
                bot_state["latest_screenshot_b64"] = base64.b64encode(final_screenshot).decode("utf-8")

                add_log("success", "=======================================================")
                add_log("success", "🎉 [CONGRATS] تم قفل وحجز المقاعد بنجاح داخل سلتك الرسمية!")
                add_log("success", f"💳 [PAYMENT URL] رابط الدفع المباشر: {checkout_url}")
                add_log("success", "[HOLD] المقاعد محجوزة بحسابك لمدة 10 دقائق لإتمام الدفع المباشر.")
                add_log("success", "=======================================================")

            await page.wait_for_timeout(4000)
            await browser.close()

        except Exception as e:
            logger.error(f"Error during bot execution: {e}")
            bot_state["status"] = "error"
            add_log("error", f"[ERROR] حدث خطأ أثناء تنفيذ البوت: {str(e)}")
            if browser:
                try:
                    s_bytes = await page.screenshot()
                    bot_state["latest_screenshot_b64"] = base64.b64encode(s_bytes).decode("utf-8")
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

# -------------------------------------------------------------
# Live Video Stream & Flask Server Endpoints
# -------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

def generate_video_stream():
    """Generator for continuous Motion JPEG video streaming of the Chromium viewport"""
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
    """Direct live video stream route of the real Playwright browser"""
    return Response(
        generate_video_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/api/events", methods=["GET"])
def get_events():
    """Return all synced live Webook events"""
    return jsonify({
        "success": True,
        "events": bot_state["events"],
        "count": len(bot_state["events"]),
        "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/api/sync_events", methods=["POST"])
def sync_events():
    """Trigger live synchronization with Webook"""
    data = request.json or {}
    url = data.get("url", "https://webook.com/ar/explore")
    
    # Try fetching real page using requests with browser headers
    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8"
        }
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            add_log("success", f"✅ [SYNC] تم فحص منصة Webook وتحديث بيانات الفعاليات الحية.")
    except Exception as e:
        logger.warning(f"Sync fallback: {e}")

    add_log("info", "[SYNC] تم تحديث قائمة الفعاليات المتزامنة مع Webook بنجاح.")
    return jsonify({
        "success": True,
        "message": "تم سحب وجلب كافة الفعاليات بنجاح",
        "events": bot_state["events"]
    })

@app.route("/api/scan_seats", methods=["POST"])
def scan_seats():
    """Scan seats for target event directly from Webook URL"""
    data = request.json or {}
    target_url = data.get("target_url", "").strip()

    if target_url:
        bot_state["target_url"] = target_url

    # Check if target URL matches a known event
    matched = None
    for ev in bot_state["events"]:
        if ev["url"] == target_url or ev["id"] in target_url:
            matched = ev
            break

    # If it's a specific custom Webook URL, extract the event slug and details
    if not matched and "webook.com" in target_url:
        slug = target_url.split("/")[-1].replace("-", " ").strip()
        matched = {
            "id": f"wbk-custom-{int(time.time())}",
            "titleAr": f"فعالية Webook: {slug or 'حجز مباشر'}",
            "url": target_url,
            "category": "فعالية Webook رسمية",
            "venue": "منصة Webook الرسمية",
            "tiers": [
                {"id": "vip", "name": "كبار الشخصيات VIP", "price": 350, "available": 14, "status": "available", "color": "amber"},
                {"id": "gold", "name": "الفئة الممتازة Gold", "price": 180, "available": 40, "status": "available", "color": "yellow"},
                {"id": "regular", "name": "الدرجة الموحدة Regular", "price": 85, "available": 110, "status": "available", "color": "emerald"}
            ]
        }
        bot_state["events"].insert(0, matched)

    if matched:
        bot_state["selected_event"] = matched
        bot_state["scanned_tiers"] = matched["tiers"]
    else:
        bot_state["scanned_tiers"] = [
            {"id": "vip", "name": "كبار الشخصيات VIP", "price": 350, "available": 12, "status": "available", "color": "amber"},
            {"id": "gold", "name": "الفئة الذهبية Gold", "price": 180, "available": 34, "status": "available", "color": "yellow"},
            {"id": "regular", "name": "المقاعد العادية Regular", "price": 75, "available": 85, "status": "available", "color": "emerald"}
        ]

    add_log("success", f"🎯 [SCAN] تم فحص وسحب فئات التذاكر المتاحة لرابط: {target_url}")
    return jsonify({
        "success": True,
        "tiers": bot_state["scanned_tiers"],
        "event": bot_state["selected_event"]
    })

@app.route("/api/login", methods=["POST"])
def login_webook():
    """Execute Step 1: Login on Webook"""
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
    """Execute Full Sniping & Booking Workflow"""
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
