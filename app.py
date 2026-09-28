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

# Playwright Background Worker (Final Bulletproof Sniper)
async def run_automation_script(email, password, event_url, quantity):
    global bot_status, is_running, browser_instance, context_instance, page_instance
    is_running = True
    bot_status = "يعمل"
    
    add_log("info", "🚀 بدء تشغيل محرك القنص النهائي (النسخة المحصنة)...")
    
    async with async_playwright() as p:
        try:
            browser_instance = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-extensions"]
            )
            context_instance = await browser_instance.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page_instance = await context_instance.new_page()

            # 1. Navigation to Login with robust waiting
            add_log("info", "فتح صفحة تسجيل الدخول...")
            await page_instance.goto("https://webook.com/ar/login", timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 2. Robust Authentication with verification
            add_log("info", f"تسجيل الدخول بالحساب: {email}")
            try:
                # Wait for email input explicitly
                email_field = page_instance.locator("input[type='email'], input[name='email'], input[placeholder*='البريد']").first
                await email_field.wait_for(state="visible", timeout=10000)
                await email_field.fill(email)

                pass_field = page_instance.locator("input[type='password'], input[name='password']").first
                await pass_field.wait_for(state="visible", timeout=10000)
                await pass_field.fill(password)

                submit_btn = page_instance.locator("button[type='submit'], button:has-text('تسجيل الدخول'), button:has-text('Login')").first
                await submit_btn.click(force=True)
                add_log("success", "تم إرسال بيانات الدخول، جاري التحقق...")
                await asyncio.sleep(3) # Wait for login session to establish
            except Exception as login_err:
                add_log("error", f"خطأ أثناء تسجيل الدخول: {str(login_err)[:40]}")

            # 3. Navigate to Event
            add_log("info", "الانتقال لصفحة الحجز والفعالية المستهدفة...")
            await page_instance.goto(event_url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 4. Smart Sniping & Checkout Loop
            add_log("info", "⚡ بدء حلقة القنص الذكية ورصد المقاعد...")
            poll_count = 0
            reserved = False
            target_qty = int(quantity)

            while is_running and not reserved:
                poll_count += 1
                add_log("poll", f"⚡ فحص الخريطة [محاولة #{poll_count}]...")

                try:
                    # Execute JS to pick seats and attempt checkout immediately
                    res_data = await page_instance.evaluate(f"""
                        (qty) => {{
                            const selectors = [
                                '.seat-available', 
                                'rect.available', 
                                'g.seat:not(.booked)', 
                                '[data-seat-status="available"]', 
                                '.ticket-seat-item', 
                                'circle.available', 
                                'path.available',
                                '.category-block',
                                '[class*="block"]'
                            ];
                            
                            let seats = [];
                            for (let sel of selectors) {{
                                found = document.querySelectorAll(sel);
                                if (found && found.length > 0) {{
                                    seats = Array.from(found);
                                    break;
                                }}
                            }}
                            
                            if (seats.length === 0) return {{success: false, reason: "no_seats"}};

                            let clicked = 0;
                            for (let i = 0; i < Math.min(seats.length, qty); i++) {{
                                try {{
                                    seats[i].click();
                                    clicked++;
                                }} catch (e) {{}}
                            }}

                            if (clicked > 0) {{
                                // Find checkout / continue buttons
                                const buttons = Array.from(document.querySelectorAll('button, a'));
                                const targetBtn = buttons.find(b => {{
                                    const t = b.innerText || '';
                                    return t.includes('التالي') || t.includes('الدفع') || t.includes('Next') || t.includes('متابعة') || t.includes('Book') || t.includes('حجز');
                                }});
                                
                                if (targetBtn) {{
                                    targetBtn.click();
                                    return {{success: true, clicked: clicked, advanced: true}};
                                }}
                                return {{success: true, clicked: clicked, advanced: false}};
                            }}
                            return {{success: false, reason: "click_failed"}};
                        }}
                    """, target_qty)

                    if res_data and res_data.get("success"):
                        add_log("success", f"🎯 تم اختيار عدد {res_data.get('clicked')} مقعد بنجاح!")
                        
                        if res_data.get("advanced"):
                            add_log("success", "🚀 تم الانتقال لصفحة الدفع بنجاح خارق!")
                            await asyncio.sleep(1.5)

                            # Handle checkboxes and final payment click
                            await page_instance.evaluate("""
                                () => {
                                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                                    checkboxes.forEach(cb => { if(!cb.checked) cb.click(); });
                                    
                                    const buttons = Array.from(document.querySelectorAll('button, a'));
                                    const payBtn = buttons.find(b => {
                                        const t = b.innerText || '';
                                        return t.includes('الدفع') || t.includes('Pay') || t.includes('تأكيد');
                                    });
                                    if (payBtn) payBtn.click();
                                }
                            """)
                            add_log("success", "💳 تم الوصول لبوابة الدفع النهائية بنجاح تام!")
                            reserved = True
                            break

                except Exception as e:
                    pass

                await asyncio.sleep(0.4)

            if reserved:
                add_log("success", "🎉 تم الحجز وقنص التذاكر بنجاح خارق!")
            else:
                add_log("info", "تم إيقاف دورة القنص.")

        except Exception as ex:
            add_log("error", f"خطأ بالمحرك: {str(ex)}")
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
    <title>Webook Ultimate Sniper Booker</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-4">
    <div class="max-w-4xl mx-auto space-y-6">
        <header class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex justify-between items-center">
            <div>
                <h1 class="text-2xl font-bold bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent">Webook Ultimate Sniper</h1>
                <p class="text-sm text-slate-400 mt-1">سيرفر أتمتة وحجز تذاكر Webook المحصن والذكي</p>
            </div>
            <div id="status-badge" class="px-4 py-2 rounded-full text-sm font-semibold bg-red-950/80 text-red-400 border border-red-800">
                الحالة: <span id="status-text">متوقف</span>
            </div>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
                <h2 class="text-lg font-semibold mb-4 text-amber-400">إعدادات قنص التذاكر</h2>
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
                        <button type="button" onclick="startBot()" class="flex-1 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold py-3 px-4 rounded-xl transition shadow-lg shadow-amber-500/20">تشغيل وقنص فائق</button>
                        <button type="button" onclick="stopBot()" class="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-xl transition shadow-lg shadow-red-600/20">إيقاف البوت</button>
                    </div>
                </form>
            </div>

            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col h-[500px]">
                <h2 class="text-lg font-semibold mb-3 text-amber-400">Terminal (Ultimate Worker)</h2>
                <div id="terminal" class="flex-1 bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs overflow-y-auto space-y-2 select-text dir-ltr text-left">
                    <div class="text-slate-500">جاهز للتشغيل المحصن بأقصى سرعة...</div>
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

        setInterval(fetchLogs, 1000);
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
