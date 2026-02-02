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

from extensions import db, bcrypt, login_manager, migrate, babel, csrf, cache

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

    from config import Config, USE_ONLY_LOCAL_SQLITE, _default_sqlite_path
    app.config.from_object(Config)
    # إجبار SQLite المحلي فقط – لا Render ولا PostgreSQL
    if USE_ONLY_LOCAL_SQLITE:
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{_default_sqlite_path}"
    else:
        uri = (app.config.get('SQLALCHEMY_DATABASE_URI') or '').lower()
        if 'postgres' in uri or 'render.com' in uri:
            app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{_default_sqlite_path}"
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
    # Phase 1 – No global load: accounts, settings, permissions MUST NOT be loaded here
    # or in before_request. Navbar and layout use only these globals (no DB).
    # Each route/blueprint loads what it needs per screen.
    from flask_wtf.csrf import generate_csrf
    @app.context_processor
    def inject_globals():
        from flask_login import current_user

        def can(screen: str, action: str = 'view', branch_scope: str = None) -> bool:
            try:
                if not getattr(current_user, 'is_authenticated', False):
                    return False
                if getattr(current_user, 'username', '') == 'admin' or getattr(current_user, 'id', None) == 1:
                    return True
                if getattr(current_user, 'role', '') == 'admin':
                    return True
                return True
            except Exception:
                return True

        def section_image_for(name: str) -> str:
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


    # لغة الواجهة: الجلسة أولاً ثم معامل الطلب ثم المستخدم ثم المتصفح
    from flask import request, session
    def get_locale():
        loc = session.get('locale')
        if loc in ('ar', 'en'):
            return loc
        loc = (request.args.get('lang') or '').strip().lower()
        if loc in ('ar', 'en'):
            return loc
        try:
            from flask_login import current_user
            if getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'language_pref', None):
                return current_user.language_pref
        except Exception:
            pass
        # Default to Arabic so UI is consistent; use EN/ع in navbar to switch
        return 'ar'

    if babel is not None:
        try:
            babel.init_app(app, locale_selector=get_locale)
        except Exception:
            babel.init_app(app)
    else:
        pass

    @app.context_processor
    def inject_locale():
        return {'get_locale': get_locale}

    # ربط الكائنات بالتطبيق
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    if cache is not None:
        cache.init_app(app)
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

    # تسجيل Blueprints
    from app.routes import main, vat
    try:
        from app.emp_pay import emp_pay_bp
    except Exception:
        emp_pay_bp = None
    app.register_blueprint(main)
    app.register_blueprint(vat)
    try:
        from app.reports.payroll_reports import reports_bp
        app.register_blueprint(reports_bp)
    except Exception:
        pass
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
    try:
        from routes.expenses import bp as expenses_bp
        app.register_blueprint(expenses_bp)
    except Exception:
        pass
    try:
        from routes.purchases import bp as purchases_bp
        app.register_blueprint(purchases_bp)
    except Exception:
        pass
    try:
        from routes.suppliers import bp as suppliers_bp
        app.register_blueprint(suppliers_bp)
    except Exception:
        pass
    try:
        from routes.customers import bp as customers_bp
        app.register_blueprint(customers_bp)
        try:
            csrf.exempt('customers.api_customers_create')
        except Exception:
            pass
    except Exception:
        pass
    try:
        from routes.payments import bp as payments_bp
        app.register_blueprint(payments_bp)
    except Exception:
        pass
    try:
        from routes.inventory import bp as inventory_bp
        app.register_blueprint(inventory_bp)
    except Exception:
        pass
    try:
        from routes.reports import bp as reports_bp
        app.register_blueprint(reports_bp)
    except Exception:
        pass
    try:
        from routes.sales import bp as sales_bp
        app.register_blueprint(sales_bp)
    except Exception:
        pass

    # Ensure tables exist on startup (SQLite only)
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
            # Lightweight auto-migration for SQLite: add missing columns and indexes
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                # Check if supplier_invoice_number column exists
                try:
                    rows = conn.execute(text("PRAGMA table_info(purchase_invoices)")).fetchall()
                    names = {str(r[1]).lower() for r in rows}
                    if 'supplier_invoice_number' not in names:
                        conn.execute(text("ALTER TABLE purchase_invoices ADD COLUMN supplier_invoice_number TEXT"))
                        conn.commit()
                except Exception:
                    pass
                # Create indexes for SQLite
                try:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_type_invoice ON payments (invoice_type, invoice_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales_invoices (created_at)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_purchases_created_at ON purchase_invoices (created_at)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_expenses_created_at ON expense_invoices (created_at)"))
                    conn.commit()
                except Exception:
                    pass
                # Ensure settings table has all model columns (fix "no such column" on save)
                try:
                    from models import Settings
                    existing = set()
                    try:
                        ri = conn.execute(text("PRAGMA table_info(settings)")).fetchall()
                        existing = {str(r[1]).lower() for r in ri}
                    except Exception:
                        pass
                    for col in Settings.__table__.c:
                        c = col.key
                        if c.lower() in existing:
                            continue
                        t = type(col.type).__name__
                        if "Int" in t or "Bool" in t:
                            sqltyp = "INTEGER"
                        elif "Numeric" in t or "Float" in t or "Real" in t:
                            sqltyp = "REAL"
                        else:
                            sqltyp = "TEXT"
                        try:
                            conn.execute(text("ALTER TABLE settings ADD COLUMN %s %s" % (c, sqltyp)))
                            conn.commit()
                        except Exception:
                            pass
                except Exception:
                    pass
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
        with app.app_context():
            from app.routes import refresh_chart_from_db
            refresh_chart_from_db()
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
