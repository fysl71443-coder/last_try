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
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect

# Initialize extensions with optimized session options
db = SQLAlchemy(session_options={
    "autoflush": False,  # تقليل مشاكل الـ lock
    "autocommit": False,
    "expire_on_commit": True
})
bcrypt = Bcrypt()
migrate = Migrate()
login_manager = LoginManager()
babel = Babel()
csrf = CSRFProtect()

# SocketIO will be initialized conditionally when needed
socketio = None
