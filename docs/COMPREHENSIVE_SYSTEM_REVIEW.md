# مراجعة شاملة للنظام — China Town / Place India

**تاريخ المراجعة:** 2026-02-03  
**النطاق:** البنية، المحاسبة، الأمان، الأداء، النشر، الاختبارات، والتوصيات.

---

## ١. الملخص التنفيذي

| البند | الحالة |
|--------|--------|
| **نوع النظام** | تطبيق ويب محاسبي + نقطة بيع (POS) لمطعمين |
| **الإطار** | Flask (Python) |
| **قاعدة البيانات** | SQLite (تطوير) / PostgreSQL (إنتاج — Render) |
| **المصدر الوحيد للحقيقة المالية** | قيود اليومية المنشورة (`journal_entries` + `journal_lines`) |
| **الأمان** | Flask-Login، bcrypt، CSRF، صلاحيات حسب الشاشة |
| **الاختبارات** | E2E smoke، pytest (تدفقات محاسبية، رواتب، مصروفات، عمليات سريعة) |
| **النشر** | Render مع دعم ENV/DATABASE_URL وضمان أعمدة customers على PostgreSQL عند البدء |

النظام **متسق محاسبياً** ومُوثَّق جيداً؛ التوصيات التالية تركز على صيانة مستمرة وتحسينات اختيارية.

---

## ٢. البنية والهيكل

### ٢.١ نقطة الدخول

- **`wsgi.py`** → `application` (Gunicorn على Render).
- **`app/__init__.py`** → `create_app()` يُنشئ التطبيق، يسجّل الـ Blueprints، ويشغّل ضمانات بدء التشغيل (إنشاء الجداول، أعمدة إضافية لـ SQLite/PostgreSQL مثل `customers`).
- **`app.py`** (في الجذر): monolith قديم ما زال يحتوي مسارات ومُنشئ فواتير؛ يُستخدم جزئياً مع انتقال تدريجي إلى `app/` و `routes/`.

### ٢.٢ Blueprints المسجّلة

| Blueprint | المصدر | الوظيفة الرئيسية |
|-----------|--------|-------------------|
| **main** | `app.routes` | تسجيل الدخول، لوحة التحكم، الموظفون/الرواتب، القائمة، المستخدمون، الإعدادات، الفواتير، POS، الطاولات |
| **vat** | `app.routes` | لوحة ضريبة القيمة المضافة والطباعة |
| **journal** | `routes.journal` | قيود اليومية (عرض، إنشاء، ترحيل، عكس، حذف مع الربط بالفاتورة) |
| **financials** | `routes.financials` | الحسابات، ميزان المراجعة، قائمة الدخل، الميزانية، كشف الحساب، التدفق النقدي، العمليات السريعة، backfill القيود |
| **expenses** | `routes.expenses` | المصروفات (إنشاء، قائمة، ربط قيود) |
| **purchases** | `routes.purchases` | فواتير المشتريات (إنشاء، تحديث إجماليات من الأصناف) |
| **suppliers** | `routes.suppliers` | الموردون وكشف المورد |
| **customers** | `routes.customers` | العملاء (نقدي/آجل)، كشف العميل |
| **payments** | `routes.payments` | المدفوعات (قائمة موحدة: مشتريات/مصروفات/مبيعات)، تسجيل دفعات، إجماليات من أصناف الفواتير عند الصفر |
| **inventory** | `routes.inventory` | المخزون والتقارير |
| **reports** | `routes.reports` | تقارير المبيعات/المشتريات/المصروفات، طباعة، تصدير |
| **sales** | `routes.sales` | المبيعات، الفواتير، POS |

جميع المسارات الحساسة محمية بـ `@login_required` (أكثر من 120 موضعاً في `routes/`).

### ٢.٣ الإعداد (config.py)

- **ENV:** `development` (افتراضي) → SQLite في `instance/accounting_app.db`؛ `production` → PostgreSQL من `DATABASE_URL` (مع تصحيح `postgres://` → `postgresql://`).
- **Cache:** Redis عند `REDIS_URL`، وإلا SimpleCache محلياً.
- **الجلسات:** SameSite، Secure حسب البيئة (متوافق مع Render).
- **Babel:** locale افتراضي عربي، دعم en/ar.

---

## ٣. قاعدة البيانات والنماذج

### ٣.١ الجداول الرئيسية (models.py)

- **مصادقة:** `users`, `user_permissions`
- **مبيعات:** `sales_invoices`, `sales_invoice_items`
- **مشتريات:** `purchase_invoices`, `purchase_invoice_items` (مع `get_effective_totals()` عند إجمالي رأس صفري)
- **مصروفات:** `expense_invoices`, `expense_invoice_items`
- **عملاء/موردون:** `customers` (customer_type, discount_percent, active, created_at), `suppliers`
- **محاسبة:** `accounts`, `account_usage_map`, `journal_entries`, `journal_lines`, `journal_audit`, `ledger_entries`
- **مدفوعات:** `payments`
- **رواتب:** `employees`, `salaries`, `department_rates`, `employee_hours`, `employee_salary_defaults`
- **قائمة ووجبات:** `meals`, `meal_ingredients`, `menu_categories`, `menu_items`, `raw_materials`
- **طاولات وأوامر:** `tables`, `table_settings`, `table_sections`, `draft_orders`, `draft_order_items`
- **إعدادات:** `settings`

### ٣.٢ الهجرات (Alembic)

- مسار هجرات واضح (من initial حتى perf_idx_01، مع دمج الرؤوس حيث لزم).
- هجرة أعمدة العملاء (`customer_type`, `discount_percent`, `active`, `created_at`) موجودة؛ على Render يُضاف ضمان في `app/__init__.py` لإضافة هذه الأعمدة عند البدء إذا لم تُنفَّذ الهجرة (ADD COLUMN IF NOT EXISTS لـ PostgreSQL).

---

## ٤. المحاسبة والقواعد الثابتة

- **مصدر الحقيقة:** القيود المنشورة فقط (`status='posted'`). ميزان المراجعة، قائمة الدخل، الميزانية، كشف الحساب، التدفق النقدي تُبنى من `journal_lines` + `journal_entries`.
- **ربط المعاملات بالقيود:** كل فاتورة/دفعة/عملية مالية تُنتج قيداً مرتبطاً (`invoice_id` + `invoice_type` أو `salary_id`). حذف القيد يحذف الفاتورة/العملية (والعكس حسب السياسة في `docs/IMMUTABLE_ACCOUNTING_RULES.md`).
- **القيود المنشورة:** لا تُعدَّل ولا تُحذف مباشرة؛ يُسمح بعكس القيد فقط.
- **فواتير المشتريات بإجمالي صفري:** استخدام `get_effective_totals()` من الأصناف عند إنشاء القيود وعند العرض (صفحة المدفوعات)؛ سكربت `fix_purchase_journal_zero_amounts.py` لتصحيح القيود القديمة.

---

## ٥. الأداء والتحسينات المُنفَّذة

- **فهارس:** فهارس على `journal_entries (status, date)`، `journal_lines`، `sales_invoices`، `purchase_invoices`، `payments` (هجرات منفصلة).
- **ترقيم الصفحات:** كشف الحساب، قائمة القيود، التدفق النقدي (مع زر طباعة الكل).
- **تخزين مؤقت:** ميزان المراجعة وقائمة الدخل (مفتاح حسب التاريخ/الفرع، TTL 5 دقائق).
- **تقليل N+1:** `selectinload` لـ JournalEntry.lines، PurchaseInvoice.items، ExpenseInvoice.items في التقارير وقائمة القيود.
- **عرض الفواتير الصفرية:** إجماليات من جدول الأصناف عند كون رأس الفاتورة صفراً (المدفوعات والقيود).

راجع `docs/PERFORMANCE_AND_QUERY_OPTIMIZATION.md` لمزيد من التوصيات (مثل Materialized View اختيارية).

---

## ٦. الأمان

- **المصادقة:** Flask-Login، كلمات مرور مشفرة (bcrypt).
- **CSRF:** مفعّل مع استثناءات لبعض واجهات API (مثل إنشاء عميل، عمليات دفع معينة).
- **الصلاحيات:** نموذج صلاحيات حسب الشاشة (dashboard، sales، purchases، journal، إلخ) مع دعم admin وتطوير (السماح للمستخدم المصادق افتراضياً في بيئة التطوير).
- **الجلسات:** إعدادات آمنة للكوكيز (SameSite، Secure عند النشر).
- **أمان الإنتاج:** تأكد من ضبط `SECRET_KEY` و `ENV=production` و `DATABASE_URL` على Render؛ عدم كشف مفاتيح أو بيانات حساسة في المستودع.

---

## ٧. النشر (Render)

- **البيئة:** `ENV=production`، `DATABASE_URL` (PostgreSQL).
- **التشغيل:** سكربتات البداية تشغّل `flask db upgrade` (أو run_migrations.py) ثم Gunicorn؛ في حال فشل الهجرة يستمر التشغيل مع رسالة تحذير.
- **ضمان أعمدة العملاء:** عند البدء، إن كان المحرك PostgreSQL يتم تنفيذ `ALTER TABLE customers ADD COLUMN IF NOT EXISTS` للأعمدة المطلوبة لتفادي خطأ `customer_type does not exist`.
- **التوثيق:** `docs/DEPLOY_RENDER_POSTGRES_WITHOUT_DATA_LOSS.md`.

---

## ٨. الاختبارات

- **E2E Smoke (`tools/e2e_smoke.py`):** فحص الصفحات الرئيسية، التقارير، الطباعة، واجهات JSON، وعمليات POST أساسية (مع ملاحظة أن POST بدون CSRF يُرفض بشكل صحيح).
- **Pytest (`tests/`):** مسارات أساسية، تدفق مشتريات ومدفوعات، رواتب، مصروفات وقيود، تسوية استحقاقات، إيداع بنكي سريع. اختبار التكامل مع خدمة Node.js محاسبة يُتخطى عند عدم ضبط المتغيرات.
- **التوصية:** اختبار يدوي واحد بعد كل نشر (مثلاً إضافة مصروف من الواجهة) لضمان عدم كسر التدفق مع CSRF.

---

## ٩. الوثائق الموجودة

| الملف | المحتوى |
|-------|---------|
| `SYSTEM_MAP.md` | خريطة النظام، نقطة الدخول، الهيكل، Blueprints |
| `SYSTEM_REVIEW_AND_TEST_RESULTS.md` | مراجعة سابقة، نتائج الاختبارات، التدفق المحاسبي، فجوات وتوصيات |
| `IMMUTABLE_ACCOUNTING_RULES.md` | قواعد المحاسبة الثابتة (مصدر الحقيقة، القيود، الحذف، التعديل) |
| `DB_JOURNAL_SOURCE_OF_TRUTH.md` | اعتماد التقارير على القيود المنشورة |
| `DATA_PERSISTENCE_AND_IDEAL_BEHAVIOR.md` | استمرارية البيانات، الربط بالمورد/العميل، حذف القيد والفاتورة |
| `PERFORMANCE_AND_QUERY_OPTIMIZATION.md` | فهارس، تخزين مؤقت، ترقيم، N+1، views |
| `DEPLOY_RENDER_POSTGRES_WITHOUT_DATA_LOSS.md` | النشر على Render مع PostgreSQL |
| `ACCOUNTING_AUDIT.md` | تدقيق محاسبي وحذف القيد المرتبط |
| `WASTE_INVENTORY_AND_CLOSING.md` | الهدر والمخزون وإقفال الفترة |

---

## ١٠. المخاطر والديون التقنية

1. **ازدواجية المسارات:** جزء كبير من المسارات ما زال في `app/routes.py` و `app.py`؛ التقسيم إلى Blueprints في `routes/` جيد لكن الهجرة الكاملة من monolith لم تكتمل.
2. **فشل الهجرة بصمت:** عند فشل `flask db upgrade` يتم المتابعة دون إيقاف التشغيل؛ ضمان أعمدة `customers` في البدء يخفف أثر غياب عمود واحد، لكن يفضّل جعل تنفيذ الهجرات إلزامياً في مرحلة النشر (Release Command) أو التأكد من عدم فشلها.
3. **اختبارات POST مع CSRF:** الاختبارات الآلية لا ترسل توكن CSRF؛ الاعتماد على اختبار يدوي بعد النشر مقبول لكن يُفضّل إضافة مسار اختبار معفى من CSRF للـ smoke أو استخدام عميل يضيف التوكن.
4. **سكربتات مؤقتة في الجذر:** عدد من الملفات (check_*.py، fix_*.py، create_*.py) قد تكون لمرة واحدة؛ يُفضّل نقلها إلى `scripts/` أو أرشفتها لتنظيف الجذر.

---

## ١١. التوصيات

| الأولوية | التوصية |
|----------|---------|
| عالية | تشغيل `flask db upgrade` كجزء من Release Command على Render (أو التأكد من عدم فشله في Start) لتفادي تأخر تطبيق الهجرات. |
| عالية | الاحتفاظ باختبار يدوي واحد بعد كل نشر (مصروف، أو فاتورة مشتريات، أو قيد) لضمان التدفق مع CSRF والقيود. |
| متوسطة | توحيد نقطة إنشاء قيود المشتريات/المصروفات في مكان واحد (مثلاً دوال مشتركة من `app.routes` أو `routes/journal.py`) لتقليل التكرار وتسهيل الصيانة. |
| متوسطة | نقل السكربتات المؤقتة من جذر المشروع إلى `scripts/` أو `archive/` وتحسين تنظيم المستودع. |
| منخفضة | إضافة اختبار آلي يتحقق من توازن كل قيد منشور (Σ مدين = Σ دائن). |
| منخفضة | توثيق اختياري لـ API المدفوعات/التقارير للمدمجين الخارجيين. |

---

## ١٢. الخلاصة

النظام **محاسبياً متسق**، يعتمد على قيود اليومية كمصدر وحيد للحقيقة، ومُوثَّق جيداً. البنية قابلة للصيانة مع Blueprints منفصلة، ودعم واضح لـ SQLite و PostgreSQL، وضمانات بدء تشغيل لأعمدة العملاء على الإنتاج. التحسينات الأخيرة (فهارس، تخزين مؤقت، ترقيم، إصلاح الفواتير والقيود الصفرية، ضمان أعمدة customers) تعزز الاستقرار والأداء. المراقبة الدورية للهجرات والاختبار اليدوي بعد النشر كافية للمرحلة الحالية.
