# Phase 7–8: Render Setup + التحقق النهائي قبل الإنتاج

## تشديد الأمان قبل Render (Pre‑Render)

### 1. Node Accounting — حد الطلبات والتحقق من Payload

- **Rate limit** على `/api/external/*`: `express-rate-limit`، افتراضي 60 طلب/دقيقة لكل IP.
  - Env: `RATE_LIMIT_WINDOW_MS` (مثلاً 60000)، `RATE_LIMIT_MAX_REQUESTS` (مثلاً 60).
  - عند التجاوز → **429**؛ الـ adapter يرفع `AccountingUnavailableError`.
- **التحقق من Payload:**
  - `source_system` **إلزامي** وقيمته من القائمة المسموحة فقط (مثلاً `flask-pos`).
  - إن وُجد `source_ref_type` فيصلح أن يكون من الأنواع المعروفة (مثل `sales`, `purchase`, `expense`, …).
  - رفض أي payload غير مطابق → **400**.

### 2. اختبار اتزان القيود (موصى به)

```sql
SELECT journal_id, SUM(debit) AS debit, SUM(credit) AS credit
FROM journal_lines
GROUP BY journal_id
HAVING ABS(COALESCE(SUM(debit),0) - COALESCE(SUM(credit),0)) > 0.01;
```

يجب أن يرجع **0 صفوف** دائماً. انظر `test_journal_entries_balanced` في `tests/test_accounting_integration.py`.

### اختبار اتزان القيود وقاعدة البيانات

- تم إضافة سكربت **Bash:** `scripts/check_accounting_db_and_api.sh`
- تم إضافة سكربت **PowerShell:** `scripts/check_accounting_db_and_api.ps1`
- يقوم السكربت بالتحقق من:
  - السنة المالية 2026
  - اتزان القيود في `journal_lines`
  - الفواتير بدون `journal_entry_id`
  - التكرار على مصدر القيد
  - اختبار POST API لفاتورة جديدة
  - اختبار رفض الفواتير على سنة مغلقة
- **يجب تشغيل Node محلياً على المنفذ 3000** قبل اختبار خطوات الـ API (5 و 6).

### 3. اختبار إغلاق السنة (إلزامي قبل الإنتاج)

- **السيناريو:** إغلاق سنة 2026 من Node → إرسال فاتورة من Flask لتاريخ ضمن 2026.
- **المتوقع:**
  - **403 Fiscal Year Closed** من Node.
  - Flask **لا يحفظ** الفاتورة.
  - **لا يُنشأ** `journal_entry` جديد.
- انظر `test_fiscal_year_closed_rejects_invoice` (يتطلب `DATABASE_URL` Postgres).

### 4. Unique index على المصدر (اختياري — نضج عالي)

- `(source_system, source_ref_type, source_ref_id)` → **unique index** في Node (حيث القيم غير NULL).
- يمنع التكرار على مستوى قاعدة البيانات؛ مُطبَّق في `schema.sql` كـ `idx_journal_source_unique`.

---

## Render Setup

### Service 1: Flask App (POS)

- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn wsgi:application` or `python -m app` (as per existing Procfile)
- **Env:**
  - `DATABASE_URL` — PostgreSQL (shared or dedicated)
  - `ACCOUNTING_API` — `https://<accounting-service>.onrender.com`
  - `ACCOUNTING_KEY` — نفس المفتاح المُستخدم في Node
  - `SECRET_KEY`, etc.

### Service 2: Node Accounting

- **Root:** `accounting-service/`
- **Build:** `npm install`
- **Start:** `npm start` ( runs `node src/index.js` )
- **Env:**
  - `DATABASE_URL` — PostgreSQL (يمكن مشاركته مع Flask أو منفصل)
  - `ACCOUNTING_KEY` — مفتاح سري لـ `X-API-KEY`
  - `PORT` — Render يضبطه تلقائياً

### Database: PostgreSQL

- استخدم PostgreSQL من Render. نفّذ `accounting-service/src/schema.sql` على قاعدة المحاسبة (أو قاعدة مشتركة مع إنشاء جداول المحاسبة فيها).
- **لا تشغّل seed تلقائياً عند deploy.** نفّذ schema يدوياً أو عبر شغل مرة واحدة لسكربت init.

---

## Environment Variables Summary

| Variable | Service | الوصف |
|----------|---------|--------|
| `DATABASE_URL` | Both | PostgreSQL connection string |
| `ACCOUNTING_API` | Flask | Base URL of Node accounting (e.g. `https://accounting-service.onrender.com`) |
| `ACCOUNTING_KEY` | Both | API key for `X-API-KEY` — استخدم قيمة قوية في الإنتاج |
| `ACCOUNTING_TIMEOUT` | Flask | Optional; default 15s |
| `SECRET_KEY` | Flask | Flask secret |
| `NODE_ENV` | Node | `production` |
| `RATE_LIMIT_WINDOW_MS` | Node | Optional; default 60000 |
| `RATE_LIMIT_MAX_REQUESTS` | Node | Optional; default 60 |

---

## Checklist قبل الإنتاج

- [ ] **لا يوجد أي Insert مباشر في Journal من Flask** عند استخدام Adapter (توثيق Phase 1 يُظهر كل المواضع ❌).
- [ ] **جميع القيود تأتي من Node** عندما `ACCOUNTING_API` + `ACCOUNTING_KEY` مضبوطان.
- [ ] **Audit Log يعمل** في Node (`audit_log` لكل قيد مع `"Created from Flask POS System"`).
- [ ] **Fiscal Year Lock يعمل:** إغلاق سنة في Node → 403 عند إنشاء فاتورة من Flask؛ عدم حفظ الفاتورة ولا إنشاء قيد جديد.
- [ ] **Idempotency:** إرسال نفس الطلب مرتين لا يُنشئ قيدين؛ 409 مع نفس `journal_entry_id`.
- [ ] **Flask لا يسجل فاتورة بدون قيد** عندما Adapter مُفعّل: Rollback عند فشل Node، عدم حفظ الفاتورة.
- [ ] **اتزان القيود:** استعلام اتزان `journal_lines` يرجع 0 صفوف (`test_journal_entries_balanced`).
- [ ] **Rate limit وتحقق Payload:** حد طلبات على `/api/external/*`، ورفض `source_system` غير مسموح.
- [ ] **التقارير متطابقة** بين النظام القديم (إن وُجد) والنظام الجديد بعد التبديل.

**⚠️ لا تشغّل `init-db` تلقائياً عند Deploy.** نفّذ schema/init يدوياً مرة واحدة.

---

## قواعد ممنوعة (Non‑Negotiable)

- ❌ Flask يحسب محاسبة (debit/credit).
- ❌ نظامان يكتبان قيوداً (Flask + Node معاً على نفس الجداول).
- ❌ تعديل مباشر على جداول المحاسبة من Flask.
- ❌ تجاوز قفل السنة المالية.

---

## النتيجة المتوقعة

- نظام محاسبي مستقل (Node)، مدقّق، قابل للتوسع.
- Flask نظام تشغيلي فقط (POS / Sales / Inventory / Payroll).
- إمكانية إضافة Mobile App، ERP، E‑Commerce لاحقاً عبر نفس Node API دون كسر المحاسبة.
