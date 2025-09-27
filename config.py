import os
from sqlalchemy.pool import NullPool

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

    # CSRF Protection settings
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens
    WTF_CSRF_SSL_STRICT = False  # Allow CSRF over HTTP for development

    # Admin settings
    ADMIN_DELETE_PASSWORD = os.getenv('ADMIN_DELETE_PASSWORD', '1991')

    # Force SQLite for local development
    SQLALCHEMY_DATABASE_URI = "sqlite:///accounting_app.db"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": NullPool,  # تجنب مشاكل connection pooling مع eventlet
        "connect_args": {"check_same_thread": False},
        "echo": False  # تعطيل SQL logging للتطوير
    }
