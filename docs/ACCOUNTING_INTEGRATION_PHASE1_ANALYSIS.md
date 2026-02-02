# المرحلة 1: تحليل النظام المحاسبي في Flask

## الهدف
تحديد **جميع** الأماكن التي تنشئ `JournalEntry`، `JournalLine`، `LedgerEntry`، أو تحسب `Debit`/`Credit`، لاستبدالها لاحقاً باستدعاءات REST إلى نظام المحاسبة Node.js.

---

## 1. `models.py` — نماذج قاعدة البيانات

### ❌ دوال تحسب قيوداً (Debit/Credit) — يجب إزالتها أو تحييدها

| الموقع | النموذج | الدالة | الوصف |
|--------|---------|--------|--------|
| L89–117 | `SalesInvoice` | `to_journal_entries()` | ❌ يحسب صفوف قيود المبيعات: cash/AR، revenue، VAT |
| L282–294 | `PurchaseInvoice` | `to_journal_entries()` | ❌ يحسب صفوف قيود المشتريات: inventory، VAT input، AP |
| L334–380 | `ExpenseInvoice` | `to_journal_entries()` | ❌ يحسب صفوف قيود المصروفات + دفع فوري |
| L503–510 | `Salary` | `to_journal_entries()` | ❌ يحسب صفوف قيود الرواتب |

**ملاحظة:** Flask لا يجب أن يعرف `debit`/`credit`. هذه الدوال تُستبدل بطلب إلى Node (مثل `POST /api/external/sales-invoice`) ويعيد Node `journal_entry_id` فقط.

---

## 2. `app/routes.py` — المسارات والمنطق المحاسبي

### ❌ دوال مساعدة محاسبية (تُستبدل بـ Adapter أو إزالة)

| الدالة | الموقع التقريبي | الوصف |
|--------|------------------|--------|
| `_account(code, name, kind)` | ~L12589 | إنشاء/جلب حساب من `Account` |
| `_pm_account(pm)` | ~L12600 | حساب النقد/البنك حسب طريقة الدفع |
| `_resolve_account(code, name, kind)` | ~L12957 | تحويل رموز مختصرة (AP, AR, VAT_IN...) إلى رموز رقمية |
| `_post_ledger(date, acc_code, acc_name, acc_type, debit_amt, credit_amt, ref)` | ~L12744 | ❌ إنشاء `LedgerEntry` مباشرة |
| `_create_purchase_journal(inv)` | ~L12694 | ❌ إنشاء `JournalEntry` + `JournalLine` للمشتريات |
| `_expense_account_by_code(code)` | ~L12759 | تحديد حساب مصروف حسب رمز |
| `_expense_account_for(desc)` | ~L12775 | تحديد حساب مصروف حسب الوصف |

### ❌ ثوابت محاسبية

- `CHART_OF_ACCOUNTS` (~L12793+): خريطة حسابات. ❌ تنتقل بالكامل إلى Node.
- `SHORT_TO_NUMERIC`: رموز مختصرة → رقمية. ❌ تنتقل إلى Node.

### ❌ مسارات تستخدم `to_journal_entries` أو تزامن محاسبي

| المسار | الدالة | الوصف |
|--------|--------|--------|
| `POST /api/sync/pos` | `api_sync_pos` | L802–836: يمر على `SalesInvoice` ويستدعي `s.to_journal_entries()` ثم `api_transactions_post` — ❌ |
| `POST /api/sync/payroll` | `api_sync_payroll` | L844–877: نفس النمط مع `Salary.to_journal_entries()` — ❌ |

### ❌ فواتير المشتريات

| الموقع | الوصف |
|--------|--------|
| L1467–1482 | `_post_ledger` للمشتريات: debit (مخزون/COGS)، VAT_IN، AP |
| L1483–1515 | `_post_ledger` لدفع المشتريات (AP، نقدية، عمولات بنكية) |
| L1517–1519 | `_create_purchase_journal(inv)` — ❌ |

### ❌ فواتير المصروفات

| الموقع | الوصف |
|--------|--------|
| L2976–3005 | `_post_ledger` للمصروفات (حساب مصروف، VAT_IN، AP) ودفع المصروفات |

### ❌ المبيعات (Sales) — Checkout ودفع

| المسار/الدالة | الموقع | الوصف |
|---------------|--------|--------|
| `api_draft_checkout` | L7534–7715 | إنشاء `SalesInvoice` + `SalesInvoiceItem` ثم ❌ `_post_ledger` (AR، revenue، VAT، وإذا مدفوع: دفع نقدي) |
| `api_sales_checkout` | L7728–7785+ | نفس النمط: فاتورة + ❌ `_post_ledger` للمبيعات والدفع |
| `api_invoice_confirm_print` | L7839–7975+ | تحديث حالة الدفع + ❌ `_post_ledger` (تحصيل AR، نقدية) |
| `register_payment_ajax` | L8131–8235 | إنشاء `Payment` + ❌ `JournalEntry` + `JournalLine` (تحصيل: مدين نقدية، دائن AR) |

### ❌ الرواتب (Salaries)

| الموقع | الوصف |
|--------|--------|
| L3747–3763 | دفع رواتب: ❌ `JournalEntry` + `JournalLine` (مستحقات رواتب، نقدية) + `_post_ledger` |
| L3803–3813 | سلف موظفين: ❌ `JournalEntry` + `JournalLine` + `_post_ledger` |
| L4503–4529 | دفع راتب فردي: `_post_ledger` (سلف، مستحقات، نقدية) |
| L4514–4521 | ❌ `JournalEntry` + `JournalLine` لدفع الراتب |
| L5212–5225 | استحقاق راتب: ❌ `JournalEntry` + `JournalLine` + `_post_ledger` |
| L5342–5354 | نفس الاستحقاق في مسار آخر |
| L9024–9036 | استحقاق راتب في سياق آخر |

### ❌ حذف فواتير (عكس القيود)

| الموقع | الوصف |
|--------|--------|
| L3122–3130 | حذف `JournalEntry`/`JournalLine`/`LedgerEntry` المرتبطة بفاتورة مبيعات |
| L3413–3476 | حذف قيود عند حذف فواتير (مبيعات/مشتريات/مصروفات) |

### ❌ فتح أرصدة (Opening Balances)

| المسار | الموقع | الوصف |
|--------|--------|--------|
| `POST /api/opening-balances/import` (ضمن financials) | L621–722 ( routes / app ) | ❌ إنشاء `JournalEntry` + `JournalLine` لأرصدة الافتتاح |

### ❌ Backfill / إنشاء Ledger من الفواتير

| المسار/الدالة | الموقع | الوصف |
|---------------|--------|--------|
| `refresh_chart_from_db` / backfill | L10816–10886 | ❌ إنشاء `LedgerEntry` مباشرة من `SalesInvoice`، `PurchaseInvoice`، `ExpenseInvoice` |

### ❌ إنشاء قيود مصروفات (Expense) داخل routes

| الموقع | الوصف |
|--------|--------|
| L12720–12741 | دالة تُنشئ `JournalEntry` + `JournalLine` لمصروف (5100، 6200، 2110) |

### ❌ استعلامات محاسبية (قراءة فقط — تبقى في التقارير أو تنتقل لـ Node)

- تجميع `LedgerEntry` (debit/credit) لميزان المراجعة، قائمة الدخل، إلخ. في `routes/financials.py` و `app/routes.py`.  
- يمكن لاحقاً استبدالها بـ GET من Node أو الاحتفاظ بها كقراءة فقط بعد أن يصبح Node مصدر الحقيقة.

---

## 3. `routes/journal.py` — القيود اليومية

| الدالة/المسار | الوصف |
|---------------|--------|
| `create_missing_journal_entries()` | L80–224+: ❌ إنشاء `JournalEntry` + `JournalLine` لجميع المبيعات/المشتريات/المصروفات الناقصة |
| `create_missing_journal_entries_for(kind)` | L305+: ❌ نفس الفكرة حسب النوع |
| `post_entry(jid)` | L1221+: عند ترحيل القيد ❌ إنشاء `LedgerEntry` من `JournalLine` |
| استخدام `api_transactions_post` من `api_sync_*` | — | ❌ يُغذي القيود من Flask |

---

## 4. `routes/financials.py`

| الدالة/المسار | الوصف |
|---------------|--------|
| `_normalize_short_aliases` | دمج حسابات، تحديث `JournalLine`/`LedgerEntry` — ❌ منطق يخص المحاسبة |
| Backfill / حذف قيود | إدارة قيود وحسابات — ❌ |
| تقارير مبنية على `LedgerEntry` (trial balance، إلخ) | قراءة — يمكن نقلها لـ Node لاحقاً |

---

## 5. `app/emp_pay.py` — دفع الرواتب

| الدالة | الوصف |
|--------|--------|
| `_post_ledger_safe` | L35–40: ❌ يستدعي `_post_ledger` |
| `_pm_account` | L42–46: جلب حساب نقدية/بنك |
| `api_employee_pay_salary` | إنشاء `Payment` ثم يستخدم `_post_ledger_safe` — ❌ |

---

## 6. ملفات خارج التطبيق الرئيسي

| الملف | الوصف |
|-------|--------|
| `accounting_fixes.py` | ❌ إنشاء `JournalEntry`/`JournalLine` وتعديل حسابات |
| `quick_accounting_fix.py` | ❌ إنشاء قيود مبيعات ودفعات |
| `update_payment_function.py` | ❌ تعديل منطق تسجيل الدفعات وقيود التحصيل |
| `scripts/seed_coa_and_sync_pos.py` | ❌ يستدعي `create_missing_journal_entries_for('sales')` |

---

## 7. ملخص القواعد الممنوعة بعد التكامل

- ❌ Flask ينشئ أو يعدّل `JournalEntry` أو `JournalLine` أو `LedgerEntry`.
- ❌ Flask يحسب `debit`/`credit` أو يختار حسابات المحاسبة.
- ❌ أي استدعاء لـ `_post_ledger` أو `to_journal_entries` في المسار التشغيلي (مبيعات، مشتريات، مصروفات، رواتب).

---

## 8. ما يبقى في Flask (تشغيلي فقط)

- إنشاء/تحديث/حذف: `SalesInvoice`, `SalesInvoiceItem`, `PurchaseInvoice`, `ExpenseInvoice`, `Salary`, `Payment`, `Employee`, إلخ.
- حساب **مبالغ تشغيلية** فقط: `subtotal`, `discount`, `vat`, `total` (للعرض والطباعة).
- الاحتفاظ بـ `journal_entry_id` (أو مرجع مماثل) لكل فاتورة/دفعة بعد استلامه من Node.
- استدعاء REST فقط إلى Node لإنشاء القيود واستعلام التقارير عند الحاجة.

---

**المرحلة التالية:** تصميم عقد API (Phase 2) ثم تنفيذ طبقة التكامل في Node.js وتبسيط Flask إلى نظام تشغيلي + Adapter فقط.
