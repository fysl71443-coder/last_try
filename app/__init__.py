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
        # Permission helper using AppKV-based storage (user_perms:<scope>:<uid>)
        import json
        from flask import request
        from flask_login import current_user
        from app.models import AppKV

        def _normalize_scope(s: str) -> str:
            s = (s or '').strip().lower()
            if s in ('place', 'palace', 'india', 'palace_india'): return 'place_india'
            if s in ('china', 'china town', 'chinatown'): return 'china_town'
            return s or 'all'

        def _read_perms(uid: int, scope: str):
            try:
                k = f"user_perms:{scope}:{int(uid)}"
                row = AppKV.query.filter_by(k=k).first()
                if not row:
                    return {}
                data = json.loads(row.v)
                items = data.get('items') or []
                out = {}
                for it in items:
                    key = it.get('screen_key')
                    if not key:
                        continue
                    out[key] = {
                        'view': bool(it.get('view')),
                        'add': bool(it.get('add')),
                        'edit': bool(it.get('edit')),
                        'delete': bool(it.get('delete')),
                        'print': bool(it.get('print')),
                    }
                return out
            except Exception:
                return {}

        def can(screen: str, action: str = 'view', branch_scope: str = None) -> bool:
            try:
                # Admins can do everything
                if getattr(current_user, 'is_authenticated', False):
                    # Treat username 'admin' (or user id==1) as superuser since User has no role field
                    if getattr(current_user, 'username', '') == 'admin' or getattr(current_user, 'id', None) == 1:
                        return True
                    if getattr(current_user, 'role', '') == 'admin':
                        return True
                else:
                    return False
                # Resolve scopes to check
                if branch_scope:
                    scopes = [_normalize_scope(branch_scope), 'all']
                else:
                    # For top-level menus with no explicit branch, consider any allowed scope
                    scopes = ['all', 'china_town', 'place_india']
                # Evaluate
                for sc in scopes:
                    perms = _read_perms(current_user.id, sc)
                    scr = perms.get(screen)
                    if scr and scr.get(action):
                        return True
                return False
            except Exception:
                # Fail-closed for non-admins
                return False

        # simple image chooser for categories
        def section_image_for(name: str):
            try:
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
    # Exempt API routes from CSRF
    csrf.exempt('main.api_table_layout')
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
