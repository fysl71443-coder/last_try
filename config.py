import os
from sqlalchemy.pool import NullPool

# ─── استخدام SQLite المحلي فقط – لا Render ولا PostgreSQL ───
# ─── قاعدة البيانات الدائمة (لا تضييع بيانات) ───
# ❌ لا نستخدم أبداً: sqlite:///:memory: (يُمسح عند إعادة التشغيل)
# ❌ لا نستخدم: /tmp أو مجلد مؤقت (يُمسح عند إعادة التشغيل)
# ✅ مسار ثابت داخل المشروع: instance/accounting_app.db (أو LOCAL_SQLITE_PATH مثل data/db.sqlite)
# ✅ كل تعديل يُحفظ عبر db.session.commit() (Flask-SQLAlchemy يلتزم نهاية الطلب)
# ─────────────────────────────────────────────────────────────────
USE_ONLY_LOCAL_SQLITE = True
_base_dir = os.path.abspath(os.path.dirname(__file__))
_project_root = _base_dir
_instance_dir = os.path.join(_project_root, 'instance')
os.makedirs(_instance_dir, exist_ok=True)
_default_sqlite_path = os.getenv('LOCAL_SQLITE_PATH') or os.path.join(_instance_dir, 'accounting_app.db')
# تجاهل DATABASE_URL تماماً – لا نقرأ من Render أبداً
_database_url = f"sqlite:///{_default_sqlite_path}"


def _engine_options_for(db_uri: str):
    """Return SQLAlchemy engine options for SQLite only."""
    # استخدام SQLite فقط - لا حاجة لخيارات PostgreSQL
    return {
        "poolclass": NullPool,  # Avoid connection pooling issues on SQLite
        "connect_args": {"check_same_thread": False},
        "echo": False,
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

    # Phase 3 – Cache (Redis when REDIS_URL set, else SimpleCache for local dev)
    _redis_url = os.getenv('REDIS_URL', '').strip()
    if _redis_url and _redis_url.startswith('redis://'):
        CACHE_TYPE = 'redis'
        CACHE_REDIS_URL = _redis_url
    else:
        CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 min default
    CACHE_KEY_PREFIX = 'ctpi_'

    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options_for(SQLALCHEMY_DATABASE_URI)

    # Babel / i18n — تبديل اللغة (عربي / إنجليزي)
    BABEL_DEFAULT_LOCALE = os.getenv('BABEL_DEFAULT_LOCALE', 'ar')
    BABEL_SUPPORTED_LOCALES = ['ar', 'en']
    BABEL_TRANSLATION_DIRECTORIES = os.getenv('BABEL_TRANSLATION_DIRECTORIES') or os.path.join(_project_root, 'translations')
