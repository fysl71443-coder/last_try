# قواعد المطورين: مصدر الحقيقة المحاسبي (GL)

## القاعدة الأساسية
**أي شاشة أو تقرير أو API يعرض أرصدة أو حركات محاسبية يجب أن يقرأ من:**
- **`JournalLine`** + **`JournalEntry`** (مع `JournalEntry.status == 'posted'` فقط).

**لا تستخدم** تجميعات من جداول الفواتير أو الدفعات أو أي جدول وسيط كـ**مصدر وحيد** للأرصدة. يمكن استخدام الفواتير/الدفعات للعرض الوصفي أو الربط (مثل وصف الحركة)، لكن **الرقم المعروض (رصيد، إجمالي مدين/دائن) يجب أن يكون مستمداً من القيود**.

## إذا استخدمت LedgerEntry
جدول **`LedgerEntry`** موجود للتوافق مع شيفرة قديمة أو تقارير لم تُحوَّل بعد إلى JournalLine.  
**استثناء مسموح فقط إذا:**
1. وثّقت في الكود **سبب الاستثناء** (تعليق أو docstring).
2. أضفت في هذا الملف أو في GL_SOURCE_OF_TRUTH.md **قائمة بالشاشات/الملفات التي تقرأ من LedgerEntry** والسبب.

مثال توثيق في الكود:
```python
# استثناء: تقرير X ما زال يستخدم LedgerEntry لأن [...]. انظر docs/DEVELOPER_GL_RULES.md
rows = db.session.query(LedgerEntry).filter(...)
```

## دوال جاهزة في services/gl_truth.py
- **`get_account_debit_credit_from_gl(account_id, asof_date)`** → (debit_sum, credit_sum)
- **`get_account_balance_from_gl_by_code(account_code, asof_date)`** → (balance, account_type)
- **`sum_gl_by_account_code_and_date_range(account_codes, start_date, end_date, credit_minus_debit)`** → float

استخدمها بدلاً من استعلامات مباشرة على LedgerEntry أو على الفواتير عند الحاجة إلى رصيد أو مجموع.

## شاشات جديدة
عند إضافة شاشة جديدة تعرض:
- أرصدة حسابات
- حركات مدين/دائن
- تقارير مالية (ميزان مراجعة، قائمة مركز مالي، قائمة دخل، كشوف حسابات)

يجب أن تكون الاستعلامات من **JournalLine** مع **join على JournalEntry** و**filter بـ status == 'posted'**، أو استخدام الدوال أعلاه.  
لا تضيف قراءة جديدة من **LedgerEntry** دون توثيق الاستثناء كما في القسم "إذا استخدمت LedgerEntry".

## المراجع
- **GL_SOURCE_OF_TRUTH.md**: ملخص ما تم تنفيذه ومصدر الحقيقة.
- **services/gl_truth.py**: تنفيذ دوال الأرصدة ومزامنة LedgerEntry.
