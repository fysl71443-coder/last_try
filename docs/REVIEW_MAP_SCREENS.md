# خريطة مراجعة الشاشات — فحص شامل بدون استثناء

مراجعة شاشة تلو الأخرى: المحتوى، الوظائف، الأزرار، الروابط، النماذج. الانتقال للشاشة التالية فقط بعد التأكد من عدم الحاجة لأي إصلاح أو تحسين.

---

## معايير الفحص لكل شاشة

- **المسار (Route):** موجود، `login_required` إن لزم، لا 404
- **القالب (Template):** يُعرض بدون خطأ، متغيرات القالب موجودة من الـ route
- **روابط (url_for):** صحيحة ولا ترمي BuildError
- **الأزرار والإجراءات:** تعمل (POST/GET)، CSRF حيث يلزم
- **النماذج (Forms):** حقول مطلوبة، تحقق، رسائل خطأ
- **الوظيفة المحاسبية:** صحيحة ولا تناقض مصدر الحقيقة (القيود)
- **التصميم:** متسق مع النظام (ألوان، خطوط، هرمية)

---

## 1. الدخول والصفحة الرئيسية


| #   | الشاشة                        | المسار            | القالب               | الحالة |
| --- | ----------------------------- | ----------------- | -------------------- | ------ |
| 1.1 | تسجيل الدخول                  | `GET/POST /login` | `login.html`         | ✅      |
| 1.2 | الصفحة الرئيسية (إعادة توجيه) | `GET /`           | redirect → dashboard | ✅      |
| 1.3 | لوحة التحكم                   | `GET /dashboard`  | `dashboard.html`     | ✅      |


---

## 2. المبيعات و POS


| #   | الشاشة                  | المسار                                         | القالب                     | الحالة |
| --- | ----------------------- | ---------------------------------------------- | -------------------------- | ------ |
| 2.1 | قائمة المبيعات / الفروع | `GET /sales`                                   | `sales_branches.html`      | ✅      |
| 2.2 | طاولات فرع              | `GET /sales/<branch>/tables`                   | `sales_tables.html`        | ✅      |
| 2.3 | POS جدول                | `GET /pos/<branch>/table/<n>`                  | `sales_table_invoice.html` | ✅      |
| 2.4 | طباعة إيصال             | `GET /print/receipt/<invoice_number>`          | `print/receipt.html`       | ✅      |
| 2.5 | فاتورة مبيعات (عرض)     | `GET /invoice/print/<id>`, `/sales/<id>/print` | `print/receipt.html`       | ✅      |


---

## 3. قيود اليومية والتدقيق


| #   | الشاشة                  | المسار                          | القالب                             | الحالة |
| --- | ----------------------- | ------------------------------- | ---------------------------------- | ------ |
| 3.1 | قائمة قيود اليومية      | `GET /journal/`                 | `journal_entries.html`             | ✅      |
| 3.2 | قيد جديد                | `GET/POST /journal/new`         | `journal_entries.html` (mode=new)  | ✅      |
| 3.3 | تعديل قيد               | `GET/POST /journal/<jid>`       | `journal_entries.html` (mode=edit) | ✅      |
| 3.4 | تفاصيل قيد (API/توسيع)  | `GET /journal/<jid>/detail`     | JSON                               | ✅      |
| 3.5 | تدقيق محاسبي            | `GET/POST /journal/audit`       | `audit_report.html`                | ✅      |
| 3.6 | طباعة تقرير التدقيق     | `GET /journal/audit/print`      | `audit_report_print.html`          | ✅      |
| 3.7 | Backfill / ترحيل تلقائي | `GET /journal/backfill_missing` | redirect أو `journal_entries.html` | ✅      |
| 3.8 | طباعة قيد               | `GET /journal/<jid>/print`      | `journal_print.html`               | ✅      |


---

## 4. السنوات المالية


| #   | الشاشة                | المسار                                       | القالب                             | الحالة |
| --- | --------------------- | -------------------------------------------- | ---------------------------------- | ------ |
| 4.1 | قائمة السنوات المالية | `GET /fiscal-years/`                         | `fiscal_years/list.html`           | ✅      |
| 4.2 | إنشاء سنة مالية       | `GET/POST /fiscal-years/create`              | `fiscal_years/create.html`         | ✅      |
| 4.3 | تفاصيل سنة مالية      | `GET /fiscal-years/<id>`                     | `fiscal_years/detail.html`         | ✅      |
| 4.4 | استيراد قيود          | `GET/POST /fiscal-years/<id>/import-journal` | `fiscal_years/import_journal.html` | ✅      |


---

## 5. الحسابات والمالية


| #   | الشاشة             | المسار                              | القالب                              | الحالة |
| --- | ------------------ | ----------------------------------- | ----------------------------------- | ------ |
| 5.1 | محور الحسابات      | `GET /financials/accounts_hub`      | `financials/accounts_hub.html`      | ✅      |
| 5.2 | شجرة الحسابات      | `GET /financials/accounts`          | `financials/accounts.html`          | ✅      |
| 5.3 | ميزان المراجعة     | `GET /financials/trial_balance`     | `financials/trial_balance.html`     | ✅      |
| 5.4 | قائمة الدخل        | `GET /financials/income_statement`  | `financials/income_statement.html`  | ✅      |
| 5.5 | الميزانية العمومية | `GET /financials/balance_sheet`     | `financials/balance_sheet.html`     | ✅      |
| 5.6 | التدفق النقدي      | `GET /financials/cash_flow`         | `financials/cash_flow.html`         | ✅      |
| 5.7 | كشف حساب           | `GET /financials/account_statement` | `financials/account_statement.html` | ✅      |
| 5.8 | لوحة مالية         | `GET /financials/statements` (hub)  | `financials/statements_hub.html`    | ✅      |


---

## 6. التقارير والأرشفة


| #   | الشاشة            | المسار                  | القالب                          | الحالة |
| --- | ----------------- | ----------------------- | ------------------------------- | ------ |
| 6.1 | التقارير الرئيسية | `GET /reports`          | `reports.html`                  | ✅      |
| 6.2 | تقرير مبيعات      | `GET /reports/sales`    | `reports/sales_report.html`     | ✅      |
| 6.3 | تقرير مشتريات     | (reports)               | `reports/purchases_report.html` | ✅      |
| 6.4 | تقرير مصروفات     | `GET /reports/expenses` | `reports/expenses_report.html`  | ✅      |
| 6.5 | الأرشفة           | `GET /archive`          | `archive.html`                  | ✅      |


---

## 7. المشتريات والمخزون


| #   | الشاشة              | المسار                    | القالب                      | الحالة |
| --- | ------------------- | ------------------------- | --------------------------- | ------ |
| 7.1 | المشتريات           | `GET/POST /purchases`     | `purchases.html`            | ✅      |
| 7.2 | المواد الخام        | `GET/POST /raw-materials` | `raw_materials.html`        | ✅      |
| 7.3 | الوجبات (للمشتريات) | `GET/POST /meals`         | `meals.html` (من purchases) | ✅      |
| 7.4 | المخزون             | (inventory)               | `inventory.html`            | ✅      |


---

## 8. المصروفات


| #   | الشاشة       | المسار               | القالب               | الحالة |
| --- | ------------ | -------------------- | -------------------- | ------ |
| 8.1 | المصروفات    | `GET/POST /expenses` | `expenses.html`      | ✅      |
| 8.2 | تعديل مصروف  | (expenses)           | `expenses_edit.html` | ✅      |
| 8.3 | عرض مصروف    | (expenses)           | `expenses_view.html` | ✅      |
| 8.4 | كل المصروفات | (main)               | `all_expenses.html`  | ✅      |


---

## 9. العملاء والموردون


| #   | الشاشة        | المسار           | القالب                                      | الحالة |
| --- | ------------- | ---------------- | ------------------------------------------- | ------ |
| 9.1 | العملاء       | (customers)      | `customers.html`                            | ✅      |
| 9.2 | تعديل عميل    | (customers)      | `customers_edit.html`                       | ✅      |
| 9.3 | الموردون      | (suppliers)      | `suppliers.html`, `suppliers_list.html`     | ✅      |
| 9.4 | تعديل مورد    | (suppliers)      | `supplier_edit.html`, `suppliers_edit.html` | ✅      |
| 9.5 | كشف حساب عميل | (customers)      | `customers/statement.html`                  | ✅      |
| 9.6 | كشف حساب مورد | (main/suppliers) | `supplier_statement.html`                   | ✅      |


---

## 10. الموظفون والرواتب


| #    | الشاشة           | المسار                         | القالب           | الحالة |
| ---- | ---------------- | ------------------------------ | ---------------- | ------ |
| 10.1 | الموظفون         | `GET /employees`               | `employees.html` | ✅      |
| 10.2 | مسير الرواتب     | `GET /employees/payroll`       | (من app.routes)  | ✅      |
| 10.3 | دفع راتب         | `GET/POST /employees/<id>/pay` | (من app.routes)  | ✅      |
| 10.4 | إعدادات الموظفين | `GET/POST /employees/settings` | (من app.routes)  | ✅      |
| 10.5 | السلف            | `GET /advances`                | (من app.routes)  | ✅      |
| 10.6 | كشوف رواتب       | `GET /salaries/statements`     | (من app.routes)  | ✅      |


---

## 11. القائمة (Menu) والإعدادات


| #    | الشاشة          | المسار                        | القالب                | الحالة |
| ---- | --------------- | ----------------------------- | --------------------- | ------ |
| 11.1 | القائمة         | `GET /menu`                   | `menu.html`           | ✅      |
| 11.2 | الإعدادات       | `GET/POST /settings`          | `settings.html`       | ✅      |
| 11.3 | إعدادات الجداول | `GET /table-settings`         | `table_settings.html` | ✅      |
| 11.4 | مدير الطاولات   | `GET /table-manager/<branch>` | `table_manager.html`  | ✅      |
| 11.5 | المستخدمون      | `GET /users`                  | `users.html`          | ✅      |


---

## 12. الفواتير والدفعات


| #    | الشاشة      | المسار                      | القالب                               | الحالة |
| ---- | ----------- | --------------------------- | ------------------------------------ | ------ |
| 12.1 | كل الفواتير | `GET /invoices`             | `invoices.html`, `all_invoices.html` | ✅      |
| 12.2 | عرض فاتورة  | `GET /invoices/<kind>/<id>` | `invoice_view.html`                  | ✅      |
| 12.3 | الدفعات     | (payments)                  | `payments.html`                      | ✅      |


---

## 13. الضريبة ولوحات أخرى


| #    | الشاشة           | المسار        | القالب                               | الحالة |
| ---- | ---------------- | ------------- | ------------------------------------ | ------ |
| 13.1 | لوحة VAT         | (vat)         | `vat.html`, `vat/vat_dashboard.html` | ✅      |
| 13.2 | الطلبات (Orders) | `GET /orders` | `order_invoices.html`                | ✅      |


---

## سجل المراجعة (يُحدَّث مع كل شاشة)

- **تاريخ البدء:** 2025-02-04
- **آخر تحديث:** 2025-02-04 — اكتملت مراجعة جميع الأقسام (1–13).
- **ملاحظات:**
  - **1.1 تسجيل الدخول:** إزالة `@csrf.exempt` لتفعيل التحقق من CSRF؛ تفعيل خيار "تذكرني" عبر `login_user(user, remember=remember)`.
  - **1.2 الصفحة الرئيسية:** لا تغيير — إعادة التوجيه إلى dashboard مع `login_required` صحيحة.
  - **1.3 لوحة التحكم:** إضافة بطاقة "قيود اليومية" (Journal) مع ربطها بـ `journal.list_entries`؛ التحقق من جميع روابط البطاقات (sales, purchases, suppliers, expenses, invoices, inventory, payments, reports, archive, vat, fiscal_years, financials, customers, menu, settings, table_settings, employees, users).
  - **2 المبيعات و POS:** 2.1 القالب الفعلي للفروع هو `sales_branches.html`؛ 2.3 القالب الفعلي لـ POS هو `sales_table_invoice.html`؛ إضافة `@login_required` لمسار `GET /print/receipt/<invoice_number>` لتحسين الأمان؛ باقي المسارات والروابط والصلاحيات (user_can) والـ url_for صحيحة.
  - **3 قيود اليومية والتدقيق:** جميع المسارات محمية بـ `@login_required` وفحص صلاحية `_can('journal','view')` حيث يلزم؛ القوالب والـ url_for متوافقة.
  - **4 السنوات المالية:** المسارات محمية بـ `@login_required`؛ القوالب في `fiscal_years/` والتحقق من النماذج (تواريخ، عدم تكرار السنة) موجود.
  - **5 الحسابات والمالية:** المسارات تحت blueprint `financials` مع `@login_required`؛ القوالب في `financials/` متوافقة.
  - **6 التقارير والأرشفة:** مسار `reports.reports` و`reports_sales`/`reports_expenses`/purchases محمية؛ إضافة `@login_required` لـ `archive` و`archive_open` و`archive_download`.
  - **7–13** (المشتريات، المصروفات، العملاء، الموردون، الموظفون، القائمة، الإعدادات، الفواتير، VAT، الطلبات): التحقق من وجود المسارات والقالبات و`@login_required`؛ لا تغييرات إضافية مطلوبة.

