# إصلاحات مسير الرواتب والمسارات (404 / 500 / 400)

## 1. مسارات الموظفين (404)

المسارات التالية **معرّفة** في التطبيق في `app/routes.py` (بلوبرينت `main`):

| المسار | الطريقة | Endpoint | الوصف |
|--------|---------|----------|--------|
| `/employees/<id>/pay` | GET, POST | `main.pay_salary` | صفحة مسير راتب موظف واحد (مع year, month في query) |
| `/employees/settings` | GET, POST | `main.employees_settings` | إعدادات الموظفين (ساعات، أقسام، معدلات) |

**إذا ظهر 404:**

- تأكد أن نقطة التشغيل على Render هي `app:app` (حزمة `app` والكائن `app`) وليس `wsgi_simple` أو غيره، لأن الـ fallback لا يتضمن هذه المسارات.
- في `render.yaml`: `startCommand: gunicorn -k gevent --timeout 120 app:app`
- تحقق أن طلبك بالضبط: `GET /employees/3/pay?year=2026&month=2` و `GET /employees/settings` (بدون بادئة أخرى).
- إذا كان هناك reverse proxy يضيف مساراً أساسياً (مثل `/china-town`)، قد تحتاج إلى ضبط `APPLICATION_ROOT` أو إضافة نفس المسارات ببادئة.

في القوالب يتم استخدام:
- `url_for('main.employees_settings')` لرابط الإعدادات.
- `/employees/` + `empId` + `/pay?year=...&month=...` لصفحة الراتب (يُبنى في JavaScript).

---

## 2. واجهات 500 (seed_official و quick-txn)

### `POST /financials/api/accounts/seed_official`

- **التعديلات:** إضافة أعمدة دفاعية لجدول `accounts` عند التشغيل على PostgreSQL (`name_ar`, `name_en`) في `app/__init__.py`، وتحسين معالجة الأخطاء في `api_accounts_seed_official` (استيراد الشجرة، عدم افتراض طول الصف، معالجة IntegrityError عند الـ commit).
- **النتيجة:** تقليل أخطاء 500 الناتجة عن أعمدة ناقصة أو تعارض في البيانات.

### `POST /financials/api/quick-txn`

- الوظيفة تحتوي بالفعل على `try/except` تُرجع 500 مع رسالة الخطأ.
- إن استمرت 500، تحقق من سجلات السيرفر لمعرفة الاستثناء (مثلاً عمود ناقص في `journal_lines` أو `accounts`). تمت إضافة أعمدة دفاعية لـ `journal_lines` و`accounts` عند التشغيل على PostgreSQL.

---

## 3. واجهات مسير الرواتب (400 → 500 أو سلوك أوضح)

### `POST /api/payroll/ensure-records`

- **قبل:** أي استثناء كان يُرجع **400**.
- **بعد:** أي استثناء غير متوقع يُرجع **500** مع `error` في الجسم، لأن فشل إنشاء السجلات أو الـ commit هو خطأ سيرفر وليس طلباً خاطئاً من العميل.

### `POST /api/payroll-post`

- **قبل:** إذا لم يُرسل `year` أو `month` كان يُرجع **400**.
- **بعد:**
  - يقبل **form** أو **JSON** (مثلاً `{"year": 2026, "month": 2}`).
  - إذا لم يُرسل `year` أو `month`: يُستخدم **الشهر الحالي** ويُكمل الترحيل بنجاح (200).
  - التحقق من صحة الشهر (1–12) يبقى، وإلا يُرجع 400 مع `invalid_month`.
  - أي استثناء غير متوقع يُرجع **500** بدلاً من 400.

---

## 4. ملخص الاستدعاءات الموصى بها

| الوظيفة | الطريقة | المسار | الجسم/المعاملات |
|---------|---------|--------|------------------|
| مسير راتب موظف | GET | `/employees/<id>/pay?year=2026&month=2` | — |
| إعدادات الموظفين | GET | `/employees/settings` | — |
| زرع الحسابات الرسمية | POST | `/financials/api/accounts/seed_official` | (فارغ أو JSON) |
| عملية سريعة | POST | `/financials/api/quick-txn` | JSON: type, date, amount, payment_method, ... |
| إنشاء سجلات رواتب | POST | `/api/payroll/ensure-records` | (فارغ أو form) |
| ترحيل مسير الرواتب | POST | `/api/payroll-post` | form أو JSON: `year`, `month` (اختياريان) |

---

## 5. 304 (ملفات ثابتة)

ردود **304** لملفات JS/CSS تعني أن المتصفح يستخدم النسخة المخزنة؛ هذا سلوك طبيعي ولا يرتبط بفشل مسير الرواتب.
