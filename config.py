import os
from sqlalchemy.pool import NullPool

# ─── إعداد قاعدة ذكي حسب البيئة (الحل المثالي) ───
# ✔ تطوير محلي: SQLite (سريع، لا إعداد)
# ✔ إنتاج: PostgreSQL من DATABASE_URL (مستقر، لا فقدان بيانات)
# 📌 لا يوجد أي مسار SQLite معرّف خارج هذا الملف
# ─────────────────────────────────────────────────────────────────

_base_dir = os.path.abspath(os.path.dirname(__file__))
_project_root = _base_dir
_instance_dir = os.path.join(_project_root, 'instance')
os.makedirs(_instance_dir, exist_ok=True)

ENV = os.getenv("ENV", "development")

if ENV == "production":
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be set in production (ENV=production)")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    _database_uri = DATABASE_URL
else:
    # تطوير: SQLite في instance/ — دائماً ملف فعلي (لا :memory:)؛ غيّر LOCAL_SQLITE_PATH إن شئت
    _sqlite_path = os.getenv("LOCAL_SQLITE_PATH") or os.path.join(_instance_dir, "accounting_app.db")
    _sqlite_path = os.path.abspath(_sqlite_path)
    if ":memory:" in _sqlite_path or not _sqlite_path.strip():
        _sqlite_path = os.path.join(_instance_dir, "accounting_app.db")
        _sqlite_path = os.path.abspath(_sqlite_path)
    _database_uri = "sqlite:///" + _sqlite_path.replace("\\", "/")

# للمساعدات والسكربتات فقط (قراءة المسار المحلي عند التطوير)
LOCAL_SQLITE_PATH_FOR_SCRIPTS = os.getenv("LOCAL_SQLITE_PATH") or os.path.join(_instance_dir, "accounting_app.db")


def _engine_options_for(db_uri: str):
    """خيارات المحرك: SQLite (NullPool, check_same_thread) أو PostgreSQL (pool_pre_ping)."""
    if db_uri and "sqlite" in db_uri:
        return {
            "poolclass": NullPool,
            "connect_args": {"check_same_thread": False},
            "echo": False,
        }
    return {
        "pool_pre_ping": True,
        "echo": False,
    }


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

    # CSRF Protection settings
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False

    # Cookie/session settings (Render-friendly defaults)
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '1' if os.getenv('RENDER_EXTERNAL_URL') else '0').strip().lower() in ('1','true','yes','on')
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PREFERRED_URL_SCHEME = 'https' if SESSION_COOKIE_SECURE else 'http'

    # Admin settings
    ADMIN_DELETE_PASSWORD = os.getenv('ADMIN_DELETE_PASSWORD', '1991')

    # Phase 3 – Cache (Redis when REDIS_URL set, else SimpleCache for local dev)
    _redis_url = os.getenv('REDIS_URL', '').strip()
    if _redis_url and _redis_url.startswith('redis://'):
        CACHE_TYPE = 'redis'
        CACHE_REDIS_URL = _redis_url
    else:
        CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_KEY_PREFIX = 'ctpi_'

    SQLALCHEMY_DATABASE_URI = _database_uri
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options_for(SQLALCHEMY_DATABASE_URI)

    # Babel / i18n
    BABEL_DEFAULT_LOCALE = os.getenv('BABEL_DEFAULT_LOCALE', 'ar')
    BABEL_SUPPORTED_LOCALES = ['ar', 'en']
    BABEL_TRANSLATION_DIRECTORIES = os.getenv('BABEL_TRANSLATION_DIRECTORIES') or os.path.join(_project_root, 'translations')
