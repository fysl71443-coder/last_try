# Troubleshooting Internal Server Error

## 🔍 خطوات تشخيص الخطأ

### 1. فحص Render Logs
```bash
# في Render Dashboard:
# 1. اذهب إلى Service
# 2. اضغط على "Logs"
# 3. ابحث عن رسائل الخطأ
```

### 2. الأخطاء الشائعة وحلولها

#### ❌ Database Connection Error
```
psycopg2.OperationalError: could not connect to server
```
**الحل:**
- تأكد من أن DATABASE_URL متصل بشكل صحيح
- تحقق من إعدادات PostgreSQL في Render

#### ❌ Template Not Found
```
TemplateNotFound: simple_login.html
```
**الحل:**
- تأكد من وجود مجلد templates/
- تأكد من وجود الملفات:
  - templates/simple_login.html
  - templates/simple_dashboard.html

#### ❌ Import Error
```
ModuleNotFoundError: No module named 'flask'
```
**الحل:**
- تأكد من requirements_simple.txt
- تأكد من buildCommand في render.yaml

### 3. اختبار محلي

#### تشغيل التطبيق محلياً:
```bash
python clean_app.py
```

#### اختبار التشخيص:
```bash
python diagnose_error.py
```

#### اختبار التطبيق المبسط:
```bash
python minimal_app.py
```

### 4. فحص Health Endpoint

#### اختبار صحة التطبيق:
```bash
curl https://your-app.onrender.com/health
```

**الاستجابة المتوقعة:**
```json
{"status": "ok", "message": "App is running"}
```

### 5. خطوات الإصلاح التدريجي

#### الخطوة 1: استخدم minimal_app.py
```bash
# في Procfile:
web: gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT minimal_app:app
```

#### الخطوة 2: تحقق من المتغيرات البيئية
```bash
# في Render Dashboard > Environment:
SECRET_KEY=your_secret_key_here
FLASK_ENV=production
```

#### الخطوة 3: تحقق من قاعدة البيانات
```bash
# تأكد من إنشاء PostgreSQL database في Render
# وربطها بالتطبيق
```

### 6. رسائل Log المفيدة

#### ✅ رسائل النجاح:
```
INFO:clean_app:Using PostgreSQL database
INFO:clean_app:Database tables created successfully
INFO:clean_app:Admin user created successfully
```

#### ❌ رسائل الخطأ:
```
ERROR:clean_app:Database initialization error: ...
ERROR:clean_app:Login route error: ...
ERROR:clean_app:Internal server error: ...
```

### 7. حلول سريعة

#### إذا استمر الخطأ:

1. **استخدم minimal_app.py بدلاً من clean_app.py**
2. **تأكد من Procfile_simple**
3. **استخدم requirements_simple.txt**
4. **فعّل logging في Render**

#### أوامر Render المفيدة:
```bash
# في Render Shell:
python -c "from clean_app import app; print('App works!')"
python -c "import flask; print('Flask version:', flask.__version__)"
```

### 8. إعدادات Render المثلى

#### Build Command:
```bash
pip install -r requirements_simple.txt
```

#### Start Command:
```bash
gunicorn -k eventlet -w 1 --timeout 120 --log-level info -b 0.0.0.0:$PORT clean_app:app
```

#### Environment Variables:
```
SECRET_KEY=auto-generated
FLASK_ENV=production
```

### 9. اختبار نهائي

بعد تطبيق الحلول، اختبر:

1. **Health endpoint**: `/health`
2. **Login page**: `/login`
3. **Login functionality**: admin/admin
4. **Dashboard**: `/dashboard`
5. **Logout**: `/logout`

إذا استمرت المشكلة، شارك رسائل الـ logs من Render للمساعدة في التشخيص.
