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

    DATABASE_URL = os.getenv("DATABASE_URL")

    if DATABASE_URL:
        # Normalize postgres:// to postgresql:// (Render compatibility)
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
        SQLALCHEMY_ENGINE_OPTIONS = {
            "poolclass": NullPool,
            "pool_pre_ping": True,
            "echo": False
        }
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"
        SQLALCHEMY_ENGINE_OPTIONS = {
            "poolclass": NullPool,  # تجنب مشاكل connection pooling مع eventlet
            "connect_args": {"check_same_thread": False},
            "echo": False  # تعطيل SQL logging للتطوير
        }
