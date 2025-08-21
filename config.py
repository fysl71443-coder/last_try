import os
from sqlalchemy.pool import NullPool

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

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
            "echo": True  # تفعيل SQL logging للتطوير
        }
