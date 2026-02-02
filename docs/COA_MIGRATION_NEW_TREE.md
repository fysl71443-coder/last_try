# هجرة شجرة الحسابات المعتمدة

## الملخص

تم استبدال شجرة الحسابات الحالية بالشجرة المتكاملة المعتمدة (من `data/coa_new_tree`) دون حذف أي حساب ودون فقدان بيانات.

## ما تم تنفيذه

1. **`data/coa_new_tree.py`**  
   - تعريف الشجرة الجديدة (`NEW_COA_TREE`)، الحسابات الورقية فقط (`LEAF_CODES`)، وخريطة القديم → الجديد (`OLD_TO_NEW_MAP`).
   - دوال `build_coa_dict()` و `get_short_to_numeric()` لدعم `CHART_OF_ACCOUNTS` و `SHORT_TO_NUMERIC` في التطبيق.

2. **سكربت الهجرة**
   - **`scripts/coa_migrate_standalone.py`** (موصى به): اتصال مباشر بقاعدة البيانات (افتراضيًا SQLite المحلي `instance/local.db`). لا يحمّل تطبيق Flask.
   - **`scripts/coa_migrate_to_new_tree.py`**: يعمل ضمن سياق Flask؛ قد يكون أبطأ بسبب تحميل التطبيق بالكامل.

3. **تحديث التطبيق**
   - `app/routes.py`: استبدال `CHART_OF_ACCOUNTS` و `SHORT_TO_NUMERIC` بالمصدر الجديد، وتحديث كل المراجع (دفع رواتب، مبيعات، مشتريات، مصروفات، تقارير مالية، إلخ).
   - `routes/financials.py`, `routes/journal.py`, `routes/vat.py`, `routes/payments.py`, `routes/reports.py`: استبدال رموز الحسابات القديمة بالجديدة.

## تشغيل الهجرة

### SQLite المحلي (الافتراضي)

```bash
python scripts/coa_migrate_standalone.py
```

يستخدم `instance/local.db` ما لم يتم ضبط `COA_MIGRATE_USE_ENV_DB`.

### استخدام قاعدة البيانات من `DATABASE_URL` (مثل PostgreSQL)

```bash
set COA_MIGRATE_USE_ENV_DB=1
set DATABASE_URL=postgresql://...
python scripts/coa_migrate_standalone.py
```

## قواعد الهجرة

- **لا يُحذف أي حساب.** الحسابات القديمة تبقى في الجدول.
- حركات **journal_lines** و **ledger_entries** المرتبطة بحسابات قديمة تُنقل إلى الحساب الجديد حسب `OLD_TO_NEW_MAP`.
- الحسابات الجديدة من الشجرة تُضاف فقط إن لم يكن الرمز موجودًا.
- الحسابات التجميعية (مثل 0001, 1100) لا تُستخدم في القيود؛ فقط الحسابات الورقية.

## فروع مبيعات ومصروفات مستقلة (China Town / Place India)

الشجرة تدعم حسابات مبيعات ومصروفات مستقلة لكل فرع:

| الفرع | مبيعات | مصروفات |
|-------|--------|---------|
| China Town | 4111 مبيعات China Town | 5111 مصروفات China Town |
| Place India | 4112 مبيعات Place India | 5112 مصروفات Place India |

- **اختصارات:** `REV_CT` → 4111، `REV_PI` → 4112، `EXP_CT` → 5111، `EXP_PI` → 5112.
- **القيود:** مبيعات الفواتير تُمرَّر حسب `branch` إلى 4111 أو 4112؛ إنشاء قيود المبيعات في الـ journal يستخدم نفس الرموز.
- **التقارير:** `revenue_by_branch` و `expense_by_branch` في لوحة القوائم المالية تعتمد على 4111/4112 و 5111/5112.
- **دفعة المعاملات (batch):** يمكن تمرير `branch` (`china_town` / `place_india`) في كل صف؛ تُستخدم 5111 أو 5112 للمصروفات ومورد دائن (غير مخزون) عند وجود الفرع.

## الربط بالسداد (كما في المواصفات)

| عملية     | الحساب المستخدم                    |
|-----------|-------------------------------------|
| سداد غرامة | مصروف غرامات (5240)                |
| سداد كهرباء | مصروف كهرباء (5120)               |
| سداد راتب | رواتب مستحقة (2121) → بنك (112x)  |
| سداد VAT | VAT مستحقة (2141) → بنك (112x)    |

## متابعة (مراجع إضافية)

تم تطبيق المراجع التالية في **متابعة** الهجرة:

- **`models.py`**: `to_journal_entries` في `SalesInvoice`, `PurchaseInvoice`, `ExpenseInvoice`, `Salary` — استخدام الرموز الجديدة (1111, 1121, 1141, 1161, 1171, 2111, 2121, 2141, 4110, 4120, 5210, 5230, …).
- **`routes/financials.py`**: `hide_codes`, `_resolve_method`, `_resolve_expense`, دفعة المعاملات (batch)، ورموز الحسابات في النماذج/التصدير.
- **`routes/payments.py`**: الحساب الافتراضي للمدينين (`1020` → `1141`).
- **`app/routes.py`**: مرشحات القوائم المالية (VAT، إيرادات)، `pm_code` في الـ backfill، سيناريو `cash_deposit`.
- **`routes/journal.py`**: `_acc_by_code` للمشتريات/المصروفات (1171, 2111).

## ملاحظات

- بعد الهجرة، إعادة تشغيل خادم التطبيق.
- في بيئة الإنتاج مع PostgreSQL، استخدم `COA_MIGRATE_USE_ENV_DB=1` و `DATABASE_URL` المناسبة ثم شغّل `coa_migrate_standalone.py`.
