import eventlet
eventlet.monkey_patch()

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from extensions import db
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_babel import Babel, gettext as _
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect, CSRFError
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')
os.makedirs(instance_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(instance_dir, 'accounting_app.db')}"

# Production DB (Render) support — override sqlite if DATABASE_URL provided
_db_url = os.getenv('DATABASE_URL')
if _db_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = _db_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Babel / i18n
app.config['BABEL_DEFAULT_LOCALE'] = os.getenv('BABEL_DEFAULT_LOCALE', 'en')
babel = Babel()
# CSRF protection for forms and APIs (for APIs, use JSON + header in future)
# Trust proxy headers (Render)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Secure cookies config
app.config.update(
    REMEMBER_COOKIE_SECURE=True,
    REMEMBER_COOKIE_HTTPONLY=True,
    PREFERRED_URL_SCHEME='https'
)

csrf = CSRFProtect(app)



# --- Security hardening (cookies, headers, CORS) ---
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# tighten SocketIO CORS in production (Render sets RENDER to true)
allowed_origins = os.getenv('ALLOWED_ORIGINS') or os.getenv('RENDER_EXTERNAL_URL') or '*'
socketio = SocketIO(app, cors_allowed_origins=allowed_origins)

# security headers
@app.after_request
def set_security_headers(resp):
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    resp.headers['Referrer-Policy'] = 'no-referrer-when-downgrade'
    # basic CSP allowing self; adjust as needed for CDNs
    resp.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com"
    return resp

# Create instance directory if it doesn't exist
os.makedirs('instance', exist_ok=True)
from flask import session


db.init_app(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Basic error logging to file (errors only)
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')


def save_to_db(instance):
    try:
        db.session.add(instance)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logging.error('Database Error: %s', e, exc_info=True)
        return False


# Rate limiting for login attempts
login_attempts = {}  # { ip_address: {"count": int, "last_attempt": datetime} }

# Import models after db created
import models
models.db = db
from models import User, Invoice, SalesInvoice, SalesInvoiceItem, Product, RawMaterial, Meal, MealIngredient, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Employee, Salary, Payment, Account, LedgerEntry

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_locale():
    # language selection from query param, user pref, or accept headers
    lang = request.args.get('lang')
    if lang:
        return lang
    try:
        if current_user.is_authenticated:
            return getattr(current_user, 'language_pref', None) or app.config.get('BABEL_DEFAULT_LOCALE', 'ar')
    except Exception:
        pass
    return request.accept_languages.best_match(['ar', 'en']) or 'ar'

# Health check endpoint for Render
@app.route('/healthz')
def healthz():
    return jsonify(status='ok'), 200

# Disable Flask debug by default when running under Gunicorn/Render
if os.getenv('RENDER') or os.getenv('GUNICORN_CMD_ARGS'):
    app.config['DEBUG'] = False

@app.context_processor
def inject_settings():
    try:
        from models import Settings
        s = Settings.query.first()
        return dict(settings=s)
    except Exception:
        return dict(settings=None)

# Make CSRF token generator available in templates for forms and JS
@app.context_processor
def inject_csrf_token():
    from flask_wtf.csrf import generate_csrf
    return dict(csrf_token=generate_csrf)

@app.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    current = session.get('theme') or (getattr(inject_settings().get('settings'), 'default_theme', 'light'))
    session['theme'] = 'dark' if current != 'dark' else 'light'
    return redirect(request.referrer or url_for('dashboard'))

babel.init_app(app, locale_selector=get_locale)

# Make get_locale available in templates
@app.context_processor
def inject_conf_vars():
    return {
        'get_locale': get_locale
    }

@app.route('/')
def index():
    return redirect(url_for('login'))

from forms import LoginForm, SalesInvoiceForm, RawMaterialForm, MealForm, PurchaseInvoiceForm, ExpenseInvoiceForm, EmployeeForm, SalaryForm
# Register blueprints
try:
    from routes.vat import bp as vat_bp
    app.register_blueprint(vat_bp)
except Exception as _e:
    pass
# Register financials blueprint
try:
    from routes.financials import bp as financials_bp
    app.register_blueprint(financials_bp)
except Exception:
    pass



@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    client_ip = request.remote_addr

    # Check if blocked
    if client_ip in login_attempts:
        attempts_info = login_attempts[client_ip]
        if attempts_info["count"] >= 5 and datetime.utcnow() - attempts_info["last_attempt"] < timedelta(minutes=10):
            flash(_('Too many attempts. Try again later. / عدد المحاولات كبير، حاول لاحقاً.'), 'danger')
            return render_template('login.html', form=form)

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            if not user.active:
                flash(_('حسابك غير مفعل / Your account is not active.'), 'danger')
                return render_template('login.html', form=form)

            login_user(user, remember=form.remember.data)
            user.last_login()
            db.session.commit()
            login_attempts.pop(client_ip, None)  # reset attempts
            flash(_('تم تسجيل الدخول بنجاح / Logged in successfully.'), 'success')
            return redirect(url_for('dashboard'))

        # Wrong credentials — increment counter
        if client_ip not in login_attempts:
            login_attempts[client_ip] = {"count": 1, "last_attempt": datetime.utcnow()}
        else:
            login_attempts[client_ip]["count"] += 1
            login_attempts[client_ip]["last_attempt"] = datetime.utcnow()

        flash(_('اسم المستخدم أو كلمة المرور غير صحيحة / Invalid credentials.'), 'danger')

    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('تم تسجيل الخروج / Logged out.'), 'info')
    return redirect(url_for('login'))

# Dashboard routes
@app.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():
    import json
    # Permissions: POST requires 'add'
    if request.method == 'POST' and not can_perm('sales','add'):
        flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
        return redirect(url_for('sales'))

    # Get meals for dropdown (ready meals from cost management)
    meals = Meal.query.filter_by(active=True).all()
    product_choices = [(0, _('Select Meal / اختر الوجبة'))] + [(m.id, m.display_name) for m in meals]

    form = SalesInvoiceForm()

    # Set product choices for all item forms
    for item_form in form.items:
        item_form.product_id.choices = product_choices

    # Prepare meals JSON for JavaScript
    products_json = json.dumps([{
        'id': m.id,
        'name': m.display_name,
        'price_before_tax': float(m.selling_price)  # Use selling price from cost calculation
    } for m in meals])

    if form.validate_on_submit():
        # Generate invoice number
        last_invoice = SalesInvoice.query.order_by(SalesInvoice.id.desc()).first()
        if last_invoice:
            last_num = int(last_invoice.invoice_number.split('-')[-1])
            invoice_number = f'SAL-2024-{last_num + 1:03d}'
        else:
            invoice_number = 'SAL-2024-001'

        # Calculate totals
        total_before_tax = 0
        total_tax = 0
        total_discount = 0
        tax_rate = 0.15

        # Create invoice
        invoice = SalesInvoice(
            invoice_number=invoice_number,
            date=form.date.data,
            payment_method=form.payment_method.data,
            branch=form.branch.data,
            customer_name=form.customer_name.data,
            total_before_tax=0,  # Will be calculated
            tax_amount=0,  # Will be calculated
            discount_amount=0,  # Will be calculated
            total_after_tax_discount=0,  # Will be calculated
            status='unpaid',
            user_id=current_user.id
        )
        db.session.add(invoice)
        db.session.flush()

        # Add invoice items and calculate totals
        for item_form in form.items.entries:
            if item_form.product_id.data and item_form.product_id.data != 0:  # Valid meal selected
                meal = Meal.query.get(item_form.product_id.data)
                if meal:
                    qty = item_form.quantity.data
                    discount = float(item_form.discount.data or 0)

                    # Calculate amounts using meal's selling price
                    price_before_tax = float(meal.selling_price) * qty
                    tax = price_before_tax * tax_rate
                    total_item = price_before_tax + tax - discount

                    # Add to invoice totals
                    total_before_tax += price_before_tax
                    total_tax += tax
                    total_discount += discount

                    # Create invoice item
                    inv_item = SalesInvoiceItem(
                        invoice_id=invoice.id,
                        product_name=meal.display_name,
                        quantity=qty,
                        price_before_tax=meal.selling_price,
                        tax=tax,
                        discount=discount,
                        total_price=total_item
                    )
                    db.session.add(inv_item)

        # Update invoice totals
        total_after_tax_discount = total_before_tax + total_tax - total_discount
        invoice.total_before_tax = total_before_tax
        invoice.tax_amount = total_tax
        invoice.discount_amount = total_discount
        invoice.total_after_tax_discount = total_after_tax_discount

        db.session.commit()
        # Post to ledger (Revenue, VAT Output, Cash/AR)
        try:
            # Ensure core accounts exist
            def get_or_create(code, name, type_):
                acc = Account.query.filter_by(code=code).first()
                if not acc:
                    acc = Account(code=code, name=name, type=type_)
                    db.session.add(acc); db.session.flush()
                return acc
            rev_acc = get_or_create('4000', 'Sales Revenue', 'REVENUE')
            vat_out_acc = get_or_create('2100', 'VAT Output', 'LIABILITY')
            cash_acc = get_or_create('1000', 'Cash', 'ASSET')
            ar_acc = get_or_create('1100', 'Accounts Receivable', 'ASSET')

            # Determine settlement account based on payment method
            settle_acc = cash_acc if invoice.payment_method in ['cash','mada','visa','bank'] else ar_acc
            # Revenue entry
            db.session.add(LedgerEntry(date=invoice.date, account_id=rev_acc.id, credit=invoice.total_before_tax, debit=0, description=f'Sales {invoice.invoice_number}'))
            # VAT output
            db.session.add(LedgerEntry(date=invoice.date, account_id=vat_out_acc.id, credit=invoice.tax_amount, debit=0, description=f'VAT Output {invoice.invoice_number}'))
            # Settlement (debit)
            db.session.add(LedgerEntry(date=invoice.date, account_id=settle_acc.id, debit=invoice.total_after_tax_discount, credit=0, description=f'Settlement {invoice.invoice_number}'))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error('Ledger posting (sales) failed: %s', e, exc_info=True)


        # Emit real-time update
        socketio.emit('sales_update', {
            'invoice_number': invoice_number,
            'branch': form.branch.data,
            'total': float(total_after_tax_discount)
        }, broadcast=True)

        flash(_('Invoice created successfully / تم إنشاء الفاتورة بنجاح'), 'success')
        return redirect(url_for('sales'))

    # Set default date for new form
    if request.method == 'GET':
        form.date.data = datetime.utcnow().date()

    # Get all sales invoices
    invoices = SalesInvoice.query.order_by(SalesInvoice.date.desc()).all()
    return render_template('sales.html', form=form, invoices=invoices, products_json=products_json)

@app.route('/purchases', methods=['GET', 'POST'])
@login_required
def purchases():
    import json

    # Get raw materials for dropdown
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    material_choices = [(0, _('Select Raw Material / اختر المادة الخام'))] + [(m.id, m.display_name) for m in raw_materials]

    form = PurchaseInvoiceForm()

    # Set material choices for all item forms
    for item_form in form.items:
        item_form.raw_material_id.choices = material_choices

    # Prepare materials JSON for JavaScript
    materials_json = json.dumps([{
        'id': m.id,
        'name': m.display_name,
        'cost_per_unit': float(m.cost_per_unit),
        'unit': m.unit,
        'stock_quantity': float(m.stock_quantity)
    } for m in raw_materials])

    if form.validate_on_submit():
        # Generate invoice number
        last_invoice = PurchaseInvoice.query.order_by(PurchaseInvoice.id.desc()).first()
        if last_invoice:
            last_num = int(last_invoice.invoice_number.split('-')[-1])
            invoice_number = f'PUR-2024-{last_num + 1:03d}'
        else:
            invoice_number = 'PUR-2024-001'

        # Calculate totals
        total_before_tax = 0
        total_tax = 0
        total_discount = 0
        tax_rate = 0.15

        # Create invoice
        invoice = PurchaseInvoice(
            invoice_number=invoice_number,
            date=form.date.data,
            supplier_name=form.supplier_name.data,
            payment_method=form.payment_method.data,
            total_before_tax=0,  # Will be calculated
            tax_amount=0,  # Will be calculated
            discount_amount=0,  # Will be calculated
            total_after_tax_discount=0,  # Will be calculated
            status='unpaid',
            user_id=current_user.id
        )
        db.session.add(invoice)
        db.session.flush()

        # Add invoice items and update stock
        for item_form in form.items.entries:
            if item_form.raw_material_id.data and item_form.raw_material_id.data != 0:  # Valid material selected
                raw_material = RawMaterial.query.get(item_form.raw_material_id.data)
                if raw_material:
                    qty = float(item_form.quantity.data)
                    unit_price = float(item_form.price_before_tax.data)
                    discount = float(item_form.discount.data or 0)

                    # Calculate amounts
                    price_before_tax = unit_price * qty
                    tax = price_before_tax * tax_rate
                    total_item = price_before_tax + tax - discount

                    # Add to invoice totals
                    total_before_tax += price_before_tax
                    total_tax += tax
                    total_discount += discount

                    # Update raw material stock quantity
                    raw_material.stock_quantity += qty

                    # Update cost per unit (weighted average)
                    if raw_material.stock_quantity > 0:
                        old_total_cost = float(raw_material.cost_per_unit) * (float(raw_material.stock_quantity) - qty)
                        new_total_cost = old_total_cost + (unit_price * qty)
                        raw_material.cost_per_unit = new_total_cost / float(raw_material.stock_quantity)

                    # Create invoice item
                    inv_item = PurchaseInvoiceItem(
                        invoice_id=invoice.id,
                        raw_material_id=raw_material.id,
                        raw_material_name=raw_material.display_name,
                        quantity=qty,
                        price_before_tax=unit_price,
                        tax=tax,
                        discount=discount,
                        total_price=total_item
                    )
                    db.session.add(inv_item)


        # Update invoice totals
        total_after_tax_discount = total_before_tax + total_tax - total_discount
        invoice.total_before_tax = total_before_tax
        invoice.tax_amount = total_tax
        invoice.discount_amount = total_discount
        invoice.total_after_tax_discount = total_after_tax_discount
        # Update invoice totals
        total_after_tax_discount = total_before_tax + total_tax - total_discount
        invoice.total_before_tax = total_before_tax
        invoice.tax_amount = total_tax
        invoice.discount_amount = total_discount
        invoice.total_after_tax_discount = total_after_tax_discount

        db.session.commit()

        # Post to ledger (Inventory, VAT Input, Cash/AP)
        try:
            def get_or_create(code, name, type_):
                acc = Account.query.filter_by(code=code).first()
                if not acc:
                    acc = Account(code=code, name=name, type=type_)
                    db.session.add(acc)
                    db.session.flush()
                return acc
            inv_acc = get_or_create('1200', 'Inventory', 'ASSET')
            vat_in_acc = get_or_create('1300', 'VAT Input', 'ASSET')
            cash_acc = get_or_create('1000', 'Cash', 'ASSET')
            ap_acc = get_or_create('2000', 'Accounts Payable', 'LIABILITY')

            settle_acc = cash_acc if invoice.payment_method in ['cash','mada','visa','bank'] else ap_acc
            db.session.add(LedgerEntry(date=invoice.date, account_id=inv_acc.id, debit=invoice.total_before_tax, credit=0, description=f'Purchase {invoice.invoice_number}'))
            db.session.add(LedgerEntry(date=invoice.date, account_id=vat_in_acc.id, debit=invoice.tax_amount, credit=0, description=f'VAT Input {invoice.invoice_number}'))
            db.session.add(LedgerEntry(date=invoice.date, account_id=settle_acc.id, credit=invoice.total_after_tax_discount, debit=0, description=f'Settlement {invoice.invoice_number}'))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error('Ledger posting (purchase) failed: %s', e, exc_info=True)


        db.session.commit()

        # Emit real-time update
        socketio.emit('purchase_update', {
            'invoice_number': invoice_number,
            'supplier': form.supplier_name.data,
            'total': float(total_after_tax_discount)
        }, broadcast=True)

        flash(_('Purchase invoice created and stock updated successfully / تم إنشاء فاتورة الشراء وتحديث المخزون بنجاح'), 'success')
        return redirect(url_for('purchases'))

    # Set default date for new form
    if request.method == 'GET':
        form.date.data = datetime.utcnow().date()

    # Get all purchase invoices
    invoices = PurchaseInvoice.query.order_by(PurchaseInvoice.date.desc()).all()
    return render_template('purchases.html', form=form, invoices=invoices, materials_json=materials_json)

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    form = ExpenseInvoiceForm()

    if form.validate_on_submit():
        # Generate invoice number
        last_invoice = ExpenseInvoice.query.order_by(ExpenseInvoice.id.desc()).first()
        if last_invoice:
            last_num = int(last_invoice.invoice_number.split('-')[-1])
            invoice_number = f'EXP-2024-{last_num + 1:03d}'
        else:
            invoice_number = 'EXP-2024-001'

        # Calculate totals
        total_before_tax = 0
        total_tax = 0
        total_discount = 0

        # Create invoice
        invoice = ExpenseInvoice(
            invoice_number=invoice_number,
            date=form.date.data,
            payment_method=form.payment_method.data,
            status='paid',  # Expenses are usually paid immediately
            total_before_tax=0,  # Will be calculated
            tax_amount=0,  # Will be calculated
            discount_amount=0,  # Will be calculated
            total_after_tax_discount=0,  # Will be calculated
            user_id=current_user.id
        )
        db.session.add(invoice)
        db.session.flush()

        # Add invoice items
        for item_form in form.items.entries:
            if item_form.description.data:  # Only process items with description
                qty = float(item_form.quantity.data)
                price = float(item_form.price_before_tax.data)
                tax = float(item_form.tax.data or 0)
                discount = float(item_form.discount.data or 0)

                # Calculate amounts
                item_before_tax = price * qty
                total_item = item_before_tax + tax - discount

                # Add to invoice totals
                total_before_tax += item_before_tax
                total_tax += tax
                total_discount += discount

                # Create invoice item
                inv_item = ExpenseInvoiceItem(
                    invoice_id=invoice.id,
                    description=item_form.description.data,
                    quantity=qty,
                    price_before_tax=price,
                    tax=tax,
                    discount=discount,
                    total_price=total_item
                )
                db.session.add(inv_item)

        # Update invoice totals
        total_after_tax_discount = total_before_tax + total_tax - total_discount
        invoice.total_before_tax = total_before_tax
        invoice.tax_amount = total_tax
        invoice.discount_amount = total_discount
        invoice.total_after_tax_discount = total_after_tax_discount

        db.session.commit()
        # Post to ledger (Expense, VAT Input, Cash/AP)
        try:
            def get_or_create(code, name, type_):
                acc = Account.query.filter_by(code=code).first()
                if not acc:
                    acc = Account(code=code, name=name, type=type_)
                    db.session.add(acc); db.session.flush()
                return acc
            exp_acc = get_or_create('6000', 'Operating Expenses', 'EXPENSE')
            vat_in_acc = get_or_create('1300', 'VAT Input', 'ASSET')
            cash_acc = get_or_create('1000', 'Cash', 'ASSET')
            ap_acc = get_or_create('2000', 'Accounts Payable', 'LIABILITY')

            settle_acc = cash_acc if invoice.payment_method in ['cash','mada','visa','bank'] else ap_acc
            db.session.add(LedgerEntry(date=invoice.date, account_id=exp_acc.id, debit=invoice.total_before_tax, credit=0, description=f'Expense {invoice.invoice_number}'))
            db.session.add(LedgerEntry(date=invoice.date, account_id=vat_in_acc.id, debit=invoice.tax_amount, credit=0, description=f'VAT Input {invoice.invoice_number}'))
            db.session.add(LedgerEntry(date=invoice.date, account_id=settle_acc.id, debit=0, credit=invoice.total_after_tax_discount, description=f'Settlement {invoice.invoice_number}'))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error('Ledger posting (expense) failed: %s', e, exc_info=True)


        # Emit real-time update
        socketio.emit('expense_update', {
            'invoice_number': invoice_number,
            'total': float(total_after_tax_discount)
        }, broadcast=True)

        flash(_('Expense invoice created successfully / تم إنشاء فاتورة المصروفات بنجاح'), 'success')
        return redirect(url_for('expenses'))

    # Set default date for new form
    if request.method == 'GET':
        form.date.data = datetime.utcnow().date()

    # Get all expense invoices
    invoices = ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).all()
    return render_template('expenses.html', form=form, invoices=invoices)

@app.route('/invoices')
@login_required
def invoices():
    from sqlalchemy import func
    # Normalize type
    raw_type = (request.args.get('type') or 'all').lower()
    if raw_type in ['purchases','purchase']: tfilter = 'purchase'
    elif raw_type in ['expenses','expense']: tfilter = 'expense'
    elif raw_type in ['sales','sale']: tfilter = 'sales'
    else: tfilter = 'all'

    # Build unified list from specialized invoices + payments
    sales_q = SalesInvoice.query
    purchase_q = PurchaseInvoice.query
    expense_q = ExpenseInvoice.query

    rows = []
    def paid_map_for(kind, ids):
        if not ids: return {}
        mm = db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).\
            filter(Payment.invoice_type==kind, Payment.invoice_id.in_(ids)).\
            group_by(Payment.invoice_id).all()
        return {pid: float(total or 0) for (pid,total) in mm}

    if tfilter in ['all','sales']:
        sales = sales_q.order_by(SalesInvoice.date.desc()).all()
        paid = paid_map_for('sales', [s.id for s in sales])
        for s in sales:
            total = float(s.total_after_tax_discount or 0)
            p = paid.get(s.id, 0.0)
            rows.append({
                'id': s.id,
                'invoice_number': s.invoice_number,
                'invoice_type': 'sales',
                'customer_supplier': s.customer_name or '-',
                'total_amount': total,
                'paid_amount': p,
                'remaining_amount': max(total - p, 0.0),
                'status': s.status,
                'due_date': None,
            })
    if tfilter in ['all','purchase']:
        purchases = purchase_q.order_by(PurchaseInvoice.date.desc()).all()
        paid = paid_map_for('purchase', [p.id for p in purchases])
        for pch in purchases:
            total = float(pch.total_after_tax_discount or 0)
            p = paid.get(pch.id, 0.0)
            rows.append({
                'id': pch.id,
                'invoice_number': pch.invoice_number,
                'invoice_type': 'purchase',
                'customer_supplier': pch.supplier_name or '-',
                'total_amount': total,
                'paid_amount': p,
                'remaining_amount': max(total - p, 0.0),
                'status': pch.status,
                'due_date': None,
            })
    if tfilter in ['all','expense']:
        expenses = expense_q.order_by(ExpenseInvoice.date.desc()).all()
        paid = paid_map_for('expense', [e.id for e in expenses])
        for ex in expenses:
            total = float(ex.total_after_tax_discount or 0)
            p = paid.get(ex.id, 0.0)
            rows.append({
                'id': ex.id,
                'invoice_number': ex.invoice_number,
                'invoice_type': 'expense',
                'customer_supplier': 'Expense',
                'total_amount': total,
                'paid_amount': p,
                'remaining_amount': max(total - p, 0.0),
                'status': ex.status,
                'due_date': None,
            })

    # Sort unified rows by invoice number or leave as-is; here sort by id desc
    rows.sort(key=lambda r: (r.get('id') or 0), reverse=True)

    # For nav highlighting, keep original choice
    current_type = raw_type
    return render_template('invoices.html', invoices=rows, current_type=current_type)


@app.route('/invoices/<string:kind>/<int:invoice_id>')
@login_required
def view_invoice(kind, invoice_id):
    kind = (kind or '').lower()
    inv = None
    items = []
    title = 'Invoice'
    if kind == 'sales':
        inv = SalesInvoice.query.get_or_404(invoice_id)
        items = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).all()
        title = 'Sales Invoice'
    elif kind == 'purchase':
        inv = PurchaseInvoice.query.get_or_404(invoice_id)
        items = PurchaseInvoiceItem.query.filter_by(invoice_id=inv.id).all()
        title = 'Purchase Invoice'
    elif kind == 'expense':
        inv = ExpenseInvoice.query.get_or_404(invoice_id)
        items = ExpenseInvoiceItem.query.filter_by(invoice_id=inv.id).all()
        title = 'Expense Invoice'
    else:
        flash(_('Unknown invoice type / نوع فاتورة غير معروف'), 'danger')
        return redirect(url_for('invoices'))

    # Compute paid/remaining from payments
    from sqlalchemy import func
    paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).\
        filter_by(invoice_type=kind, invoice_id=invoice_id).scalar() or 0)
    total = float(getattr(inv, 'total_after_tax_discount', 0) or 0)
    remaining = max(total - paid, 0.0)

    return render_template('invoice_view.html', kind=kind, inv=inv, items=items, title=title, paid=paid, remaining=remaining)

@app.route('/inventory')
@login_required
def inventory():
    # Get all raw materials and meals for display
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    meals = Meal.query.filter_by(active=True).all()
    return render_template('inventory.html', raw_materials=raw_materials, meals=meals)



@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    form = EmployeeForm()
    if form.validate_on_submit():
        try:
            emp = Employee(
                employee_code=form.employee_code.data.strip(),
                full_name=form.full_name.data.strip(),
                national_id=form.national_id.data.strip(),
                department=form.department.data.strip() if form.department.data else None,
                position=form.position.data.strip() if form.position.data else None,
                phone=form.phone.data.strip() if form.phone.data else None,
                email=form.email.data.strip() if form.email.data else None,
                hire_date=form.hire_date.data,
                status=form.status.data
            )
            db.session.add(emp)
            db.session.commit()
            flash(_('تم إضافة الموظف بنجاح / Employee added successfully'), 'success')
            return redirect(url_for('employees'))
        except Exception as e:
            db.session.rollback()
            flash(_('تعذرت إضافة الموظف. تحقق من أن رقم الموظف والهوية غير مكررين. / Could not add employee. Ensure code and national id are unique.'), 'danger')
    employees_list = Employee.query.order_by(Employee.full_name.asc()).all()
    return render_template('employees.html', form=form, employees=employees_list)


@app.route('/salaries', methods=['GET', 'POST'])
@login_required
def salaries():
    # Redirect to monthly view as primary workflow
    if request.method == 'GET' and not request.args:
        return redirect(url_for('salaries_monthly'))
    form = SalaryForm()
    # Load employees into choices
    form.employee_id.choices = [(e.id, e.full_name) for e in Employee.query.order_by(Employee.full_name.asc()).all()]

    if form.validate_on_submit():
        try:
            basic = float(form.basic_salary.data or 0)
            allowances = float(form.allowances.data or 0)
            deductions = float(form.deductions.data or 0)
            prev_due = float(form.previous_salary_due.data or 0)
            total = basic + allowances - deductions + prev_due

            salary = Salary(
                employee_id=form.employee_id.data,
                year=form.year.data,
                month=form.month.data,
                basic_salary=basic,
                allowances=allowances,
                deductions=deductions,
                previous_salary_due=prev_due,
                total_salary=total,
                status=form.status.data
            )
            db.session.add(salary)
            db.session.commit()
            flash(_('تم حفظ الراتب بنجاح / Salary saved successfully'), 'success')
            return redirect(url_for('salaries'))
        except Exception:
            db.session.rollback()
            flash(_('تعذر حفظ الراتب. تأكد من عدم تكرار نفس الشهر لنفس الموظف / Could not save. Ensure month is unique per employee'), 'danger')

    salaries_list = Salary.query.order_by(Salary.year.desc(), Salary.month.desc()).all()
    return render_template('salaries.html', form=form, salaries=salaries_list)

@app.route('/payments', methods=['GET'])
@login_required
def payments():
    status_filter = request.args.get('status')
    type_filter = request.args.get('type')

    # Build unified invoices view via union_all
    from sqlalchemy import literal, func
    sales_q = db.session.query(
        SalesInvoice.id.label('id'),
        literal('sales').label('type'),
        SalesInvoice.customer_name.label('party'),
        SalesInvoice.total_after_tax_discount.label('total'),
        literal(0).label('paid'),
        SalesInvoice.date.label('date'),
        SalesInvoice.status.label('status')
    )
    purchases_q = db.session.query(
        PurchaseInvoice.id,
        literal('purchase'),
        PurchaseInvoice.supplier_name,
        PurchaseInvoice.total_after_tax_discount,
        literal(0),
        PurchaseInvoice.date,
        PurchaseInvoice.status
    )
    expenses_q = db.session.query(
        ExpenseInvoice.id,
        literal('expense'),
        literal('Expense').label('party'),
        ExpenseInvoice.total_after_tax_discount,
        literal(0),
        ExpenseInvoice.date,
        ExpenseInvoice.status
    )
    salaries_q = db.session.query(
        Salary.id,
        literal('salary'),
        Employee.full_name,
        Salary.total_salary,
        literal(0),
        func.date(func.printf('%04d-%02d-01', Salary.year, Salary.month)),
        Salary.status
    ).join(Employee)

    from sqlalchemy import union_all
    union_q = union_all(sales_q, purchases_q, expenses_q, salaries_q).alias('u')
    rows = db.session.query(union_q).all()

    # Compute paid from Payments table per invoice
    from sqlalchemy import func
    invoices = []
    for r in rows:
        paid_sum = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
            Payment.invoice_id == r.id,
            Payment.invoice_type == r.type
        ).scalar() or 0
        total_val = float(r.total) if r.total is not None else 0.0
        paid_val = float(paid_sum)
        # Compute status dynamically to always reflect latest payments
        if paid_val >= total_val and total_val > 0:
            status_val = 'paid'
        elif paid_val > 0:
            status_val = 'partial'
        else:
            status_val = 'unpaid'
        invoices.append(dict(
            id=r.id,
            type=r.type,
            party=r.party,
            total=total_val,
            paid=paid_val,
            date=r.date,
            status=status_val
        ))

    # Apply filters in memory (small datasets) — can be pushed to SQL later
    if status_filter:
        invoices = [i for i in invoices if i['status'] == status_filter]

    if type_filter:
        invoices = [i for i in invoices if i['type'] == type_filter]


    return render_template('payments.html', invoices=invoices)

@app.route('/reports', methods=['GET'])
@login_required
def reports():
    from sqlalchemy import func, cast, Date
    period = request.args.get('period', 'this_month')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')

    today = datetime.utcnow().date()
    if period == 'today':
        start_dt = end_dt = today
    elif period == 'this_week':
        start_dt = today - datetime.timedelta(days=today.weekday())
        end_dt = today
    elif period == 'this_month':
        start_dt = today.replace(day=1)
        end_dt = today
    elif period == 'this_year':
        start_dt = today.replace(month=1, day=1)
        end_dt = today
    elif period == 'custom' and start_arg and end_arg:
        try:
            start_dt = datetime.strptime(start_arg, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_arg, '%Y-%m-%d').date()
        except Exception:
            start_dt = today.replace(day=1)
            end_dt = today
    else:
        start_dt = today.replace(day=1)
        end_dt = today

    # Sales totals by branch
    sales_place = db.session.query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0)) \
        .filter(SalesInvoice.date.between(start_dt, end_dt), SalesInvoice.branch == 'place_india').scalar() or 0
    sales_china = db.session.query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0)) \
        .filter(SalesInvoice.date.between(start_dt, end_dt), SalesInvoice.branch == 'china_town').scalar() or 0
    total_sales = float(sales_place) + float(sales_china)

    # Purchases and Expenses
    total_purchases = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
        .filter(PurchaseInvoice.date.between(start_dt, end_dt)).scalar() or 0)
    total_expenses = float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_after_tax_discount), 0))
        .filter(ExpenseInvoice.date.between(start_dt, end_dt)).scalar() or 0)

    # Salaries within period: compute by month-year mapping to 1st day of month
    salaries_rows = Salary.query.all()
    total_salaries = 0.0
    for s in salaries_rows:
        try:
            s_date = datetime(s.year, s.month, 1).date()
            if start_dt <= s_date <= end_dt:
                total_salaries += float(s.total_salary or 0)
        except Exception:
            continue

    profit = float(total_sales) - (float(total_purchases) + float(total_expenses) + float(total_salaries))

    # Line chart: daily sales
    daily_rows = db.session.query(SalesInvoice.date.label('d'), func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0).label('t')) \
        .filter(SalesInvoice.date.between(start_dt, end_dt)) \
        .group_by(SalesInvoice.date) \
        .order_by(SalesInvoice.date.asc()).all()
    line_labels = [r.d.strftime('%Y-%m-%d') for r in daily_rows]
    line_values = [float(r.t or 0) for r in daily_rows]

    # Payment method distribution across invoices
    def pm_counts(model, date_col, method_col):
        rows = db.session.query(getattr(model, method_col), func.count('*')) \
            .filter(getattr(model, date_col).between(start_dt, end_dt)) \
            .group_by(getattr(model, method_col)).all()
        return { (k or 'unknown'): int(v) for k, v in rows }

    pm_map = {}
    for d in (pm_counts(SalesInvoice, 'date', 'payment_method'),
              pm_counts(PurchaseInvoice, 'date', 'payment_method'),
              pm_counts(ExpenseInvoice, 'date', 'payment_method')):
        for k, v in d.items():
            pm_map[k] = pm_map.get(k, 0) + v
    pm_labels = list(pm_map.keys())
    pm_values = [pm_map[k] for k in pm_labels]

    # Comparison bars: totals
    comp_labels = ['Sales', 'Purchases', 'Expenses+Salaries']
    comp_values = [float(total_sales), float(total_purchases), float(total_expenses) + float(total_salaries)]

    # Cash flows from Payments table
    start_dt_dt = datetime.combine(start_dt, datetime.min.time())
    end_dt_dt = datetime.combine(end_dt, datetime.max.time())
    inflow = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
        Payment.invoice_type == 'sales', Payment.payment_date.between(start_dt_dt, end_dt_dt)
    ).scalar() or 0)
    outflow = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
        Payment.invoice_type.in_(['purchase','expense','salary']), Payment.payment_date.between(start_dt_dt, end_dt_dt)
    ).scalar() or 0)
    net_cash = inflow - outflow

    # Top products by quantity
    top_rows = db.session.query(SalesInvoiceItem.product_name, func.coalesce(func.sum(SalesInvoiceItem.quantity), 0)) \
        .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id) \
        .filter(SalesInvoice.date.between(start_dt, end_dt)) \
        .group_by(SalesInvoiceItem.product_name) \
        .order_by(func.sum(SalesInvoiceItem.quantity).desc()) \
        .limit(10).all()
    top_labels = [r[0] for r in top_rows]
    # Settings for labels/currency
    from models import Settings
    s = Settings.query.first()
    place_lbl = s.place_india_label if s and s.place_india_label else 'Place India'
    china_lbl = s.china_town_label if s and s.china_town_label else 'China Town'
    currency = s.currency if s and s.currency else 'SAR'

    top_values = [float(r[1] or 0) for r in top_rows]

    # Low stock raw materials
    low_stock = RawMaterial.query.order_by(RawMaterial.stock_quantity.asc()).limit(10).all()

    return render_template('reports.html',
        period=period, start_date=start_dt, end_date=end_dt,
        sales_place=float(sales_place), sales_china=float(sales_china), total_sales=float(total_sales),
        total_purchases=total_purchases, total_expenses=total_expenses, total_salaries=float(total_salaries), profit=profit,
        line_labels=line_labels, line_values=line_values,
        pm_labels=pm_labels, pm_values=pm_values,
        comp_labels=comp_labels, comp_values=comp_values,
        inflow=inflow, outflow=outflow, net_cash=net_cash,
        top_labels=top_labels, top_values=top_values,
        low_stock=low_stock,
        place_lbl=place_lbl, china_lbl=china_lbl, currency=currency
    )



@app.route('/register_payment', methods=['POST'])
@login_required
def register_payment_ajax():
    from sqlalchemy import literal
    invoice_id = int(request.form['invoice_id'])
    invoice_type = request.form['invoice_type']
    amt_str = request.form.get('amount', '').strip().replace(',', '.')
    try:
        amount = float(amt_str)
    except Exception:
        return jsonify({'status':'error', 'message':'invalid_amount'}), 400
    if amount <= 0:
        return jsonify({'status':'error', 'message':'invalid_amount'}), 400
    method = request.form.get('payment_method')

    # Register payment
    pay = Payment(invoice_id=invoice_id, invoice_type=invoice_type, amount_paid=amount, payment_method=method)
    db.session.add(pay)

    # Update invoice paid and status according to invoice type
    remaining = None
    if invoice_type == 'sales':
        inv = SalesInvoice.query.get(invoice_id)
        if not inv: return jsonify({'status':'error'}), 404
        paid = float(getattr(inv, 'paid_amount', 0) or 0) + amount
        inv.paid_amount = paid
        total = float(inv.total_after_tax_discount)
        inv.status = 'paid' if paid >= total else ('partial' if paid > 0 else 'unpaid')
    elif invoice_type == 'purchase':
        inv = PurchaseInvoice.query.get(invoice_id)
        if not inv: return jsonify({'status':'error'}), 404
        paid = float(getattr(inv, 'paid_amount', 0) or 0) + amount
        inv.paid_amount = paid
        total = float(inv.total_after_tax_discount)
        inv.status = 'paid' if paid >= total else ('partial' if paid > 0 else 'unpaid')
    elif invoice_type == 'expense':
        inv = ExpenseInvoice.query.get(invoice_id)
        if not inv: return jsonify({'status':'error'}), 404
        paid = float(getattr(inv, 'paid_amount', 0) or 0) + amount
        inv.paid_amount = paid
        total = float(inv.total_after_tax_discount)
        inv.status = 'paid' if paid >= total else ('partial' if paid > 0 else 'paid')  # expenses usually paid
    elif invoice_type == 'salary':
        inv = Salary.query.get(invoice_id)
        if not inv: return jsonify({'status':'error'}), 404
        paid = float(getattr(inv, 'paid_amount', 0) or 0) + amount
        inv.paid_amount = paid
        total = float(inv.total_salary)
        inv.status = 'paid' if paid >= total else ('partial' if paid > 0 else 'unpaid')
    else:
        return jsonify({'status':'error'}), 400
    # Ledger postings for payments: adjust AR/AP/Cash
    try:
        def get_or_create(code, name, type_):
            acc = Account.query.filter_by(code=code).first()
            if not acc:
                acc = Account(code=code, name=name, type=type_)
                db.session.add(acc); db.session.flush()
            return acc
        cash_acc = get_or_create('1000', 'Cash', 'ASSET')
        ar_acc = get_or_create('1100', 'Accounts Receivable', 'ASSET')
        ap_acc = get_or_create('2000', 'Accounts Payable', 'LIABILITY')

        if invoice_type == 'sales':
            # receipt: debit cash, credit AR
            db.session.add(LedgerEntry(date=pay.payment_date.date(), account_id=cash_acc.id, debit=amount, credit=0, description=f'Receipt sales #{invoice_id}'))
            db.session.add(LedgerEntry(date=pay.payment_date.date(), account_id=ar_acc.id, debit=0, credit=amount, description=f'Settle AR sales #{invoice_id}'))
        elif invoice_type in ['purchase','expense','salary']:
            # payment: credit cash, debit AP (or expense/salary direct, but we keep AP)
            db.session.add(LedgerEntry(date=pay.payment_date.date(), account_id=ap_acc.id, debit=amount, credit=0, description=f'Settle AP {invoice_type} #{invoice_id}'))
            db.session.add(LedgerEntry(date=pay.payment_date.date(), account_id=cash_acc.id, debit=0, credit=amount, description=f'Payment {invoice_type} #{invoice_id}'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error('Ledger posting (payment) failed: %s', e, exc_info=True)


    db.session.commit()

    # Emit socket event (if desired)
    try:
        socketio.emit('payment_update', {'invoice_id': invoice_id, 'invoice_type': invoice_type, 'amount': amount}, broadcast=True)
    except Exception:
        pass

    return jsonify({'status': 'success'})






# Employees: Edit

# Deprecated inline VAT route is replaced by blueprint

@app.route('/employees/<int:emp_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    form = EmployeeForm(obj=emp)
    if form.validate_on_submit():
        try:
            emp.employee_code = form.employee_code.data.strip()
            emp.full_name = form.full_name.data.strip()
            emp.national_id = form.national_id.data.strip()
            emp.department = form.department.data.strip() if form.department.data else None
            emp.position = form.position.data.strip() if form.position.data else None
            emp.phone = form.phone.data.strip() if form.phone.data else None
            emp.email = form.email.data.strip() if form.email.data else None
            emp.hire_date = form.hire_date.data
            emp.status = form.status.data
            db.session.commit()
            flash(_('تم تعديل بيانات الموظف / Employee updated'), 'success')
            return redirect(url_for('employees'))
        except Exception:
            db.session.rollback()
            flash(_('تعذر التعديل. تحقق من عدم تكرار الرمز/الهوية / Could not update. Ensure code/national id are unique.'), 'danger')
    return render_template('employees.html', form=form, employees=None)

# Employees: Delete
@app.route('/employees/<int:emp_id>/delete', methods=['POST'])
@login_required
def delete_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    try:
        if emp.salaries and len(emp.salaries) > 0:
            flash(_('لا يمكن حذف الموظف لوجود رواتب مرتبطة / Cannot delete employee with linked salaries'), 'danger')
            return redirect(url_for('employees'))
        db.session.delete(emp)
        db.session.commit()
        flash(_('تم حذف الموظف / Employee deleted'), 'info')
    except Exception:
        db.session.rollback()
        flash(_('تعذر حذف الموظف / Could not delete employee'), 'danger')
    return redirect(url_for('employees'))

# Salaries: Edit
@app.route('/salaries/<int:salary_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_salary(salary_id):
    sal = Salary.query.get_or_404(salary_id)
    form = SalaryForm(obj=sal)
    form.employee_id.choices = [(e.id, e.full_name) for e in Employee.query.order_by(Employee.full_name.asc()).all()]
    if request.method == 'GET':
        form.employee_id.data = sal.employee_id
        form.month.data = sal.month
    if form.validate_on_submit():
        try:
            sal.employee_id = form.employee_id.data
            sal.year = form.year.data
            sal.month = form.month.data
            sal.basic_salary = float(form.basic_salary.data or 0)
            sal.allowances = float(form.allowances.data or 0)
            sal.deductions = float(form.deductions.data or 0)
            sal.previous_salary_due = float(form.previous_salary_due.data or 0)
            sal.total_salary = sal.basic_salary + sal.allowances - sal.deductions + sal.previous_salary_due
            sal.status = form.status.data
            db.session.commit()
            flash(_('تم تعديل الراتب / Salary updated'), 'success')
            return redirect(url_for('salaries'))
        except Exception:
            db.session.rollback()
            flash(_('تعذر تعديل الراتب. تحقق من عدم تكرار الشهر لنفس الموظف / Could not update. Ensure month is unique per employee'), 'danger')
    return render_template('salaries.html', form=form, salaries=None)

# Salaries: Delete
# Payroll statements (كشف الرواتب)
@app.route('/salaries/statements', methods=['GET'])
@login_required
def salaries_statements():
    # Permission: view
    try:
        if not (getattr(current_user,'role','')=='admin' or can_perm('salaries','view')):
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('dashboard'))
    except Exception:
        pass
    # Year/month
    try:
        year = int(request.args.get('year') or datetime.utcnow().year)
    except Exception:
        year = datetime.utcnow().year
    try:
        month = int(request.args.get('month') or datetime.utcnow().month)
    except Exception:
        month = datetime.utcnow().month

    from sqlalchemy import func
    qs = Salary.query.filter_by(year=year, month=month).join(Employee).order_by(Employee.full_name.asc())
    recs = qs.all()
    # Payments per salary
    pays = db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).\
        filter(Payment.invoice_type=='salary', Payment.invoice_id.in_([r.id for r in recs])).\
        group_by(Payment.invoice_id).all()
    paid_map = {pid: float(total or 0) for (pid,total) in pays}

    rows = []
    totals = dict(basic=0.0, allow=0.0, ded=0.0, prev=0.0, total=0.0, paid=0.0, remaining=0.0)
    for s in recs:
        paid = paid_map.get(s.id, 0.0)
        total = float(s.total_salary or 0)
        remaining = max(total - paid, 0.0)
        rows.append({
            'id': s.id,
            'employee_name': s.employee.full_name if s.employee else str(s.employee_id),
            'basic': float(s.basic_salary or 0),
            'allow': float(s.allowances or 0),
            'ded': float(s.deductions or 0),
            'prev': float(s.previous_salary_due or 0),
            'total': total,
            'paid': paid,
            'remaining': remaining,
            'status': s.status,
        })
        totals['basic'] += float(s.basic_salary or 0)
        totals['allow'] += float(s.allowances or 0)
        totals['ded'] += float(s.deductions or 0)
        totals['prev'] += float(s.previous_salary_due or 0)
        totals['total'] += total
        totals['paid'] += paid
        totals['remaining'] += remaining

    return render_template('salaries_statements.html', year=year, month=month, rows=rows, totals=totals)

@app.route('/salaries/statements/print', methods=['GET'])
@login_required
def salaries_statements_print():
    # Permission: print
    try:
        if not (getattr(current_user,'role','')=='admin' or can_perm('salaries','print')):
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('salaries_statements'))
    except Exception:
        pass
    try:
        year = int(request.args.get('year'))
        month = int(request.args.get('month'))
    except Exception:
        flash(_('Select year and month / اختر السنة والشهر'), 'danger')
        return redirect(url_for('salaries_statements'))

    from sqlalchemy import func
    recs = Salary.query.filter_by(year=year, month=month).join(Employee).order_by(Employee.full_name.asc()).all()
    pays = db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).\
        filter(Payment.invoice_type=='salary', Payment.invoice_id.in_([r.id for r in recs])).\
        group_by(Payment.invoice_id).all()
    paid_map = {pid: float(total or 0) for (pid,total) in pays}

    # Collect company name
    try:
        from models import Settings
        s = Settings.query.first()
        company_name = (s.company_name or '').strip() if s and s.company_name else 'Company'
    except Exception:
        company_name = 'Company'

    # Try PDF via reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import io, os as _os

        def register_ar_font():
            candidates = [
                r"C:\\Windows\\Fonts\\trado.ttf",
                r"C:\\Windows\\Fonts\\Tahoma.ttf",
                r"C:\\Windows\\Fonts\\arial.ttf",
                "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            for fp in candidates:
                if _os.path.exists(fp):
                    pdfmetrics.registerFont(TTFont('Arabic', fp))
                    return 'Arabic'
            return None
        def shape_ar(t):
            try:
                import arabic_reshaper
                from bidi.algorithm import get_display
                return get_display(arabic_reshaper.reshape(t))
            except Exception:
                return t

        buf = io.BytesIO()
        p = canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        ar = register_ar_font()
        # Header
        if ar:
            p.setFont(ar, 14)
            p.drawString(20*mm, h-20*mm, shape_ar(company_name))
            p.setFont(ar, 11)
            p.drawString(20*mm, h-28*mm, shape_ar(f"كشف الرواتب لشهر {year}-{month:02d}"))
        else:
            p.setFont("Helvetica-Bold", 14)
            p.drawString(20*mm, h-20*mm, company_name)
            p.setFont("Helvetica", 11)
            p.drawString(20*mm, h-28*mm, f"Payroll Statement {year}-{month:02d}")

        # Table header
        y = h - 40*mm
        if ar:
            p.setFont(ar, 10)
            headers = ["الموظف","الأساسي","البدلات","الاستقطاعات","سابقة","الإجمالي","المدفوع","المتبقي","الحالة"]
            xcols = [20, 70, 95, 120, 145, 170, 195, 220, 245]
            for i, txt in enumerate(headers):
                p.drawString(xcols[i]*mm, y, shape_ar(txt))
        else:
            p.setFont("Helvetica", 10)
            headers = ["Employee","Basic","Allow","Deduct","Prev","Total","Paid","Remain","Status"]
            xcols = [20, 70, 95, 120, 145, 170, 195, 220, 245]
            for i, txt in enumerate(headers):
                p.drawString(xcols[i]*mm, y, txt)
        y -= 8*mm

        # Rows
        for s_row in recs:
            paid = paid_map.get(s_row.id, 0.0)
            total = float(s_row.total_salary or 0)
            remaining = max(total - paid, 0.0)
            vals = [
                s_row.employee.full_name if s_row.employee else str(s_row.employee_id),
                f"{float(s_row.basic_salary or 0):.2f}",
                f"{float(s_row.allowances or 0):.2f}",
                f"{float(s_row.deductions or 0):.2f}",
                f"{float(s_row.previous_salary_due or 0):.2f}",
                f"{total:.2f}", f"{paid:.2f}", f"{remaining:.2f}", s_row.status
            ]
            if ar:
                vals[0] = shape_ar(vals[0])
                vals[-1] = shape_ar(vals[-1])
            for i, v in enumerate(vals):
                p.drawString(xcols[i]*mm, y, v)
            y -= 7*mm
            if y < 20*mm:
                p.showPage(); y = h - 20*mm
                if ar: p.setFont(ar, 10)
                else: p.setFont("Helvetica", 10)

        p.showPage(); p.save(); buf.seek(0)
        return send_file(buf, as_attachment=False, download_name=f"Payroll_{year}-{month:02d}.pdf", mimetype='application/pdf')
    except Exception:
        # Fallback to HTML template for print
        return render_template('salaries_statements.html', year=year, month=month, rows=[{
            'id': r.id,
            'employee_name': r.employee.full_name if r.employee else str(r.employee_id),
            'basic': float(r.basic_salary or 0),
            'allow': float(r.allowances or 0),
            'ded': float(r.deductions or 0),
            'prev': float(r.previous_salary_due or 0),
            'total': float(r.total_salary or 0),
            'paid': paid_map.get(r.id, 0.0),
            'remaining': max(float(r.total_salary or 0) - paid_map.get(r.id, 0.0), 0.0),
            'status': r.status,
        } for r in recs], totals=None)


@app.route('/salaries/<int:salary_id>/delete', methods=['POST'])
@login_required
def delete_salary(salary_id):
    sal = Salary.query.get_or_404(salary_id)
    try:
        db.session.delete(sal)
        db.session.commit()
        flash(_('تم حذف الراتب / Salary deleted'), 'info')
    except Exception:
        db.session.rollback()
        flash(_('تعذر حذف الراتب / Could not delete salary'), 'danger')
    return redirect(url_for('salaries'))



# Salaries monthly management
@app.route('/salaries/monthly', methods=['GET', 'POST'])
@login_required
def salaries_monthly():
    from sqlalchemy import func
    # Permission: view
    try:
        if not (getattr(current_user,'role','')=='admin' or can_perm('salaries','view')):
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('dashboard'))
    except Exception:
        pass
    # Select year/month
    try:
        year = int(request.values.get('year') or datetime.utcnow().year)
    except Exception:
        year = datetime.utcnow().year
    try:
        month = int(request.values.get('month') or datetime.utcnow().month)
    except Exception:
        month = datetime.utcnow().month

    # Ensure salary rows exist for all active employees
    emps = Employee.query.filter_by(status='active').order_by(Employee.full_name.asc()).all()
    existing = {(s.employee_id, s.year, s.month): s for s in Salary.query.filter_by(year=year, month=month).all()}
    created = 0
    for e in emps:
        if (e.id, year, month) not in existing:
            s = Salary(employee_id=e.id, year=year, month=month,
                       basic_salary=0, allowances=0, deductions=0, previous_salary_due=0,
                       total_salary=0, status='due')
            db.session.add(s)
            created += 1
    if created:
        db.session.commit()

    # Fetch salaries for period with payments summary
    salaries_q = Salary.query.filter_by(year=year, month=month).join(Employee).order_by(Employee.full_name.asc())
    salaries_list = salaries_q.all()

    # Payments sum per salary
    pays = db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).\
        filter(Payment.invoice_type=='salary', Payment.invoice_id.in_([s.id for s in salaries_list])).\
        group_by(Payment.invoice_id).all()
    paid_map = {pid: float(total or 0) for (pid,total) in pays}

    # Prepare rows
    rows = []
    for s in salaries_list:
        paid = paid_map.get(s.id, 0.0)
        total = float(s.total_salary or 0)
        remaining = max(total - paid, 0.0)
        rows.append({
            'id': s.id,
            'employee_name': s.employee.full_name if s.employee else str(s.employee_id),
            'basic_salary': float(s.basic_salary or 0),
            'allowances': float(s.allowances or 0),
            'deductions': float(s.deductions or 0),
            'previous_salary_due': float(s.previous_salary_due or 0),
            'total_salary': total,
            'status': s.status,
            'paid': paid,
            'remaining': remaining,
        })

    return render_template('salaries_monthly.html', year=year, month=month, rows=rows)

@app.route('/salaries/monthly/save', methods=['POST'])
@login_required
def salaries_monthly_save():
    from sqlalchemy import func
    # Permission: edit
    try:
        if not (getattr(current_user,'role','')=='admin' or can_perm('salaries','edit')):
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('salaries_monthly', year=request.form.get('year'), month=request.form.get('month')))
    except Exception:
        pass
    # Expect fields like basic_salary_<id>, allowances_<id>, deductions_<id>, previous_salary_due_<id>
    updated = 0
    for key, val in request.form.items():
        try:
            if '_' not in key: continue
            field, sid_str = key.rsplit('_', 1)
            sid = int(sid_str)
            s = Salary.query.get(sid)
            if not s: continue
            if field in ['basic_salary','allowances','deductions','previous_salary_due']:
                try:
                    num = float((val or '0').replace(',', '.'))
                except Exception:
                    num = 0.0
                setattr(s, field, num)
                # Recompute total
                s.total_salary = float(s.basic_salary or 0) + float(s.allowances or 0) - float(s.deductions or 0) + float(s.previous_salary_due or 0)
                # Update status based on payments
                paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).\
                    filter_by(invoice_type='salary', invoice_id=s.id).scalar() or 0)
                s.status = 'paid' if paid >= float(s.total_salary or 0) else ('partial' if paid > 0 else 'due')
                updated += 1
        except Exception:
            continue
    if updated:
        db.session.commit()
        flash(_('تم حفظ التعديلات / Changes saved'), 'success')
    else:
        flash(_('لا تعديلات / No changes'), 'info')
    return redirect(url_for('salaries_monthly', year=request.form.get('year'), month=request.form.get('month')))


# Legacy /vat route redirects to the new VAT dashboard
@app.route('/vat')
@login_required
def vat():
    return redirect(url_for('vat.vat_dashboard'))


# Deprecated placeholder route kept for backward compatibility
@app.route('/financials')
@login_required
def financials():
    return redirect(url_for('financials.income_statement'))

@app.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    from models import Settings
    s = Settings.query.first()
    if request.method == 'POST':
        if not s:
            s = Settings()
            db.session.add(s)
        s.company_name = request.form.get('company_name')
        s.tax_number = request.form.get('tax_number')
        s.address = request.form.get('address')
        s.phone = request.form.get('phone')
        s.email = request.form.get('email')
        try:
            s.vat_rate = float(request.form.get('vat_rate') or 15)
        except Exception:
            s.vat_rate = 15.0
        s.currency = request.form.get('currency') or 'SAR'
        s.place_india_label = request.form.get('place_india_label') or 'Place India'
        s.china_town_label = request.form.get('china_town_label') or 'China Town'
        s.default_theme = (request.form.get('default_theme') or 'light').lower()
        db.session.commit()
        flash(_('Settings saved successfully / تم حفظ الإعدادات'), 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html', s=s or Settings())

# ---- Simple permission checker usable in routes (Python scope)
from models import UserPermission

def can_perm(screen:str, perm:str)->bool:
    try:
        if getattr(current_user,'role','') == 'admin':
            return True
        q = UserPermission.query.filter_by(user_id=current_user.id, screen_key=screen)
        for p in q.all():
            if perm == 'view' and p.can_view: return True
            if perm == 'add' and p.can_add: return True
            if perm == 'edit' and p.can_edit: return True
            if perm == 'delete' and p.can_delete: return True
            if perm == 'print' and p.can_print: return True
    except Exception:
        pass
    return False

# ---------------------- Users API ----------------------
@csrf.exempt
@app.route('/api/users', methods=['GET'])
@login_required
def api_users_list():
    if not can_perm('users','view'):
        return jsonify({'error':'forbidden'}), 403
    q = (request.args.get('q') or '').strip().lower()
    page = int(request.args.get('page') or 1)
    per_page = min(50, int(request.args.get('per_page') or 10))
    sort = request.args.get('sort') or 'username'
    query = User.query
    if q:
        query = query.filter((User.username.ilike(f'%{q}%')) | (User.email.ilike(f'%{q}%')))
    if sort in ['username','email','role','active']:
        query = query.order_by(getattr(User, sort).asc())
    pag = query.paginate(page=page, per_page=per_page, error_out=False)
    data = [
        {'id':u.id,'username':u.username,'email':u.email,'role':u.role,'active':u.active}
        for u in pag.items
    ]
    return jsonify({'items':data,'page':pag.page,'pages':pag.pages,'total':pag.total})

@csrf.exempt
@app.route('/api/users', methods=['POST'])
@login_required
def api_users_create():
    if not can_perm('users','add'):
        return jsonify({'error':'forbidden'}), 403
    payload = request.get_json(force=True) or {}
    username = (payload.get('username') or '').strip()
    email = (payload.get('email') or '').strip() or None
    role = (payload.get('role') or 'user').strip()
    password = (payload.get('password') or '').strip()
    if not username or not password:
        return jsonify({'error':'username and password required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error':'username already exists'}), 400
    u = User(username=username, email=email, role=role, active=True)
    u.set_password(password, bcrypt)
    db.session.add(u)
    db.session.commit()
    return jsonify({'status':'ok','id':u.id})

@csrf.exempt
@app.route('/api/users/<int:uid>', methods=['PATCH'])
@login_required
def api_users_update(uid):
    u = User.query.get_or_404(uid)
    payload = request.get_json(force=True) or {}
    for field in ['email','role']:
        if field in payload:
            setattr(u, field, payload[field])
    if 'active' in payload:
        u.active = bool(payload['active'])
    if 'password' in payload and payload['password']:
        u.set_password(payload['password'], bcrypt)
    db.session.commit()
    return jsonify({'status':'ok'})

@csrf.exempt
@app.route('/api/users', methods=['DELETE'])
@login_required
def api_users_delete():
    if not can_perm('users','delete'):
        return jsonify({'error':'forbidden'}), 403
    payload = request.get_json(force=True) or {}
    ids = payload.get('ids') or []
    if not ids:
        return jsonify({'error':'no ids'}), 400
    User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'status':'ok','deleted':len(ids)})

# ----- Permissions enforcement helpers -----
from functools import wraps
from flask import abort

def user_has_perm(user, screen_key:str, perm:str)->bool:
    try:
        if getattr(user, 'role', '') == 'admin':
            return True
        from models import UserPermission
        q = UserPermission.query.filter_by(user_id=user.id, screen_key=screen_key)
        # If any scope grants the permission, allow
        for p in q.all():
            if perm == 'view' and p.can_view: return True
            if perm == 'add' and p.can_add: return True
            if perm == 'edit' and p.can_edit: return True
            if perm == 'delete' and p.can_delete: return True
            if perm == 'print' and p.can_print: return True
    except Exception:
        pass
    return False

def require_perm(screen_key:str, perm:str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if getattr(current_user, 'role', '') == 'admin' or user_has_perm(current_user, screen_key, perm):
                return fn(*args, **kwargs)
            # API vs Page
            if request.path.startswith('/api/'):
                return jsonify({'error':'forbidden', 'detail': f'missing {screen_key}:{perm}'}), 403
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('dashboard'))
        return wrapper
    return decorator

@app.context_processor
def inject_can():
    return dict(can=lambda screen,perm: (getattr(current_user,'role','')=='admin') or user_has_perm(current_user, screen, perm))

# ---------------------- Permissions API ----------------------
from models import UserPermission

@csrf.exempt
@app.route('/api/users/<int:uid>/permissions', methods=['GET'])
@login_required
def api_user_permissions_get(uid):
    if not can_perm('users','view'):
        return jsonify({'error':'forbidden'}), 403
    User.query.get_or_404(uid)
    scope = request.args.get('branch_scope')
    q = UserPermission.query.filter_by(user_id=uid)
    if scope:
        q = q.filter_by(branch_scope=scope)
    perms = q.all()
    out = [
        {
            'screen_key': p.screen_key,
            'branch_scope': p.branch_scope,
            'view': p.can_view,
            'add': p.can_add,
            'edit': p.can_edit,
            'delete': p.can_delete,
            'print': p.can_print,
        } for p in perms
    ]
    return jsonify({'items': out})

@csrf.exempt
@app.route('/api/users/<int:uid>/permissions', methods=['POST'])
@login_required
def api_user_permissions_save(uid):
    if not can_perm('users','edit'):
        return jsonify({'error':'forbidden'}), 403
    User.query.get_or_404(uid)
    payload = request.get_json(force=True) or {}
    items = payload.get('items') or []
    branch_scope = (payload.get('branch_scope') or 'all').lower()
    # Remove existing for this branch scope, then insert new
    UserPermission.query.filter_by(user_id=uid, branch_scope=branch_scope).delete(synchronize_session=False)
    for it in items:
        key = (it.get('screen_key') or '').strip()
        if not key: continue
        p = UserPermission(
            user_id=uid, screen_key=key, branch_scope=branch_scope,
            can_view=bool(it.get('view')), can_add=bool(it.get('add')),
            can_edit=bool(it.get('edit')), can_delete=bool(it.get('delete')),
            can_print=bool(it.get('print'))
        )
        db.session.add(p)
    db.session.commit()
    return jsonify({'status':'ok','count':len(items)})


@app.route('/users')
@login_required
@require_perm('users','view')
def users():
    us = User.query.order_by(User.username.asc()).all()
    return render_template('users.html', users=us)

# Invoice management routes
@app.route('/invoices/print/<string:section>')
@login_required
def print_invoices(section):
    from flask import make_response
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import io

    if section == 'all':
        query = Invoice.query.all()
    else:
        query = Invoice.query.filter_by(invoice_type=section).all()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    y = 800

    # Helpers: register Arabic-capable font and shape Arabic text if libs exist
    def register_ar_font():
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import os as _os
            candidates = [
                r"C:\\Windows\\Fonts\\trado.ttf",  # Traditional Arabic (Windows)
                r"C:\\Windows\\Fonts\\arial.ttf",
                r"C:\\Windows\\Fonts\\Tahoma.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
            ]
            for fp in candidates:
                if _os.path.exists(fp):
                    pdfmetrics.registerFont(TTFont('Arabic', fp))
                    return 'Arabic'
        except Exception:
            pass
        return None

    def shape_ar(text:str)->str:
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text

    # Header with company name
    try:
        from models import Settings
        s = Settings.query.first()
        company_name = (s.company_name or '').strip() if s and s.company_name else ''
    except Exception:
        company_name = ''

    ar_font = register_ar_font()
    if ar_font:
        p.setFont(ar_font, 14)
        p.drawString(50, y, shape_ar(company_name or "Company"))
        y -= 20
        p.setFont(ar_font, 12)
        p.drawString(50, y, shape_ar(f"Invoices - {section.title()}"))
    else:
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, company_name or "Company")
        y -= 20
        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Invoices - {section.title()}")
    y -= 30

    # Body rows
    if ar_font:
        p.setFont(ar_font, 10)
    else:
        p.setFont("Helvetica", 10)
    for inv in query:
        line = f"{getattr(inv,'invoice_number','')} | {getattr(inv,'customer_supplier','') or ''} | {getattr(inv,'total_amount','')} | {getattr(inv,'status','')}"
        p.drawString(50, y, shape_ar(line) if ar_font else line)
        y -= 20
        if y < 50:  # New page if needed
            p.showPage()
            y = 800
            if ar_font:
                p.setFont(ar_font, 10)
            else:
                p.setFont("Helvetica", 10)

    p.showPage()
    p.save()

    buffer.seek(0)
    return make_response(buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'inline; filename="{section}_invoices.pdf"'
    })

@app.route('/invoices/single_payment/<int:invoice_id>', methods=['POST'])
@login_required
def single_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    payment_amount = float(request.form.get('payment_amount', 0))

    if payment_amount > 0:
        invoice.paid_amount += payment_amount
        invoice.update_status()
        db.session.commit()

        # Emit real-time update
        socketio.emit('invoice_update', {
            'invoice_id': invoice_id,
            'new_status': invoice.status,
            'paid_amount': invoice.paid_amount
        }, broadcast=True)

        flash(_('Payment recorded successfully / تم تسجيل الدفعة بنجاح'), 'success')

    return redirect(url_for('invoices'))

@app.route('/invoices/bulk_payment', methods=['POST'])
@login_required
def bulk_payment():
    invoice_ids = request.form.getlist('invoice_ids')
    bulk_payment_amount = float(request.form.get('bulk_payment_amount', 0))

    if invoice_ids and bulk_payment_amount > 0:
        # Distribute payment equally among selected invoices
        payment_per_invoice = bulk_payment_amount / len(invoice_ids)

        for invoice_id in invoice_ids:
            invoice = Invoice.query.get(int(invoice_id))
            if invoice:
                invoice.paid_amount += payment_per_invoice
                invoice.update_status()

        db.session.commit()

        # Emit real-time update
        socketio.emit('invoice_update', {
            'bulk_update': True,
            'updated_invoices': invoice_ids
        }, broadcast=True)

        flash(_('Bulk payment recorded successfully / تم تسجيل الدفعة الجماعية بنجاح'), 'success')

    return redirect(url_for('invoices'))

# Raw Materials Management
@app.route('/raw_materials', methods=['GET', 'POST'])
@login_required
def raw_materials():
    form = RawMaterialForm()

    if form.validate_on_submit():
        raw_material = RawMaterial(
            name=form.name.data,
            name_ar=form.name_ar.data,
            unit=form.unit.data,
            cost_per_unit=form.cost_per_unit.data,
            category=form.category.data,
            active=True
        )
        db.session.add(raw_material)
        db.session.commit()

        flash(_('Raw material added successfully / تم إضافة المادة الخام بنجاح'), 'success')
        return redirect(url_for('raw_materials'))

    materials = RawMaterial.query.filter_by(active=True).all()
    return render_template('raw_materials.html', form=form, materials=materials)

# Meals Management
@app.route('/meals', methods=['GET', 'POST'])
@login_required
def meals():
    import json

    # Get raw materials for dropdown
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    material_choices = [(0, _('Select Ingredient / اختر المكون'))] + [(m.id, m.display_name) for m in raw_materials]

    form = MealForm()

    # Set material choices for all ingredient forms
    for ingredient_form in form.ingredients:
        ingredient_form.raw_material_id.choices = material_choices

    # Prepare materials JSON for JavaScript cost calculation
    materials_json = json.dumps([{
        'id': m.id,
        'name': m.display_name,
        'cost_per_unit': float(m.cost_per_unit),
        'unit': m.unit
    } for m in raw_materials])

    if form.validate_on_submit():
        # Create meal
        meal = Meal(
            name=form.name.data,
            name_ar=form.name_ar.data,
            description=form.description.data,
            category=form.category.data,
            profit_margin_percent=form.profit_margin_percent.data,
            user_id=current_user.id
        )
        db.session.add(meal)
        db.session.flush()  # Get meal ID

        # Add ingredients and calculate total cost
        total_cost = 0
        for ingredient_form in form.ingredients.entries:
            if ingredient_form.raw_material_id.data and ingredient_form.raw_material_id.data != 0:
                raw_material = RawMaterial.query.get(ingredient_form.raw_material_id.data)
                if raw_material:
                    ingredient = MealIngredient(
                        meal_id=meal.id,
                        raw_material_id=raw_material.id,
                        quantity=ingredient_form.quantity.data
                    )
                    ingredient.calculate_cost()
                    db.session.add(ingredient)
                    total_cost += float(ingredient.total_cost)

        # Update meal costs
        meal.total_cost = total_cost
        meal.calculate_selling_price()

        db.session.commit()

        # Emit real-time update
        socketio.emit('meal_update', {
            'meal_name': meal.display_name,
            'total_cost': float(meal.total_cost),
            'selling_price': float(meal.selling_price)
        }, broadcast=True)

        flash(_('Meal created successfully / تم إنشاء الوجبة بنجاح'), 'success')
        return redirect(url_for('meals'))

    # Get all meals
    all_meals = Meal.query.filter_by(active=True).all()
    return render_template('meals.html', form=form, meals=all_meals, materials_json=materials_json)

# Delete routes
@app.route('/delete_raw_material/<int:material_id>', methods=['POST'])
@login_required
def delete_raw_material(material_id):
    material = RawMaterial.query.get_or_404(material_id)

    # Check if material is used in any meals
    meals_using_material = MealIngredient.query.filter_by(raw_material_id=material_id).all()
    if meals_using_material:
        meal_names = [ingredient.meal.display_name for ingredient in meals_using_material]
        flash(_('Cannot delete material. It is used in meals: {}').format(', '.join(meal_names)), 'error')
        return redirect(url_for('raw_materials'))

    # Check if material is used in any purchase invoices
    purchase_items = PurchaseInvoiceItem.query.filter_by(raw_material_id=material_id).all()
    if purchase_items:
        flash(_('Cannot delete material. It has purchase history. Material will be deactivated instead.'), 'warning')
        material.active = False
    else:
        db.session.delete(material)

    db.session.commit()
    flash(_('Raw material deleted successfully / تم حذف المادة الخام بنجاح'), 'success')
    return redirect(url_for('raw_materials'))

@app.route('/delete_meal/<int:meal_id>', methods=['POST'])
@login_required
def delete_meal(meal_id):
    meal = Meal.query.get_or_404(meal_id)

    # Check if meal is used in any sales invoices
    sales_items = SalesInvoiceItem.query.filter_by(product_name=meal.display_name).all()
    if sales_items:
        flash(_('Cannot delete meal. It has sales history. Meal will be deactivated instead.'), 'warning')
        meal.active = False
    else:
        # Delete meal ingredients first
        MealIngredient.query.filter_by(meal_id=meal_id).delete()
        db.session.delete(meal)

    db.session.commit()
    flash(_('Meal deleted successfully / تم حذف الوجبة بنجاح'), 'success')
    return redirect(url_for('meals'))

@app.route('/delete_purchase_invoice/<int:invoice_id>', methods=['POST'])
@login_required
def delete_purchase_invoice(invoice_id):
    invoice = PurchaseInvoice.query.get_or_404(invoice_id)

    # Reverse stock updates
    for item in invoice.items:
        raw_material = item.raw_material
        if raw_material:
            # Reduce stock quantity
            raw_material.stock_quantity -= item.quantity

            # Recalculate weighted average cost (simplified approach)
            # In a real system, you might want to track cost history more precisely
            if raw_material.stock_quantity <= 0:
                raw_material.stock_quantity = 0
                # Keep the last known cost

    # Delete invoice items first
    PurchaseInvoiceItem.query.filter_by(invoice_id=invoice_id).delete()

    # Delete invoice
    db.session.delete(invoice)
    db.session.commit()

    flash(_('Purchase invoice deleted and stock updated / تم حذف فاتورة الشراء وتحديث المخزون'), 'success')
    return redirect(url_for('purchases'))

@app.route('/delete_sales_invoice/<int:invoice_id>', methods=['POST'])
@login_required
def delete_sales_invoice(invoice_id):
    invoice = SalesInvoice.query.get_or_404(invoice_id)

    # Delete invoice items first
    SalesInvoiceItem.query.filter_by(invoice_id=invoice_id).delete()

    # Delete invoice
    db.session.delete(invoice)
    db.session.commit()

    flash(_('Sales invoice deleted successfully / تم حذف فاتورة المبيعات بنجاح'), 'success')
    return redirect(url_for('sales'))

@app.route('/delete_expense_invoice/<int:invoice_id>', methods=['POST'])
@login_required
def delete_expense_invoice(invoice_id):
    invoice = ExpenseInvoice.query.get_or_404(invoice_id)

    # Delete invoice items first
    ExpenseInvoiceItem.query.filter_by(invoice_id=invoice_id).delete()

    # Delete invoice
    db.session.delete(invoice)
    db.session.commit()

    flash(_('Expense invoice deleted successfully / تم حذف فاتورة المصروفات بنجاح'), 'success')
    return redirect(url_for('expenses'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
