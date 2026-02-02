# ملخص تكامل المحاسبة — Flask ↔ Node.js

## ما تم تنفيذه

### المرحلة 1 — التحليل
- **`docs/ACCOUNTING_INTEGRATION_PHASE1_ANALYSIS.md`**: توثيق كل الأماكن التي تنشئ `JournalEntry` / `JournalLine` / `LedgerEntry` أو تحسب Debit/Credit، مع وضع ❌ عليها.

### المرحلة 2 — عقد API
- **`docs/ACCOUNTING_INTEGRATION_API_CONTRACT.md`**: تعريف `POST /api/external/*` (sales-invoice, purchase-invoice, expense-invoice, payment, salary-payment, salary-accrual)، الـ Request/Response، X-API-KEY، Idempotency، و‌403 عند إغلاق السنة المالية.

### المرحلة 3 — خدمة Node.js
- **`accounting-service/`**:
  - Express، pg، مسارات `/api/external/*`.
  - **Fiscal years:** `fiscal_years`، `assertFiscalYearOpen` → 403 إذا السنة مغلقة.
  - **Journal engine:** إنشاء قيود متوازنة، VAT، حسابات افتراضية.
  - **Middleware:** التحقق من `X-API-KEY`.
  - **Idempotency:** `idempotency_keys`، إرجاع 409 مع نفس `journal_entry_id` عند التكرار.
  - **Audit:** `audit_log` لكل قيد مع `"Created from Flask POS System"`.

### المرحلة 4 — طبقة التكيّف في Flask
- **`services/accounting_adapter.py`**: دوال `post_sales_invoice`, `post_purchase_invoice`, `post_expense_invoice`, `post_payment`, `post_salary_payment`, `post_salary_accrual`. استثناءات `FiscalYearClosedError`, `InvalidApiKeyError`, `AccountingUnavailableError`, `BadRequestError`.
- **`models.SalesInvoice`**: إضافة `journal_entry_id`.
- **`app/routes.api_sales_checkout`**: عند ضبط `ACCOUNTING_API` + `ACCOUNTING_KEY` يُستدعى الـ adapter بدل `_post_ledger` / `_create_sale_journal`. عند فشل Node → rollback و‌503/403/400. Flask لا يحفظ فاتورة بدون قيد من Node.
- **`migrations/versions/add_journal_entry_id_to_invoices.py`**: إضافة العمود `journal_entry_id` لجدول `sales_invoices`.

### المرحلة 5–6 — الاختبارات
- **`tests/test_accounting_integration.py`**: اختبارات تكامل (adapter configured، sales-invoice success، idempotency). توثيق سيناريوهات الفشل (Invalid key، Node down، Fiscal year closed، Payload ناقص).

### المرحلة 7–8 — النشر والتحقق
- **`docs/ACCOUNTING_INTEGRATION_RENDER_AND_CHECKLIST.md`**: إعداد Render (Flask + Node + PostgreSQL)، متغيرات البيئة، Checklist نهائي قبل الإنتاج، والقواعد الممنوعة.

---

## تشغيل سريع

1. **قاعدة بيانات المحاسبة (Node):**
   ```bash
   psql $DATABASE_URL -f accounting-service/src/schema.sql
   # Optional: INSERT fiscal_years لل سنة الحالية
   ```

2. **تشغيل Node:**
   ```bash
   cd accounting-service && npm install && npm start
   ```

3. **تشغيل Flask:**
   ```bash
   export ACCOUNTING_API=http://localhost:3000
   export ACCOUNTING_KEY=your-secret-key
   python -m app  # أو gunicorn wsgi:application
   ```

4. **اختبار التكامل:**
   ```bash
   export ACCOUNTING_API=http://localhost:3000 ACCOUNTING_KEY=your-secret-key
   pytest tests/test_accounting_integration.py -v
   ```

---

## الخطوات التالية (اختياري)

- استبدال بقية المسارات المحاسبية (مشتريات، مصروفات، رواتب، دفعات) باستدعاءات الـ adapter بدل `_post_ledger` و‌`_create_*_journal`، وفقاً لـ Phase 1.
- إضافة `journal_entry_id` إلى `purchase_invoices` و‌`expense_invoices` عند التكامل.
- إغلاق السنة المالية في Node (مثلاً `UPDATE fiscal_years SET closed = TRUE WHERE year = 2025`) واختبار 403 من Flask.
