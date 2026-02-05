# مصفوفة سلامة الشاشات (Screen Integrity Matrix)

مرجع سريع: الشاشة، المسار، القالب، وتأثيرها على القيود (نعم/لا).

| Screen | Route | Template | Journal Impact |
|--------|--------|----------|----------------|
| **1. الدخول والرئيسية** |
| تسجيل الدخول | `GET/POST /login` | `login.html` | No |
| الصفحة الرئيسية | `GET /` | redirect → dashboard | No |
| لوحة التحكم | `GET /dashboard` | `dashboard.html` | No |
| **2. المبيعات و POS** |
| قائمة الفروع | `GET /sales` | `sales_branches.html` | No |
| طاولات فرع | `GET /sales/<branch>/tables` | `sales_tables.html` | No |
| POS جدول | `GET /pos/<branch>/table/<n>` | `sales_table_invoice.html` | No |
| طباعة إيصال | `GET /print/receipt/<invoice_number>` | `print/receipt.html` | Read (من قيد مرتبط) |
| فاتورة مبيعات (عرض) | `GET /invoice/print/<id>`, `/sales/<id>/print` | `print/receipt.html` | Read (من قيد مرتبط) |
| **3. قيود اليومية والتدقيق** |
| قائمة قيود اليومية | `GET /journal/` | `journal_entries.html` | Read |
| قيد جديد | `GET/POST /journal/new` | `journal_entries.html` | **Yes** (إنشاء) |
| تعديل قيد | `GET/POST /journal/<jid>` | `journal_entries.html` | **Yes** (تعديل) |
| تفاصيل قيد | `GET /journal/<jid>/detail` | JSON | Read |
| تدقيق محاسبي | `GET/POST /journal/audit` | `audit_report.html` | Read |
| طباعة تقرير التدقيق | `GET /journal/audit/print` | `audit_report_print.html` | Read |
| Backfill | `GET /journal/backfill_missing` | `journal_entries.html` | **Yes** (إنشاء قيود) |
| طباعة قيد | `GET /journal/<jid>/print` | `journal_print.html` | Read |
| **4. السنوات المالية** |
| قائمة السنوات المالية | `GET /fiscal-years/` | `fiscal_years/list.html` | No |
| إنشاء سنة مالية | `GET/POST /fiscal-years/create` | `fiscal_years/create.html` | No |
| تفاصيل سنة مالية | `GET /fiscal-years/<id>` | `fiscal_years/detail.html` | No |
| استيراد قيود | `GET/POST /fiscal-years/<id>/import-journal` | `fiscal_years/import_journal.html` | **Yes** (عند التنفيذ) |
| **5. الحسابات والمالية** |
| محور الحسابات | `GET /financials/accounts_hub` | `financials/accounts_hub.html` | No |
| شجرة الحسابات | `GET /financials/accounts` | `financials/accounts.html` | Read (أرصدة من قيود) |
| ميزان المراجعة | `GET /financials/trial_balance` | `financials/trial_balance.html` | Read |
| قائمة الدخل | `GET /financials/income_statement` | `financials/income_statement.html` | Read |
| الميزانية العمومية | `GET /financials/balance_sheet` | `financials/balance_sheet.html` | Read |
| التدفق النقدي | `GET /financials/cash_flow` | `financials/cash_flow.html` | Read |
| كشف حساب | `GET /financials/account_statement` | `financials/account_statement.html` | Read |
| **6. التقارير والأرشفة** |
| التقارير الرئيسية | `GET /reports` | `reports.html` | No |
| تقرير مبيعات/مشتريات/مصروفات | `GET /reports/sales` إلخ | `reports/*.html` | Read |
| الأرشفة | `GET /archive` | `archive.html` | Read |
| تحميل أرشفة | `GET /archive/download` | — | Read (فواتير مرتبطة بقيود فقط) |
| **7. المشتريات والمخزون** |
| المشتريات | `GET/POST /purchases` | `purchases.html` | **Yes** (فاتورة → قيد) |
| المواد الخام / الوجبات | `GET/POST /raw-materials`, `/meals` | `raw_materials.html`, `meals.html` | No |
| المخزون | (inventory) | `inventory.html` | No |
| **8. المصروفات** |
| المصروفات | `GET/POST /expenses` | `expenses.html` | **Yes** (فاتورة → قيد) |
| تعديل/عرض مصروف | (expenses) | `expenses_edit.html`, `expenses_view.html` | Read/Yes |
| **9. العملاء والموردون** |
| العملاء / الموردون | (customers), (suppliers) | `customers.html`, `suppliers.html` | No |
| كشف حساب عميل/مورد | (customers), (suppliers) | `*_statement.html` | Read |
| **10. الموظفون والرواتب** |
| الموظفون / مسير الرواتب | `GET /employees`, `/employees/payroll` | `employees.html` إلخ | **Yes** (رواتب → قيود) |
| **11. القائمة والإعدادات** |
| القائمة / الإعدادات / الجداول / المستخدمون | `GET /menu`, `/settings` إلخ | `menu.html`, `settings.html` إلخ | No |
| **12. الفواتير والدفعات** |
| كل الفواتير / عرض فاتورة | `GET /invoices`, `/invoices/<kind>/<id>` | `invoices.html`, `invoice_view.html` | Read |
| الدفعات | (payments) | `payments.html` | **Yes** (دفعة → قيد) |
| **13. الضريبة والطلبات** |
| لوحة VAT | (vat) | `vat/vat_dashboard.html` | Read |
| الطلبات | `GET /orders` | `order_invoices.html` | No |

---

**ملاحظة:** أي شاشة ذات **Journal Impact = Yes** يجب أن تمر عبر حارس السنة المالية (راجع `docs/FINANCIAL_YEAR_GUARD.md`).
