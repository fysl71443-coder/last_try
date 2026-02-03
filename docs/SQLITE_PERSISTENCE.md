# قاعدة بيانات SQLite — عدم ضياع البيانات

## المبدأ

- **المصدر الوحيد للحقيقة** = ملف SQLite في مسار **ثابت** داخل المشروع.
- ❌ لا نستخدم أبداً `:memory:` أو مجلد مؤقت (`/tmp`) في التشغيل العادي.
- ✅ كل تعديل يُحفظ عبر `db.session.commit()` (Flask-SQLAlchemy يلتزم نهاية الطلب).

---

## المسار المعتمد

| البيئة | المسار الافتراضي |
|--------|-------------------|
| التطبيق | `instance/accounting_app.db` |
| متغير اختياري | `LOCAL_SQLITE_PATH` (مثلاً `data/db.sqlite`) |

التكوين في `config.py`:

- `_instance_dir = project/instance` → يُنشأ تلقائياً إن لم يكن موجوداً.
- `_default_sqlite_path = os.getenv('LOCAL_SQLITE_PATH') or instance/accounting_app.db`

---

## الطريقة الصحيحة

1. **ملف دائم:** المسار داخل المشروع (مثل `instance/` أو `data/`) وليس في الذاكرة أو `/tmp`.
2. **Commit:** التطبيق يستخدم Flask-SQLAlchemy؛ الالتزام يتم في نهاية الطلب. السكربتات التي تكتب في DB يجب أن تستدعي `db.session.commit()` بعد التعديلات.
3. **نسخة احتياطية:** تشغيل دوري لسكربت النسخ الاحتياطي.

---

## النسخ الاحتياطي اليدوي

```bash
python scripts/backup_sqlite_db.py
```

ينسخ الملف الحالي إلى:

`backup/db_backup_YYYYMMDD_HHMMSS.sqlite`

يمكن جدولة هذا الأمر (cron / Task Scheduler) كل يوم أو أسبوع.

---

## هيكل مقترح

```
project/
├── instance/
│   └── accounting_app.db   ← قاعدة البيانات الدائمة (الافتراضي)
├── data/                   ← اختياري: لو استخدمت LOCAL_SQLITE_PATH=data/db.sqlite
│   └── db.sqlite
├── backup/                 ← يُنشأ عند تشغيل backup_sqlite_db.py
│   └── db_backup_*.sqlite
├── config/
└── ...
```

أي إعادة تشغيل للخادم → البيانات تبقى محفوظة طالما المسار ثابت وتم عمل `commit()` بعد التعديلات.
