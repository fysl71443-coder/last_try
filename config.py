import os
from sqlalchemy.pool import NullPool


# Resolve database configuration dynamically so Render (PostgreSQL) works
_base_dir = os.path.abspath(os.path.dirname(__file__))
_project_root = os.path.abspath(os.path.join(_base_dir, '..'))
_instance_dir = os.path.join(_project_root, 'instance')
os.makedirs(_instance_dir, exist_ok=True)

_default_sqlite_path = os.getenv('LOCAL_SQLITE_PATH') or os.path.join(_instance_dir, 'accounting_app.db')
_database_url = os.getenv('DATABASE_URL')
if _database_url:
    # Render supplies postgres://, but SQLAlchemy needs postgresql://
    if _database_url.startswith('postgres://'):
        _database_url = _database_url.replace('postgres://', 'postgresql://', 1)
else:
    _database_url = f"sqlite:///{_default_sqlite_path}"


def _engine_options_for(db_uri: str):
    """Return SQLAlchemy engine options suited for the current backend."""
    if db_uri.startswith('sqlite'):
        return {
            "poolclass": NullPool,  # Avoid connection pooling issues on SQLite
            "connect_args": {"check_same_thread": False},
            "echo": False,
        }
    # Default options for PostgreSQL / other production databases
    return {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv('DB_POOL_RECYCLE', '280')),
        "pool_size": int(os.getenv('DB_POOL_SIZE', '5')),
        "max_overflow": int(os.getenv('DB_MAX_OVERFLOW', '10')),
    }


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

    # CSRF Protection settings
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens
    WTF_CSRF_SSL_STRICT = False  # Allow CSRF over HTTP for development

    # Cookie/session settings (Render-friendly defaults)
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '1' if os.getenv('RENDER_EXTERNAL_URL') else '0').strip().lower() in ('1','true','yes','on')
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PREFERRED_URL_SCHEME = 'https' if SESSION_COOKIE_SECURE else 'http'

    # Admin settings
    ADMIN_DELETE_PASSWORD = os.getenv('ADMIN_DELETE_PASSWORD', '1991')

    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options_for(SQLALCHEMY_DATABASE_URI)
