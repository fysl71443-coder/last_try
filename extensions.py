"""
Flask Extensions
================
All Flask extensions are initialized here to avoid circular imports
and make them easily accessible throughout the application.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_login import LoginManager
try:
    from flask_babel import Babel
except Exception:
    class Babel:  # Fallback stub for environments without flask_babel
        def __init__(self, *args, **kwargs):
            pass
        def init_app(self, app):
            try:
                # Provide a minimal gettext to avoid template failures
                app.jinja_env.globals.setdefault('_', lambda s, **kw: s.format(**kw) if kw else s)
            except Exception:
                pass
from flask_wtf.csrf import CSRFProtect

# Initialize extensions with eventlet-compatible session options
db = SQLAlchemy(session_options={
    "autocommit": False,
    "autoflush": False,
    "expire_on_commit": False  # مهم لـ eventlet
})
bcrypt = Bcrypt()
migrate = Migrate()
login_manager = LoginManager()
babel = Babel()
csrf = CSRFProtect()

# SocketIO will be initialized conditionally when needed
socketio = None
