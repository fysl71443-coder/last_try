import os

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

    DATABASE_URL = os.getenv("DATABASE_URL")

    if DATABASE_URL:
        # Render أو أي خدمة PostgreSQL
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600  # إعادة تدوير الاتصالات كل ساعة
        }
    else:
        # تشغيل محلي باستخدام SQLite
        SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"check_same_thread": False}
        }

    # Babel / i18n
    BABEL_DEFAULT_LOCALE = os.getenv('BABEL_DEFAULT_LOCALE', 'ar')
    LANGUAGES = ['en', 'ar']

    # CSRF settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Session settings
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    # Debug mode
    DEBUG = os.getenv('FLASK_ENV') != 'production'
