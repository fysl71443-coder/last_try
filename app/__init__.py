import os
from flask import Flask
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
try:
    from flask_babel import Babel
except Exception:
    class Babel:  # Fallback stub for environments without flask_babel
        def __init__(self, *args, **kwargs):
            pass
        def init_app(self, app):
            try:
                app.jinja_env.globals.setdefault('_', lambda s, **kw: s.format(**kw) if kw else s)
            except Exception:
                pass
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

    try:
        os.environ.setdefault('TZ', 'Asia/Riyadh')
        import time as _time
        if hasattr(_time, 'tzset'):
            _time.tzset()
    except Exception:
        pass

    # Honor reverse proxy headers (Render), fix scheme/host/port
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    except Exception:
        pass

    # Load configuration (prefers local SQLite when no DATABASE_URL)
    from config import Config
    app.config.from_object(Config)
    # Ensure secrets
    app.config.setdefault('SECRET_KEY', os.getenv('SECRET_KEY', os.urandom(24)))
    app.config.setdefault('WTF_CSRF_SECRET_KEY', app.config['SECRET_KEY'])
    # Feature flags (disabled by default for production control)
    try:
        app.config.setdefault('INVENTORY_INTEL_ENABLED', bool(int(os.getenv('INVENTORY_INTEL_ENABLED', '0'))))
    except Exception:
        app.config.setdefault('INVENTORY_INTEL_ENABLED', False)
    # Timezone helpers for templates
    try:
        KSA_TZ = ZoneInfo("Asia/Riyadh") if ZoneInfo else None
    except Exception:
        KSA_TZ = None
    def get_saudi_now():
        try:
            return datetime.now(KSA_TZ) if KSA_TZ else datetime.now()
        except Exception:
            return datetime.now()
    def get_saudi_today():
        try:
            return get_saudi_now().date()
        except Exception:
            return datetime.now().date()

    try:
        app.jinja_env.globals.setdefault('get_saudi_now', get_saudi_now)
        app.jinja_env.globals.setdefault('get_saudi_today', get_saudi_today)
    except Exception:
        pass

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
            'get_saudi_now': get_saudi_now,
            'get_saudi_today': get_saudi_today,
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
    # Exempt bulk salary receipt print (HTML POST not sensitive)
    csrf.exempt('main.salary_receipt_bulk')
    # Exempt employee payment APIs to allow AJAX calls from UVD screen
    try:
        csrf.exempt('emp_pay.api_employee_pay_salary')
        csrf.exempt('emp_pay.api_employee_pay_salary_bulk')
        csrf.exempt('emp_pay.api_employee_pay_health')
    except Exception:
        pass
    # Flask-Login setup: login view and user loader
    login_manager.login_view = 'main.login'
    from models import User
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # Block legacy employee-related screens globally (allow new UVD and settings/pay)
    @app.before_request
    def _blk_emp_screens():
        from flask import request
        try:
            p = (request.path or '').lower()
        except Exception:
            p = ''
        # Block only the legacy payroll dashboard route; allow new salaries/pay and salary receipts
        if p.startswith('/employees/payroll'):
            return ('', 404)



    # تسجيل Blueprints
    from app.routes import main, vat
    try:
        from app.emp_pay import emp_pay_bp
    except Exception:
        emp_pay_bp = None
    from app.reports.payroll_reports import reports_bp
    app.register_blueprint(main)
    app.register_blueprint(vat)
    app.register_blueprint(reports_bp)
    if emp_pay_bp:
        app.register_blueprint(emp_pay_bp)
    # Alias certain API endpoints without blueprint prefix to avoid template BuildError
    try:
        vf = app.view_functions
        alias_map = {
            'api_sales_mark_platform_unpaid': 'main.api_sales_mark_platform_unpaid',
            'api_sales_mark_unpaid_paid': 'main.api_sales_mark_unpaid_paid',
            'api_sales_batch_pay': 'main.api_sales_batch_pay',
            'api_sales_pay': 'main.api_sales_pay',
        }
        for alias, orig in alias_map.items():
            if orig in vf and alias not in vf:
                app.add_url_rule(
                    '/api/sales/mark-platform-unpaid' if alias=='api_sales_mark_platform_unpaid' else (
                        '/api/sales/mark-unpaid-paid' if alias=='api_sales_mark_unpaid_paid' else (
                            '/api/sales/batch-pay' if alias=='api_sales_batch_pay' else '/api/sales/pay'
                        )
                    ),
                    endpoint=alias,
                    view_func=vf[orig],
                    methods=['GET','POST']
                )
    except Exception:
        pass

    # Override Jinja url_for with safe wrapper that tries blueprint fallback
    try:
        from flask import url_for as _flask_url_for
        def url_for_safe(endpoint, *args, **kwargs):
            try:
                return _flask_url_for(endpoint, *args, **kwargs)
            except Exception:
                try:
                    return _flask_url_for(f'main.{endpoint}', *args, **kwargs)
                except Exception:
                    # Known alias fallback for platform unpaid normalization
                    if endpoint == 'api_sales_mark_platform_unpaid':
                        return '/api/sales/mark-platform-unpaid'
                    return '#'
        app.jinja_env.globals['url_for'] = url_for_safe
    except Exception:
        pass
    try:
        from routes.journal import bp as journal_bp
        app.register_blueprint(journal_bp)
    except Exception:
        pass
    try:
        from routes.financials import bp as financials_bp
        app.register_blueprint(financials_bp)
    except Exception:
        pass

    # Ensure tables exist on startup (useful for local SQLite/Postgres runs)
    try:
        with app.app_context():
            db.create_all()
            try:
                from sqlalchemy import text
                with db.engine.connect() as conn:
                    cols = conn.execute(text("PRAGMA table_info('suppliers')")).fetchall()
                    col_names = {str(c[1]).lower() for c in cols}
                    if 'payment_method' not in col_names:
                        conn.execute(text("ALTER TABLE suppliers ADD COLUMN payment_method VARCHAR(20) DEFAULT 'CASH'"))
                        conn.commit()
                    cols_pi = conn.execute(text("PRAGMA table_info('purchase_invoices')")).fetchall()
                    col_names_pi = {str(c[1]).lower() for c in cols_pi}
                    if 'supplier_invoice_number' not in col_names_pi:
                        conn.execute(text("ALTER TABLE purchase_invoices ADD COLUMN supplier_invoice_number VARCHAR(100)"))
                        conn.commit()
                    if 'notes' not in col_names_pi:
                        conn.execute(text("ALTER TABLE purchase_invoices ADD COLUMN notes TEXT"))
                        conn.commit()
            except Exception:
                pass
            # Lightweight auto-migration for Postgres: add purchase_invoices.supplier_invoice_number if missing
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                if conn.dialect.name == 'postgresql':
                    rows = conn.execute(text("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name='purchase_invoices'
                    """)).fetchall()
                    names = {str(r[0]).lower() for r in rows}
                    if 'supplier_invoice_number' not in names:
                        conn.execute(text("ALTER TABLE purchase_invoices ADD COLUMN supplier_invoice_number VARCHAR(100)"))
                        conn.commit()
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_type_invoice ON payments (invoice_type, invoice_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales_invoices (created_at)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_purchases_created_at ON purchase_invoices (created_at)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_expenses_created_at ON expense_invoices (created_at)"))
                    conn.commit()
        except Exception:
            pass
            if ext_db is not None:
                try:
                    ext_db.create_all()
                except Exception:
                    pass
    except Exception:
        pass
    try:
        from logging_setup import setup_logging
        setup_logging(app)
    except Exception:
        pass

    return app

# Export a ready-to-use app instance for test clients and simple scripts
app = create_app()
