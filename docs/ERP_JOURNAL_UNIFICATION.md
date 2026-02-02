# توحيد المحاسبة: JournalEntry/JournalLine كالمصدر الوحيد

## الهدف
ضمان أن جميع البيانات المالية المعروضة في الشاشات مرتبطة بقيود يومية فعلية، ولا يوجد بيان مالي بدون قيد يثبته.

## التغييرات المنفذة

### 1. إلغاء LedgerEntry كمسجل مالي
- تم إبطال دالة `_post_ledger` لتصبح فارغة (no-op)
- جميع العمليات المالية تستخدم الآن `JournalEntry` و `JournalLine` فقط

### 2. دوال إنشاء القيود الجديدة

| الدالة | الوصف | الاستخدام |
|--------|-------|-----------|
| `_create_sale_journal(inv)` | قيد المبيعات (نقدي/آجل) | فواتير المبيعات |
| `_create_receipt_journal(...)` | قيد تحصيل من عميل (مدين صندوق، دائن ذمم مدينة) | السداد اللاحق للعملاء الآجلين |
| `_create_purchase_journal(inv)` | قيد مشتريات | فواتير المشتريات |
| `_create_supplier_payment_journal(...)` | قيد دفعة لمورد (مدين موردون، دائن صندوق) | سداد فواتير المشتريات |
| `_create_expense_journal(inv)` | قيد مصروف | فواتير المصروفات |
| `_create_expense_payment_journal(...)` | قيد دفعة مصروف | سداد فواتير المصروفات |
| `_create_supplier_direct_payment_journal(...)` | قيد دفعة مباشرة لمورد | دفعات الموردين غير المرتبطة بفاتورة |

### 3. الربط مع الفواتير
- `JournalEntry` يحتوي على `invoice_id` و `invoice_type` عند إنشائه من فاتورة
- أنواع الفواتير: `sales`, `purchase`, `expense`, `sales_payment`, `expense_payment`

### 4. المصادر التي تعرض البيانات
- **شاشة الحسابات المتكاملة** (`accounts_hub`): تجلب البيانات من `/api/trial_balance_json` و `/api/account_ledger_json` ← تستخدم `JournalLine` فقط
- **قائمة الدخل، المركز المالي، ميزان المراجعة** (routes/financials): تستخدم `JournalLine` فقط
- **تدفقات نقدية، كشوف حساب**: من `JournalLine`

### 5. التحقق
- وجود فاتورة أو عملية مالية → وجود قيد يثبتها
- وجود قيد → وجود فاتورة أو عملية مرتبطة (عبر `invoice_id` أو `description`)
- لا يُنشأ أي بيان مالي بدون قيد

## الملفات المعدّلة
- `app/routes.py`: دوال القيود الجديدة، إبطال _post_ledger
- `routes/sales.py`: استخدام _create_sale_journal و _create_receipt_journal
- `routes/purchases.py`: استخدام _create_purchase_journal و _create_supplier_payment_journal
- `routes/expenses.py`: استخدام _create_expense_journal و _create_expense_payment_journal
- `routes/payments.py`: استخدام _create_supplier_direct_payment_journal

## ملاحظات
- جدول `ledger_entries` ما زال موجوداً للتوافق مع البيانات القديمة ولكنه لم يعد يُحدَّث
- جميع العمليات الجديدة تُسجَّل في `journal_entries` و `journal_lines` فقط
