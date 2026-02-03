# توصيات تحسين سرعة الاستجابة والاستعلامات

## 1. قاعدة البيانات (Database)

### 1.1 الفهارس (Indexes)
- **تم تنفيذه:** فهارس على `journal_lines (line_date)` و `(line_date, account_id)` و `account_id` و `invoice_id` / `invoice_type`.
- **مقترح إضافي:**
  - `journal_entries`: فهرس مركّب على `(status, date)` لأن أغلب الاستعلامات تفلتر `status = 'posted'` وبنطاق تاريخ.
  - `sales_invoices` / `purchase_invoices`: فهرس على `(date)` و `(branch)` و `(customer_id)` أو `(supplier_id)` حسب تقاريرك.
  - `payments`: فهرس على `(invoice_type, invoice_id)` لتسريع تجميع المدفوعات.

```sql
-- أمثلة (PostgreSQL / SQLite)
CREATE INDEX IF NOT EXISTS idx_journal_entries_status_date ON journal_entries (status, date);
CREATE INDEX IF NOT EXISTS idx_sales_invoices_date ON sales_invoices (date);
CREATE INDEX IF NOT EXISTS idx_sales_invoices_branch ON sales_invoices (branch);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments (invoice_type, invoice_id);
```

### 1.2 تجميع الاتصالات (Connection pooling) — PostgreSQL
- في الإنتاج تأكد من استخدام **pool_pre_ping** (موجود في `config.py`) وضبط حجم الـ pool إذا لزم:
  - `SQLALCHEMY_ENGINE_OPTIONS`: إضافة `pool_size=5`, `max_overflow=10` حسب الحمل.

### 1.3 تجنب جلب بيانات غير ضرورية
- استخدم **أعمدة محددة** عندما لا تحتاج كل الأعمدة:
  - مثال: `db.session.query(JournalLine.id, JournalLine.debit, JournalLine.credit, JournalLine.line_date)` بدل جلب الـ object كاملاً إن كنت تحتاج هذه الحقول فقط.
- في التقارير الكبيرة: **لا تستخدم `SELECT *`**؛ حدد الأعمدة المطلوبة فقط.

---

## 2. طبقة التطبيق (Application Layer)

### 2.1 تجنب مشكلة N+1
- عند عرض قائمة مع علاقات (مثلاً فواتير + مورد/عميل)، اجلب العلاقة **مسبقاً**:
  - استخدام `joinedload` أو `selectinload`:
    ```python
    from sqlalchemy.orm import joinedload
    invs = SalesInvoice.query.options(joinedload(SalesInvoice.customer)).filter(...).limit(50).all()
    ```
- تجنب استدعاء `Supplier.query.get(id)` أو `Customer.query.get(id)` **داخل حلقة** على عشرات الصفوف؛ استخدم الخيار أعلاه أو بناء قاموس (id → object) من استعلام واحد.

### 2.2 الترقيم (Pagination) في كل القوائم الكبيرة
- **تم تنفيذه:** تقرير التدفق النقدي (50 صف/صفحة مع LIMIT منطقي عبر slice).
- **مقترح:** تطبيق نفس النمط على:
  - كشف الحساب (account_statement)
  - قائمة القيود (journal list)
  - تقرير المبيعات إذا تجاوز الصفوف حداً معيناً (مثلاً 100)
- استخدم `request.args.get('page', 1, type=int)` و `per_page` ثم:
  - إما استعلام مع `LIMIT` و `OFFSET` (أو `.limit(per_page).offset((page-1)*per_page)`)،
  - أو جلب النتائج المطلوبة فقط من طبقة التخزين (مثلاً من view أو استعلام مجمّع).

### 2.3 التخزين المؤقت (Caching)
- **موجود:** Redis عند `REDIS_URL`، و `CACHE_TYPE = 'simple'` محلياً.
- **مقترح:**
  - تخزين مؤقت قصير (دقائق) لنتائج **ميزان المراجعة** و **قائمة الدخل** و **الميزانية** حسب `date` و `branch` (مفتاح مثل `tb:{date}:{branch}`).
  - تخزين مؤقت لشجرة الحسابات (COA) أو قوائم الحسابات لأنها تتغير نادراً.
- مثال بسيط:
  ```python
  from flask_caching import Cache
  cache_key = f"trial_balance:{asof}:{branch}"
  data = cache.get(cache_key)
  if data is None:
      data = _compute_trial_balance(asof, branch)
      cache.set(cache_key, data, timeout=300)  # 5 دقائق
  ```

### 2.4 تجميع (Aggregation) في قاعدة البيانات
- احسب المجاميع في الاستعلام بدل تجميع آلاف الصفوف في بايثون:
  - مثال: `db.session.query(Account.code, func.sum(JournalLine.debit), func.sum(JournalLine.credit)).join(...).filter(...).group_by(Account.code)` ثم استخدم النتائج مباشرة.
- تجنب جلب كل صفوف `journal_lines` ثم `sum(...)` في بايثون عندما يكفي استعلام واحد مع `GROUP BY`.

---

## 3. Views و Materialized Views (PostgreSQL)

### 3.1 View بسيط للتقارير المتكررة
- إن كان نفس الاستعلام (مثلاً تدفق نقدي مجمّع حسب حساب وتاريخ) يُستخدم في أكثر من مكان، إنشاء **View** يقلل تكرار المنطق ويسمح للمحرك بتحسين التنفيذ:
  ```sql
  CREATE OR REPLACE VIEW v_cash_movements AS
  SELECT jl.id, a.code AS account_code, a.name AS account_name, jl.line_date, jl.debit, jl.credit
  FROM journal_lines jl
  JOIN accounts a ON a.id = jl.account_id
  JOIN journal_entries je ON je.id = jl.journal_id
  WHERE a.code IN ('1111','1112','1121','1122','1123') AND je.status = 'posted';
  ```
- ثم استعلام الـ View مع `WHERE line_date BETWEEN ...` و `LIMIT/OFFSET`.

### 3.2 Materialized View للمجاميع الثقيلة
- للتقارير التي تعتمد على نفس البيانات ولا تحتاج لحظة-بلحظة:
  ```sql
  CREATE MATERIALIZED VIEW cashflow_summary_mv AS
  SELECT account_id, line_date, SUM(debit) AS total_debit, SUM(credit) AS total_credit
  FROM journal_lines jl
  JOIN journal_entries je ON je.id = jl.journal_id
  WHERE je.status = 'posted'
  GROUP BY account_id, line_date;
  CREATE UNIQUE INDEX ON cashflow_summary_mv (account_id, line_date);
  ```
- تحديث دوري (Cron أو مهمة مجدولة):
  ```sql
  REFRESH MATERIALIZED VIEW CONCURRENTLY cashflow_summary_mv;
  ```

---

## 4. الواجهة الأمامية (Frontend)

### 4.1 تم تنفيذه
- رؤوس جداول ثابتة (sticky headers) في التدفق النقدي وتقرير المبيعات.
- ترقيم صفحات في التدفق النقدي مع زر "طباعة الكل".
- فاصل صفحة عند الطباعة كل 25 صفاً لتقارير الجداول الطويلة.

### 4.2 مقترح إضافي
- **تحميل كسول (Lazy loading):** إن وُجدت جداول ضخمة في صفحة واحدة، اعرض الجزء الأول فقط ثم حمّل المزيد عند التمرير أو عبر "تحميل المزيد".
- **تصفية وترتيب من الخادم:** عند وجود فلاتر (تاريخ، فرع، حساب)، أرسل المعايير في الطلب وليكن الاستعلام والترتيب (ORDER BY) من الخادم بدل جلب كل البيانات وفلترتها في المتصفح.

---

## 5. مراقبة وتشخيص الأداء

### 5.1 تفعيل echo للاستعلامات (مؤقت)
- في التطوير فقط، يمكن تفعيل `echo=True` في `SQLALCHEMY_ENGINE_OPTIONS` لطباعة كل استعلام SQL وملاحظة الاستعلامات البطيئة أو المكررة.

### 5.2 تحليل الاستعلامات البطيئة (PostgreSQL)
- استخدام `pg_stat_statements` أو سجلات PostgreSQL لرصد الاستعلامات الأكثر استهلاكاً للوقت.
- تحليل خطط التنفيذ:
  ```sql
  EXPLAIN (ANALYZE, BUFFERS) SELECT ... ;
  ```

### 5.3 تقليل حجم الاستجابة
- للـ APIs التي تُرجع قوائم كبيرة: تأكد من استخدام الترقيم وعدم إرجاع آلاف الصفوف في طلب واحد.
- ضغط الاستجابة (GZip) عادةً يُفعّل من مستوى الـ reverse proxy أو الخادم (مثل Nginx أو Render).

---

## 6. ملخص أولويات التنفيذ

| الأولوية | الإجراء | التأثير المتوقع |
|----------|---------|------------------|
| عالية | ضمان وجود فهارس على `journal_entries (status, date)` و `journal_lines (line_date, account_id)` | تسريع كل التقارير المعتمدة على القيود |
| عالية | ترقيم الصفحات في كشف الحساب وقائمة القيود | تقليل زمن الاستجابة وحجم الـ HTML |
| متوسطة | تخزين مؤقت قصير لنتائج ميزان المراجعة / قائمة الدخل | تقليل تحميل قاعدة البيانات عند تكرار نفس الفترة |
| متوسطة | استخدام joinedload/selectinload عند عرض قوائم مع علاقات | إزالة N+1 وتقليل عدد الاستعلامات |
| منخفضة | Materialized View للتدفق النقدي أو تجميعات ثقيلة أخرى | تسريع كبير مع تحديث دوري |

---

تم إعداد هذا الملف كمرجع؛ تنفيذ التوصيات حسب أولوية احتياجك وبيئة التشغيل (SQLite محلياً vs PostgreSQL في الإنتاج).
