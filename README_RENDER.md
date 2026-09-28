# 🚀 دليل رفع وتشغيل بوت Webook Auto-Booker على استضافة Render.com

هذا الدليل يوضح لك بالخطوات الدقيقة كيفية رفع المشروع كاملاً على استضافة **Render** المجانية أو المدفوعة، وضمان تشغيل محرك أتمتة **Playwright** بدون أي مشاكل أو نقص في مكتبات المتصفح (`libasound2`, `libnss3`, etc.).

---

## 📁 الملفات المجهزة والمضمنة في المشروع:

1. **`app.py`**: سيرفر Flask المتكامل، مرتبط بمحرك Playwright وChromium فائق السرعة، ومسارات API للتحكم المباشر (`/api/start`, `/api/stop`, `/api/status`, `/api/reset`).
2. **`templates/index.html`**: لوحة تحكم ويب احترافية (Web Dashboard) تتيح لك إدخال الحسابات، اختيار التذاكر، متابعة شاشة المتصفح الحية (`Chromium Mirror`)، وسجل العمليات اللحظي (`Live Terminal Logs`).
3. **`Dockerfile`** *(موصى به جداً)*: مبني على صورة مايكروسوفت الرسمية `mcr.microsoft.com/playwright/python:v1.44.0-jammy` التي تحتوي على جميع حزم نظام Linux المسبقة للمتصفح.
4. **`requirements.txt`**: قائمة المكتبات المحددة (`Flask`, `playwright`, `gunicorn`, `requests`, إلخ).
5. **`Procfile`**: أمر تشغيل السيرفر التلقائي على Render عبر خادم Gunicorn.
6. **`build.sh`**: سكربت التثبيت للبيئة العادية (Python Native).
7. **`render.yaml`**: ملف إعدادات Render Blueprint لنشر المشروع بضغطة زر واحدة.

---

## 🌟 الطريقة الموصى بها (الطريقة رقم 1: بيئة Docker - أضمن وأسرع 100%)

بيئة **Docker** على Render تضمن عمل متصفح Playwright بدون أي خطأ خاص بنقص الحزم أو الصلاحيات.

### الخطوة 1: إنشاء مستودع على GitHub
1. اذهب إلى [GitHub](https://github.com) وأنشئ مستودعاً جديداً (New Repository) مثلاً: `webook-bot`.
2. ارفع الملفات التالية مباشرة داخل المستودع:
   - `app.py`
   - مجلد `templates` وبداخله `index.html`
   - `Dockerfile`
   - `requirements.txt`
   - `Procfile`
   - `render.yaml`

### الخطوة 2: الربط والنشر على Render
1. ادخل إلى لوحة تحكم [dashboard.render.com](https://dashboard.render.com).
2. اضغط على زر **New +** واختر **Web Service**.
3. اختر **Build and deploy from a Git repository** واضغط **Next**.
4. اختر المستودع الخاص بك من القائمة (`webook-bot`).
5. في صفحة الإعدادات:
   - **Name**: `webook-auto-booker` (أو أي اسم تفضله).
   - **Region**: اختر الأقرب لك (مثل Frankfurt أو London).
   - **Runtime**: اختر **Docker** (سيتعرف عليه تلقائياً بوجود ملف `Dockerfile`).
   - **Instance Type**: اختر **Free** (أو Starter).
6. اضغط على **Create Web Service**.

خلال دقيقتين سيتم بناء الحاوية وتشغيل السيرفر وستحصل على رابط موقعك المباشر، مثل:
`https://webook-auto-booker.onrender.com`

---

## 🛠️ الطريقة البديلة (الطريقة رقم 2: بيئة Python Native)

إذا أردت اختيار بيئة **Python** التقليدية في Render بدلاً من Docker:

1. في Render اختر **Runtime: Python 3**.
2. **Build Command**:
   ```bash
   pip install -r requirements.txt && playwright install chromium
   ```
3. **Start Command**:
   ```bash
   gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --worker-class sync --timeout 300 app:app
   ```
4. أضف متغير بيئة في **Environment Variables**:
   - `PYTHON_VERSION` = `3.11.9`
5. اضغط **Create Web Service**.

---

## 📱 كيفية استخدام لوحة التحكم بعد النشر:

1. افتح الرابط المباشر من هاتفك أو جهاز الكمبيوتر (`https://your-app.onrender.com`).
2. أدخل بيانات حساب Webook (البريد الإلكتروني وكلمة المرور).
3. ضع رابط الفعالية المطلوبة في Webook (مثل مباريات موسم الرياض أو الحفلات).
4. حدد الفئة المفضلة (VIP أو Regular) وعدد المقاعد (1 - 8 مقاعد).
5. (اختياري) أدخل توكن بوت تليجرام ومعرف المحادثة (`Chat ID`) لاستلام لقطة الشاشة وتأكيد الحجز على هاتفك فوراً.
6. اضغط على **"بدء تشغيل البوت الآن (Run Bot)"**.
7. ستشاهد مباشرة:
   - لقطات حية للمتصفح وهو يتخطى الحماية ويسجل الدخول ويختار التذاكر.
   - سجل العمليات بالثواني.
   - عند نجاح الحجز، يتم حفظ المقاعد في سلتك الرسمية على Webook لمدة 10 دقائق لإتمام الدفع ببطاقتك البنكية.

---

## 💡 نصائح مهمة للتشغيل المستقر على خوادم Render:

1. **الذاكرة العشوائية (RAM)**: تم تزويد متصفح Chromium في الكود بإعدادات تحسين الذاكرة (`--no-sandbox`, `--disable-dev-shm-usage`, `--single-process`) ليعمل بخفة وسرعة ضمن سعة 512MB RAM المتاحة في خطة Render المجانية.
2. **استمرارية التشغيل**: في الخطة المجانية، يدخل السيرفر في وضع الخمول بعد 15 دقيقة من عدم الاستخدام. وبمجرد فتح الرابط، يستيقظ السيرفر تلقائياً خلال 30 ثانية.
3. **الأمان**: جميع البيانات تمر مباشرة داخل السيرفر وتُستخدم للتنقل في المتصفح فقط ولا يتم مشاركتها إطلاقاً.
