# Phase 1 – تخفيف الحمل (No Global Load)

## قواعد إلزامية

### ممنوع في `before_request` و `context_processor`

- **accounts** — لا استعلام عن الحسابات (مثلاً `Account.query`)  
- **settings** — لا استعلام عن الإعدادات (`Settings.query`)  
- **permissions** — لا استعلام عن الصلاحيات (`AppKV` / `user_perms`)  

### النتيجة

- الـ **Navbar** و**base layout** لا يطلبان DB. يعتمدان فقط على:
  - `settings` من السياق = `None` (fallback: `"Company"`, `"light"`)
  - `can(screen, action)` = منطق فقط (admin أو authenticated ⇒ True)، بدون DB
- **كل Blueprint/route** يحدد ما يحتاجه: يجرى تحميل **settings** أو **accounts** أو غيره **داخل المسار** عند الحاجة فقط.

### الملفات المعدّلة

- `app/__init__.py`: `inject_globals` لا يحمّل accounts/settings/permissions؛ `before_request` يبقى بدون DB.
- `templates/base.html`: تعليق يذكّر أن الـ Navbar يجب أن يبقى بدون DB.

### تحسين متوقّع

تقليل استعلامات كل طلب (حسب الاستخدام السابق) بنسبة تقديرية **20–30%** في التنقل العادي.

---

## Phase 2 – إعادة توزيع المسارات (بدء)

- **`routes/common.py`**: مساعدات مشتركة (`kv_get`, `kv_set`, `BRANCH_LABELS`, `safe_table_number`, `user_can`) دون استعلام في السياق العام.
- **`routes/expenses.py`**: Blueprint `expenses` للمسارات `/expenses`, `/expenses/delete/<eid>`, `/expenses/test`. نفس الـ URLs، لا كسر.
- **`routes/purchases.py`**: Blueprint `purchases` للمسارات `/purchases`, `/raw-materials`, `/meals`, `/meals/import`, `/api/purchase-categories`, `/api/raw_materials`, `/api/raw_materials/categories`. نفس الـ URLs.
- **`routes/suppliers.py`**: Blueprint `suppliers` للمسارات `/suppliers`, `/suppliers/list`, `/suppliers/edit/<id>`, `/suppliers/<id>/toggle`, `/suppliers/export`, `/suppliers/<id>/delete`. نفس الـ URLs.
- **`routes/customers.py`**: Blueprint `customers` للمسارات `/customers`, `/customers/<id>/toggle`, `/customers/<id>/delete`, `/api/customers/search`, `/api/pos/<branch>/customers/search`, `/api/customers` (POST). نفس الـ URLs.
- **`routes/payments.py`**: Blueprint `payments` للمسارات `/payments`, `/payments.json`, `/payments/export`, `/api/payments/register`, `/api/payments/supplier/register`, `/api/payments/pay_all`. نفس الـ URLs.
- **`routes/inventory.py`**: Blueprint `inventory` للمسارات `/inventory`, `/inventory-intelligence`, `/api/inventory/intelligence`. نفس الـ URLs.
- **`routes/reports.py`**: Blueprint `reports` للمسارات `/reports`, `/reports/monthly`, `/reports/print/*`, `/api/reports/*`. نفس الـ URLs (18 route).
- **`routes/sales.py`**: Blueprint `sales` للمسارات `/sales`, `/pos/*`, `/api/sales/*`, `/api/draft/*`, `/api/table*`, `/print/receipt`, `/print/order*`, `/invoice/print`. نفس الـ URLs (~32 route).
- **`app/routes.py`**: تقلّص بشكل كبير (~8000 → ~5800 سطر). يحتوي الآن فقط على: Auth, Dashboard, Employees/Salaries, Menu, Users, Settings, VAT, Journal, Archive, وبعض الـ helpers.
- **القوالب**: جميع `url_for` محدّثة للـ blueprints الجديدة.

### ✅ Phase 3 – Cache حقيقي (مكتمل)

- **Flask-Caching + Redis** (أو SimpleCache عند عدم وجود `REDIS_URL`).
- **الإعدادات (settings):** TTL 10 دقائق. `get_cached_settings()` / `invalidate_settings_cache()` عند الحفظ.
- **شجرة الحسابات (COA):** TTL 15 دقيقة. كاش لـ `/api/coa`، إبطال عند استيراد COA.
- **VAT lookups:** TTL 5 دقائق. كاش لوحة VAT حسب `(start_date, end_date, branch)`.
- **تقارير المعاينة (reports preview):** TTL 2 دقيقة. كاش لـ `/api/reports/preview` حسب المعاملات.
- الإعدادات في `config.py`؛ المساعدات في `utils/cache_helpers.py`.

---

### ✅ Phase 4 – تحسين التنقل وسرعة الاستجابة (مكتمل)

- **تنقل جزئي:** استبدال `#app-messages` و `#app-main` فقط عبر `fetch`؛ الهيدر ثابت.
- **الملفات:** `base.html` (`#app-messages`, `#app-main`, `data-partial-links` على المحتوى، `data-partial` على الشعار)، `static/js/nav-partial.js`.
- **الروابط:** أي `<a>` داخل `#app-main` أو `[data-partial-links]` أو `data-partial` تُحمّل جزئياً. مستثنى: تسجيل الدخول/الخروج، `target="_blank"`، روابط التجزئة.
- **دعم الرجوع:** `pushState` / `popstate`، مؤشر تحميل أثناء الجلب.

---

### ✅ Phase 2 مكتمل

تم استخراج **8 blueprints**:
1. `expenses` - المصروفات
2. `purchases` - المشتريات والمواد والوجبات
3. `suppliers` - الموردين
4. `customers` - العملاء
5. `payments` - المدفوعات
6. `inventory` - المخزون
7. `reports` - التقارير
8. `sales` - المبيعات ونقاط البيع
