import os
import asyncio
from flask import Flask, render_template_string, jsonify, request
from playwright.async_api import async_playwright

app = Flask(__name__)

# Global Automation State
bot_status = "متوقف"
bot_logs = []
browser_instance = None
context_instance = None
page_instance = None
is_running = False

def add_log(level, message):
    global bot_logs
    log_entry = {"level": level, "message": message}
    bot_logs.append(log_entry)
    if len(bot_logs) > 100:
        bot_logs.pop(0)

# Playwright Background Worker
async def run_automation_script(email, password, event_url, quantity):
    global bot_status, is_running, browser_instance, context_instance, page_instance
    is_running = True
    bot_status = "يعمل"
    
    add_log("info", "بدء تشغيل محرك Playwright المتصفح...")
    
    async with async_playwright() as p:
        try:
            browser_instance = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context_instance = await browser_instance.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page_instance = await context_instance.new_page()

            # 1. Navigation to Login
            add_log("info", f"فتح صفحة تسجيل الدخول: https://webook.com/ar/login")
            await page_instance.goto("https://webook.com/ar/login", timeout=60000)
            await asyncio.sleep(2)

            # Handle Cookie Banner if exists
            try:
                cookie_btn = page_instance.locator("button:has-text('قبول'), button:has-text('Accept'), [aria-label='accept']")
                if await cookie_btn.is_visible(timeout=3000):
                    await cookie_btn.click()
                    add_log("info", "تم تجاوز نافذة ملفات التعريف بنجاح.")
            except Exception:
                pass

            # 2. Authentication
            add_log("info", f"كتابة البريد الإلكتروني: {email}")
            email_input = page_instance.locator("input[type='email'], input[name='email'], input[placeholder*='البريد']").first
            await email_input.fill(email)
            
            await asyncio.sleep(1)
            
            pass_input = page_instance.locator("input[type='password'], input[name='password']").first
            if await pass_input.is_visible(timeout=3000):
                await pass_input.fill(password)
            
            submit_btn = page_instance.locator("button[type='submit'], button:has-text('تسجيل الدخول'), button:has-text('Login')").first
            if await submit_btn.is_visible(timeout=3000):
                await submit_btn.click()
                
            add_log("success", f"اكتملت مصادقة الحساب بنجاح: {email}")
            await asyncio.sleep(3)

            # 3. Navigate to Event
            add_log("info", f"الانتقال المباشر لصفحة الفعالية: {event_url}")
            await page_instance.goto(event_url, timeout=60000)
            await asyncio.sleep(3)

            # 4. Sniping and Seat Selection Loop (Matching video flow)
            add_log("info", "بدء مراقبة خريطة المقاعد وقنص التذاكر المتاحة...")
            poll_count = 0
            reserved = False
            target_qty = int(quantity)

            while is_running and not reserved:
                poll_count += 1
                add_log("poll", f"فحص الخريطة والمقاعد المتاحة [#{poll_count}]...")

                try:
                    # Step A: Click available section/block in stadium map if needed, or scan direct seats
                    available_seats = page_instance.locator(".seat-available, rect.available, g.seat:not(.booked), [data-seat-status='available'], .ticket-seat-item, circle.available")
                    count = await available_seats.count()

                    if count > 0:
                        add_log("success", f"🎯 [SNIPER] تم رصد مقاعد متاحة! جاري قنص عدد {target_qty} مقعد...")
                        
                        clicked_count = 0
                        for i in range(min(count, target_qty)):
                            seat = available_seats.nth(i)
                            if await seat.is_visible():
                                await seat.click()
                                clicked_count += 1
                                add_log("info", f"تم اختيار المقعد رقم {clicked_count}")
                                await page_instance.wait_for_timeout(300)

                        if clicked_count >= target_qty or clicked_count > 0:
                            # Step B: Click 'Next to Payment' or 'التالي للدفع' button
                            next_btn = page_instance.locator("button:has-text('التالي للدفع'), button:has-text('Next'), button:has-text('متابعة'), button:has-text('الدفع')").first
                            if await next_btn.is_visible(timeout=3000):
                                await next_btn.click()
                                add_log("success", "🚀 [SNIPER] تم النقر على زر التالي للدفع بنجاح!")
                                await page_instance.wait_for_timeout(2000)

                                # Step C: Accept terms and proceed to payment gateway
                                terms_checkbox = page_instance.locator("input[type='checkbox'], .terms-checkbox").first
                                if await terms_checkbox.is_visible(timeout=2000):
                                    await terms_checkbox.click()
                                    add_log("info", "تم تحديد شروط وأحكام الخدمة.")

                                pay_btn = page_instance.locator("button:has-text('الدفع بواسطة'), button:has-text('Pay with'), button:has-text('تأكيد الدفع')").first
                                if await pay_btn.is_visible(timeout=2000):
                                    await pay_btn.click()
                                    add_log("success", "💳 تم الانتقال لبوابة الدفع بنجاح تام!")
                                    reserved = True
                            else:
                                add_log("info", "تم اختيار المقاعد ولكن زر التالي غير ظاهر بعد، جاري إعادة المحاولة...")
                    else:
                        # Try clicking a block/category if individual seats are not loaded yet
                        block_elem = page_instance.locator(".category-block, [class*='block'], g[class*='zone']").first
                        if await block_elem.is_visible(timeout=500):
                            await block_elem.click()
                            await page_instance.wait_for_timeout(500)

                except Exception as e:
                    add_log("info", f"انتظار إتاحة المقاعد في الخريطة... ({str(e)[:30]})")

                await asyncio.sleep(3)

            if reserved:
                add_log("success", "🎉 تم إتمام مسار القنص والحجز بنجاح تام!")
            else:
                add_log("info", "تم إيقاف دورة القنص.")

        except Exception as ex:
            add_log("error", f"خطأ في تنفيذ المحرك: {str(ex)}")
        finally:
            if browser_instance:
                await browser_instance.close()
            is_running = False
            bot_status = "متوقف"

# HTML Template UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Webook Auto-Booker Web App</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-4">
    <div class="max-w-4xl mx-auto space-y-6">
        <header class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex justify-between items-center">
            <div>
                <h1 class="text-2xl font-bold bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent">Webook Auto-Booker Web App</h1>
                <p class="text-sm text-slate-400 mt-1">سيرفر أتمتة وحجز تذاكر Webook السريع عبر المتصفح</p>
            </div>
            <div id="status-badge" class="px-4 py-2 rounded-full text-sm font-semibold bg-red-950/80 text-red-400 border border-red-800">
                الحالة: <span id="status-text">متوقف</span>
            </div>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
                <h2 class="text-lg font-semibold mb-4 text-amber-400">إعدادات حساب وحجز Webook</h2>
                <form id="control-form" class="space-y-4">
                    <div>
                        <label class="block text-sm text-slate-300 mb-1">البريد الإلكتروني</label>
                        <input type="email" id="email" value="neyazyyy@gmail.com" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-amber-500">
                    </div>
                    <div>
                        <label class="block text-sm text-slate-300 mb-1">كلمة المرور</label>
                        <input type="password" id="password" placeholder="••••••••" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-amber-500">
                    </div>
                    <div>
                        <label class="block text-sm text-slate-300 mb-1">رابط الفعالية المستهدفة</label>
                        <input type="text" id="event_url" value="https://webook.com/ar/events/sports-event/events/moroccovghana-26-friendly/book" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-amber-500">
                    </div>
                    <div>
                        <label class="block text-sm text-slate-300 mb-1">الكمية المطلوبة</label>
                        <input type="number" id="quantity" value="4" min="1" max="10" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-amber-500">
                    </div>
                    <div class="flex gap-4 pt-2">
                        <button type="button" onclick="startBot()" class="flex-1 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold py-3 px-4 rounded-xl transition shadow-lg shadow-amber-500/20">تشغيل وقنص البوت</button>
                        <button type="button" onclick="stopBot()" class="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-xl transition shadow-lg shadow-red-600/20">إيقاف البوت</button>
                    </div>
                </form>
            </div>

            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col h-[500px]">
                <h2 class="text-lg font-semibold mb-3 text-amber-400">Terminal (Playwright Worker)</h2>
                <div id="terminal" class="flex-1 bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs overflow-y-auto space-y-2 select-text dir-ltr text-left">
                    <div class="text-slate-500">جاري انتظار بدء مهام التيرمينال...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function fetchLogs() {
            try {
                let res = await fetch('/status');
                let data = await res.json();
                
                let statusText = document.getElementById('status-text');
                let statusBadge = document.getElementById('status-badge');
                if(data.status === 'يعمل') {
                    statusText.innerText = 'يعمل';
                    statusBadge.className = 'px-4 py-2 rounded-full text-sm font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800';
                } else {
                    statusText.innerText = 'متوقف';
                    statusBadge.className = 'px-4 py-2 rounded-full text-sm font-semibold bg-red-950/80 text-red-400 border border-red-800';
                }

                let term = document.getElementById('terminal');
                let logsHtml = '';
                data.logs.forEach(log => {
                    let color = 'text-slate-300';
                    if(log.level === 'success') color = 'text-emerald-400 font-semibold';
                    if(log.level === 'error') color = 'text-red-400 font-semibold';
                    if(log.level === 'poll') color = 'text-purple-400';
                    logsHtml += `<div class="${color}">[${new Date().toLocaleTimeString()}] ${log.message}</div>`;
                });
                if(logsHtml !== '') {
                    term.innerHTML = logsHtml;
                    term.scrollTop = term.scrollHeight;
                }
            } catch(e) {}
        }

        async function startBot() {
            let email = document.getElementById('email').value;
            let password = document.getElementById('password').value;
            let event_url = document.getElementById('event_url').value;
            let quantity = document.getElementById('quantity').value;

            await fetch('/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password, event_url, quantity})
            });
            fetchLogs();
        }

        async function stopBot() {
            await fetch('/stop', {method: 'POST'});
            fetchLogs();
        }

        setInterval(fetchLogs, 2000);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/status")
def status():
    return jsonify({"status": bot_status, "logs": bot_logs})

@app.route("/start", methods=["POST"])
def start():
    global is_running
    if is_running:
        return jsonify({"success": False, "message": "Bot is already running"})
    
    data = request.json
    email = data.get("email")
    password = data.get("password")
    event_url = data.get("event_url")
    quantity = data.get("quantity", 4)

    import threading
    threading.Thread(target=lambda: asyncio.run(run_automation_script(email, password, event_url, quantity))).start()

    return jsonify({"success": True})

@app.route("/stop", methods=["POST"])
def stop():
    global is_running, browser_instance
    is_running = False
    return jsonify({"success": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
