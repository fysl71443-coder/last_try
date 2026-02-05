# التقرير الشامل لفحص البنية والمجلدات والجودة
## Comprehensive Structure, Database, Code, Security, Performance, Tests & Deployment Audit

**تاريخ الفحص:** 2026-02  
**النطاق:** بنية المشروع، قاعدة البيانات، المنطق المحاسبي، الكود، الأمان، الأداء، الاختبارات، النشر.

---

## ١. فحص البنية والمجلدات والملفات الأساسية

### ١.١ الملفات والمجلدات المطلوبة

| البند | الحالة | الملاحظات |
|--------|--------|-----------|
| **app.py** | ✅ موجود | في الجذر؛ تطبيق Flask احتياطي/قديم (كبير، آلاف الأسطر). التعليق في بداية الملف يشير إلى أن التطبيق الرئيسي في `app/`. |
| **run.py** | ✅ موجود | يشغّل التطبيق عبر `create_app()` من الحزمة `app`، يهيئ SQLite محلياً، وينشئ مستخدم admin إن لم يوجد. **نقطة الدخول الموصى بها للتطوير.** |
| **server.py** | ✅ موجود | يستورد `from app import app` ويشغّل `app.run()` على المنفذ 5000. يعتمد على نسخة التطبيق المُصدَّرة من الحزمة `app`. |
| **modules/** | ✅ موجود | يحتوي: `audit/` (engine, report_builder, rules). منظم بشكل جيد. |
| **services/** | ✅ موجود | account_validation, accounting_adapter, audit_engine, audit_snapshot_cache, gl_truth. |
| **routes/** | ✅ موجود | 14 ملف: common, customers, expenses, financials, fiscal_years, inventory, journal, payments, print_receipt, purchases, reports, sales, suppliers, vat. |
| **templates/** | ✅ موجود | عشرات القوالب (مالية، تقارير، طباعة، فروع، إلخ). |
| **static/** | ✅ موجود | CSS, JS, صور (مجلد uploads). |

### ١.٢ هيكل التطبيق (Flask)

- **نمط المصنع (Factory):** مُطبَّق في `app/__init__.py` عبر `create_app(config_class=None)`. يتم تهيئة Flask، الإعدادات، db، bcrypt، login_manager، migrate، babel، csrf، cache، وتسجيل الـ blueprints.
- **تصدير التطبيق:** في نهاية `app/__init__.py` يوجد `app = create_app()` لاستخدام السكربتات و`server.py` و`wsgi`.
- **ازدواجية محتملة:** يوجد تطبيقان: (1) تطبيق المصنع في `app/` وهو المستخدم في `run.py` و`wsgi.py`، (2) `app.py` في الجذر (تطبيق ضخم قديم). يُنصح بالاعتماد على `run.py` + `app/` فقط وتقليص دور `app.py` تدريجياً.

### ١.٣ ملفات التهيئة والترحيل

| الملف | الحالة | ملاحظات |
|--------|--------|----------|
| **config.py** | ✅ | إعدادات حسب ENV (development → SQLite في instance/، production → DATABASE_URL). دعم Redis للكاش، إعدادات الجلسة والـ CSRF. |
| **config_production.py** | ✅ | موجود. |
| **alembic.ini** | ✅ | موجود في الجذر **وفي** `migrations/`. سكربت الترحيل الاحتياطي يشير إلى `alembic.ini` في الجذر. |
| **requirements.txt** | ✅ | موجود. توجد أيضاً requirements_simple.txt و requirements-dev.txt. |
| **migrations/** | ✅ | مجلد الترحيل مع `env.py` و`versions/` (عدة ترحيلات: fiscal_years، journal، audit، indexes، إلخ). |
| **render_setup.sql** | ✅ | سكربت لـ PostgreSQL على Render: يضيف أعمدة لـ `draft_orders` (table_number، status، branch_code، إلخ) وفهارس. |

### ١.٤ خلاصة البنية

- البنية منظمة وتحتوي على كل الملفات والمجلدات الأساسية.
- نمط المصنع مُطبَّق في `app/`. وجود `app.py` ضخم في الجذر يخلق ازدواجية؛ التوصية: توحيد نقطة الدخول على `run.py` + `app/`.

---

## ٢. فحص قاعدة البيانات والمنطق المحاسبي

### ٢.١ تطابق الجداول مع النماذج

| الجدول/النموذج | الحالة | أعمدة حرجة (عينة) |
|-----------------|--------|---------------------|
| **employees** | ✅ | Employee: status (active/inactive)، علاقات مع EmployeeHours، EmployeeSalaryDefault. |
| **draft_orders** | ✅ | DraftOrder: table_number (String)، status (draft)، branch_code. مطابق لـ render_setup.sql. |
| **expenses** | ✅ | ExpenseInvoice، ExpenseInvoiceItem؛ status (paid/pending). |
| **sales** | ✅ | SalesInvoice (table_number، status، branch)، SalesInvoiceItem. |
| **purchases** | ✅ | PurchaseInvoice، PurchaseInvoiceItem؛ status (unpaid/partial/paid). |
| **FiscalYear** | ✅ | fiscal_years: year، start_date، end_date، status (open/closed/partial/locked)، closed_until، إلخ. |
| **Table / TableSettings** | ✅ | table_number، status (available/reserved/occupied)، branch_code، UniqueConstraint(branch_code, table_number). |

العلاقات (FK) وأنواع البيانات في `models.py` متسقة مع الاستخدام في المسارات والترحيلات.

### ٢.٢ التكرار وتسرب البيانات المحاسبية

- **مصدر الحقيقة:** خدمة `services/gl_truth.py` تحدد أن القيود اليومية (GL) هي مصدر الحقيقة؛ التحكم الزمني عبر السنوات المالية فقط، ويوجد تحقق من فتح الفترة قبل إنشاء فواتير/قيود (`can_create_invoice_on_date`).
- **استحقاق الرواتب:** مسار الرواتب ينشئ قيود استحقاق (مثل JE-PR)؛ الاختبار `test_real_accrual_settlement` يغطي ذلك.
- **المصروفات:** مسار المصروفات يتحقق من `can_create_invoice_on_date` ثم ينشئ الفاتورة والقيد (مثل JE-EXP).
- **سداد من العمليات:** تسجيل الدفعات وربطها بالفواتير موجود في routes (payments، purchases، sales).
- **القيود اليومية والتقارير المالية:** إنشاء القيود من المبيعات/المشتريات/المصروفات/الرواتب موزع على routes (journal، financials، app.routes)؛ التقارير (ميزان مراجعة، قائمة دخل، تدفق نقدي) في `routes/financials.py` وتستخدم الكاش حيث يناسب.

**توصية:** مراجعة دورية لـ `docs/GL_SOURCE_OF_TRUTH.md` و`docs/FINANCIAL_YEAR_GUARD.md` لضمان عدم إنشاء حركات خارج الفترة المفتوحة.

---

## ٣. فحص الكود البرمجي

### ٣.١ أسلوب الكتابة والاستثناءات والتسجيل

| البند | الحالة | ملاحظات |
|--------|--------|----------|
| **PEP8** | ⚠️ | المشروع كبير؛ توجد تفاوتات في طول الأسطر والتعليقات. يُنصح بتشغيل flake8/black على الملفات الجديدة والحرجة. |
| **معالجة الاستثناءات** | ✅ | استخدام try/except في المسارات الحرجة (مثل routes/sales، journal، financials). وجود rollback عند فشل الالتزام. |
| **Logging** | ✅ | `logging_setup.py`: RotatingFileHandler لـ logs/local-errors.log، ربط بـ Flask و Werkzeug. `logging_config.py` موجود. `app/__init__.py` يستدعي `setup_logging(app)` عند إنشاء التطبيق. |

### ٣.٢ الأجزاء الحرجة

| الجزء | الملفات/السكربتات | الحالة |
|--------|---------------------|--------|
| **إدارة طاولات POS** | templates (sales_tables، pos)، routes/sales، check_all_tables.py | المسارات محمية بـ `@login_required` و`user_can('sales','view', branch_code)`. تحقق من الحالة والتزامن للطاولات. |
| **الشجرة المحاسبية** | fix_db_menu.py، seed_main_sections (scripts)، app.routes (refresh_chart، COA) | fix_db_menu يستخدم PRAGMA table_info بأسماء جداول ثابتة (آمن). ربط القوائم بالحسابات عبر بيانات أولية وسكربتات. |
| **الشاشات حسب الفرع** | routes/sales (branch_code في URL)، routes/reports، financials (فلترة branch) | الفلترة حسب `branch` أو `branch_code` مطبقة في الاستعلامات (SalesInvoice.branch، JournalEntry.branch_code، إلخ). |
| **العمليات المالية** | extensions.py (db، bcrypt)، accounting_fixes (سكربتات)، forms في app | استخدام ORM وليس سلاسل SQL خام من المدخلات؛ يقلل خطر الحقن. |

---

## ٤. فحص الأمان

### ٤.١ نظام تسجيل الدخول وكلمات المرور

| البند | الحالة | ملاحظات |
|--------|--------|----------|
| **كلمات مرور مشفرة** | ✅ | استخدام Flask-Bcrypt في `extensions.py`؛ `User.set_password` و`check_password` في `models.py` يعتمدان على bcrypt. |
| **التحقق من كلمة المرور** | ✅ | مسار تسجيل الدخول يستخدم `check_password_hash` (في app.py) أو `user.check_password` (النموذج الجذر). |
| **السكربتات** | ✅ | check_admin_user.py، create_admin_user.py لإنشاء/التحقق من مستخدم admin؛ كلمة افتراضية (مثل admin123) للتطوير فقط — يجب تغييرها في الإنتاج. |

### ٤.٢ SQL Injection وحماية الجلسات

| البند | الحالة | ملاحظات |
|--------|--------|----------|
| **استعلامات آمنة** | ✅ | الاستعلامات عبر SQLAlchemy ORM (filter، filter_by) ومعاملات مرتبطة. لا يوجد تركيب سلاسل SQL من مدخلات المستخدم في المسارات. |
| **الجلسات** | ✅ | SESSION_COOKIE_HTTPONLY، SESSION_COOKIE_SAMESITE، SESSION_COOKIE_SECURE (حسب البيئة). session_protection = "strong" في login_manager. |
| **CSRF** | ✅ | CSRFProtect مفعّل من extensions؛ WTF_CSRF_TIME_LIMIT وWTF_CSRF_SSL_STRICT في الإعدادات. |

### ٤.٣ عزل بيانات الفروع

| البند | الحالة | ملاحظات |
|--------|--------|----------|
| **user_can و branch_scope** | ⚠️ | في `routes/common.py`، الدالة `user_can(screen, action, branch_scope)` تعيد حالياً `True` لجميع المستخدمين المصرح لهم (بعد التحقق من admin أو role admin). **لا يوجد تقييد فعلي لفرع المستخدم:** أي مستخدم مسجل يمكنه نظرياً الوصول لبيانات كل الفروع إذا عرف الـ URL أو معامل branch. |
| **توصية** | — | تنفيذ عزل فرع حقيقي: ربط المستخدم بفرع (أو قائمة فروع) وفرض أن `branch_scope` في التقارير والمسارات يقتصر على فروع المستخدم فقط. |

---

## ٥. فحص الأداء والاستقرار

### ٥.١ استعلامات N+1 والكاش

| البند | الحالة | ملاحظات |
|--------|--------|----------|
| **تجنب N+1** | ✅ | استخدام `joinedload` (app.py لقائمة المنيو)، `selectinload` في reports (PurchaseInvoice.items، ExpenseInvoice.items) وفي journal (JournalEntry.lines + JournalLine.account). |
| **كاش البيانات الثقيلة** | ✅ | ميزان المراجعة وقائمة الدخل: `cache.get`/`cache.set` في routes/financials مع مفتاح حسب التاريخ والفرع. COA والإعدادات: `get_cached_coa`، `get_cached_settings` في utils/cache_helpers. |
| **فهارس** | ✅ | وجود ترحيلات لفهارس (journal_lines، journal_entries، إلخ). وثيقة PERFORMANCE_AND_QUERY_OPTIMIZATION.md توصي بفهارس إضافية (مثل status+date لـ journal_entries). |

### ٥.٢ الطلبات المتزامنة والأزرار

- **التزامن:** استخدام جلسة DB وآليات القفل حيث يلزم (مثل تحديث حالة الطاولة)؛ لا يوجد دليل على تعارض غير مُدار في المسارات الحرجة.
- **أزرار بدون إعادة تحميل:** واجهات POS والجداول تعتمد على طلبات AJAX/API (مثل `/api/draft-order/`, `/api/tables/`)؛ الأزرار تُحدّث البيانات عبر JavaScript دون إعادة تحميل كاملة للصفحة حيث تم تطبيق ذلك.

---

## ٦. فحص الاختبارات

### ٦.١ ملفات الاختبار المذكورة

| الملف | الموقع | الحالة |
|--------|--------|--------|
| **e2e_test_runner.py** | جذر المشروع | ✅ موجود. يستخدم Selenium وChrome، لقطات شاشة، وتقارير في test_results/. |
| **simple_e2e_test.py** | جذر المشروع | ✅ موجود. |
| **functional_e2e_test.py** | جذر المشروع | ✅ موجود. |
| **quick_e2e_test.py** | جذر المشروع | ✅ موجود. |
| **tests/** | مجلد tests | pytest: test_audit_engine، test_employee_payment، test_payments_and_purchases، test_real_accrual_settlement، test_routes_smoke_pytest، conftest (test_app، client). |
| **tools/e2e_smoke.py** | tools | دخان E2E للصفحات والـ APIs. |
| **tools/smoke_test.py** | tools | تدفقات مبيعات/مشتريات/مصروفات؛ يتطلب سنة مالية ومستخدم admin. |

### ٦.٢ السيناريوهات الحرجة

- **مبيعات:** مغطاة في tests (test_purchase_and_payment_flow، test_real_accrual_settlement)، وsmoke_test، وe2e_sales_invoices_test.
- **مصروفات:** test_expense_creates_journal (مع fixture سنة مالية + admin).
- **رواتب:** test_employee_payment، test_payroll_run_creates_accrual_journal.

التوصية: تشغيل `pytest tests/ -v --ignore=tests/test_accounting_integration.py` بانتظام (النتيجة المتوقعة: 14 passed). انظر `docs/COMPREHENSIVE_TEST_AND_AUDIT_REPORT.md`.

---

## ٧. فحص ملفات النشر والتشغيل

### ٧.١ Dockerfile و Procfile و render.yaml

| الملف | الحالة | ملاحظات |
|--------|--------|----------|
| **Dockerfile** | ✅ | Python 3.11-slim، تثبيت requirements + eventlet + gunicorn، FLASK_APP=app.py، CMD عبر scripts/start_render.sh. |
| **Procfile** | ✅ | `web: python run_migrations.py && gunicorn ... wsgi:application`. يشغّل الترحيلات ثم wsgi (التطبيق من `app` package). |
| **Procfile_simple** | ✅ | بديل. |
| **render.yaml** | ✅ | خدمة web، بناء بـ pip -r requirements.txt، startCommand: gunicorn -k gevent app:app. **ملاحظة:** يستخدم `app:app` (الحزمة app تُصدّر app)، بينما start_render.sh يستخدم `simple_app:app`. توحيد نقطة الدخول (إما app:app أو simple_app:app أو wsgi:application) يقلل الالتباس. |

### ٧.٢ المتغيرات البيئية

- **DATABASE_URL:** مطلوب في الإنتاج (config.py يفرضه عند ENV=production).
- **SECRET_KEY:** يُستمد من البيئة؛ افتراضي في التطوير فقط.
- **REDIS_URL:** اختياري للكاش في الإنتاج.
- **RENDER_EXTERNAL_URL / PORT:** مستخدمة في الإعدادات والـ start script.

يُنصح بعدم تخزين SECRET_KEY أو DATABASE_URL في الكود؛ استخدام متغيرات بيئة أو نظام إدارة أسرار المنصة.

---

## ٨. ملخص نقاط الخطر والتحسينات

### نقاط الخطر / الأخطاء المحتملة

1. **عزل الفروع:** `user_can` لا يقيّد المستخدم العادي بفرع معين؛ إمكانية وصوله لبيانات كل الفروع إذا عرف المسار أو المعاملات.
2. **ازدواجية التطبيق:** وجود `app.py` ضخم و`app/` (Factory) قد يسبب التباساً في الصيانة ونقطة الدخول في النشر.
3. **نقطة دخول Gunicorn:** اختلاف بين render.yaml (`app:app`)، start_render.sh (`simple_app:app`)، و Procfile (`wsgi:application`). توحيدها يضمن سلوكاً متوقعاً على كل بيئة.

### تحسينات مقترحة

- **الأمان:** تنفيذ ربط المستخدم بفرع (أو صلاحيات فرع) وتطبيق `user_can` بحيث يقتصر الوصول على فروع المستخدم فقط.
- **الأداء:** تطبيق التوصيات في `docs/PERFORMANCE_AND_QUERY_OPTIMIZATION.md` (فهارس إضافية، ترقيم ثابت للقوائم الكبيرة).
- **المنطق/DB/UI:** الاستمرار في الاعتماد على `can_create_invoice_on_date` وخدمة gl_truth لجميع الحركات المالية؛ مراجعة أي مسار جديد يكتب على GL أو الفواتير. للواجهة: التأكد من أن الأزرار الحرجة تعمل دون إعادة تحميل كاملة حيث تم تصميمها لذلك.

### إصلاحات مقترحة فورية

1. توحيد أمر تشغيل Gunicorn في Render (نفس الـ module:app في render.yaml و start_render.sh).
2. إضافة فحص في `user_can` لربط المستخدم بفرع (أو قائمة فروع) ورفض الطلبات التي تتجاوزها.
3. توثيق نقطة الدخول الرسمية (run.py + app/) في README أو دليل النشر ووضع app.py كـ legacy حتى إكمال الهجرة.

---

**نهاية التقرير.** للمزيد من تفاصيل الاختبارات والنتائج راجع `docs/COMPREHENSIVE_TEST_AND_AUDIT_REPORT.md` و `docs/SYSTEM_REVIEW_AND_TEST_RESULTS.md`.
