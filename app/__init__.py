import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
# Also support legacy extensions module models
try:
    from extensions import db as ext_db
except Exception:
    ext_db = None

# إنشاء كائنات db و login و bcrypt فقط مرة واحدة

# These objects will be imported in models/routes
# and initialized once per app instance

from extensions import db, bcrypt, login_manager, migrate, babel, csrf

def create_app(config_class=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..'))
    template_dir = os.path.join(project_root, 'templates')
    static_dir = os.path.join(project_root, 'static')
    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path='/static'
    )

    # Load configuration (prefers local SQLite when no DATABASE_URL)
    from config import Config
    app.config.from_object(Config)
    # Ensure secrets
    app.config.setdefault('SECRET_KEY', os.getenv('SECRET_KEY', os.urandom(24)))
    app.config.setdefault('WTF_CSRF_SECRET_KEY', app.config['SECRET_KEY'])
    # Inject common template globals (asset version + CSRF token helper)
    from flask_wtf.csrf import generate_csrf
    @app.context_processor
    def inject_globals():
        # simple permission helper: allow everything for now (can be tightened later)
        from flask_login import current_user
        def can(module, action='view'):
            # In future, check current_user.role/permissions here
            return bool(getattr(current_user, 'is_authenticated', False))
        # simple image chooser for categories
        def section_image_for(name: str):
            try:
                n = (name or '').lower()
                # Use a single existing placeholder image to avoid 404s in development
                return '/static/logo.svg'
            except Exception:
                return '/static/logo.svg'
        return {
            'ASSET_VERSION': os.getenv('ASSET_VERSION', ''),
            'csrf_token': generate_csrf,
            'can': can,
            'settings': None,
            'section_image_for': section_image_for,
        }


    # ربط الكائنات بالتطبيق
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app)
    csrf.init_app(app)
    # Flask-Login setup: login view and user loader
    login_manager.login_view = 'main.login'
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None



    # تسجيل Blueprints
    from app.routes import main, vat, financials
    app.register_blueprint(main)
    app.register_blueprint(vat)
    app.register_blueprint(financials)

    # Ensure tables exist on startup (useful for local SQLite runs)
    try:
        with app.app_context():
            db.create_all()
            if ext_db is not None:
                try:
                    ext_db.create_all()
                except Exception:
                    pass
    except Exception:
        pass

    return app
