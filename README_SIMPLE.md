# Simple Restaurant App

## الملفات المبسطة

### 1. clean_app.py
```python
from flask import Flask, render_template, redirect, url_for, request, flash 
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy.pool import NullPool

# ===== إنشاء التطبيق =====
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ===== تصحيح Eventlet/SQLAlchemy =====
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"poolclass": NullPool}

# ... باقي الكود
```

### 2. templates/simple_login.html
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login</title>
</head>
<body>
    <h2>Login</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div style="color:red;">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form method="POST">
        <label>Username:</label><input type="text" name="username" required><br>
        <label>Password:</label><input type="password" name="password" required><br>
        <button type="submit">Login</button>
    </form>
</body>
</html>
```

### 3. templates/simple_dashboard.html
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Dashboard</title>
</head>
<body>
    <h2>Welcome, {{ username }}!</h2>
    <a href="{{ url_for('logout') }}">Logout</a>
</body>
</html>
```

### 4. Procfile_simple
```
web: gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT clean_app:app
```

### 5. requirements_simple.txt
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Bcrypt==1.0.1
Flask-Login==0.6.3
gunicorn==21.2.0
eventlet==0.36.1
```

## تشغيل التطبيق

### محلياً:
```bash
python clean_app.py
```

### على Render:
```bash
export FLASK_APP=clean_app.py
gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT clean_app:app
```

## بيانات الدخول
- Username: admin
- Password: admin

## الميزات
- ✅ تسجيل دخول بسيط
- ✅ حماية الصفحات
- ✅ إنشاء مستخدم admin تلقائياً
- ✅ NullPool لحل مشاكل eventlet
- ✅ جاهز للنشر على Render
