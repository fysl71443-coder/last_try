import os

class Config:
    # إذا DATABASE_URL موجودة (من Render أو أي خدمة) نستخدمها
    if os.getenv("DATABASE_URL"):
        SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    else:
        # تشغيل محلي باستخدام SQLite
        SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"check_same_thread": False}
        }

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

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
