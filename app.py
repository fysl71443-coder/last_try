# This file has been cleaned up - the main app is now in app/__init__.py
# Run the application using: python -m app


# --- Bootstrap minimal Flask app early so decorators and Jinja loader work ---
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, current_app

# Create Flask app instance
app = Flask(__name__)
try:
    from flask_login import LoginManager, login_required, current_user, login_user, logout_user
except Exception:
    # Fallbacks if flask_login is unavailable during import
    class _DummyUser: pass
    def login_required(f):
        return f
    current_user = _DummyUser()
    def login_user(*args, **kwargs):
        pass
    def logout_user(*args, **kwargs):
        pass
    LoginManager = lambda app=None: None
try:
    from flask_babel import gettext as _, Babel
except Exception:
    _ = lambda s, **kwargs: (s.format(**kwargs) if kwargs else s)
    Babel = None

_app_secret = os.getenv('SECRET_KEY', 'dev')
try:
    from config import Config as _AppConfig
    app.config.from_object(_AppConfig)
except Exception:
    pass
try:
    from extensions import db as db, bcrypt as bcrypt
    db.init_app(app)
except Exception as _db_init_err:
    try:
        print(f"⚠️ DB init warning: {_db_init_err}")
    except Exception:
        pass
app.secret_key = _app_secret
app.config['SECRET_KEY'] = _app_secret
app.config.setdefault('WTF_CSRF_SECRET_KEY', _app_secret)
# Session settings - expire when browser closes
app.config['PERMANENT_SESSION_LIFETIME'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
login_manager = LoginManager(app) if callable(LoginManager) else None
try:
    from extensions import csrf as _csrf
    if _csrf:
        _csrf.init_app(app)
except Exception:
    _csrf = None
# Initialize Babel if available
babel = None
try:
    if 'Babel' in globals() and Babel:
        babel = Babel(app)
except Exception:
    babel = None

# Login manager config and user_loader
try:
    from extensions import db as _db
    from models import User
    if login_manager:
        login_manager.login_view = 'login'
        login_manager.session_protection = "strong"  # Stronger session protection
        @login_manager.user_loader
        def load_user(user_id):
            try:
                return _db.session.get(User, int(user_id))
            except Exception:
                return None
except Exception:
    # If models/extensions not ready yet, a later block may re-register user_loader
    pass

# Ensure key models are importable at module scope to avoid NameError in routes
try:
    from models import RawMaterial, ExpenseInvoice, ExpenseInvoiceItem, TableSettings
except Exception:
    # Will be imported lazily inside routes if needed
    RawMaterial = globals().get('RawMaterial')
    ExpenseInvoice = globals().get('ExpenseInvoice')
    ExpenseInvoiceItem = globals().get('ExpenseInvoiceItem')
    TableSettings = globals().get('TableSettings')


# ===== شاشة المبيعات الجديدة (من clean_sales_app.py) =====
from jinja2 import DictLoader
from datetime import datetime
from zoneinfo import ZoneInfo

# بيانات الفروع والطاولات
branches = [
    {"code": "CT", "name": "CHINA TOWN"},
    {"code": "PI", "name": "PALACE INDIA"},
]
tables_data = {
    "CT": [{"number": i, "is_busy": False} for i in range(1, 10)],
    "PI": [{"number": i, "is_busy": False} for i in range(1, 7)],
}

# بيانات العملاء
customers_data = [
    {"id": 1, "name": "Ahmed Ali", "phone": "+966500000001", "discount": 10},
    {"id": 2, "name": "Sara Mohammed", "phone": "+966500000002", "discount": 5},
    {"id": 3, "name": "Mohammed Saad", "phone": "+966500000003", "discount": 0},
]

# إعدادات المطعم
settings_sales = {
    "restaurant_name": "PALACE INDIA",
    "vat_number": "300000000000003",
    "address": "Riyadh, KSA",
    "phone": "+966500000000",
    "logo_base64": "",
    "currency_code": "SAR",
    "currency_png_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==",
}

# بيانات المنيو
menu_data = {

    1: {"name": "Appetizers", "items": [{"name": "Spring Rolls", "price": 12.0}, {"name": "Garlic Bread", "price": 8.0}]},
    2: {"name": "Beef & Lamb", "items": [{"name": "Beef Steak", "price": 45.0}, {"name": "Lamb Chops", "price": 48.0}]},
    3: {"name": "Charcoal Grill / Kebabs", "items": [{"name": "Chicken Kebab", "price": 25.0}, {"name": "Seekh Kebab", "price": 27.0}]},
    4: {"name": "Chicken", "items": [{"name": "Butter Chicken", "price": 30.0}, {"name": "Grilled Chicken", "price": 28.0}]},
    5: {"name": "Chinese Sizzling", "items": [{"name": "Kung Pao Chicken", "price": 32.0}, {"name": "Szechuan Beef", "price": 35.0}]},
    6: {"name": "House Special", "items": [{"name": "Chef Special Noodles", "price": 22.0}]},
    7: {"name": "Indian Delicacy (Chicken)", "items": [{"name": "Tandoori Chicken", "price": 29.0}]},
    8: {"name": "Indian Delicacy (Fish)", "items": [{"name": "Fish Curry", "price": 33.0}]},
    9: {"name": "Indian Delicacy (Vegetables)", "items": [{"name": "Paneer Masala", "price": 24.0}]},
    10: {"name": "Juices", "items": [{"name": "Orange Juice", "price": 10.0}, {"name": "Apple Juice", "price": 10.0}]},
    11: {"name": "Noodles & Chopsuey", "items": [{"name": "Veg Noodles", "price": 18.0}, {"name": "Chicken Chopsuey", "price": 20.0}]},
    12: {"name": "Prawns", "items": [{"name": "Fried Prawns", "price": 38.0}]},
    13: {"name": "Rice & Biryani", "items": [{"name": "Chicken Biryani", "price": 26.0}, {"name": "Veg Biryani", "price": 22.0}]},
    14: {"name": "Salads", "items": [{"name": "Greek Salad", "price": 16.0}, {"name": "Caesar Salad", "price": 18.0}]},
    15: {"name": "Seafoods", "items": [{"name": "Grilled Salmon", "price": 42.0}]},
    16: {"name": "Shaw Faw", "items": [{"name": "Shawarma Wrap", "price": 15.0}]},
    17: {"name": "Soft Drink", "items": [{"name": "Coke", "price": 6.0}, {"name": "Pepsi", "price": 6.0}]},
    18: {"name": "Soups", "items": [{"name": "Tomato Soup", "price": 12.0}, {"name": "Chicken Soup", "price": 14.0}]},
}

# تخزين الفواتير لكل طاولة

# API: Purchases report (JSON)
@app.route('/api/reports/purchases')
def api_purchases_report():
    try:
        from datetime import datetime, date as _date
        from sqlalchemy import func
        from models import PurchaseInvoice, PurchaseInvoiceItem
        # Parse filters
        sd = request.args.get('start_date'); ed = request.args.get('end_date')
        if sd and ed:
            start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        else:
            today = _date.today()
            start_dt = _date(today.year, today.month, 1)
            end_dt = today
        rows = db.session.query(
            PurchaseInvoice.date.label('date'),
            PurchaseInvoice.invoice_number.label('invoice_number'),
            PurchaseInvoice.payment_method.label('payment_method'),
            PurchaseInvoice.supplier_name.label('supplier'),
            PurchaseInvoiceItem.raw_material_name.label('item_name'),
            PurchaseInvoiceItem.quantity.label('qty'),
            PurchaseInvoiceItem.price_before_tax.label('unit_price'),
            PurchaseInvoiceItem.tax.label('tax')
        ).join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
         .filter(PurchaseInvoice.date.between(start_dt, end_dt)).all()
        data = []
        for r in rows:
            amount_bt = float(r.unit_price or 0) * float(r.qty or 0)
            data.append({
                'date': str(r.date),
                'invoice': r.invoice_number,
                'item': r.item_name,
                'amount': amount_bt,
                'tax': float(r.tax or 0),
                'payment': f"{(r.payment_method or '').upper()} / {(r.supplier or '')}"
            })
        return jsonify({'purchases': data})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'purchases': [], 'error': str(e)}), 500

# API: Expenses report (JSON)
@app.route('/api/reports/expenses')
def api_expenses_report():
    try:
        from datetime import datetime, date as _date
        from sqlalchemy import func
        from models import ExpenseInvoice, ExpenseInvoiceItem
        sd = request.args.get('start_date'); ed = request.args.get('end_date')
        if sd and ed:
            start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        else:
            today = _date.today()
            start_dt = _date(today.year, today.month, 1)
            end_dt = today
        rows = db.session.query(
            ExpenseInvoice.date.label('date'),
            ExpenseInvoice.invoice_number.label('invoice_number'),
            ExpenseInvoice.payment_method.label('payment_method'),
            ExpenseInvoiceItem.description.label('desc'),
            ExpenseInvoiceItem.quantity.label('qty'),
            ExpenseInvoiceItem.price_before_tax.label('unit_price'),
            ExpenseInvoiceItem.tax.label('tax'),
            ExpenseInvoiceItem.discount.label('discount')
        ).join(ExpenseInvoice, ExpenseInvoiceItem.invoice_id == ExpenseInvoice.id) \
         .filter(ExpenseInvoice.date.between(start_dt, end_dt)).all()
        data = []
        for r in rows:
            amount_line = (float(r.unit_price or 0) * float(r.qty or 0)) + float(r.tax or 0) - float(r.discount or 0)
            data.append({
                'date': str(r.date),
                'voucher': r.invoice_number,
                'type': r.desc,
                'amount': amount_line,
                'payment': r.payment_method
            })
        return jsonify({'expenses': data})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'expenses': [], 'error': str(e)}), 500

# API: Payroll report (JSON)
# API: All invoices (Sales + Purchases + Expenses) unified rows
@app.route('/api/reports/all-invoices')
def api_all_invoices():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import SalesInvoice, SalesInvoiceItem, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem
        # Read filters (optional, same as others)
        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        branch = (request.args.get('branch') or 'all').lower()
        pm = (request.args.get('payment_method') or 'all').lower()
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max

        rows = []
        branch_totals = {}
        def _add_branch_tot(bname, amount, discount, vat, total):
            s = branch_totals.get(bname) or {'amount':0.0,'discount':0.0,'vat':0.0,'total':0.0}
            s['amount'] += float(amount or 0)
            s['discount'] += float(discount or 0)
            s['vat'] += float(vat or 0)
            s['total'] += float(total or 0)
            branch_totals[bname] = s

        # Sales
        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(SalesInvoiceItem, SalesInvoiceItem.invoice_id==SalesInvoice.id)
        q = q.filter(SalesInvoice.date.between(start_d, end_d))
        if branch != 'all':
            b = 'china_town' if 'china' in branch else ('place_india' if ('india' in branch or 'place' in branch) else branch)
            q = q.filter(SalesInvoice.branch == b)
        if pm != 'all':
            q = q.filter(func.lower(SalesInvoice.payment_method) == pm)
        for inv, it in q.order_by(SalesInvoice.branch.asc(), SalesInvoice.date.desc(), SalesInvoice.id.desc(), SalesInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0)
            unit = float(it.price_before_tax or 0)
            amount = unit * qty
            total_line = float(it.total_price or (amount - float(it.discount or 0) + float(it.tax or 0)))
            bname = BRANCH_CODES.get(inv.branch, inv.branch)
            rows.append({
                'branch': bname,
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'invoice_number': inv.invoice_number,
                'item_name': it.product_name,
                'quantity': qty,
                'price': float(amount),
                'discount': float(it.discount or 0),
                'vat': float(it.tax or 0),
                'total': total_line,
                'payment_method': inv.payment_method or ''
            })
            _add_branch_tot(bname, amount, it.discount, it.tax, total_line)
        # Purchases
        pq = db.session.query(PurchaseInvoice, PurchaseInvoiceItem).join(PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id==PurchaseInvoice.id)
        pq = pq.filter(PurchaseInvoice.date.between(start_d, end_d))
        if pm != 'all':
            pq = pq.filter(func.lower(PurchaseInvoice.payment_method) == pm)
        for inv, it in pq.order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc(), PurchaseInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0)
            unit = float(it.price_before_tax or 0)
            amount = unit * qty
            total_line = float(it.total_price or (amount - float(it.discount or 0) + float(it.tax or 0)))
            bname = 'Purchases'
            rows.append({
                'branch': bname,
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'invoice_number': inv.invoice_number,
                'item_name': it.raw_material_name,
                'quantity': qty,
                'price': float(amount),
                'discount': float(it.discount or 0),
                'vat': float(it.tax or 0),
                'total': total_line,
                'payment_method': inv.payment_method or ''
            })
            _add_branch_tot(bname, amount, it.discount, it.tax, total_line)
        # Expenses
        eq = db.session.query(ExpenseInvoice, ExpenseInvoiceItem).join(ExpenseInvoiceItem, ExpenseInvoiceItem.invoice_id==ExpenseInvoice.id)
        eq = eq.filter(ExpenseInvoice.date.between(start_d, end_d))
        if pm != 'all':
            eq = eq.filter(func.lower(ExpenseInvoice.payment_method) == pm)
        for inv, it in eq.order_by(ExpenseInvoice.date.desc(), ExpenseInvoice.id.desc(), ExpenseInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0)
            unit = float(it.price_before_tax or 0)
            amount = unit * qty
            total_line = float(it.total_price or (amount - float(it.discount or 0) + float(it.tax or 0)))
            bname = 'Expenses'
            rows.append({
                'branch': bname,
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'invoice_number': inv.invoice_number,
                'item_name': it.description,
                'quantity': qty,
                'price': float(amount),
                'discount': float(it.discount or 0),
                'vat': float(it.tax or 0),
                'total': total_line,
                'payment_method': inv.payment_method or ''
            })
            _add_branch_tot(bname, amount, it.discount, it.tax, total_line)

        # Summary (overall totals)
        summary = {
            'amount': sum(r.get('price', 0.0) for r in rows),
            'discount': sum(r.get('discount', 0.0) for r in rows),
            'vat': sum(r.get('vat', 0.0) for r in rows),
            'total': sum(r.get('total', 0.0) for r in rows),
        }
        return jsonify({'invoices': rows, 'branch_totals': branch_totals, 'overall_totals': summary, 'summary': summary})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'invoices': [], 'branch_totals': {}, 'overall_totals': {'amount':0,'discount':0,'vat':0,'total':0}, 'summary': {'amount':0,'discount':0,'vat':0,'total':0}, 'error': str(e)}), 500


# Alias endpoint for dashboard All Invoices page to reuse the same data structure
@app.route('/api/all-invoices')
def api_all_invoices_alias():
    return api_all_invoices()

# Dashboard page: All Invoices (itemized, grouped by branch)
@app.route('/all-invoices')
@login_required
def all_invoices_page():
    return render_template('all_invoices.html')


# Printable reports for All Invoices page
@app.route('/reports/print/all-invoices/sales')
@login_required
def print_all_invoices_sales():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import SalesInvoice, SalesInvoiceItem
        # filters
        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        pm = (request.args.get('payment_method') or 'all').lower()
        branch = (request.args.get('branch') or 'all').lower()
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max
        rows = []
        branch_totals = {}
        def _add_branch_tot(bname, amount, discount, vat, total):
            s = branch_totals.get(bname) or {'amount':0.0,'discount':0.0,'vat':0.0,'total':0.0}
            s['amount'] += float(amount or 0)
            s['discount'] += float(discount or 0)
            s['vat'] += float(vat or 0)
            s['total'] += float(total or 0)
            branch_totals[bname] = s
        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(SalesInvoiceItem, SalesInvoiceItem.invoice_id==SalesInvoice.id)
        q = q.filter(SalesInvoice.date.between(start_d, end_d))
        if branch != 'all':
            b = 'china_town' if 'china' in branch else ('place_india' if ('india' in branch or 'place' in branch) else branch)
            q = q.filter(SalesInvoice.branch == b)
        if pm != 'all':
            q = q.filter(func.lower(SalesInvoice.payment_method) == pm)
        for inv, it in q.order_by(SalesInvoice.branch.asc(), SalesInvoice.date.desc(), SalesInvoice.id.desc(), SalesInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0); unit = float(it.price_before_tax or 0)
            amount = unit * qty
            total_line = float(it.total_price or (amount - float(it.discount or 0) + float(it.tax or 0)))
            bname = BRANCH_CODES.get(inv.branch, inv.branch)
            rows.append({
                'branch': bname,
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'invoice_number': inv.invoice_number,
                'item_name': it.product_name,
                'quantity': qty,
                'amount': float(amount),
                'discount': float(it.discount or 0),
                'vat': float(it.tax or 0),
                'total': total_line,
                'payment_method': inv.payment_method or ''
            })
            _add_branch_tot(bname, amount, it.discount, it.tax, total_line)
        overall = {
            'amount': sum(r.get('amount', 0.0) for r in rows),
            'discount': sum(r.get('discount', 0.0) for r in rows),
            'vat': sum(r.get('vat', 0.0) for r in rows),
            'total': sum(r.get('total', 0.0) for r in rows),
        }
        rows.sort(key=lambda r: (r.get('branch') or '', r.get('date') or ''), reverse=True)
        meta = {
            'title': 'All Invoices — Sales (Detailed)',
            'generated_at': _dt.now().strftime('%Y-%m-%d %H:%M'),
            'start_date': start_s,
            'end_date': end_s,
            'payment_method': pm,
            'branch': branch,
        }
        from models import Settings
        settings = Settings.query.first()
        # Build unified columns/data for generic print template
        columns = ["Branch","Date","Invoice No","Item","Qty","Amount","Discount","VAT","Total","Payment Method"]
        data = []
        for r in rows:
            data.append({
                "Branch": r.get('branch',''),
                "Date": r.get('date',''),
                "Invoice No": r.get('invoice_number',''),
                "Item": r.get('item_name',''),
                "Qty": r.get('quantity',0),
                "Amount": r.get('amount',0),
                "Discount": r.get('discount',0),
                "VAT": r.get('vat',0),
                "Total": r.get('total',0),
                "Payment Method": r.get('payment_method','')
            })
        # Append branch totals as data rows
        for b, t in sorted(branch_totals.items()):
            data.append({
                "Branch": f"Branch Totals ({b})",
                "Date": "",
                "Invoice No": "",
                "Item": "",
                "Qty": "",
                "Amount": t.get('amount',0),
                "Discount": t.get('discount',0),
                "VAT": t.get('vat',0),
                "Total": t.get('total',0),
                "Payment Method": ""
            })
        totals = {"Amount": overall.get('amount',0), "Discount": overall.get('discount',0), "VAT": overall.get('vat',0), "Total": overall.get('total',0)}
        return render_template('print_report.html',
                               report_title="Sales Invoices",
                               columns=columns,
                               data=data,
                               totals=totals,
                               totals_columns=["Amount","Discount","VAT","Total"],
                               totals_colspan=5,
                               settings=settings,
                               start_date=meta.get('start_date'), end_date=meta.get('end_date'),
                               payment_method=meta.get('payment_method'), branch=meta.get('branch'),
                               generated_at=meta.get('generated_at'))
    except Exception as e:
        logging.exception('print_all_invoices_sales error')
        flash(_('Error generating report'), 'danger')
        return redirect(url_for('invoices'))

@app.route('/reports/print/all-invoices/purchases')
@login_required
def print_all_invoices_purchases():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import PurchaseInvoice, PurchaseInvoiceItem
        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        pm = (request.args.get('payment_method') or 'all').lower()
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max
        rows = []
        q = db.session.query(PurchaseInvoice, PurchaseInvoiceItem).join(PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id==PurchaseInvoice.id)
        q = q.filter(PurchaseInvoice.date.between(start_d, end_d))
        if pm != 'all':
            q = q.filter(func.lower(PurchaseInvoice.payment_method) == pm)
        for inv, it in q.order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc(), PurchaseInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0); unit = float(it.price_before_tax or 0)
            amount = unit * qty
            total_line = float(it.total_price or (amount - float(it.discount or 0) + float(it.tax or 0)))
            rows.append({
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'invoice_number': inv.invoice_number,
                'item_name': it.raw_material_name,
                'quantity': qty,
                'amount': float(amount),
                'discount': float(it.discount or 0),
                'vat': float(it.tax or 0),
                'total': total_line,
                'payment_method': inv.payment_method or ''
            })
        overall = {
            'amount': sum(r.get('amount', 0.0) for r in rows),
            'discount': sum(r.get('discount', 0.0) for r in rows),
            'vat': sum(r.get('vat', 0.0) for r in rows),
            'total': sum(r.get('total', 0.0) for r in rows),
        }
        meta = {
            'title': 'All Invoices — Purchases (Detailed)',
            'generated_at': _dt.now().strftime('%Y-%m-%d %H:%M'),
            'start_date': start_s,
            'end_date': end_s,
            'payment_method': pm,
        }
        from models import Settings
        settings = Settings.query.first()
        columns = ["Date","Purchase No","Item","Qty","Amount","Discount","VAT","Total","Payment Method"]
        data = []
        for r in rows:
            data.append({
                "Date": r.get('date',''),
                "Purchase No": r.get('invoice_number',''),
                "Item": r.get('item_name',''),
                "Qty": r.get('quantity',0),
                "Amount": r.get('amount',0),
                "Discount": r.get('discount',0),
                "VAT": r.get('vat',0),
                "Total": r.get('total',0),
                "Payment Method": r.get('payment_method','')
            })
        totals = {"Amount": overall.get('amount',0), "Discount": overall.get('discount',0), "VAT": overall.get('vat',0), "Total": overall.get('total',0)}
        return render_template('print_report.html',
                               report_title="Purchase Invoices",
                               columns=columns,
                               data=data,
                               totals=totals,
                               totals_columns=["Amount","Discount","VAT","Total"],
                               totals_colspan=4,
                               settings=settings,
                               start_date=meta.get('start_date'), end_date=meta.get('end_date'),
                               payment_method=meta.get('payment_method'),
                               generated_at=meta.get('generated_at'))
    except Exception as e:
        logging.exception('print_all_invoices_purchases error')
        flash(_('Error generating report'), 'danger')
        return redirect(url_for('invoices'))
@app.route('/reports/print/all-invoices/expenses')
@login_required
def print_all_invoices_expenses():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import ExpenseInvoice, ExpenseInvoiceItem
        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        pm = (request.args.get('payment_method') or 'all').lower()
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max
        rows = []
        q = db.session.query(ExpenseInvoice, ExpenseInvoiceItem).join(ExpenseInvoiceItem, ExpenseInvoiceItem.invoice_id==ExpenseInvoice.id)
        q = q.filter(ExpenseInvoice.date.between(start_d, end_d))
        if pm != 'all':
            q = q.filter(func.lower(ExpenseInvoice.payment_method) == pm)
        for inv, it in q.order_by(ExpenseInvoice.date.desc(), ExpenseInvoice.id.desc(), ExpenseInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0); unit = float(it.price_before_tax or 0)
            amount = unit * qty
            rows.append({
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'expense_number': inv.invoice_number,
                'item_name': it.description,
                'amount': float(amount),
                'payment_method': inv.payment_method or ''
            })
        overall = { 'amount': sum(r.get('amount', 0.0) for r in rows) }
        meta = {
            'title': 'All Invoices — Expenses (Detailed)',
            'generated_at': _dt.now().strftime('%Y-%m-%d %H:%M'),
            'start_date': start_s,
            'end_date': end_s,
            'payment_method': pm,
        }
        from models import Settings
        settings = Settings.query.first()
        columns = ["Date","Expense No","Description","Amount","Payment Method"]
        data = []
        for r in rows:
            data.append({
                "Date": r.get('date',''),
                "Expense No": r.get('expense_number',''),
                "Description": r.get('item_name',''),
                "Amount": r.get('amount',0),
                "Payment Method": r.get('payment_method','')
            })
        totals = {"Amount": overall.get('amount',0)}
        return render_template('print_report.html',
                               report_title="Expenses",
                               columns=columns,
                               data=data,
                               totals=totals,
                               totals_columns=["Amount"],
                               totals_colspan=3,
                               settings=settings,
                               start_date=meta.get('start_date'), end_date=meta.get('end_date'),
                               payment_method=meta.get('payment_method'),
                               generated_at=meta.get('generated_at'))
    except Exception as e:
        logging.exception('print_all_invoices_expenses error')
        flash(_('Error generating report'), 'danger')
        return redirect(url_for('invoices'))


# API: All Purchases (no branch grouping) — itemized with overall totals
@app.route('/api/reports/all-purchases')
def api_all_purchases():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import PurchaseInvoice, PurchaseInvoiceItem
        # Filters
        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        pm = (request.args.get('payment_method') or 'all').lower()
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max

        q = db.session.query(PurchaseInvoice, PurchaseInvoiceItem) \
            .join(PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
            .filter(PurchaseInvoice.date.between(start_d, end_d))
        if pm != 'all':
            q = q.filter(func.lower(PurchaseInvoice.payment_method) == pm)
        rows = []
        for inv, it in q.order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc(), PurchaseInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0)
            unit = float(it.price_before_tax or 0)
            amount = unit * qty
            total_line = float(it.total_price or (amount - float(it.discount or 0) + float(it.tax or 0)))
            rows.append({
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'purchase_number': inv.invoice_number,
                'item_name': it.raw_material_name,
                'quantity': qty,
                'price': float(amount),
                'discount': float(it.discount or 0),
                'vat': float(it.tax or 0),
                'total': total_line,
                'payment_method': inv.payment_method or ''
            })
        overall = {
            'amount': sum(r.get('price', 0.0) for r in rows),
            'discount': sum(r.get('discount', 0.0) for r in rows),
            'vat': sum(r.get('vat', 0.0) for r in rows),
            'total': sum(r.get('total', 0.0) for r in rows),
        }
        return jsonify({'purchases': rows, 'overall_totals': overall})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'purchases': [], 'overall_totals': {'amount':0,'discount':0,'vat':0,'total':0}, 'error': str(e)}), 500

    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'invoices': [], 'summary': {'amount':0,'discount':0,'vat':0,'total':0}, 'error': str(e)}), 500
@app.route('/api/reports/payroll')
def api_payroll_report():
    try:
        from datetime import datetime, date as _date
        from sqlalchemy import func
        from models import Salary
        sd = request.args.get('start_date'); ed = request.args.get('end_date')
        if sd and ed:
            start_dt = datetime.strptime(sd, '%Y-%m-%d').date()

            end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        else:
            today = _date.today()
            start_dt = _date(today.year, today.month, 1)
            end_dt = today
        # Map year-month into a comparable value
        start_key = start_dt.year * 100 + start_dt.month
        end_key = end_dt.year * 100 + end_dt.month
        rows = db.session.query(
            Salary.year, Salary.month,
            func.coalesce(func.sum(Salary.basic_salary), 0),
            func.coalesce(func.sum(Salary.allowances), 0),
            func.coalesce(func.sum(Salary.deductions), 0),
            func.coalesce(func.sum(Salary.total_salary), 0),
            func.count('*')
        ).group_by(Salary.year, Salary.month).order_by(Salary.year, Salary.month).all()
        data = []
        for y, m, basic, allow, ded, total, cnt in rows:
            key = int(y) * 100 + int(m)
            if key < start_key or key > end_key:
                continue
            month_str = f"{y:04d}-{int(m):02d}"
            data.append({
                'month': month_str,
                'basic': float(basic or 0),
                'allowances': float(allow or 0),
                'deductions': float(ded or 0),
                'net': float(total or 0),
                'employees': int(cnt or 0)
            })
        return jsonify({'payroll': data})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'payroll': [], 'error': str(e)}), 500

invoices = {}
def get_invoice_obj(branch_code, table_number):
    key = (branch_code, table_number)
    inv = invoices.get(key)
    if inv is None:
        inv = {'items': [], 'customer': None}
        invoices[key] = inv
    elif isinstance(inv, list):
        inv = {'items': inv, 'customer': None}
        invoices[key] = inv
    return inv

# ترقيم الفواتير + توليد TLV للـ ZATCA
invoice_counters = {}
def next_invoice_no(branch_code: str) -> str:
    year = datetime.now(ZoneInfo("Asia/Riyadh")).year
    key = (branch_code, year)
    invoice_counters[key] = invoice_counters.get(key, 0) + 1
    return f"{branch_code}-{year}-{invoice_counters[key]:03d}"

def zatca_tlv_base64(seller_name: str, vat_number: str, timestamp_iso: str, total_with_vat: float, vat_amount: float) -> str:
    import base64
    def tlv(tag: int, value_bytes: bytes) -> bytes:
        length = len(value_bytes)
        return bytes([tag, length]) + value_bytes
    payload = b"".join([
        tlv(1, (seller_name or "").encode("utf-8")),
        tlv(2, (vat_number or "").encode("utf-8")),
        tlv(3, (timestamp_iso or "").encode("utf-8")),
        tlv(4, f"{total_with_vat:.2f}".encode("utf-8")),
        tlv(5, f"{vat_amount:.2f}".encode("utf-8")),
    ])
    return base64.b64encode(payload).decode("utf-8")
# ===== Templates (inline via DictLoader) =====
branches_html = """...existing code..."""
tables_html = """...existing code..."""

@app.route('/all-expenses')
@login_required
def all_expenses_page():
    return render_template('all_expenses.html')

# API: All Expenses (no branch grouping) — itemized with overall totals
@app.route('/api/all-expenses')
@login_required
def api_all_expenses():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import ExpenseInvoice, ExpenseInvoiceItem
        # Filters
        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        pm = (request.args.get('payment_method') or 'all').lower()
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max

        rows = []
        q = db.session.query(ExpenseInvoice, ExpenseInvoiceItem) \
            .join(ExpenseInvoiceItem, ExpenseInvoiceItem.invoice_id == ExpenseInvoice.id)
        q = q.filter(ExpenseInvoice.date.between(start_d, end_d))
        if pm != 'all':
            q = q.filter(func.lower(ExpenseInvoice.payment_method) == pm)
        for inv, it in q.order_by(ExpenseInvoice.date.desc(), ExpenseInvoice.id.desc(), ExpenseInvoiceItem.id.desc()).all():
            qty = float(it.quantity or 0)
            unit = float(it.price_before_tax or 0)
            amount = unit * qty
            rows.append({
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'expense_number': inv.invoice_number,
                'item': it.description,
                'amount': float(amount),
                'payment_method': inv.payment_method or ''
            })
        overall = {
            'amount': sum(r.get('amount', 0.0) for r in rows)
        }
        return jsonify({'expenses': rows, 'overall_totals': overall})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'expenses': [], 'overall_totals': {'amount': 0}, 'error': str(e)}), 500

new_invoice_html = """...existing code..."""
receipt_html = """...existing code..."""
settings_currency_html = """...existing code..."""

# Disabled: lite POS inline templates loader to avoid overriding real templates
# app.jinja_loader = DictLoader({
#     "branches.html": branches_html,
#     "tables.html": tables_html,
#     "new_invoice.html": new_invoice_html,
#     "receipt.html": receipt_html,
#     "settings_currency.html": settings_currency_html,
# })

# ===== Routes =====
# @app.route("/")
def index():
    return redirect(url_for("branches_view"))

# @app.route("/sales")
def sales_root():
    return redirect(url_for("branches_view"))

# @app.route("/branches")
def branches_view():
    return render_template("branches.html", branches=branches)

# @app.route("/settings/currency", methods=["GET","POST"])
def settings_currency():
    if request.method == "POST":
        b64 = (request.form.get("base64") or "").strip()
        file = request.files.get("file")
        import base64
        updated = False
        if file and getattr(file, 'filename', ''):
            data = file.read()
            try:
                settings_sales["currency_png_base64"] = base64.b64encode(data).decode("utf-8")
                flash("Currency symbol updated from file")
                updated = True
            except Exception:
                flash("Failed to read file")
        elif b64:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            b64 = b64.replace("\n", "").replace("\r", "")
            try:
                base64.b64decode(b64, validate=True)
                settings_sales["currency_png_base64"] = b64
                flash("Currency symbol updated from base64")
                updated = True
            except Exception:
                flash("Invalid base64 string")
        else:
            flash("No file or base64 provided")
        return redirect(url_for("settings_currency"))
    return render_template("settings_currency.html", settings=settings_sales)

# @app.route("/sales/<branch_code>/tables")
def tables_view(branch_code):
    branch = next((b for b in branches if b["code"] == branch_code), None)
    tables = tables_data.get(branch_code, [])
    return render_template("tables.html", branch=branch, tables=tables)

# @app.route("/sales/<branch_code>/table/<int:table_number>/new_invoice", methods=["GET", "POST"])
def new_invoice(branch_code, table_number):
    branch = next((b for b in branches if b["code"] == branch_code), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    if request.method == "POST" and "add_item" in request.form:
        item_name = request.form.get("item_name")
        price = float(request.form.get("price") or 0)
        inv = get_invoice_obj(branch_code, table_number)
        inv['items'].append({"name": item_name, "price": price, "qty": 1})
        table["is_busy"] = True
        return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))
    inv = get_invoice_obj(branch_code, table_number)
    normalized = []
    for it in inv['items']:
        if isinstance(it, dict):
            name = it.get('name')
            price = float(it.get('price') or 0)
            qty = int(it.get('qty') or 1)
        else:
            name = str(it)
            price = 0.0
            qty = 1
        normalized.append({'name': name, 'price': price, 'qty': qty, 'line_total': round(price*qty, 2)})
    subtotal = round(sum(i['line_total'] for i in normalized), 2)
    cust = inv.get('customer') or {}
    discount_rate = float((cust.get('discount') if isinstance(cust, dict) else 0) or 0)
    discount_amount = round(subtotal * (discount_rate/100.0), 2)
    total = round(subtotal - discount_amount, 2)
    vat_rate = 15.0
    vat_amount = round(total * (vat_rate/100.0), 2)
    grand_total = round(total + vat_amount, 2)
    now_riyadh_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d %H:%M")
    return render_template(
        "new_invoice.html",
        branch=branch,
        table=table,
        menu=menu_data,
        customers=customers_data,
        current_items=normalized,
        selected_customer=inv.get('customer'),
        subtotal=subtotal,
        discount_rate=discount_rate,
        discount_amount=discount_amount,
        total=total,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        grand_total=grand_total,
        now_riyadh_str=now_riyadh_str,
        settings=settings_sales
    )

# Disabled broken preview route (kept as stub)
def preview_receipt(branch_code, table_number):
    return 'Preview disabled', 404

# @app.route("/sales/<branch_code>/table/<int:table_number>/delete_item/<int:item_index>", methods=["POST"])
def delete_item(branch_code, table_number, item_index):
    password = request.form.get("password")
    if password != "1991":
        flash("Wrong password!")
        return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))
    inv = get_invoice_obj(branch_code, table_number)
    if 0 <= item_index < len(inv['items']):
        inv['items'].pop(item_index)
    if not inv['items']:
        table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
        table["is_busy"] = False
    return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))

# @app.route("/sales/<branch_code>/table/<int:table_number>/cancel_invoice", methods=["POST"])
def cancel_invoice(branch_code, table_number):
    password = request.form.get("password")
    if password != "1991":
        flash("Wrong password!")
        return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))
    invoices.pop((branch_code, table_number), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    table["is_busy"] = False
    return redirect(url_for("tables_view", branch_code=branch_code))

# @app.route("/sales/<branch_code>/table/<int:table_number>/pay", methods=["POST"])
def pay_invoice(branch_code, table_number):
    payment_method = request.form.get("payment_method")
    branch = next((b for b in branches if b["code"] == branch_code), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    inv = get_invoice_obj(branch_code, table_number)
    normalized = []
    for it in inv['items']:
        if isinstance(it, dict):
            name = it.get('name')
            price = float(it.get('price') or 0)
            qty = int(it.get('qty') or 1)
        else:
            name = str(it)
            price = 0.0
            qty = 1
        normalized.append({'name': name, 'price': price, 'qty': qty, 'line_total': round(price*qty, 2)})
    subtotal = round(sum(i['line_total'] for i in normalized), 2)
    cust = inv.get('customer') or {}
    discount_rate = float((cust.get('discount') if isinstance(cust, dict) else 0) or 0)
    discount_amount = round(subtotal * (discount_rate/100.0), 2)
    total = round(subtotal - discount_amount, 2)
    vat_rate = 15.0
    vat_amount = round(total * (vat_rate/100.0), 2)
    grand_total = round(total + vat_amount, 2)
    now_riyadh_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d %H:%M")
    if not inv.get('invoice_no'):
        inv['invoice_no'] = next_invoice_no(branch_code)
    invoice_no = inv['invoice_no']
    # Build server-side ZATCA QR as PNG base64
    from utils.qr import generate_zatca_qr_base64
    dt_ksa = get_saudi_now()
    zatca_b64 = generate_zatca_qr_base64(
        settings_sales.get('restaurant_name') or '',
        settings_sales.get('vat_number') or '',
        dt_ksa,
        grand_total,
        vat_amount
    )
    qr_data_url = 'data:image/png;base64,' + zatca_b64 if zatca_b64 else None
    return render_template(
        "receipt.html",
        branch=branch,
        table=table,
        items=normalized,
        customer=inv.get('customer'),
        payment_method=payment_method,
        subtotal=subtotal,
        discount_rate=discount_rate,
        discount_amount=discount_amount,
        total=total,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        grand_total=grand_total,
        now_riyadh_str=now_riyadh_str,
        settings=settings_sales,
        invoice_no=invoice_no,
        location_name=branch.get('name'),
        currency_code=settings_sales.get('currency_code'),
        currency_png_base64=settings_sales.get('currency_png_base64'),
        qr_data_url=qr_data_url,
        zatca_b64=zatca_b64
    )

# @app.route("/sales/<branch_code>/table/<int:table_number>/pay/confirm", methods=["POST"])
def confirm_payment(branch_code, table_number):
    payment_method = request.form.get("payment_method")
    invoices.pop((branch_code, table_number), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    table["is_busy"] = False
    flash(f"Payment successful via {payment_method}. Invoice posted.")
    return redirect(url_for("tables_view", branch_code=branch_code))

# @app.route("/sales/<branch_code>/table/<int:table_number>/set_customer", methods=["POST"])
def set_customer(branch_code, table_number):
    inv = get_invoice_obj(branch_code, table_number)
    inv['customer'] = {
        'id': request.form.get('id'),
        'name': request.form.get('name'),
        'phone': request.form.get('phone'),
        'discount': float(request.form.get('discount') or 0)
    }
    flash("Customer linked to invoice")
    return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))
# =========================
# START OF APP.PY (Top)
# =========================

import os

# Optional async monkey patching with eventlet based on env (hosting-compatible)
_USE_EVENTLET = os.getenv('USE_EVENTLET', '0').lower() in ('1','true','yes')
if _USE_EVENTLET and __name__ == '__main__':
    try:
        import eventlet
        eventlet.monkey_patch()
    except Exception:
        pass

# 1️⃣ Standard libraries
import os
import sys
import logging
import json
import traceback
import time
import uuid
import pytz
from datetime import datetime, timedelta, timezone

# ========================
# ضبط التوقيت على السعودية
# ========================
os.environ['TZ'] = 'Asia/Riyadh'
# time.tzset() is not available on Windows
try:
    time.tzset()
except AttributeError:
    pass  # Windows doesn't support tzset
KSA_TZ = pytz.timezone("Asia/Riyadh")

def get_saudi_now():
    """Get current datetime in Saudi Arabia timezone"""
    return datetime.now(KSA_TZ)

def get_saudi_today():
    """Get current date in Saudi Arabia timezone"""
    return get_saudi_now().date()

# Generate branch/year sequential invoice number with CT/PI prefix
def generate_branch_invoice_number(branch_code: str) -> str:
    """Return invoice number like CT-2025-001 based on branch and current KSA year.
    Safe to call before invoice is persisted; uses count for the current year.
    """
    try:
        from models import SalesInvoice
        from sqlalchemy import func
        now = get_saudi_now()
        year = now.year
        prefix = 'CT' if branch_code == 'china_town' else ('PI' if branch_code == 'place_india' else 'INV')
        from datetime import date as _date
        start_date = _date(year, 1, 1)
        end_date = _date(year, 12, 31)
        seq = (db.session.query(func.count(SalesInvoice.id))
               .filter(SalesInvoice.branch == branch_code,
                       SalesInvoice.date >= start_date,
                       SalesInvoice.date <= end_date)
               .scalar() or 0) + 1
        return f"{prefix}-{year}-{int(seq):03d}"
    except Exception:
        try:
            import time as _time
            fallback_year = get_saudi_now().year
            prefix = 'CT' if branch_code == 'china_town' else ('PI' if branch_code == 'place_india' else 'INV')
            return f"{prefix}-{fallback_year}-{int(_time.time() % 1000):03d}"
        except Exception:
            return f"INV-{get_saudi_now().year}-000"
def create_pos_tables():
    """Stub: simplified POS tables creator (disabled to avoid import-time errors).
    Use the admin route /admin/create-pos-tables to (re)create sample POS tables/data.
    """
    try:
        # Intentionally left minimal. Database bootstrap is handled elsewhere.
        return True
    except Exception:
        return False



    # Import models after db created
    from models import User, Invoice, SalesInvoice, SalesInvoiceItem, Product, RawMaterial, Meal, MealIngredient, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Employee, Salary, Payment, Account, LedgerEntry

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # Add test route for timezone
    @app.route('/test-time')
    def test_time():
        now_ksa = get_saudi_now().strftime("%Y-%m-%d %H:%M:%S %Z")
        return f"الوقت الحالي في السعودية: {now_ksa}"

    return app


# =========================
# Security Helper Functions
# =========================
import hmac

def verify_admin_password(pw: str) -> bool:
    """Verify admin password for delete operations"""
    required = str(app.config.get('ADMIN_DELETE_PASSWORD', '1991'))
    return hmac.compare_digest(str(pw or ''), required)

# Rate limiting for login attempts
login_attempts = {}  # { ip_address: {"count": int, "last_attempt": datetime} }

# Global socketio instance (configurable)
DISABLE_SOCKETIO = os.getenv('DISABLE_SOCKETIO', '0').lower() in ('1', 'true', 'yes')
try:
    if not DISABLE_SOCKETIO:
        from flask_socketio import SocketIO
        async_mode = 'eventlet' if _USE_EVENTLET else 'threading'
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode)
    else:
        socketio = None
except ImportError:
    socketio = None

def csrf_exempt(f):
    """Decorator that exempts a route from CSRF protection if CSRF is available"""
    from extensions import csrf
    if csrf:
        return csrf.exempt(f)
    return f

# Database helper functions are now imported from db_helpers.py

@app.route('/api/print-copy', methods=['POST'])
@csrf_exempt
def api_print_copy():
    """Generate professional receipt copy without payment processing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Extract data
        branch_code = (data.get('branch_code') or '').strip()
        table_number = data.get('table_number')
        items_payload = data.get('items') or []  # [{meal_id, qty}]
        customer_name = data.get('customer_name') or ''
        discount_pct = float(data.get('discount_pct') or data.get('discount_percentage') or 0)
        tax_pct = float(data.get('tax_pct') or 15)

        if not is_valid_branch(branch_code):
            return jsonify({'success': False, 'error': 'Invalid branch'}), 400
        if not table_number:
            return jsonify({'success': False, 'error': 'Table number required'}), 400
        if not items_payload:
            return jsonify({'success': False, 'error': 'No items provided'}), 400

        # Build items with prices from DB and compute totals (discount BEFORE tax)
        from models import Meal
        subtotal = 0.0
        rows = []  # for proportional discount
        for it in items_payload:
            try:
                meal_id = int(it.get('meal_id') or it.get('id'))
                qty = float(it.get('qty') or it.get('quantity') or 0)
            except Exception:
                continue
            if qty <= 0:
                continue
            meal = Meal.query.get(meal_id)
            if not meal:
                continue
            unit = float(meal.selling_price or 0)
            line_sub = unit * qty
            rows.append({'name': meal.display_name, 'qty': qty, 'unit': unit, 'line_sub': line_sub})
            subtotal += line_sub

        discount_val = subtotal * (discount_pct / 100.0)
        tax_total = 0.0
        items_rows = []
        for r in rows:
            prop = (r['line_sub'] / subtotal) if subtotal > 0 else 0.0
            line_discount = discount_val * prop
            discounted_sub = max(0.0, r['line_sub'] - line_discount)
            line_tax = discounted_sub * (tax_pct / 100.0)
            total_line = discounted_sub + line_tax
            tax_total += line_tax
            items_rows.append({
                'product_name': r['name'],
                'quantity': r['qty'],
                'price_before_tax': r['unit'],
                'total_price': total_line
            })
        grand_total = (subtotal - discount_val) + tax_total

        # Save as Order (print before payment)
        try:
            from models import OrderInvoice
            # Ensure table exists in case migrations didn't run yet
            try:
                OrderInvoice.__table__.create(bind=db.engine, checkfirst=True)
            except Exception:
                pass

            # Generate a unique order invoice number
            attempt = 0
            saved = False
            while attempt < 3 and not saved:
                attempt += 1
                invoice_no = f"ORD-{get_saudi_now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                try:
                    # Normalize items for JSON
                    items_json = [
                        {
                            'name': r['name'],
                            'qty': float(r['qty']),
                            'unit': float(r['unit']),
                            'line_total': float(r['line_sub'])
                        } for r in rows
                    ]
                    order = OrderInvoice(
                        branch=branch_code,
                        invoice_no=invoice_no,
                        customer=(customer_name or None),
                        items=items_json,
                        subtotal=float(subtotal),
                        discount=float(discount_val),
                        vat=float(tax_total),
                        total=float(grand_total),
                        payment_method='PENDING'
                    )
                    db.session.add(order)
                    db.session.commit()
                    saved = True
                except Exception as save_err:
                    db.session.rollback()
                    # If duplicate invoice_no or transient error, retry once with a new number
                    if attempt >= 3:
                        current_app.logger.error('Failed to save order invoice: %s', save_err)
                        # Do not fail the preview; continue to render receipt
                        break
        except Exception as e:
            try:
                current_app.logger.error('Order invoice save block failed: %s', e)
            except Exception:
                pass

        # Minimal invoice-like object for template
        from types import SimpleNamespace
        inv = SimpleNamespace(
            id=str(uuid.uuid4())[:8],
            invoice_number=f"PREVIEW-{uuid.uuid4().hex[:6].upper()}",
            date=get_saudi_now().date(),
            branch=branch_code,
            branch_code=branch_code,
            table_number=table_number,
            customer_name=customer_name,
            payment_method='',  # hidden in template
            total_before_tax=float(subtotal),
            tax_amount=float(tax_total),
            discount_amount=float(discount_val),
            total_after_tax_discount=float(grand_total),
            status='unpaid'
        )

        # Header data
        s = get_settings_safe()
        branch_upper_map = {'china_town': 'CHINA TOWN', 'place_india': 'PALACE INDIA'}
        branch_name = branch_upper_map.get(branch_code, branch_code.upper())
        date_time = get_saudi_now().strftime('%Y-%m-%d %H:%M:%S')

        # Build minimal HTML directly to avoid template formatting issues
        rows_html = "".join([
            f"<tr><td>{it['product_name']}</td><td style='text-align:center'>{it['quantity']:.2f}</td><td style='text-align:center'>{(it['price_before_tax']):.2f}</td><td style='text-align:right'>{(it['total_price']):.2f}</td></tr>"
            for it in items_rows
        ])
        discount_row = (
            f"<div style='display:flex;justify-content:space-between'><span>Discount</span><span>-{inv.discount_amount:.2f}</span></div>"
            if inv.discount_amount and inv.discount_amount > 0 else ""
        )
        html = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>Preview {inv.invoice_number}</title>
<style>
  body{{font-family:Arial,sans-serif;font-size:12px}}
  .wrap{{width:80mm;max-width:80mm;margin:0 auto}}
  .center{{text-align:center}}
  table{{width:100%;border-collapse:collapse}}
  th,td{{padding:6px 0;border-bottom:1px dashed #ddd}}
  .total-row{{font-weight:bold}}
  .no-print{{display:block}}
  @media print{{.no-print{{display:none}}}}
</style>
</head>
<body>
<div class='wrap'>
  <div class='center'>
    <div><strong>{branch_name}</strong></div>
  </div>
  <hr/>
  <div style='font-size:12px'>
    <div>Invoice No: {inv.invoice_number}</div>
    <div>Date/Time: {date_time}</div>
    <div>Branch: {branch_name}</div>
    <div>Table: {inv.table_number}</div>
    <div>Customer: {inv.customer_name or 'Cash customer'}</div>
  </div>
  <table>
    <thead><tr><th style='text-align:left'>Item</th><th class='center'>Qty</th><th class='center'>Price</th><th style='text-align:right'>Total</th></tr></thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <div style='margin-top:8px'>
    <div style='display:flex;justify-content:space-between'><span>Subtotal</span><span>{inv.total_before_tax:.2f}</span></div>
    {discount_row}
    <div style='display:flex;justify-content:space-between'><span>VAT ({tax_pct:.0f}%)</span><span>{inv.tax_amount:.2f}</span></div>
    <div class='total-row' style='display:flex;justify-content:space-between;border-top:1px solid #000;margin-top:4px;padding-top:4px'><span>Grand Total</span><span>{inv.total_after_tax_discount:.2f}</span></div>
  </div>
  <div class='center no-print' style='margin-top:10px'>
    <button onclick='window.print()'>Print</button>
  </div>
</div>
</body></html>
"""

        # Create temporary file and expose URL
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            temp_file_path = f.name
        temp_filename = os.path.basename(temp_file_path)
        print_url = f'/temp-receipt/{temp_filename}'
        from flask import session

        session[f'temp_receipt_{temp_filename}'] = temp_file_path

        return jsonify({'success': True, 'print_url': print_url})

    except Exception as e:
        print(f"Print copy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/temp-receipt/<filename>')
def serve_temp_receipt(filename):
    """Serve temporary receipt files"""
    from flask import session
    import os
    try:
        # Get file path from session
        temp_file_path = session.get(f'temp_receipt_{filename}')
        if not temp_file_path or not os.path.exists(temp_file_path):
            return "Receipt not found", 404

        # Read and return the HTML content
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Clean up the temporary file after serving
        try:
            os.unlink(temp_file_path)
            session.pop(f'temp_receipt_{filename}', None)
        except Exception:
            pass  # Ignore cleanup errors

        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        print(f"Error serving temp receipt: {e}")
        return "Error loading receipt", 500

@app.route('/orders')
def order_invoices_list():
    """List Order Invoices (printed before payment) with totals and item summary."""
    try:
        from models import OrderInvoice
        # Fetch orders
        orders = OrderInvoice.query.order_by(OrderInvoice.invoice_date.desc()).limit(500).all()

        # Totals
        from sqlalchemy import func
        totals = db.session.query(
            func.coalesce(func.sum(OrderInvoice.subtotal), 0).label('subtotal_sum'),
            func.coalesce(func.sum(OrderInvoice.discount), 0).label('discount_sum'),
            func.coalesce(func.sum(OrderInvoice.vat), 0).label('vat_sum'),
            func.coalesce(func.sum(OrderInvoice.total), 0).label('total_sum')
        ).one()

        # Items summary: iterate in Python for cross-DB compatibility
        items_summary_map = {}
        for o in orders:
            try:
                for it in (o.items or []):
                    name = (it.get('name') if isinstance(it, dict) else None) or '-'
                    qty_val = it.get('qty') if isinstance(it, dict) else 0
                    try:
                        qty = float(qty_val or 0)
                    except Exception:
                        qty = 0.0
                    items_summary_map[name] = items_summary_map.get(name, 0.0) + qty
            except Exception:
                continue
        items_summary = [
            {'item_name': k, 'total_qty': v}
            for k, v in sorted(items_summary_map.items(), key=lambda x: (-x[1], x[0]))
        ]

        return render_template('order_invoices.html', orders=orders, totals=totals, items_summary=items_summary)
    except Exception as e:
        current_app.logger.error('Failed to load order invoices: %s', e)
        flash('Failed to load order invoices', 'danger')
        return render_template('order_invoices.html', orders=[], totals={'subtotal_sum':0,'discount_sum':0,'vat_sum':0,'total_sum':0}, items_summary=[])
@app.route('/api/pay-and-print', methods=['POST'])
@csrf_exempt
def api_pay_and_print():
    """Process payment and generate receipt"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Extract data
        items = data.get('items', [])
        table_number = data.get('table_number')
        customer_name = data.get('customer_name', '')
        discount_percentage = data.get('discount_percentage', 0)
        branch_code = data.get('branch_code', 'china_town')
        payment_method = data.get('payment_method', 'cash')

        if not items:
            return jsonify({'success': False, 'error': 'No items provided'}), 400

        if not table_number:
            return jsonify({'success': False, 'error': 'Table number required'}), 400

        # Calculate totals (from client totals or recompute here)
        subtotal = sum(float(item.get('total_price') or (item.get('price_before_tax', 0) * item.get('quantity', 0))) for item in items)
        vat_amount = subtotal * 0.15  # 15% VAT (consider pulling from settings in future)
        discount_amount = subtotal * (float(discount_percentage) / 100.0) if discount_percentage else 0.0
        total = subtotal + vat_amount - discount_amount

        # Use safe database operation for payment processing
        def create_invoice_and_payment():
            # Create sales invoice with calculated values
            invoice = SalesInvoice(
                branch=branch_code,
                table_number=str(table_number),
                customer_name=customer_name or None,
                discount_amount=float(discount_amount),
                payment_method=payment_method,
                date=get_saudi_now().date(),
                invoice_number=generate_branch_invoice_number(branch_code),
                total_before_tax=float(subtotal),
                tax_amount=float(vat_amount),
                total_after_tax_discount=float(total),
                status='paid',
                user_id=current_user.id
            )

            db.session.add(invoice)
            db.session.flush()  # Get invoice ID

            # Add invoice items
            for item in items:
                name = item.get('product_name') or item.get('name')
                qty = float(item.get('quantity') or 0)
                price = float(item.get('price_before_tax') or item.get('price') or 0)
                total_price = float(item.get('total_price') or (price * qty))
                db.session.add(SalesInvoiceItem(
                    invoice_id=invoice.id,
                    product_name=name,
                    quantity=qty,
                    price_before_tax=price,
                    total_price=total_price
                ))

            return invoice

        # Execute with error handling
        invoice = safe_db_operation(
            create_invoice_and_payment,
            "إنشاء فاتورة المبيعات والدفع"
        )

        if not invoice:
            return jsonify({'success': False, 'error': 'Failed to create invoice'}), 500

        # After successful payment: clear any draft for this table and mark table available
        try:
            from models import DraftOrder, Table
            s = str(branch_code or '').lower()
            if any(k in s for k in ('place_india','palace_india','india','palace','pi','2')):
                canonical_branch = 'place_india'
            else:
                canonical_branch = 'china_town'
            # Delete all draft orders for this table/branch
            table_no_str = str(table_number)
            drafts = DraftOrder.query.filter_by(branch_code=canonical_branch, table_number=table_no_str, status='draft').all()
            for d in drafts:
                db.session.delete(d)
            # Update table status to available
            table = Table.query.filter_by(branch_code=canonical_branch, table_number=table_no_str).first()
            if table:
                table.status = 'available'
                table.updated_at = get_saudi_now()
            db.session.commit()
            # Clear in-memory open marker as well (try common variants)
            try:
                for b in {canonical_branch, s.replace(' ', '_'), 'palace_india', 'place_india'}:
                    OPEN_INVOICES_MEM.pop(f"{b}:{table_no_str}", None)
                    OPEN_INVOICES_MEM.pop(f"{b}:{int(table_no_str)}", None)
            except Exception:
                pass
        except Exception as postpay_err:
            # Do not fail the payment due to cleanup; just log
            current_app.logger.error('Post-payment cleanup failed: %s', postpay_err)
            db.session.rollback()

        # Build receipt URL for client to open/print
        receipt_url = url_for('sales_receipt', invoice_id=invoice.id)
        return jsonify({
            'success': True,
            'receipt_url': receipt_url,
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number
        })

    except Exception as e:
        reset_db_session()
        error_message = handle_db_error(e, "معالجة الدفع والطباعة")
        print(f"Pay and print error: {e}")
        return jsonify({'success': False, 'error': error_message}), 500

def reset_db_session():
    """Safely rollback the current DB session without raising."""
    try:
        db.session.rollback()
    except Exception:
        pass


def safe_db_commit(context: str | None = None) -> bool:
    """Commit with rollback-on-failure and logging. Returns True on success."""
    try:
        db.session.commit()
        return True
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logging.error('DB commit failed%s: %s', f' ({context})' if context else '', e, exc_info=True)
        return False


def safe_db_operation(fn, context: str | None = None):
    """
    Run a DB operation function `fn()` safely: commit on success, rollback and log on error.
    Returns the function's return value on success, otherwise None.
    """
    try:
        result = fn()
        db.session.commit()
        return result
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logging.error('DB operation failed%s: %s', f' ({context})' if context else '', e, exc_info=True)
        return None


def handle_db_error(e: Exception, context: str | None = None) -> str:
    """
    Return a user-friendly bilingual error message and log the exception.
    """
    logging.error('Error%s: %s', f' ({context})' if context else '', e, exc_info=True)
    base_msg = 'حدث خطأ غير متوقع، حاول مرة أخرى / Unexpected error. Please try again.'
    if context:
        return f"{base_msg} ({context})"
    return base_msg

def save_to_db(instance):
    try:
        db.session.add(instance)
        safe_db_commit()
        return True
    except Exception as e:
        db.session.rollback()
        logging.error('Database Error: %s', e, exc_info=True)
        return False

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

# Alias for POS customer search used by POS templates
@app.route('/api/customers/search')
@login_required
def customers_search_alias():
    try:
        q = (request.args.get('q') or '').strip()
        from models import Customer
        if not q:
            return jsonify([])
        # search by name or phone prefix
        customers = Customer.query.filter(
            (Customer.name.ilike(f"%{q}%")) | (Customer.phone.ilike(f"%{q}%"))
        ).order_by(Customer.name.asc()).limit(10).all()
        return jsonify([
            {
                'id': c.id,
                'name': c.name,
                'phone': c.phone,
                'discount': float(getattr(c, 'discount', 0.0) or 0.0)
            } for c in customers
        ])
    except Exception:
        return jsonify([])

# Expose get_locale to Jinja templates
@app.context_processor
def inject_get_locale():
    try:
        return dict(get_locale=get_locale)
    except Exception:
        return {}


# Configure babel locale selector after get_locale is defined
if 'babel' in globals() and babel:
    try:
        babel.init_app(app, locale_selector=get_locale)
    except Exception:
        pass

# Babel will be configured after app creation
@app.context_processor
def inject_settings():
    try:
        from models import Settings
        s = Settings.query.first()
        return dict(settings=s)
    except Exception:
        return dict(settings=None)

@app.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    current = session.get('theme') or (getattr(inject_settings().get('settings'), 'default_theme', 'light'))
    session['theme'] = 'dark' if current != 'dark' else 'light'
    return redirect(request.referrer or url_for('dashboard'))



# Make get_locale available in templates
@app.context_processor
def inject_conf_vars():
    return {
        'get_locale': get_locale
    }

# Asset version for cache busting of static files
ASSET_VERSION = os.getenv('ASSET_VERSION', '20250909')

@app.context_processor
def inject_asset_version():
    try:
        return dict(ASSET_VERSION=ASSET_VERSION)
    except Exception:
        return dict(ASSET_VERSION='0')


@app.route('/', endpoint='root_index')
def root_index():
    return redirect(url_for('login'))

# Safe url_for helper to avoid template crashes if an endpoint is missing in current deployment
@app.context_processor
def inject_safe_url():
    def safe_url(endpoint, **kwargs):
        try:
            return url_for(endpoint, **kwargs)
        except Exception:
            return None
    return dict(safe_url=safe_url)

# Safe Settings getter to avoid 500s if DB schema is outdated
def get_settings_safe():
    try:
        from models import Settings

        # Try to get settings with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                settings = Settings.query.first()
                if settings:
                    return settings
                else:
                    # Create default settings if none exist
                    settings = Settings()
                    db.session.add(settings)
                    db.session.commit()
                    return settings
            except Exception as e:
                print(f"Settings query attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    db.session.rollback()
                    continue
                else:
                    raise e

    except Exception as e:
        print(f"get_settings_safe failed: {e}")
        import traceback
        traceback.print_exc()
        return None



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

# Register receipt blueprint
try:
    from routes.print_receipt import bp as receipt_bp
    app.register_blueprint(receipt_bp)
except Exception:
    pass
@app.route('/login', methods=['GET', 'POST'])
@csrf_exempt
def login():
    form = LoginForm()

    if request.method == 'POST':
        # قراءة الحقول من عدة مصادر لضمان عدم ضياع القيم على بعض المنصات
        username = (request.form.get('username') or request.values.get('username') or '')
        password = (request.form.get('password') or request.values.get('password') or '')
        # دعم JSON إن أُرسل
        if (not username or not password) and request.is_json:
            try:
                data = request.get_json(silent=True) or {}
                username = username or (data.get('username') or '')
                password = password or (data.get('password') or '')
            except Exception:
                pass
        username = (username or '').strip()
        password = (password or '').strip()

        # Debug خفيف لتشخيص الإنتاج (لا يطبع كلمات المرور)
        try:
            print('Login POST debug => keys:', list(request.form.keys()), 'content-type:', request.headers.get('Content-Type'))
        except Exception:
            pass

        if not username or not password:
            flash('يرجى ملء جميع الحقول المطلوبة / Please fill all required fields', 'danger')
            return render_template('login.html', form=form)

        # تحديث بيانات النموذج
        form.username.data = username
        form.password.data = password
        try:
            from models import User
            from extensions import bcrypt

            current_app.logger.info(f"Login attempt for username: {username}")
            print(f"Login attempt for username: {username}")  # للتتبع

            # البحث عن المستخدم
            try:
                user = User.query.filter_by(username=username).first()
                print(f"User found: {user is not None}")
            except Exception as db_error:
                print(f"Database query error: {db_error}")
                flash('خطأ في قاعدة البيانات / Database error', 'danger')
                return render_template('login.html', form=form)

            if user:
                try:
                    # التحقق من كلمة المرور
                    password_valid = bcrypt.check_password_hash(user.password_hash, password)
                    print(f"Password valid: {password_valid}")

                    if password_valid:
                        # تسجيل الدخول
                        login_user(user, remember=form.remember.data)
                        # Set session to expire when browser closes
                        session.permanent = False

                        # تحديث آخر تسجيل دخول
                        try:
                            user.last_login()
                            if safe_db_commit("login update"):
                                print("Login successful, redirecting to dashboard")
                                return redirect(url_for('dashboard'))
                            else:
                                print("Failed to update last login")
                        except Exception as update_error:
                            print(f"Error updating last login: {update_error}")

                        # حتى لو فشل التحديث، نسمح بالدخول
                        return redirect(url_for('dashboard'))
                    else:
                        flash('اسم المستخدم أو كلمة المرور خاطئة', 'danger')
                except Exception as bcrypt_error:
                    print(f"Bcrypt error: {bcrypt_error}")
                    flash('خطأ في التحقق من كلمة المرور / Password verification error', 'danger')
            else:
                flash('اسم المستخدم أو كلمة المرور خاطئة', 'danger')

        except Exception as e:
            # طباعة الخطأ في سجل الخادم لتعرف السبب
            print(f"Login Error: {e}")
            import traceback
            traceback.print_exc()
            flash('خطأ في النظام / System error', 'danger')

    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    # If user is a branch sales user, template will hide other modules.
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('Logged out.'), 'info')
    return redirect(url_for('login'))


@app.route('/sales/<branch_code>', methods=['GET', 'POST'])
@login_required
def sales_branch(branch_code):
    # Unified entry: redirect to tables view; old sales form is deprecated
    if not is_valid_branch(branch_code):
        flash('Invalid branch', 'danger')
        return redirect(url_for('sales'))
    return redirect(url_for('sales_tables', branch_code=branch_code))

# Sales entry: Branch cards -> Tables -> Table invoice
@app.route('/sales', methods=['GET'])
@login_required
def sales():
    branches = [
        {'code': 'china_town', 'label': 'China Town', 'url': url_for('sales_tables', branch_code='china_town')},
        {'code': 'place_india', 'label': 'Place India', 'url': url_for('sales_tables', branch_code='place_india')},
    ]
    return render_template('sales_branches.html', branches=branches)

# API: Get draft order for table (GET) and Save draft (POST)
@csrf_exempt
@app.route('/api/draft-order/<branch_code>/<table_number>', methods=['GET', 'POST'])
@login_required
def api_draft_order(branch_code, table_number):
    """Get or save draft order for a specific table"""
    if not is_valid_branch(branch_code):
        return jsonify({'success': False, 'error': 'Invalid branch'}), 400

    try:
        from models import DraftOrder, DraftOrderItem, Table
        table_number = str(table_number)

        # GET: return current draft
        if request.method == 'GET':
            draft_order = DraftOrder.query.filter_by(
                branch_code=branch_code,
                table_number=table_number,
                status='draft'
            ).order_by(DraftOrder.created_at.desc()).first()

            if draft_order:
                items = [{
                    'id': it.meal_id,
                    'name': it.product_name,
                    'price': float(it.price_before_tax or 0),
                    'quantity': float(it.quantity or 0),
                    'total_price': float(it.total_price or 0)
                } for it in draft_order.items]
                return jsonify({'success': True, 'draft_id': draft_order.id, 'items': items})
            return jsonify({'success': True, 'draft_id': None, 'items': []})

        # POST: Save or clear draft. If no items => clear drafts and mark table available
        data = request.get_json(silent=True) or {}
        items = data.get('items', [])
        # 1) Delete any existing draft(s) for this table in this branch (fuzzy branch match + int/string table)
        from sqlalchemy import or_
        branch_l = (branch_code or '').strip().lower()
        branch_opts = {branch_l}
        if 'india' in branch_l:
            branch_opts |= {'place_india', 'india_place', 'place india', 'india place'}
        elif 'china' in branch_l:
            branch_opts |= {'china_town', 'china town', 'town china', 'china'}
        try:
            tbl_int = safe_table_number(table_number)
        except Exception:
            tbl_int = None
        existing_drafts = DraftOrder.query.filter(
            DraftOrder.status == 'draft',
            DraftOrder.branch_code.in_(list(branch_opts)),
            or_(
                DraftOrder.table_number == str(table_number),
                *( [DraftOrder.table_no == tbl_int] if tbl_int is not None else [] )
            )
        ).all()
        for d in existing_drafts:
            try:
                DraftOrderItem.query.filter_by(draft_order_id=d.id).delete(synchronize_session=False)
            except Exception:
                pass
            db.session.delete(d)
        db.session.flush()

        # If no items: mark table available (robust: update all matching variants) and return success without creating a new draft
        if not items:
            from sqlalchemy import or_
            # Update all tables matching branch variants and string/int table_number
            tables = Table.query.filter(
                Table.branch_code.in_(list(branch_opts)),
                or_(
                    Table.table_number == str(table_number),
                    *( [Table.table_number == tbl_int] if tbl_int is not None else [] )
                )
            ).all()
            if tables:
                for t in tables:
                    t.status = 'available'
                    t.updated_at = get_saudi_now()
            else:
                # Create table record if not existing (normalize branch name)
                canonical_branch = (branch_l.replace(' ', '_') or branch_code)
                t = Table(branch_code=canonical_branch, table_number=str(table_number), status='available')
                db.session.add(t)
            safe_db_commit()
            return jsonify({'success': True, 'draft_id': None})

        # 2) Create new draft
        draft = DraftOrder(branch_code=branch_code, table_number=table_number, status='draft', user_id=current_user.id)
        db.session.add(draft)
        db.session.flush()

        # 3) Add items (accept multiple client shapes)
        for it in (items or []):
            name = it.get('product_name') or it.get('name') or ''
            qty = float(it.get('quantity') or it.get('qty') or 0)
            price = float(it.get('price_before_tax') or it.get('unit') or it.get('price') or 0)
            total_price = float(it.get('total_price') or it.get('total') or (price * qty))
            db.session.add(DraftOrderItem(
                draft_order_id=draft.id,
                meal_id=it.get('meal_id') or it.get('id'),
                product_name=name,
                quantity=qty,
                price_before_tax=price,
                total_price=total_price
            ))

        # 4) Mark table as occupied (always on draft creation)
        table = Table.query.filter_by(branch_code=branch_code, table_number=table_number).first()
        if not table:
            table = Table(branch_code=branch_code, table_number=table_number, status='occupied')
            db.session.add(table)
        else:
            table.status = 'occupied'
        table.updated_at = get_saudi_now()

        safe_db_commit()
        return jsonify({'success': True, 'draft_id': draft.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Save draft order
@csrf_exempt

@app.route('/api/save-draft-order', methods=['POST'])
@login_required
def api_save_draft_order():
    """Save draft order for a table"""
    try:
        data = request.get_json(silent=True) or {}
        if (not data) and request.form:
            try:
                data = request.form.to_dict(flat=True)
            except Exception:
                data = {}
        branch_code = data.get('branch_code') or data.get('branch') or request.args.get('branch_code') or request.args.get('branch')
        table_number = data.get('table_number') or data.get('table') or data.get('table_no') or request.args.get('table_number') or request.args.get('table') or request.args.get('table_no')
        items = data.get('items', [])


        logging.info("save-draft start: branch=%s table=%s items=%d", branch_code, table_number, len(items or []))

        if table_number is not None:
            table_number = str(table_number)

        if not branch_code or not table_number:
            return jsonify({
                'success': False,
                'error': 'Branch code and table number are required'
            }), 400

        # Delete any existing drafts for this table (handle int/string + legacy table_no, fuzzy branch match)
        try:
            tbl_int = safe_table_number(table_number)
        except Exception:
            tbl_int = None
        from sqlalchemy import or_
        branch_l = (branch_code or '').strip().lower()
        branch_opts = {branch_l}
        if 'india' in branch_l:
            branch_opts |= {'place_india', 'india_place', 'place india', 'india place'}
        elif 'china' in branch_l:
            branch_opts |= {'china_town', 'china town', 'town china', 'china'}
        existing_drafts = DraftOrder.query.filter(
            DraftOrder.branch_code.in_(list(branch_opts)),
            or_(
                DraftOrder.table_number == str(table_number),
                *( [DraftOrder.table_no == tbl_int] if tbl_int is not None else [] )
            )
        ).all()
        for d in existing_drafts:
            for item in list(d.items):
                db.session.delete(item)
            db.session.delete(d)

        if items:  # Only create new draft if there are items
            # Create new draft order
            draft_order = DraftOrder(
                branch_code=branch_code,
                table_number=table_number,
                user_id=current_user.id,
                status='draft'
            )
            db.session.add(draft_order)
            db.session.flush()  # Get the ID

            # Add items
            for item in items:
                draft_item = DraftOrderItem(
                    draft_order_id=draft_order.id,
                    meal_id=item.get('id'),
                    product_name=item.get('name'),
                    price_before_tax=float(item.get('price', 0)),
                    quantity=float(item.get('quantity', 1)),
                    tax=0,
                    discount=0,
                    total_price=float(item.get('price', 0)) * float(item.get('quantity', 1))
                )
                db.session.add(draft_item)

            # Update table status (handle int/string mismatch in legacy DBs)
            table = Table.query.filter_by(
                branch_code=branch_code,
                table_number=str(table_number)
            ).first()
            if not table:
                try:
                    table = Table.query.filter_by(
                        branch_code=branch_code,
                        table_number=int(table_number)
                    ).first()
                except Exception:
                    table = None

            if not table:
                table = Table(
                    branch_code=branch_code,
                    table_number=str(table_number),
                    status='occupied'
                )
                db.session.add(table)
            else:
                table.status = 'occupied'
                table.updated_at = get_saudi_now()
        else:
            # No items, mark table as available (handle int/string mismatch)
            table = Table.query.filter_by(
                branch_code=branch_code,
                table_number=str(table_number)
            ).first()
            if not table:
                try:
                    table = Table.query.filter_by(
                        branch_code=branch_code,
                        table_number=int(table_number)
                    ).first()
                except Exception:
                    table = None
            if table:
                table.status = 'available'
                table.updated_at = get_saudi_now()
            else:
                # Create table record as available if it doesn't exist
                table = Table(
                    branch_code=branch_code,
                    table_number=str(table_number),
                    status='available'
                )
                db.session.add(table)

        logging.info("save-draft done: branch=%s table=%s status=%s", branch_code, table_number, table.status if 'table' in locals() and table else 'n/a')


        db.session.commit()

        return jsonify({
            'success': True
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error saving draft order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API: Load draft order
@app.route('/api/load-draft-order/<branch_code>/<table_number>')
@login_required
def api_load_draft_order(branch_code, table_number):
    """Load draft order for a table"""
    try:
        # Find existing draft order for this table
        draft_order = DraftOrder.query.filter_by(
            branch_code=branch_code,
            table_number=table_number,
            status='draft'
        ).first()

        if not draft_order:
            return jsonify({
                'success': True,
                'items': []
            })

        # Convert draft items to format expected by frontend
        items = []
        for draft_item in draft_order.items:
            items.append({
                'id': draft_item.meal_id,
                'name': draft_item.product_name,
                'price': float(draft_item.price_before_tax),
                'quantity': float(draft_item.quantity)
            })

        return jsonify({
            'success': True,
            'items': items
        })

    except Exception as e:
        print(f"Error loading draft order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Table Settings Management
@app.route('/settings/tables')
@login_required
def table_settings():
    """Table settings management page"""
    return render_template('table_settings.html')
# API: Get table settings
@app.route('/api/table-settings')
@login_required
def api_get_table_settings():
    """Get table settings for all branches"""
    try:
        # Create tables if they don't exist
        try:
            db.create_all()
        except Exception as create_error:
            print(f"Warning: Could not create tables: {create_error}")

        china_settings = None
        india_settings = None

        try:
            china_settings = TableSettings.query.filter_by(branch_code='1').first()
        except Exception as e:
            print(f"Error querying China settings: {e}")

        try:
            india_settings = TableSettings.query.filter_by(branch_code='2').first()
        except Exception as e:
            print(f"Error querying India settings: {e}")

        settings = {
            'china': {
                'count': china_settings.table_count if china_settings else 20,
                'numbering': china_settings.numbering_system if china_settings else 'numeric',
                'custom_numbers': china_settings.custom_numbers if china_settings else ''
            },
            'india': {
                'count': india_settings.table_count if india_settings else 20,
                'numbering': india_settings.numbering_system if india_settings else 'numeric',
                'custom_numbers': india_settings.custom_numbers if india_settings else ''
            }
        }

        return jsonify({
            'success': True,
            'settings': settings
        })

    except Exception as e:
        print(f"Error getting table settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API: Save table settings
@app.route('/api/table-settings', methods=['POST'])
@login_required
def api_save_table_settings():
    """Save table settings for all branches"""
    try:
        data = request.get_json()

        # Save China Town settings
        china_data = data.get('china', {})
        china_settings = TableSettings.query.filter_by(branch_code='1').first()
        if not china_settings:
            china_settings = TableSettings(branch_code='1')
            db.session.add(china_settings)

        china_settings.table_count = china_data.get('count', 20)
        china_settings.numbering_system = china_data.get('numbering', 'numeric')
        china_settings.custom_numbers = china_data.get('custom_numbers', '')
        china_settings.updated_at = get_saudi_now()

        # Save Palace India settings
        india_data = data.get('india', {})
        india_settings = TableSettings.query.filter_by(branch_code='2').first()
        if not india_settings:
            india_settings = TableSettings(branch_code='2')
            db.session.add(india_settings)

        india_settings.table_count = india_data.get('count', 20)
        india_settings.numbering_system = india_data.get('numbering', 'numeric')
        india_settings.custom_numbers = india_data.get('custom_numbers', '')
        india_settings.updated_at = get_saudi_now()

        db.session.commit()

        return jsonify({
            'success': True,

            'message': 'تم حفظ إعدادات الطاولات بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error saving table settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================
# Table Manager Routes
# ========================================


@app.route('/table-manager/<branch_code>')
@login_required
def table_manager(branch_code):
    """Table manager for specific branch"""
    # Define branch labels
    branch_labels = {
        'china_town': 'CHINA TOWN',
        'place_india': 'PALACE INDIA'
    }
    
    if branch_code not in branch_labels:
        flash('Invalid branch', 'danger')
        return redirect(url_for('table_settings'))
    
    branch_label = branch_labels[branch_code]
    return render_template('table_manager.html', branch_code=branch_code, branch_label=branch_label)


# API: Table Sections (per branch)
@app.route('/api/table-sections/<branch_code>', methods=['GET'])
@login_required
def api_get_table_sections(branch_code):
    """Return sections and assignments for a branch (with parsed row layout)."""
    try:
        if not is_valid_branch(branch_code):
            return jsonify({'success': False, 'error': 'Invalid branch'}), 400
        # Ensure tables exist
        try:
            db.create_all()
        except Exception:
            pass
        from models import TableSection, TableSectionAssignment

        def decode_name(name: str):
            name = name or ''
            visible = name
            layout = ''
            if '[rows:' in name and name.endswith(']'):
                try:
                    before, bracket = name.rsplit('[rows:', 1)
                    visible = before.rstrip()
                    layout = bracket[:-1].strip()  # drop trailing ]
                except Exception:
                    pass
            return visible, layout

        sections = TableSection.query.filter_by(branch_code=branch_code).order_by(TableSection.sort_order, TableSection.id).all()
        assignments = TableSectionAssignment.query.filter_by(branch_code=branch_code).all()
        return jsonify({
            'success': True,
            'sections': [
                (lambda v_l: {'id': s.id, 'name': v_l[0], 'sort_order': s.sort_order, 'layout': v_l[1]})(decode_name(s.name))
                for s in sections
            ],
            'assignments': [
                {'table_number': a.table_number, 'section_id': a.section_id}
                for a in assignments
            ]
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/api/table-sections/<branch_code>', methods=['POST'])
@login_required
def api_save_table_sections(branch_code):
    """Upsert sections and replace assignments for a branch (supports full delete when no sections provided)."""
    try:
        if not is_valid_branch(branch_code):
            return jsonify({'success': False, 'error': 'Invalid branch'}), 400
        from models import TableSection, TableSectionAssignment
        data = request.get_json() or {}
        sections_data = data.get('sections', []) or []
        assignments_data = data.get('assignments', []) or []

        # If no sections provided: clear all sections and assignments for this branch
        if len(sections_data) == 0:
            TableSectionAssignment.query.filter_by(branch_code=branch_code).delete()
            TableSection.query.filter_by(branch_code=branch_code).delete()
            db.session.commit()
            return jsonify({'success': True, 'sections': []})

        # Upsert sections (support optional empty names and per-section row layout)
        def encode_name(name: str, layout: str):
            name = (name or '').strip()
            layout = (layout or '').strip()
            return f"{name} [rows:{layout}]" if layout else name

        id_map = {}  # temp mapping for names/ids (by visible name)
        kept_ids = []
        for idx, sd in enumerate(sections_data):
            sid = sd.get('id')
            visible_name = (sd.get('name') or '').strip()  # can be empty
            layout = (sd.get('layout') or '').strip()
            stored_name = encode_name(visible_name, layout)
            sort_order = int(sd.get('sort_order') or idx)
            if sid:
                sec = TableSection.query.filter_by(id=sid, branch_code=branch_code).first()
                if sec:
                    sec.name = stored_name
                    sec.sort_order = sort_order
                    id_map[visible_name] = sec.id
                    kept_ids.append(sec.id)
                else:
                    # create new if id not found for safety
                    sec = TableSection(branch_code=branch_code, name=stored_name, sort_order=sort_order)
                    db.session.add(sec)
                    db.session.flush()
                    id_map[visible_name] = sec.id
                    kept_ids.append(sec.id)
            else:
                existing = TableSection.query.filter_by(branch_code=branch_code, name=stored_name).first()
                if existing:
                    existing.sort_order = sort_order
                    id_map[visible_name] = existing.id
                    kept_ids.append(existing.id)
                else:
                    sec = TableSection(branch_code=branch_code, name=stored_name, sort_order=sort_order)
                    db.session.add(sec)
                    db.session.flush()
                    id_map[visible_name] = sec.id
                    kept_ids.append(sec.id)

        # Remove any sections not present in kept_ids (cleanup deleted sections)
        if kept_ids:
            TableSection.query.filter(TableSection.branch_code==branch_code, ~TableSection.id.in_(kept_ids)).delete(synchronize_session=False)

        # Replace assignments for this branch
        TableSectionAssignment.query.filter_by(branch_code=branch_code).delete()
        for ad in assignments_data:
            table_number = str(ad.get('table_number') or '').strip()
            section_id = ad.get('section_id')
            section_name = (ad.get('section_name') or '').strip()
            if not section_id and section_name:
                section_id = id_map.get(section_name)
                if not section_id:
                    sec = TableSection.query.filter_by(branch_code=branch_code, name=section_name).first()
                    if sec:
                        section_id = sec.id
            if not table_number or not section_id:
                continue
            # Ensure section exists and belongs to branch
            sec = TableSection.query.filter_by(id=section_id, branch_code=branch_code).first()
            if not sec:
                continue
            db.session.add(TableSectionAssignment(
                branch_code=branch_code,
                table_number=table_number,
                section_id=section_id
            ))

        db.session.commit()
        # return updated sections for client id mapping
        sections = TableSection.query.filter_by(branch_code=branch_code).order_by(TableSection.sort_order, TableSection.id).all()
        return jsonify({'success': True, 'sections': [ {'id': s.id, 'name': s.name, 'sort_order': s.sort_order} for s in sections ]})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# Table Manager API - Integrated with POS
# ========================================

@app.route('/api/table-layout/<branch_code>', methods=['GET', 'POST'])
@login_required
def api_table_layout(branch_code):
    """Table layout API that integrates with the actual POS table system"""
    # Define branch labels
    branch_labels = {
        'china_town': 'CHINA TOWN',
        'place_india': 'PALACE INDIA'
    }
    
    # Check if branch exists
    if branch_code not in branch_labels:
        return jsonify({'error': 'Branch not found'}), 404
    
    if request.method == 'GET':
        # Load layout from the actual table sections system
        try:
            from models import TableSection, TableSectionAssignment
            
            def decode_name(name: str):
                name = name or ''
                visible = name
                layout = ''
                if '[rows:' in name and name.endswith(']'):
                    try:
                        before, bracket = name.rsplit('[rows:', 1)
                        visible = before.rstrip()
                        layout = bracket[:-1].strip()  # drop trailing ]
                    except Exception:
                        pass
                return visible, layout

            sections = TableSection.query.filter_by(branch_code=branch_code).order_by(TableSection.sort_order, TableSection.id).all()
            assignments = TableSectionAssignment.query.filter_by(branch_code=branch_code).all()
            
            # Convert to table manager format
            layout_sections = []
            for s in sections:
                visible, layout = decode_name(s.name)
                section_data = {
                    'id': s.id,
                    'name': visible,
                    'rows': []
                }
                
                # Parse layout to create rows
                if layout:
                    try:
                        counts = [int(x.strip()) for x in layout.split(',') if x.strip()]
                        row_start = 1
                        for count in counts:
                            if count <= 0:
                                continue
                            row = {
                                'id': f'row_{len(section_data["rows"]) + 1}',
                                'tables': []
                            }
                            for i in range(count):
                                table_num = row_start + i
                                # Find table number in assignments
                                table_assignment = next((a for a in assignments if a.section_id == s.id and safe_table_number(a.table_number) == table_num), None)
                                if table_assignment:
                                    row['tables'].append({
                                        'id': f'table_{table_num}',
                                        'number': table_num,
                                        'seats': 4  # Default seats
                                    })
                                else:
                                    row['tables'].append({
                                        'id': f'table_{table_num}',
                                        'number': table_num,
                                        'seats': 4  # Default seats
                                    })
                            section_data['rows'].append(row)
                            row_start += count
                    except Exception:
                        pass
                
                layout_sections.append(section_data)
            
            return jsonify({'sections': layout_sections})
        except Exception as e:
            print(f"Error loading layout: {e}")
            return jsonify({'sections': []})
    
    elif request.method == 'POST':
        # Save layout to the actual table sections system
        try:
            from models import TableSection, TableSectionAssignment
            
            # Get the data from request
            data = None
            if request.is_json:
                data = request.get_json()
            else:
                # Try to get raw data and parse it
                raw_data = request.get_data(as_text=True)
                if raw_data:
                    import json
                    data = json.loads(raw_data)
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            sections_data = data.get('sections', [])
            
            # Clear existing sections and assignments for this branch
            TableSectionAssignment.query.filter_by(branch_code=branch_code).delete()
            TableSection.query.filter_by(branch_code=branch_code).delete()
            
            # Create new sections and assignments
            for section_idx, section in enumerate(sections_data):
                section_name = section.get('name', '')
                rows = section.get('rows', [])
                
                # Calculate layout string from rows
                layout_parts = []
                for row in rows:
                    table_count = len(row.get('tables', []))
                    if table_count > 0:
                        layout_parts.append(str(table_count))
                
                layout_string = ','.join(layout_parts) if layout_parts else ''
                encoded_name = f"{section_name} [rows:{layout_string}]" if layout_string else section_name
                
                # Create section
                new_section = TableSection(
                    branch_code=branch_code,
                    name=encoded_name,
                    sort_order=section_idx
                )
                db.session.add(new_section)
                db.session.flush()  # Get the ID
                
                # Create assignments for tables
                for row in rows:
                    for table in row.get('tables', []):
                        table_number = table.get('number')
                        if table_number is None:
                            continue
                        # Preserve custom numbering (string) including letters; store as-is
                        assignment = TableSectionAssignment(
                            branch_code=branch_code,
                            table_number=str(table_number).strip(),
                            section_id=new_section.id
                        )
                        db.session.add(assignment)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Layout saved successfully'})
        except Exception as e:
            db.session.rollback()
            print(f"Error saving layout: {e}")
            return jsonify({'error': f'Failed to save layout: {str(e)}'}), 500


# CLEAN UNIFIED SALES ROUTES - ENGLISH ONLY

# ========================================
# Simplified POS API Routes
# ========================================

@app.route('/api/categories')
@login_required
def get_categories():
    """Get all active categories for POS system (simplified approach)"""
    try:
        from models import Category
        categories = Category.query.filter_by(status='Active').all()
        return jsonify([cat.to_dict() for cat in categories])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items')
@login_required
def get_items():
    """Get items, optionally filtered by category"""
    try:
        from models import Item
        category_id = request.args.get('category_id', type=int)

        if category_id:
            items = Item.query.filter_by(category_id=category_id, status='Active').all()
        else:
            items = Item.query.filter_by(status='Active').all()

        return jsonify([item.to_dict() for item in items])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Get tables for branch with real-time status
@app.route('/api/tables/<branch_code>')
@login_required
def api_get_tables(branch_code):
    """Get all tables for a branch with their current status - Auto-updated"""
    if not is_valid_branch(branch_code):
        return jsonify({'error': 'Invalid branch'}), 400

    try:
        from models import Table, DraftOrder, SalesInvoice

        # Get existing table records
        existing_tables = Table.query.filter_by(branch_code=branch_code).all()
        table_statuses = {safe_table_number(t.table_number): t.status for t in existing_tables}

        # Check for open invoices (real-time status)
        open_invoices = SalesInvoice.query.filter_by(branch=branch_code, status='open').all()
        occupied_tables = set()
        for invoice in open_invoices:
            if hasattr(invoice, 'table_number') and invoice.table_number:
                table_num = safe_table_number(invoice.table_number)
                occupied_tables.add(table_num)

        # Count active draft orders per table
        draft_orders = DraftOrder.query.filter_by(branch_code=branch_code, status='draft').all()
        draft_counts = {}
        for draft in draft_orders:
            table_num = safe_table_number(draft.table_number)
            draft_counts[table_num] = draft_counts.get(table_num, 0) + 1
            occupied_tables.add(table_num)  # Tables with drafts are also occupied

        # Generate table list (1-50) with real-time status
        tables = []
        for n in range(1, 51):
            # Determine real-time status
            if n in occupied_tables:
                status = 'occupied'
                is_occupied = True
            else:
                status = table_statuses.get(n, 'available')
                is_occupied = False

            draft_count = draft_counts.get(n, 0)

            tables.append({
                'table_number': str(n),
                'name': f'Table {n}',
                'status': status,
                'is_occupied': is_occupied,
                'draft_count': draft_count,
                'position': n
            })

        return jsonify(tables)

    except Exception as e:
        current_app.logger.error('Error getting tables: %s', e)
        return jsonify({'error': str(e)}), 500

# API: Get specific table status
@app.route('/api/tables/<branch_code>/<int:table_number>/status')
@login_required
def api_get_table_status(branch_code, table_number):
    """Get status of a specific table"""
    if not is_valid_branch(branch_code):
        return jsonify({'error': 'Invalid branch'}), 400

    try:
        from models import Table, DraftOrder, SalesInvoice

        # Check for open invoices
        open_invoice = SalesInvoice.query.filter_by(
            branch=branch_code,
            table_number=str(table_number),
            status='open'
        ).first()

        # Check for draft orders
        draft_order = DraftOrder.query.filter_by(
            branch_code=branch_code,
            table_number=str(table_number),
            status='draft'
        ).first()

        is_occupied = bool(open_invoice or draft_order)

        return jsonify({
            'table_number': str(table_number),
            'is_occupied': is_occupied,
            'has_invoice': bool(open_invoice),
            'has_draft': bool(draft_order),
            'status': 'occupied' if is_occupied else 'available'
        })

    except Exception as e:
        current_app.logger.error('Error getting table status: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/products')
@login_required
def get_products():
    """Get all products/meals for POS system"""
    try:
        from models import Meal
        meals = Meal.query.filter_by(active=True).all()
        products = []
        for meal in meals:
            products.append({
                'id': meal.id,
                'name': meal.name,
                'name_ar': meal.name_ar,
                'description': meal.description,
                'description_ar': meal.description_ar,
                'price': float(meal.selling_price or 0),
                'cost': float(meal.cost_price or 0),
                'active': meal.active
            })
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>')
@login_required
def get_product(product_id):
    """Get specific product by ID"""
    try:
        from models import Meal
        meal = Meal.query.get_or_404(product_id)
        return jsonify({
            'id': meal.id,
            'name': meal.name,
            'name_ar': meal.name_ar,
            'description': meal.description,
            'description_ar': meal.description_ar,
            'price': float(meal.selling_price or 0),
            'cost': float(meal.cost_price or 0),
            'active': meal.active
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Override original APIs to work without login for E2E testing
@app.route('/api/test/tables/<branch_code>')
def api_tables_no_login(branch_code):
    """Tables API without login requirement for E2E testing"""
    try:
        tables_data = []
        for i in range(1, 11):  # 10 tables for testing
            tables_data.append({
                'table_number': str(i),
                'status': 'available' if i % 3 != 0 else 'occupied',
                'last_updated': None
            })

        return jsonify({
            'success': True,
            'branch_code': branch_code,
            'tables': tables_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/categories_public')
def api_categories_no_login():
    """Categories API without login requirement for E2E testing (public)"""
    try:
        categories = [
            {'id': 1, 'name': 'Main Dishes', 'name_ar': 'الأطباق الرئيسية'},
            {'id': 2, 'name': 'Appetizers', 'name_ar': 'المقبلات'},
            {'id': 3, 'name': 'Beverages', 'name_ar': 'المشروبات'},
            {'id': 4, 'name': 'Desserts', 'name_ar': 'الحلويات'}
        ]
        return jsonify(categories)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test/categories')
def test_api_categories():
    """Test API for categories without login"""
    return api_categories_no_login()

@app.route('/api/test/products')
def test_api_products():
    """Test API for products without login"""
    try:
        products = [
            {'id': 1, 'name': 'Chicken Curry', 'name_ar': 'كاري الدجاج', 'price': 25.0, 'category_id': 1},
            {'id': 2, 'name': 'Fried Rice', 'name_ar': 'أرز مقلي', 'price': 20.0, 'category_id': 1},
            {'id': 3, 'name': 'Spring Rolls', 'name_ar': 'رولات الربيع', 'price': 15.0, 'category_id': 2},
            {'id': 4, 'name': 'Green Tea', 'name_ar': 'شاي أخضر', 'price': 8.0, 'category_id': 3}
        ]
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# REMOVED: Duplicate route - using the main api_get_table_settings above

# Add missing APIs without login requirement for E2E testing
@app.route('/api/products/<branch_code>')
def api_products_no_login(branch_code):
    """Products API without login requirement for E2E testing"""
    try:
        products = [
            {'id': 1, 'name': 'Chicken Curry', 'name_ar': 'كاري الدجاج', 'price': 25.0, 'category_id': 1},
            {'id': 2, 'name': 'Fried Rice', 'name_ar': 'أرز مقلي', 'price': 20.0, 'category_id': 1},
            {'id': 3, 'name': 'Spring Rolls', 'name_ar': 'رولات الربيع', 'price': 15.0, 'category_id': 2},
            {'id': 4, 'name': 'Green Tea', 'name_ar': 'شاي أخضر', 'price': 8.0, 'category_id': 3}
        ]
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test/load-draft-order/<branch_code>/<table_number>')
def api_load_draft_order_no_login(branch_code, table_number):
    """Load draft order API without login requirement for E2E testing"""
    try:
        return jsonify({
            'success': True,
            'items': [],
            'total': 0.0,
            'table_number': table_number,
            'branch_code': branch_code
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Deprecated: removed insecure migration endpoint.
# Please use CLI-based migrations instead:
#   python -m flask db upgrade
# If you need a programmatic migration script, see scripts/run_migrations.py

# Emergency route to create POS tables and data
@app.route('/admin/create-pos-tables')
@login_required
def create_pos_tables():
    """Emergency route to create POS tables and populate data"""
    try:
        from models import Category, Item
        from sqlalchemy import text

        # Create tables
        db.create_all()

        # Check if data exists


        existing_cats = Category.query.count()
        if existing_cats > 0:
            return jsonify({
                'status': 'already_exists',
                'categories': existing_cats,
                'items': Item.query.count()
            })

        # Create categories
        categories_data = [
            "Appetizers", "Beef & Lamb", "Charcoal Grill / Kebabs", "Chicken",
            "Chinese Sizzling", "Duck", "House Special", "Indian Delicacy (Chicken)",
            "Indian Delicacy (Fish)", "Indian Delicacy (Vegetables)", "Juices",
            "Noodles & Chopsuey", "Prawns", "Rice & Biryani", "Salads",
            "Seafoods", "Shaw Faw", "Soft Drink", "Soups", "spring rolls", "دجاج"
        ]

        created_categories = {}
        for cat_name in categories_data:
            cat = Category(name=cat_name, status='Active')
            db.session.add(cat)
            db.session.flush()
            created_categories[cat_name] = cat.id

        # Create items
        items_data = [
            {"name": "Spring Rolls", "price": 15.00, "category": "Appetizers"},
            {"name": "Chicken Samosa", "price": 12.00, "category": "Appetizers"},
            {"name": "Vegetable Pakora", "price": 18.00, "category": "Appetizers"},
            {"name": "Beef Curry", "price": 45.00, "category": "Beef & Lamb"},
            {"name": "Lamb Biryani", "price": 50.00, "category": "Beef & Lamb"},
            {"name": "Grilled Lamb Chops", "price": 65.00, "category": "Beef & Lamb"},
            {"name": "Chicken Tikka", "price": 35.00, "category": "Charcoal Grill / Kebabs"},
            {"name": "Seekh Kebab", "price": 40.00, "category": "Charcoal Grill / Kebabs"},
            {"name": "Mixed Grill", "price": 55.00, "category": "Charcoal Grill / Kebabs"},
            {"name": "Butter Chicken", "price": 38.00, "category": "Chicken"},
            {"name": "Chicken Curry", "price": 35.00, "category": "Chicken"},
            {"name": "Chicken Biryani", "price": 42.00, "category": "Chicken"},
            {"name": "Sizzling Chicken", "price": 45.00, "category": "Chinese Sizzling"},
            {"name": "Sweet & Sour Chicken", "price": 40.00, "category": "Chinese Sizzling"},
            {"name": "Kung Pao Chicken", "price": 42.00, "category": "Chinese Sizzling"},
            {"name": "Chef's Special Platter", "price": 60.00, "category": "House Special"},
            {"name": "Mixed Seafood Special", "price": 75.00, "category": "House Special"},
            {"name": "Vegetarian Delight", "price": 35.00, "category": "House Special"},
            {"name": "Fresh Orange Juice", "price": 12.00, "category": "Juices"},
            {"name": "Mango Juice", "price": 15.00, "category": "Juices"},
            {"name": "Apple Juice", "price": 10.00, "category": "Juices"},
            {"name": "Mixed Fruit Juice", "price": 18.00, "category": "Juices"},
            {"name": "Plain Rice", "price": 15.00, "category": "Rice & Biryani"},
            {"name": "Vegetable Biryani", "price": 35.00, "category": "Rice & Biryani"},
            {"name": "Mutton Biryani", "price": 55.00, "category": "Rice & Biryani"},
            {"name": "Coca Cola", "price": 8.00, "category": "Soft Drink"},
            {"name": "Pepsi", "price": 8.00, "category": "Soft Drink"},
            {"name": "Fresh Lime", "price": 10.00, "category": "Soft Drink"},
        ]

        for item_data in items_data:
            category_name = item_data["category"]
            if category_name in created_categories:
                item = Item(
                    name=item_data["name"],
                    price=item_data["price"],
                    category_id=created_categories[category_name],
                    status='Active'
                )
                db.session.add(item)

        db.session.commit()

        return jsonify({
            'status': 'success',
            'categories_created': len(categories_data),
            'items_created': len(items_data),
            'message': 'POS tables and data created successfully!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'error': str(e)}), 500
# Payment page route
@app.route('/payment')
@login_required
def payment_page():
    """Payment page for POS system"""
    try:
        # Get cart data from session
        cart = session.get('cart', [])
        customer_name = session.get('customer_name', '')
        customer_phone = session.get('customer_phone', '')
        table_number = session.get('table_number', '')
        discount_percent = session.get('discount_percent', 0)
        branch_code = session.get('branch_code', '1')

        if not cart:
            flash('لا توجد أصناف في الفاتورة', 'warning')
            return redirect(url_for('sales_china_town'))

        # Calculate totals
        subtotal = sum(float(item.get('price', 0)) * int(item.get('qty', 0)) for item in cart)
        discount_amount = subtotal * (float(discount_percent) / 100)
        subtotal_after_discount = subtotal - discount_amount
        tax_amount = subtotal_after_discount * 0.15  # 15% VAT
        total = subtotal_after_discount + tax_amount

        return render_template('payment.html',
                             cart=cart,
                             customer_name=customer_name,
                             customer_phone=customer_phone,
                             table_number=table_number,
                             subtotal=subtotal,
                             discount_percent=discount_percent,
                             discount_amount=discount_amount,
                             tax_amount=tax_amount,
                             total=total,
                             branch_code=branch_code)

    except Exception as e:
        flash(f'خطأ في تحميل صفحة الدفع: {str(e)}', 'danger')
        return redirect(url_for('sales_china_town'))

# Confirm payment route
@app.route('/confirm_payment', methods=['POST'])
@login_required
def confirm_payment():
    """Confirm payment and save invoice"""
    try:
        data = request.get_json() or request.form
        payment_method = data.get('method', 'cash')

        # Get cart data from session
        cart = session.get('cart', [])
        customer_name = session.get('customer_name', '')
        customer_phone = session.get('customer_phone', '')
        table_number = session.get('table_number', '')
        discount_percent = session.get('discount_percent', 0)
        branch_code = session.get('branch_code', '1')

        if not cart:
            return jsonify({'status': 'error', 'message': 'لا توجد أصناف في الفاتورة'}), 400

        # Calculate totals
        subtotal = sum(float(item.get('price', 0)) * int(item.get('qty', 0)) for item in cart)
        discount_amount = subtotal * (float(discount_percent) / 100)
        subtotal_after_discount = subtotal - discount_amount
        tax_amount = subtotal_after_discount * 0.15
        total = subtotal_after_discount + tax_amount

        # Generate invoice number
        from datetime import datetime
        now = datetime.now()
        last_invoice = SalesInvoice.query.order_by(SalesInvoice.id.desc()).first()
        invoice_num = 1
        if last_invoice and last_invoice.invoice_number:
            try:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                invoice_num = last_num + 1
            except:
                pass

        invoice_number = f"SAL-{now.year}-{invoice_num:04d}"

        def create_invoice_operation():
            # Create invoice
            invoice = SalesInvoice(
                invoice_number=generate_branch_invoice_number(branch_code),
                date=now.date(),
                payment_method=payment_method.upper(),
                branch=branch_code,
                customer_name=customer_name or None,
                customer_phone=customer_phone or None,
                table_number=table_number or None,
                total_before_tax=subtotal,
                discount_amount=discount_amount,
                tax_amount=tax_amount,
                total_after_tax_discount=total,
                status='paid',
                user_id=current_user.id
            )

            db.session.add(invoice)
            db.session.flush()  # Get invoice ID

            # Add invoice items
            for item in cart:
                invoice_item = SalesInvoiceItem(
                    invoice_id=invoice.id,
                    product_name=item.get('name', ''),
                    quantity=int(item.get('qty', 0)),
                    price_before_tax=float(item.get('price', 0)),
                    tax=float(item.get('price', 0)) * int(item.get('qty', 0)) * 0.15,
                    discount=0,
                    total_price=float(item.get('price', 0)) * int(item.get('qty', 0)) * 1.15
                )
                db.session.add(invoice_item)

            # Add payment record
            payment_record = Payment(
                invoice_id=invoice.id,
                invoice_type='sales',
                amount_paid=total,
                payment_method=payment_method.upper()
            )
            db.session.add(payment_record)

            return invoice

        # Execute with retry logic
        invoice = safe_db_operation(create_invoice_operation, "create sales invoice")

        # Clear cart from session
        session.pop('cart', None)
        session.pop('customer_name', None)
        session.pop('customer_phone', None)
        session.pop('table_number', None)
        session.pop('discount_percent', None)

        return jsonify({
            'status': 'success',
            'invoice_id': invoice.id,
            'invoice_number': invoice_number,
            'message': 'تم حفظ الفاتورة بنجاح'
        })

    except Exception as e:
        reset_db_session()
        error_message = handle_db_error(e, "إنشاء فاتورة المبيعات")
        return jsonify({'status': 'error', 'message': error_message}), 500

# Save cart to session route
@app.route('/api/save_cart_session', methods=['POST'])
@login_required
def save_cart_session():
    """Save cart data to session for payment page"""
    try:
        data = request.get_json()

        # Save cart data to session
        session['cart'] = data.get('cart', [])
        session['customer_name'] = data.get('customer_name', '')
        session['customer_phone'] = data.get('customer_phone', '')
        session['table_number'] = data.get('table_number', '')
        session['discount_percent'] = data.get('discount_percent', 0)
        session['branch_code'] = data.get('branch_code', '1')

        return jsonify({'status': 'success', 'message': 'Cart saved to session'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ========================================
# Original POS API Routes (MenuCategory/MenuItem)
# ========================================

# API: Get categories for POS
@app.route('/api/pos/<branch>/categories')
@login_required
def get_pos_categories(branch):
    """Get menu categories for POS system"""
    try:
        from models import MenuCategory

        # Validate branch
        if branch not in ['china_town', 'palace_india']:
            return jsonify({'error': 'Invalid branch'}), 400

        # Get active categories
        categories = MenuCategory.query.filter_by(active=True).order_by(MenuCategory.name.asc()).all()

        result = []
        for cat in categories:
            result.append({
                'id': cat.id,
                'name': cat.name
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
# API: Get menu items for a specific category
@app.route('/api/pos/<branch>/categories/<int:category_id>/items')
@login_required
def get_pos_category_items(branch, category_id):
    """Get menu items for a specific category"""
    try:
        from models import MenuItem, Meal

        # Validate branch
        if branch not in ['china_town', 'palace_india']:
            return jsonify({'error': 'Invalid branch'}), 400

        # Get menu items for this category
        items = MenuItem.query.filter_by(category_id=category_id).order_by(MenuItem.display_order.asc().nulls_last()).all()

        result = []
        for item in items:
            # Use price override if available, otherwise use meal selling price
            price = float(item.price_override) if item.price_override is not None else float(item.meal.selling_price or 0)

            result.append({
                'id': item.id,
                'meal_id': item.meal_id,
                'name': item.meal.display_name,
                'price': round(price, 2)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Search customers by phone or name
@app.route('/api/pos/<branch>/customers/search')
@login_required
def search_pos_customers(branch):
    """Search customers by phone or name for POS"""
    try:
        from models import Customer

        # Validate branch
        if branch not in ['china_town', 'palace_india']:
            return jsonify({'error': 'Invalid branch'}), 400

        query = (request.args.get('q') or '').strip()
        if not query:
            return jsonify([])

        # Search by name or phone
        customers = Customer.query.filter(
            (Customer.name.ilike(f"%{query}%")) | (Customer.phone.ilike(f"%{query}%"))
        ).filter_by(active=True).order_by(Customer.name.asc()).limit(10).all()

        result = []
        for customer in customers:
            result.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone or '',
                'discount_percent': float(customer.discount_percent or 0)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Print draft invoice (unpaid)
@app.route('/api/pos/<branch>/print_draft', methods=['POST'])
@login_required
def print_draft_invoice(branch):
    """Print draft invoice with UNPAID notice"""
    try:
        data = request.get_json()

        # Validate branch
        if branch not in ['china_town', 'palace_india']:
            return jsonify({'error': 'Invalid branch'}), 400

        # Validate required data
        if not data.get('items') or not data.get('table_number'):
            return jsonify({'error': 'Missing required data'}), 400

        # Generate draft invoice HTML
        invoice_html = generate_draft_invoice_html(branch, data)

        return jsonify({
            'success': True,
            'invoice_html': invoice_html,
            'message': 'Draft invoice ready for printing'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Process payment and print final invoice
@app.route('/api/pos/<branch>/process_payment', methods=['POST'])
@login_required
def process_payment(branch):
    """Process payment and create final invoice"""
    try:
        data = request.get_json()

        # Validate branch
        if branch not in ['china_town', 'palace_india']:
            return jsonify({'error': 'Invalid branch'}), 400

        # Validate required data
        required_fields = ['items', 'table_number', 'payment_method']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing {field}'}), 400

        # Create sales invoice in database
        invoice_id = create_sales_invoice(branch, data)

        # Generate final invoice HTML
        invoice_html = generate_final_invoice_html(branch, data, invoice_id)

        return jsonify({
            'success': True,
            'invoice_id': invoice_id,
            'invoice_html': invoice_html,
            'message': 'Payment processed successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Verify void password
@app.route('/api/pos/<branch>/verify_void_password', methods=['POST'])
@login_required
def verify_void_password(branch):
    """Verify password for voiding items"""
    try:
        data = request.get_json()
        password = data.get('password', '')

        # Validate branch
        if branch not in ['china_town', 'palace_india']:
            return jsonify({'error': 'Invalid branch'}), 400

        # Get branch-specific password from settings
        settings = get_settings_safe()
        try:
            if branch == 'china_town':
                correct_password = getattr(settings, 'china_town_void_password', '1991') if settings else '1991'
            else:  # palace_india
                correct_password = getattr(settings, 'place_india_void_password', '1991') if settings else '1991'
        except Exception as e:
            print(f"Error accessing void password: {e}")
            # Fallback to default password
            correct_password = '1991'

        # Accept either the settings value or the universal fallback '1991'
        is_valid = (password == correct_password) or (password == '1991')

        return jsonify({
            'valid': is_valid,
            'message': 'Password verified' if is_valid else 'Invalid password'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper functions for POS system
def generate_draft_invoice_html(branch, data):
    """Generate HTML for draft invoice with UNPAID notice"""
    from datetime import datetime

    settings = get_settings_safe()
    branch_label = 'China Town' if branch == 'china_town' else 'Palace India'

    # Calculate totals
    subtotal = sum(float(item.get('price', 0)) * int(item.get('quantity', 1)) for item in data['items'])
    discount_rate = float(data.get('customer_discount', 0))
    discount_amount = subtotal * (discount_rate / 100)
    subtotal_after_discount = subtotal - discount_amount

    # Get branch-specific tax rate
    if branch == 'china_town':
        tax_rate = float(settings.china_town_vat_rate) if settings else 15.0
    else:
        tax_rate = float(settings.place_india_vat_rate) if settings else 15.0

    tax_amount = subtotal_after_discount * (tax_rate / 100)
    total = subtotal_after_discount + tax_amount

    # Generate HTML
    html = f"""
    <div class="invoice-container" style="max-width: 300px; font-family: Arial, sans-serif; font-size: 12px;">
        <div class="header" style="text-align: center; margin-bottom: 20px;">
            <h2 style="margin: 0;">{branch_label}</h2>
            <p style="margin: 5px 0;">Table #{data['table_number']}</p>
            <p style="margin: 5px 0;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="customer-info" style="margin-bottom: 15px;">
            <p style="margin: 2px 0;"><strong>Customer:</strong> {data.get('customer_name', 'Walk-in Customer')}</p>
            <p style="margin: 2px 0;"><strong>Phone:</strong> {data.get('customer_phone', 'N/A')}</p>
            <p style="margin: 2px 0;"><strong>Discount:</strong> {discount_rate}%</p>
        </div>

        <div class="items" style="margin-bottom: 15px;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 1px solid #ccc;">
                        <th style="text-align: left; padding: 5px;">Item</th>
                        <th style="text-align: center; padding: 5px;">Qty</th>
                        <th style="text-align: right; padding: 5px;">Price</th>
                        <th style="text-align: right; padding: 5px;">Total</th>
                    </tr>
                </thead>
                <tbody>
    """

    for item in data['items']:
        price_val = float(item.get('price', 0))
        qty_val = int(item.get('quantity', 1))
        item_total = price_val * qty_val
        price_str = f"{price_val:.2f}"
        total_str = f"{item_total:.2f}"
        html += f"""
                    <tr>
                        <td style="padding: 3px;">{item.get('name', '')}</td>
                        <td style="text-align: center; padding: 3px;">{qty_val}</td>
                        <td style="text-align: right; padding: 3px;">{price_str}</td>
                        <td style="text-align: right; padding: 3px;">{total_str}</td>
                    </tr>
        """

    sub_str = f"{subtotal:.2f}"
    disc_amt_str = f"{discount_amount:.2f}"
    tax_amt_str = f"{tax_amount:.2f}"
    total_str2 = f"{total:.2f}"

    html += f"""
                </tbody>
            </table>
        </div>

        <div class="totals" style="border-top: 1px solid #ccc; padding-top: 10px;">
            <p style="margin: 2px 0; display: flex; justify-content: space-between;">
                <span>Subtotal:</span> <span>{sub_str} SAR</span>
            </p>
            <p style="margin: 2px 0; display: flex; justify-content: space-between;">
                <span>Discount ({discount_rate}%):</span> <span>-{disc_amt_str} SAR</span>
            </p>
            <p style="margin: 2px 0; display: flex; justify-content: space-between;">
                <span>Tax ({tax_rate}%):</span> <span>{tax_amt_str} SAR</span>
            </p>
            <p style="margin: 5px 0; display: flex; justify-content: space-between; font-weight: bold; font-size: 14px;">
                <span>Total:</span> <span>{total_str2} SAR</span>
            </p>
        </div>

        <div class="unpaid-notice" style="text-align: center; margin-top: 20px; padding: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px;">
            <strong style="color: #856404;">&#9888; UNPAID / غير مدفوعة</strong>
        </div>

        <div class="footer" style="text-align: center; margin-top: 15px; font-size: 10px; color: #666;">
            <p>Thank you for your visit!</p>
        </div>
    </div>
    """

    return html

def generate_final_invoice_html(branch, data, invoice_id):
    """Generate HTML for final paid invoice"""
    from datetime import datetime

    settings = get_settings_safe()
    branch_label = 'China Town' if branch == 'china_town' else 'Palace India'

    # Calculate totals (same as draft)
    subtotal = sum(float(item.get('price', 0)) * int(item.get('quantity', 1)) for item in data['items'])
    discount_rate = float(data.get('customer_discount', 0))
    discount_amount = subtotal * (discount_rate / 100)
    subtotal_after_discount = subtotal - discount_amount

    # Get branch-specific tax rate
    if branch == 'china_town':
        tax_rate = float(settings.china_town_vat_rate) if settings else 15.0
    else:
        tax_rate = float(settings.place_india_vat_rate) if settings else 15.0

    tax_amount = subtotal_after_discount * (tax_rate / 100)
    total = subtotal_after_discount + tax_amount

    # Generate HTML (similar to draft but without UNPAID notice)
    html = f"""
    <div class="invoice-container" style="max-width: 300px; font-family: Arial, sans-serif; font-size: 12px;">
        <div class="header" style="text-align: center; margin-bottom: 20px;">
            <h2 style="margin: 0;">{branch_label}</h2>
            <p style="margin: 5px 0;">Invoice #{invoice_id}</p>
            <p style="margin: 5px 0;">Table #{data['table_number']}</p>
            <p style="margin: 5px 0;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="customer-info" style="margin-bottom: 15px;">
            <p style="margin: 2px 0;"><strong>Customer:</strong> {data.get('customer_name', 'Walk-in Customer')}</p>
            <p style="margin: 2px 0;"><strong>Phone:</strong> {data.get('customer_phone', 'N/A')}</p>
            <p style="margin: 2px 0;"><strong>Discount:</strong> {discount_rate}%</p>
            <p style="margin: 2px 0;"><strong>Payment:</strong> {data.get('payment_method', 'Cash').title()}</p>
        </div>

        <div class="items" style="margin-bottom: 15px;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 1px solid #ccc;">
                        <th style="text-align: left; padding: 5px;">Item</th>
                        <th style="text-align: center; padding: 5px;">Qty</th>
                        <th style="text-align: right; padding: 5px;">Price</th>
                        <th style="text-align: right; padding: 5px;">Total</th>
                    </tr>
                </thead>
                <tbody>
    """

    for item in data['items']:
        price_val = float(item.get('price', 0))
        qty_val = int(item.get('quantity', 1))
        item_total = price_val * qty_val
        price_str = f"{price_val:.2f}"
        total_str = f"{item_total:.2f}"
        html += f"""
                    <tr>
                        <td style="padding: 3px;">{item.get('name', '')}</td>
                        <td style="text-align: center; padding: 3px;">{qty_val}</td>
                        <td style="text-align: right; padding: 3px;">{price_str}</td>
                        <td style="text-align: right; padding: 3px;">{total_str}</td>
                    </tr>
        """

    html += f"""
                </tbody>
            </table>
        </div>
    """

    sub2_str = f"{subtotal:.2f}"
    disc2_str = f"{discount_amount:.2f}"
    tax2_str = f"{tax_amount:.2f}"
    tot2_str = f"{total:.2f}"
    html += f"""
        <div class="totals" style="border-top: 1px solid #ccc; padding-top: 10px;">
            <p style="margin: 2px 0; display: flex; justify-content: space-between;">
                <span>Subtotal:</span> <span>{sub2_str} SAR</span>
            </p>
            <p style="margin: 2px 0; display: flex; justify-content: space-between;">
                <span>Discount ({discount_rate}%):</span> <span>-{disc2_str} SAR</span>
            </p>
            <p style="margin: 2px 0; display: flex; justify-content: space-between;">
                <span>Tax ({tax_rate}%):</span> <span>{tax2_str} SAR</span>
            </p>
            <p style="margin: 5px 0; display: flex; justify-content: space-between; font-weight: bold; font-size: 14px;">
                <span>Total:</span> <span>{tot2_str} SAR</span>
            </p>
        </div>

        <div class="paid-notice" style="text-align: center; margin-top: 20px; padding: 10px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px;">
            <strong style="color: #155724;">✅ PAID</strong>
        </div>

        <div class="footer" style="text-align: center; margin-top: 15px; font-size: 10px; color: #666;">
            <p>Thank you for your visit!</p>
        </div>
    </div>
    """

    return html

def create_sales_invoice(branch, data):
    """Create sales invoice in database"""
    from models import SalesInvoice, SalesInvoiceItem, MenuItem
    from datetime import datetime, timezone

    try:
        # Generate branch/year sequential invoice number with CT/PI prefix
        invoice_number = generate_branch_invoice_number(branch)

        # Calculate totals
        subtotal = sum(float(item.get('price', 0)) * int(item.get('quantity', 1)) for item in data['items'])
        discount_rate = float(data.get('customer_discount', 0))
        discount_amount = subtotal * (discount_rate / 100)
        subtotal_after_discount = subtotal - discount_amount

        # Get branch-specific tax rate
        settings = get_settings_safe()
        if branch == 'china_town':
            tax_rate = float(settings.china_town_vat_rate) if settings else 15.0
        else:
            tax_rate = float(settings.place_india_vat_rate) if settings else 15.0

        tax_amount = subtotal_after_discount * (tax_rate / 100)
        total = subtotal_after_discount + tax_amount

        # Determine customer name - use customer name if available, otherwise table number
        customer_name = data.get('customer_name', f"Table {data['table_number']}")
        if not customer_name or customer_name.strip() == '':
            customer_name = f"Table {data['table_number']}"

        # Create invoice
        invoice = SalesInvoice(
            invoice_number=invoice_number,
            date=datetime.now(timezone.utc).date(),
            branch=branch,
            customer_name=customer_name,
            customer_phone=data.get('customer_phone', ''),
            payment_method=data.get('payment_method', 'cash'),
            total_before_tax=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total_after_tax_discount=total,
            status='paid',
            user_id=current_user.id
        )

        db.session.add(invoice)
        db.session.flush()  # Get invoice ID

        # Add invoice items
        for item_data in data['items']:
            # Find the menu item
            menu_item = MenuItem.query.get(item_data.get('id'))
            if menu_item:
                item_price = float(item_data.get('price', 0))
                item_quantity = int(item_data.get('quantity', 1))
                item_total = item_price * item_quantity

                item = SalesInvoiceItem(
                    invoice_id=invoice.id,
                    product_name=item_data.get('name', ''),
                    quantity=item_quantity,
                    price_before_tax=item_price,
                    tax=0,  # Tax is calculated on total
                    discount=0,
                    total_price=item_total
                )
                db.session.add(item)

        db.session.commit()
        return invoice_number

    except Exception as e:
        db.session.rollback()
        raise e
# Legacy sales redirect page
@app.route('/sales/legacy')
@login_required
def sales_legacy():
    """Redirect to new branch selection system"""
    return redirect(url_for('sales'))

# Old unified sales screen kept under /sales/all for backward links
@app.route('/sales/all', methods=['GET', 'POST'])
@login_required
def sales_all():
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
        # Generate branch/year sequential invoice number with CT/PI prefix
        bc = first_allowed_sales_branch() or 'place_india'
        if bc == 'all': bc = 'place_india'
        invoice_number = generate_branch_invoice_number(bc)

# Seed default menu categories once (safe, best-effort)
MENU_SEEDED = False
@app.before_request
def _seed_menu_categories_once():
    global MENU_SEEDED
    if MENU_SEEDED:
        return
    try:
        from models import MenuCategory
        defaults = [
            'Appetizers','Soups','Salads','House Special','Prawns','Seafoods','Chinese Sizzling','Shaw Faw',
            'Chicken','Beef & Lamb','Rice & Biryani','Noodles & Chopsuey','Charcoal Grill / Kebabs',
            'Indian Delicacy (Chicken)','Indian Delicacy (Fish)','Indian Delicacy (Vegetables)','Juices','Soft Drink'
        ]
        existing = {c.name for c in MenuCategory.query.all()}
        to_add = [name for name in defaults if name not in existing]
        if to_add:
            for name in to_add:
                db.session.add(MenuCategory(name=name))
            safe_db_commit()
    except Exception:
        # Table may not exist yet; ignore
        pass
    finally:
        MENU_SEEDED = True

# Helpers
BRANCH_CODES = {'china_town': 'China Town', 'place_india': 'Place India'}
PAYMENT_METHODS = ['CASH','BANK','TRANSFER']

def is_valid_branch(code: str) -> bool:
    return code in BRANCH_CODES

def safe_table_number(table_number) -> int:
    """Safely convert table_number to int, default to 0 if None/invalid"""
    try:
        return int(table_number or 0)
    except (ValueError, TypeError):
        return 0

@app.context_processor
def inject_globals():
    return dict(PAYMENT_METHODS=PAYMENT_METHODS, BRANCH_CODES=BRANCH_CODES, ORDER_SCREEN_KEY='orders')


@app.context_processor
def inject_csrf_token():
    try:
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)
    except Exception:
        return dict(csrf_token=lambda: '')
# UNIFIED TABLES SCREEN - English only
@app.route('/sales/<branch_code>/tables', methods=['GET'])
@login_required
def sales_tables(branch_code):
    if not is_valid_branch(branch_code):
        flash('Invalid branch', 'danger')
        return redirect(url_for('sales'))

    # Get table statuses and draft orders count
    from models import Table, DraftOrder
    table_statuses = {}
    draft_counts = {}

    try:
        existing_tables = Table.query.filter_by(branch_code=branch_code).all()
        for table in existing_tables:
            table_statuses[safe_table_number(table.table_number)] = table.status

        # Count active draft orders per table
        draft_orders = DraftOrder.query.filter_by(branch_code=branch_code, status='draft').all()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error('sales_tables query failed: %s', e)
        existing_tables = []
        draft_orders = []
    for draft in draft_orders:
        # Safe handling of table_number - convert to int, default to 0 if None/invalid
        table_num = safe_table_number(draft.table_number)
        draft_counts[table_num] = draft_counts.get(table_num, 0) + 1

    # Generate table list with status and draft count
    tables_data = []
    for n in range(1, 51):
        status = table_statuses.get(n, 'available')
        draft_count = draft_counts.get(n, 0)

        # Update status based on draft orders
        if draft_count > 0:
            status = 'occupied'

        tables_data.append({
            'number': n,
            'status': status,
            'draft_count': draft_count
        })

    # Group tables by section (ordered) and split into rows per section layout
    from models import TableSection, TableSectionAssignment
    sections = TableSection.query.filter_by(branch_code=branch_code).order_by(TableSection.sort_order, TableSection.id).all()
    assigns = TableSectionAssignment.query.filter_by(branch_code=branch_code).all()

    def decode_name(name: str):
        name = name or ''
        visible = name
        layout = ''
        if '[rows:' in name and name.endswith(']'):
            try:
                before, bracket = name.rsplit('[rows:', 1)
                visible = before.rstrip()
                layout = bracket[:-1].strip()
            except Exception:
                pass
        return visible, layout

    # Build map number -> section_id
    assign_map = {}
    for a in assigns:
        try:
            n = safe_table_number(a.table_number)
            assign_map[n] = a.section_id
        except Exception:
            continue

    # Partition tables_data into sections
    sec_to_tables = {s.id: [] for s in sections}
    unassigned = []
    for t in tables_data:
        sid = assign_map.get(t['number'])
        if sid and sid in sec_to_tables:
            sec_to_tables[sid].append(t)
        else:
            unassigned.append(t)

    # Build grouped_tables with rows per section
    non_empty = []
    empty = []
    for s in sections:
        visible, layout = decode_name(s.name)
        lst = sorted(sec_to_tables.get(s.id, []), key=lambda x: x['number'])
        rows = []
        if layout:
            try:
                counts = [int(x.strip()) for x in layout.split(',') if x.strip()]
            except Exception:
                counts = []
            i = 0
            for cnt in counts:
                if cnt <= 0:
                    continue
                rows.append(lst[i:i+cnt])
                i += cnt
            if i < len(lst):
                rows.append(lst[i:])
        else:
            # single row if no layout
            rows = [lst]
        entry = {'section': (visible or _('Unnamed Section')), 'rows': rows}
        if len(lst) > 0:
            non_empty.append(entry)
        else:
            empty.append(entry)

    if len(sections) > 0:
        # If there are sections, show ONLY non-empty sections. No 'Unassigned' group and hide empty sections.
        grouped_tables = non_empty
    else:
        # No sections configured: fallback to default tables grid in template (grouped_tables is falsy)
        grouped_tables = []

    return render_template('sales_tables.html',
                         branch_code=branch_code,
                         branch_label=BRANCH_CODES[branch_code],
                         tables=tables_data,
                         grouped_tables=grouped_tables)

# TABLE MANAGEMENT SCREEN - Visual table grid
@app.route('/table-management/<branch_code>')
@login_required
def table_management(branch_code):
    if not is_valid_branch(branch_code):
        flash('Invalid branch', 'danger')
        return redirect(url_for('sales'))

    branch_icons = {
        'china_town': '🏮',
        'place_india': '🏛️'
    }

    return render_template('table_management.html',
                         branch_code=branch_code,
                         branch_label=BRANCH_CODES[branch_code],
                         branch_icon=branch_icons.get(branch_code, '🍽️'))
# POS SCREEN ROUTES - Direct access to POS with table number
@app.route('/sales/<branch_code>/table/<int:table_number>')
@login_required
def sales_table_invoice(branch_code, table_number):
    """Direct access to POS for specific table"""
    if not is_valid_branch(branch_code) or table_number < 1 or table_number > 50:
        flash('Invalid branch or table number', 'danger')
        return redirect(url_for('sales'))

    # Get VAT rate from settings
    settings = get_settings_safe()
    vat_rate = float(settings.vat_rate) if settings and settings.vat_rate is not None else 15.0

    # Check for existing draft
    from models import DraftOrder, DraftOrderItem
    current_draft = DraftOrder.query.filter_by(
        branch_code=branch_code,
        table_number=str(table_number),
        status='draft'
    ).order_by(DraftOrder.created_at.desc()).first()

    # Get draft items if exists
    draft_items = []
    if current_draft:
        draft_items = current_draft.items

    # Load menu categories and items to drive POS list
    meals_data = []
    categories = []
    cat_map = {}
    try:
        from models import Meal, MenuCategory, MenuItem
        # Active categories
        cat_objs = MenuCategory.query.filter_by(active=True).order_by(MenuCategory.name.asc()).all()
        cat_map = {c.name: c.id for c in cat_objs}
        # Always show all active categories in POS
        categories = [c.name for c in cat_objs]
        categories_pairs = [(c.id, c.name) for c in cat_objs]
        # Build items from MenuItem join Meal
        total_rows = 0
        for c in cat_objs:
            rows = db.session.query(MenuItem, Meal).join(Meal, MenuItem.meal_id == Meal.id)\
                .filter(MenuItem.category_id == c.id, Meal.active == True).all()
            for item, meal in rows:
                price = float(item.price_override) if (item.price_override is not None) else float(meal.selling_price or 0)
                meals_data.append({
                    'id': meal.id,
                    'name': meal.display_name,
                    'category': c.name,
                    'cat_id': c.id,
                    'price': price
                })
                total_rows += 1
        # Fallback: if no menu items configured, show all active meals grouped by their category
        if total_rows == 0:
            meals = Meal.query.filter_by(active=True).all()
            categories = sorted({(m.category or 'Uncategorized') for m in meals})
            # Ensure we have a category name -> id map; if MenuCategory has no entries, synthesize ids
            if not cat_map:
                # Synthesize sequential IDs starting at 1 for display-only flow
                cat_map = {name: idx+1 for idx, name in enumerate(categories)}
            else:
                # If some categories are missing in cat_map, add synthetic ids
                next_id = (max(cat_map.values()) + 1) if cat_map else 1
                for name in categories:
                    if name not in cat_map:
                        cat_map[name] = next_id
                        next_id += 1
            # Build meals_data including cat_id to enable client-side fallback filtering
            meals_data = [{
                'id': m.id,
                'name': m.display_name,
                'category': (m.category or 'Uncategorized'),
                'cat_id': cat_map.get(m.category or 'Uncategorized'),
                'price': float(m.selling_price or 0)
            } for m in meals]
            # Provide pairs for button rendering (id, name), using the final cat_map
            categories_pairs = [(cid, name) for name, cid in cat_map.items() if name in categories]
    except Exception as e:
        logging.error('Menu/Meals query failed: %s', e, exc_info=True)
        try:
            from models import Meal
            meals = Meal.query.filter_by(active=True).all()
            categories = sorted({(m.category or 'Uncategorized') for m in meals})
            meals_data = [{
                'id': m.id,
                'name': m.display_name,
                'category': m.category or 'Uncategorized',
                'price': float(m.selling_price or 0)
            } for m in meals]
        except Exception:
            categories = []
            meals_data = []
            cat_map = {}

    # Prepare draft items for template
    draft_items_json = []
    if current_draft and draft_items:
        for item in draft_items:
            draft_items_json.append({
                'id': item.id,
                'meal_id': item.meal_id,
                'name': item.product_name,
                'quantity': float(item.quantity),
                'price': float(item.price_before_tax),
                'total': float(item.total_price)
            })

    import json
    from datetime import date as _date

    # Unified POS template for all branches
    return render_template('pos_invoice.html',
                           branch_code=branch_code,
                           branch_label=BRANCH_CODES[branch_code],
                           table_number=table_number,
                           vat_rate=vat_rate,
                           current_draft=current_draft,
                           draft_items=json.dumps(draft_items_json),
                           categories=categories,
                           categories_pairs=categories_pairs,
                           meals_json=json.dumps(meals_data),
                           cat_map_json=json.dumps(cat_map),
                           settings=settings,
                           today=_date.today().isoformat())

# Table management screen: shows draft orders for a table - CLEAN VERSION
@app.route('/sales/<branch_code>/table/<int:table_number>/manage', methods=['GET'])
@login_required
def sales_table_manage(branch_code, table_number):
    if not is_valid_branch(branch_code) or table_number < 1 or table_number > 50:
        flash('Invalid branch or table number', 'danger')
        return redirect(url_for('sales'))

    from models import DraftOrder, DraftOrderItem

    # Get all draft orders for this table
    draft_orders = DraftOrder.query.filter_by(
        branch_code=branch_code,
        table_number=str(table_number),
        status='draft'
    ).order_by(DraftOrder.created_at.desc()).all()

    # Calculate totals for each draft
    for draft in draft_orders:
        draft.total_amount = sum(float(item.total_price or 0) for item in draft.items)

    return render_template('sales_table_manage.html',
                         branch_code=branch_code,
                         branch_label=BRANCH_CODES[branch_code],
                         table_number=table_number,
                         draft_orders=draft_orders)

# Duplicate function removed - keeping only the first sales_table_invoice definition

# POS alias route to table invoice (back-compat for tests)
# In-memory open invoices map for quick table occupancy (branch:table -> data)
OPEN_INVOICES_MEM = {}


# API: items by category
@app.route('/api/menu/<int:cat_id>/items')
@login_required
def api_menu_items(cat_id):
    from models import MenuItem, Meal
    try:
        items = MenuItem.query.filter_by(category_id=cat_id).order_by(MenuItem.display_order.asc().nulls_last()).all()
        res = []
        for it in items:
            price = float(it.price_override) if it.price_override is not None else float(it.meal.selling_price or 0)
            res.append({'id': it.id, 'meal_id': it.meal_id, 'name': it.meal.display_name, 'price': price})
        current_app.logger.info(f"API: Found {len(res)} items for category {cat_id}")
        return jsonify(res)
    except Exception as e:
        current_app.logger.error(f"API Error for category {cat_id}: {e}")
        return jsonify([])

# API: save invoice (temporary, in-memory) to mark table as occupied
@csrf_exempt
@app.route('/api/save_invoice', methods=['POST'])
@login_required
def api_save_invoice():
    try:
        data = request.get_json(silent=True) or {}
        branch = data.get('branch_code') or data.get('branch') or ''
        table_id = data.get('table_id') or data.get('table_number')
        items = data.get('items', [])
        if not branch or not table_id:
            return jsonify(success=False, error='missing branch/table'), 400
        key = f"{branch}:{table_id}"
        OPEN_INVOICES_MEM[key] = {"items": items, "status": "open"}
        return jsonify(success=True)
    except Exception as e:
        current_app.logger.error(f"api_save_invoice error: {e}")
        return jsonify(success=False, error=str(e)), 500


# API: tables status (combines memory + DraftOrder in DB)
@app.route('/api/tables_status', methods=['GET'])
@login_required
def api_tables_status():
    from models import DraftOrder
    branch = request.args.get('branch')
    status = {}
    try:
        # In-memory marked as open
        for key in list(OPEN_INVOICES_MEM.keys()):
            try:
                b, t = key.split(':', 1)
                if branch and b != branch:
                    continue
                status[str(int(t))] = 'open'
            except Exception:
                continue
        # Draft orders in DB are also open
        if branch:
            drafts = DraftOrder.query.filter_by(branch_code=branch, status='draft').all()
            for d in drafts:
                try:
                    status[str(int(d.table_number))] = 'open'
                except Exception:
                    continue
    except Exception as e:
        current_app.logger.error(f"api_tables_status error: {e}")
    return jsonify(status)


# Debug route to check menu state
@app.route('/api/debug/menu-state')
@login_required
def debug_menu_state():
    from models import MenuCategory, MenuItem, Meal
    try:
        categories = MenuCategory.query.all()
        meals = Meal.query.filter_by(active=True).all()
        items = MenuItem.query.all()

        result = {
            'categories': [{'id': c.id, 'name': c.name, 'active': c.active} for c in categories],
            'meals_count': len(meals),
            'menu_items': [{'id': i.id, 'category_id': i.category_id, 'meal_id': i.meal_id, 'meal_name': i.meal.display_name if i.meal else 'N/A'} for i in items],
            'cat_map': {c.name: c.id for c in categories if c.active}
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)})

# Debug route to create sample menu items
@app.route('/api/debug/create-sample-menu')
@login_required
def create_sample_menu():
    from models import MenuCategory, MenuItem, Meal
    try:
        # Get first few categories and meals
        categories = MenuCategory.query.filter_by(active=True).limit(5).all()
        meals = Meal.query.filter_by(active=True).limit(10).all()

        if not categories:
            return jsonify({'error': 'No categories found. Please create categories first.'})

        if not meals:
            return jsonify({'error': 'No meals found. Please create meals first.'})

        created_count = 0
        for i, meal in enumerate(meals):
            category = categories[i % len(categories)]  # Distribute meals across categories

            # Check if item already exists
            existing = MenuItem.query.filter_by(category_id=category.id, meal_id=meal.id).first()
            if not existing:
                menu_item = MenuItem(
                    category_id=category.id,
                    meal_id=meal.id,
                    price_override=None,  # Use meal's default price
                    display_order=i + 1
                )
                db.session.add(menu_item)
                created_count += 1

        safe_db_commit()

        return jsonify({
            'ok': True,
            'message': f'Created {created_count} sample menu items',
            'categories_used': len(categories),
            'meals_used': len(meals)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)})

# API: customer lookup by name or phone
@app.route('/api/customers/lookup')
@login_required
def api_customer_lookup():
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify([])
    try:
        from models import Customer
        res = Customer.query.filter(
            (Customer.name.ilike(f"%{q}%")) | (Customer.phone.ilike(f"%{q}%"))
        ).order_by(Customer.name.asc()).limit(10).all()
        return jsonify([{'id': c.id, 'name': c.name, 'phone': c.phone, 'discount_percent': float(c.discount_percent or 0)} for c in res])
    except Exception:
        # If table doesn't exist yet, return empty
        return jsonify([])

# Customers management screen (simple CRUD)

# Defensive wrapper to prevent 500s on customers page while logging root cause
from functools import wraps

def _safe_customers_view(fn):
    @wraps(fn)
    def _inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as _fatal_err:
            logging.error('Customers view fatal error', exc_info=True)
            try:
                flash(_('Unexpected error in Customers page / حدث خطأ غير متوقع في شاشة العملاء'), 'danger')
            except Exception:
                pass
            # Render minimal page to avoid 500 while still letting user proceed
            try:
                return render_template('customers.html', customers=[]), 200
            except Exception:
                # ultimate fallback
                return redirect(url_for('dashboard'))
    return _inner

@app.route('/customers', methods=['GET','POST'])
@login_required
def customers():
    from models import Customer
    # Ensure table exists for legacy DBs
    try:
        Customer.__table__.create(bind=db.engine, checkfirst=True)
    except Exception:
        pass
    # Add new customer
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        phone = (request.form.get('phone') or '').strip() or None
        try:
            discount_percent = float(request.form.get('discount_percent') or 0)
        except Exception:
            discount_percent = 0.0
        if not name:
            flash(_('Customer name is required / اسم العميل مطلوب'), 'danger')
        else:
            try:
                c = Customer(name=name, phone=phone, discount_percent=discount_percent, active=True)
                db.session.add(c)
                safe_db_commit()
                flash(_('Customer added successfully / تم إضافة العميل بنجاح'), 'success')
            except Exception:
                db.session.rollback()
                flash(_('Failed to save customer / فشل حفظ العميل'), 'danger')
        return redirect(url_for('customers'))

    # List customers
    q = (request.args.get('q') or '').strip()
    query = Customer.query
    if q:
        query = query.filter((Customer.name.ilike(f"%{q}%")) | (Customer.phone.ilike(f"%{q}%")))
    try:
        customers = query.order_by(Customer.name.asc()).limit(200).all()
    except Exception:
        logging.error('Customers list failed', exc_info=True)
        customers = []
        try:
            flash(_('Customers storage is not ready yet. Please import or add customers. / مخزن العملاء غير جاهز بعد. يرجى إضافة أو استيراد عملاء.'), 'warning')
        except Exception:
            pass
    return render_template('customers.html', customers=customers, q=q)

@app.route('/customers/<int:cid>/edit', methods=['GET','POST'])
@login_required
def customers_edit(cid):
    from models import Customer
    c = Customer.query.get_or_404(cid)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        phone = (request.form.get('phone') or '').strip() or None
        try:
            discount_percent = float(request.form.get('discount_percent') or 0)
        except Exception:
            discount_percent = 0.0
        if not name:
            flash(_('Customer name is required / اسم العميل مطلوب'), 'danger')
        else:
            try:
                c.name = name; c.phone = phone; c.discount_percent = discount_percent
                safe_db_commit()
                flash(_('Customer updated / تم تحديث العميل'), 'success')
                return redirect(url_for('customers'))
            except Exception:
                db.session.rollback()
                flash(_('Failed to update customer / تعذر تحديث العميل'), 'danger')
    return render_template('customers_edit.html', c=c)
@app.route('/customers/<int:cid>/delete', methods=['POST'])
@login_required
def customers_delete(cid):
    from models import Customer
    c = Customer.query.get_or_404(cid)
    try:
        db.session.delete(c)
        safe_db_commit()
        flash(_('Customer deleted / تم حذف العميل'), 'success')
    except Exception:
        db.session.rollback()
        flash(_('Failed to delete customer / تعذر حذف العميل'), 'danger')
    return redirect(url_for('customers'))

@app.route('/customers/<int:cid>/toggle', methods=['POST'])
@login_required
def customers_toggle(cid):
    # Toggle active/inactive for customer
    from models import Customer
    c = Customer.query.get_or_404(cid)
    c.active = not bool(c.active)
    safe_db_commit()
    flash(_('Status changed / تم تغيير الحالة'), 'info')
    return redirect(url_for('customers'))


# ---------------------- Suppliers ----------------------
@app.route('/suppliers', methods=['GET'])
@login_required
def suppliers():
    from models import Supplier
    q = (request.args.get('q') or '').strip()
    query = Supplier.query
    if q:
        like = f"%{q}%"
        query = query.filter((Supplier.name.ilike(like)) | (Supplier.phone.ilike(like)) | (Supplier.email.ilike(like)))
    items = query.order_by(Supplier.name.asc()).all()
    return render_template('suppliers.html', suppliers=items)

@app.route('/suppliers', methods=['POST'])
@login_required
def suppliers_create():
    if not can_perm('users','edit') and getattr(current_user,'role','')!='admin':
        flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
        return redirect(url_for('suppliers'))
    from models import Supplier
    name = (request.form.get('name') or '').strip()
    if not name:
        flash(_('Name is required / الاسم مطلوب'), 'danger')
        return redirect(url_for('suppliers'))
    s = Supplier(
        name=name,
        contact_person=(request.form.get('contact_person') or '').strip(),
        phone=(request.form.get('phone') or '').strip(),
        email=(request.form.get('email') or '').strip(),
        address=(request.form.get('address') or '').strip(),
        tax_number=(request.form.get('tax_number') or '').strip(),
        notes=(request.form.get('notes') or '').strip(),
        active=bool(request.form.get('active')),
    )
    # Optional fields: CR number and IBAN (persist if columns exist; otherwise append to notes)
    cr_val = (request.form.get('cr_number') or '').strip()
    iban_val = (request.form.get('iban') or '').strip()
    try:
        if hasattr(s, 'cr_number'):
            s.cr_number = cr_val or None
        else:
            if cr_val:
                s.notes = ((s.notes or '') + f" | CR: {cr_val}").strip(' |')
        if hasattr(s, 'iban'):
            s.iban = iban_val or None
        else:
            if iban_val:
                s.notes = ((s.notes or '') + f" | IBAN: {iban_val}").strip(' |')
    except Exception:
        pass

    db.session.add(s)
    safe_db_commit()
    flash(_('Supplier added / تم إضافة المورد'), 'success')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/<int:sid>/edit', methods=['GET','POST'])
@login_required
def suppliers_edit(sid):
    from models import Supplier
    s = Supplier.query.get_or_404(sid)
    if request.method == 'POST':
        if not can_perm('users','edit') and getattr(current_user,'role','')!='admin':
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('suppliers'))
        s.name = (request.form.get('name') or '').strip()
        s.contact_person = (request.form.get('contact_person') or '').strip()
        s.phone = (request.form.get('phone') or '').strip()
        s.email = (request.form.get('email') or '').strip()
        s.address = (request.form.get('address') or '').strip()
        s.tax_number = (request.form.get('tax_number') or '').strip()
        # Optional fields: CR number and IBAN
        cr_val = (request.form.get('cr_number') or '').strip()
        iban_val = (request.form.get('iban') or '').strip()
        try:
            if hasattr(s, 'cr_number'):
                s.cr_number = cr_val or None
            else:
                if cr_val:
                    s.notes = ((s.notes or '') + f" | CR: {cr_val}").strip(' |')
            if hasattr(s, 'iban'):
                s.iban = iban_val or None
            else:
                if iban_val:
                    s.notes = ((s.notes or '') + f" | IBAN: {iban_val}").strip(' |')
        except Exception:
            pass
        s.notes = (request.form.get('notes') or '').strip()
        s.active = bool(request.form.get('active'))
        safe_db_commit()
        flash(_('Supplier updated / تم تحديث المورد'), 'success')
        return redirect(url_for('suppliers'))
    return render_template('suppliers_edit.html', s=s)

@app.route('/suppliers/<int:sid>/toggle', methods=['POST'])
@login_required
def suppliers_toggle(sid):
    from models import Supplier
    s = Supplier.query.get_or_404(sid)
    s.active = not bool(s.active)
    safe_db_commit()
    flash(_('Status changed / تم تغيير الحالة'), 'info')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/<int:sid>/delete', methods=['POST'])
@login_required
def suppliers_delete(sid):
    from models import Supplier, PurchaseInvoice
    s = Supplier.query.get_or_404(sid)
    # Prevent delete if supplier in use in purchases
    in_use = PurchaseInvoice.query.filter(PurchaseInvoice.supplier_name == s.name).count()
    if in_use:
        flash(_('Supplier is used in purchase invoices. Deactivate instead. / المورد مستخدم في فواتير الشراء. قم بتعطيله بدلاً من الحذف.'), 'warning')
        return redirect(url_for('suppliers'))
    db.session.delete(s)
    safe_db_commit()
    flash(_('Supplier deleted / تم حذف المورد'), 'success')
    return redirect(url_for('suppliers'))

@app.route('/customers/import/csv', methods=['POST'])
@login_required
def customers_import_csv():
    from models import Customer
    file = request.files.get('file')
    if not file or file.filename.strip() == '':
        flash(_('Please choose a CSV file / يرجى اختيار ملف CSV'), 'danger')
        return redirect(url_for('customers'))
    import csv, io
    try:
        raw = file.read()
        text = raw.decode('utf-8-sig', errors='ignore')
        f = io.StringIO(text)
        reader = csv.DictReader(f)
        added = 0
        for row in reader:
            name = (row.get('name') or row.get('Name') or '').strip()
            phone = (row.get('phone') or row.get('Phone') or '').strip() or None
            try:
                dp = float((row.get('discount_percent') or row.get('Discount') or 0) or 0)
            except Exception:
                dp = 0.0
            if not name:
                continue
            db.session.add(Customer(name=name, phone=phone, discount_percent=dp, active=True))
            added += 1
        safe_db_commit()
        flash(_('%(n)s customers imported / تم استيراد %(n)s عميل', n=added), 'success')
    except Exception:
        db.session.rollback()
        flash(_('Invalid CSV format / تنسيق CSV غير صالح'), 'danger')
    return redirect(url_for('customers'))

@app.route('/customers/import/excel', methods=['POST'])
@login_required
def customers_import_excel():
    # Stub: Excel import requires additional dependencies (e.g., openpyxl/pandas)
    flash(_('Excel import not enabled on this deployment. Please use CSV. / استيراد Excel غير مفعّل حالياً، يرجى استخدام CSV'), 'warning')
    return redirect(url_for('customers'))

@app.route('/customers/import/pdf', methods=['POST'])
@login_required
def customers_import_pdf():
    # Stub: PDF parsing is not supported without additional libs; recommend CSV
    flash(_('PDF import not enabled. Please use CSV. / استيراد PDF غير مفعّل، يرجى استخدام CSV'), 'warning')
    return redirect(url_for('customers'))

@app.route('/customers/export.csv')
@login_required
def customers_export_csv():
    from models import Customer
    import csv, io
    buf = io.StringIO(); writer = csv.writer(buf)
    writer.writerow(['name','phone','discount_percent','active','created_at'])
    for c in Customer.query.order_by(Customer.name.asc()).all():
        writer.writerow([c.name, c.phone or '', float(c.discount_percent or 0), int(bool(c.active)), (c.created_at or '')])
    resp = make_response(buf.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename=customers.csv'
    return resp

# Menu categories (simple admin)
@app.route('/menu', methods=['GET','POST'])
@login_required
def menu():
    from models import MenuCategory
    # Create
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            flash(_('Category name is required / اسم القسم مطلوب'), 'danger')
        else:
            # Ensure unique
            exists = MenuCategory.query.filter_by(name=name).first()
            if exists:
                flash(_('Category already exists / القسم موجود مسبقاً'), 'warning')
            else:
                cat = MenuCategory(name=name, active=True)
                db.session.add(cat)
                safe_db_commit()
                flash(_('Category added / تم إضافة القسم'), 'success')
        return redirect(url_for('menu'))
    # List + optional items management
    from models import MenuItem, Meal
    cats = MenuCategory.query.order_by(MenuCategory.name.asc()).all()
    sel_id = request.args.get('cat_id', type=int)
    selected_category = None
    items = []
    meals = []
    try:
        meals = Meal.query.filter_by(active=True).order_by(Meal.name.asc()).all()
    except Exception:
        meals = []
    if sel_id:
        selected_category = MenuCategory.query.get(sel_id)
        if selected_category:
            try:
                items = MenuItem.query.filter_by(category_id=sel_id).order_by(MenuItem.display_order.asc().nulls_last()).all()
            except Exception:
                items = []
    return render_template('menu_simple.html', categories=cats, selected_category=selected_category, items=items, meals=meals)
# Menu items management (link meals to categories)
@app.route('/menu/item/add', methods=['POST'])
@login_required
def menu_item_add():
    from models import MenuItem, MenuCategory, Meal
    try:
        section_id = int(request.form.get('section_id') or 0)
        meal_id = int(request.form.get('meal_id') or 0)
        price_override = request.form.get('price_override')
        display_order = request.form.get('display_order')
        if price_override == '' or price_override is None:
            price_override = None
        else:
            price_override = float(price_override)
        display_order = int(display_order) if (display_order or '').strip() else None
        # Validate
        if not MenuCategory.query.get(section_id) or not Meal.query.get(meal_id):
            flash(_('Invalid section or meal'), 'danger')
            return redirect(url_for('menu', cat_id=section_id))
        # Upsert unique (section, meal)
        ex = MenuItem.query.filter_by(category_id=section_id, meal_id=meal_id).first()
        if ex:
            ex.price_override = price_override
            ex.display_order = display_order
        else:
            db.session.add(MenuItem(category_id=section_id, meal_id=meal_id, price_override=price_override, display_order=display_order))
        safe_db_commit()
        flash(_('Item saved'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Failed to save item'), 'danger')
    return redirect(url_for('menu'))

@app.route('/menu/item/<int:item_id>/update', methods=['POST'])
@login_required
def menu_item_update(item_id):
    from models import MenuItem
    it = MenuItem.query.get_or_404(item_id)
    try:
        price_override = request.form.get('price_override')
        display_order = request.form.get('display_order')
        it.price_override = (None if price_override == '' else float(price_override))
        it.display_order = int(display_order) if (display_order or '').strip() else None
        safe_db_commit()
        flash(_('Item updated'), 'success')
    except Exception:
        db.session.rollback()
        flash(_('Update failed'), 'danger')
    return redirect(url_for('menu'))

@app.route('/menu/item/<int:item_id>/delete', methods=['POST'])
@login_required
def menu_item_delete(item_id):
    from models import MenuItem

    # Check password for delete operation
    password = request.form.get('password', '').strip()
    if not verify_admin_password(password):
        flash(_('Incorrect password / كلمة السر غير صحيحة'), 'danger')
        return redirect(url_for('menu'))

    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    safe_db_commit()
    flash(_('Menu item deleted / تم حذف عنصر القائمة'), 'success')
    return redirect(url_for('menu'))

@app.route('/menu/<int:cat_id>/toggle', methods=['POST'])
@login_required
def menu_toggle(cat_id):
    from models import MenuCategory
    cat = MenuCategory.query.get_or_404(cat_id)
    cat.active = not bool(cat.active)
    safe_db_commit()
    flash(_('Category status updated / تم تحديث حالة القسم'), 'success')
    return redirect(url_for('menu'))
# Checkout API: create invoice + items + payment, then return receipt URL
@csrf_exempt
@app.route('/api/sales/checkout', methods=['POST'])
@login_required
def api_sales_checkout():
    # Live logic: remove debug echo and proceed to real invoice creation

    try:
        from datetime import datetime as _dt
        data = request.get_json(silent=True) or {}
        branch_code = data.get('branch_code')
        table_number = int(data.get('table_number') or 0)
        items = data.get('items') or []  # [{meal_id, qty}]
        customer_name = data.get('customer_name') or None
        customer_phone = data.get('customer_phone') or None
        discount_pct = float(data.get('discount_pct') or 0)
        tax_pct = float(data.get('tax_pct') or 15)
        preview = bool(data.get('preview'))
        # For preview (print before payment), keep DB NOT NULL satisfied but hide in receipt
        payment_method = (data.get('payment_method') or 'CASH') if not preview else ''

        # Ensure models are available locally to avoid NameError
        from models import Meal, SalesInvoice, SalesInvoiceItem


        # Log checkout start
        logging.info("checkout start: branch=%s table=%s items=%d preview=%s", branch_code, table_number, len(items or []), preview)


        if not is_valid_branch(branch_code) or not items:
            return jsonify({'ok': False, 'error': 'Invalid branch or empty items'}), 400

        # Ensure tables exist
        try:
            db.create_all()
        except Exception:
            pass

        # Generate branch/year sequential invoice number with CT/PI prefix
        _now = get_saudi_now()
        invoice_number = generate_branch_invoice_number(branch_code)

        # Calculate totals (Discount BEFORE tax) and build items
        subtotal = 0.0
        items_raw = []  # hold line_sub to distribute discount proportionally
        for it in items:
            meal = Meal.query.get(int(it.get('meal_id')))
            qty = float(it.get('qty') or 0)
            if not meal or qty <= 0:
                continue
            unit = float(meal.selling_price or 0)
            line_sub = unit * qty
            items_raw.append({
                'meal': meal,
                'meal_id': int(it.get('meal_id')),
                'name': meal.display_name,
                'qty': qty,
                'unit': unit,
                'line_sub': line_sub,
            })
            subtotal += line_sub

        # Apply discount on subtotal, then compute tax on discounted base
        discount_val = subtotal * (discount_pct / 100.0)
        tax_total = 0.0
        invoice_items = []
        for row in items_raw:
            proportion = (row['line_sub'] / subtotal) if subtotal > 0 else 0.0
            line_discount = discount_val * proportion
            discounted_sub = max(0.0, row['line_sub'] - line_discount)
            line_tax = discounted_sub * (tax_pct / 100.0)
            total_line = discounted_sub + line_tax
            tax_total += line_tax
            invoice_items.append({
                'name': row['name'],
                'qty': row['qty'],
                'price_before_tax': row['unit'],
                'discount': line_discount,
                'tax': line_tax,
                'total': total_line
            })

        grand_total = (subtotal - discount_val) + tax_total



        # Persist invoice
        inv = SalesInvoice(
            invoice_number=invoice_number,
            date=_now.date(),
            payment_method=payment_method,
            branch=branch_code,
            table_number=int(table_number),
            customer_name=customer_name,
            customer_phone=customer_phone,
            total_before_tax=subtotal,
            tax_amount=tax_total,
            discount_amount=discount_val,
            total_after_tax_discount=grand_total,
            status='unpaid',  # Will be posted as paid upon printing the receipt
            user_id=current_user.id,
            created_at=_now  # Explicitly set Saudi time
        )

        def create_checkout_operation():
            db.session.add(inv)
            db.session.flush()

            # Update table status to occupied when order is created
            from models import Table
            # table_number is stored as String in the DB model; normalize to string for queries/writes
            _tbl_no = str(table_number)
            table = Table.query.filter_by(branch_code=branch_code, table_number=_tbl_no).first()
            if not table:
                table = Table(branch_code=branch_code, table_number=_tbl_no, status='occupied')
                db.session.add(table)
            else:
                table.status = 'occupied'
                table.updated_at = _now

            return inv

        try:
            inv = safe_db_operation(create_checkout_operation, "checkout invoice creation")
            if not inv:
                return jsonify({'ok': False, 'error': 'فشل في إنشاء الفاتورة'}), 500
        except Exception as e:
            reset_db_session()
            logging.exception('checkout flush failed')
            error_message = handle_db_error(e, "إنشاء فاتورة الطاولة")
            return jsonify({'ok': False, 'error': error_message}), 500

        # Do not record payment here; posting occurs on print

        def add_items_operation():
            for it in invoice_items:
                db.session.add(SalesInvoiceItem(
                    invoice_id=inv.id,
                    product_name=str(it.get('name') or ''),
                    quantity=float(it.get('qty') or 0),
                    price_before_tax=float(it.get('price_before_tax') or 0),
                    tax=float(it.get('tax') or 0),
                    discount=float(it.get('discount') or 0),
                    total_price=float(it.get('total') or 0)
                ))
            return True

        try:
            safe_db_operation(add_items_operation, "add invoice items")
        except Exception as e:
            reset_db_session()
            logging.exception('checkout commit failed')
            error_message = handle_db_error(e, "حفظ أصناف الفاتورة")
            return jsonify({'ok': False, 'error': error_message}), 500

        # Cleanup any drafts for this table to ensure availability reflects correctly
        try:
            from models import DraftOrder
            from sqlalchemy import or_
            _tbl_int = None
            try:
                _tbl_int = int(table_number)
            except Exception:
                _tbl_int = None
            DraftOrder.query.filter(
                DraftOrder.branch_code == branch_code,
                or_(
                    DraftOrder.table_number == str(table_number),
                    *( [DraftOrder.table_no == _tbl_int] if _tbl_int is not None else [] )
                )
            ).delete(synchronize_session=False)
            safe_db_commit()

        except Exception:
            db.session.rollback()

        receipt_url = url_for('print_unpaid_invoice', invoice_id=inv.id) if preview else url_for('print_invoice', invoice_id=inv.id)
        logging.info("checkout done: invoice_id=%s total=%.2f receipt=%s", inv.id, grand_total, receipt_url)
        return jsonify({
            'ok': True,
            'invoice_id': inv.id,
            'print_url': receipt_url,
            'total_amount': float(grand_total),
            'payment_method': payment_method
        })

    except Exception as e:
        logging.exception('checkout top-level failed')
        return jsonify({'ok': False, 'error': str(e)}), 500


# Receipt (80mm thermal style)
@app.route('/sales/receipt/<int:invoice_id>')
@login_required
def sales_receipt(invoice_id):
    invoice = SalesInvoice.query.get_or_404(invoice_id)
    items = SalesInvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    settings = get_settings_safe()

    # Do NOT auto-mark as paid on print. Payment/Posting must be explicit.

    # Build ZATCA TLV QR on server to avoid client-side JS cost and CDN delay
    qr_data_url = None
    try:
        import base64, io
        import qrcode
        # Compose TLV payload: seller(1), vat(2), timestamp(3), total(4), vat amount(5)
        def _tlv(tag, b):
            return bytes([tag & 0xFF, len(b) & 0xFF]) + b
        seller = (settings.company_name or '').strip().encode('utf-8') if settings else b''
        vat = (settings.tax_number or '').strip().encode('utf-8') if settings else b''
        dt_ksa = (invoice.created_at.astimezone(KSA_TZ) if getattr(invoice, 'created_at', None) else get_saudi_now())
        ts = dt_ksa.isoformat(timespec='seconds').encode('utf-8')
        total = (f"{float(invoice.total_after_tax_discount or 0):.2f}").encode('utf-8')
        vat_amt = (f"{float(invoice.tax_amount or 0):.2f}").encode('utf-8')
        payload = base64.b64encode(_tlv(1, seller) + _tlv(2, vat) + _tlv(3, ts) + _tlv(4, total) + _tlv(5, vat_amt)).decode('ascii')
        img = qrcode.make(payload)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_data_url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        qr_data_url = None  # Fallback to client-side QR if available

    # Use unified thermal receipt template that already shows Payment method
    return render_template('print/receipt.html', inv=invoice, items=items, settings=settings, qr_data_url=qr_data_url, paid=True)
@app.route('/purchases', methods=['GET', 'POST'])
@login_required
def purchases():
    import json
    from decimal import Decimal
    from decimal import Decimal

    # Ensure required models are available locally to avoid NameError
    from models import PurchaseInvoice, PurchaseInvoiceItem

    # Get raw materials for dropdown
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    # Suppliers list for auto-complete
    try:
        from models import Supplier
        suppliers_list = Supplier.query.filter_by(active=True).order_by(Supplier.name.asc()).all()
        suppliers_json = json.dumps([
            {
                'id': s.id,
                'name': s.name,
                'phone': s.phone,
                'email': s.email,
                'address': s.address,
                'tax_number': s.tax_number,
                'contact_person': s.contact_person,
                'cr_number': getattr(s, 'cr_number', None),
                'iban': getattr(s, 'iban', None),
            } for s in suppliers_list
        ])
    except Exception:
        suppliers_list = []
        suppliers_json = '[]'
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
        valid_count = 0
        for item_form in form.items.entries:
            try:
                if item_form.raw_material_id.data and int(item_form.raw_material_id.data) != 0 and \
                   (item_form.quantity.data is not None) and (item_form.price_before_tax.data is not None):
                    valid_count += 1
            except Exception:
                continue
        if valid_count == 0:
            flash(_('Please add at least one valid item / الرجاء إضافة عنصر واحد على الأقل'), 'danger')
            return render_template('purchases.html', form=form, invoices=PurchaseInvoice.query.order_by(PurchaseInvoice.date.desc()).limit(50).all(), materials_json=materials_json, suppliers_list=suppliers_list, suppliers_json=suppliers_json)

        # Generate invoice number (format: INV-PUR-YYYY-0001)
        last_invoice = PurchaseInvoice.query.order_by(PurchaseInvoice.id.desc()).first()
        year = datetime.now(timezone.utc).year
        seq = 1
        if last_invoice and last_invoice.invoice_number:
            try:
                parts = str(last_invoice.invoice_number).split('-')
                seq = int(parts[-1]) + 1
            except Exception:
                seq = 1
        invoice_number = f'INV-PUR-{year}-{seq:04d}'

        # Calculate totals
        total_before_tax = 0
        total_tax = 0
        total_discount = 0

        # Create invoice
        invoice = PurchaseInvoice(
            invoice_number=invoice_number,
            date=form.date.data,
            supplier_name=form.supplier_name.data,
            supplier_id=int(request.form.get('supplier_id') or 0) or None,
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

        # Process items: compute per-line discount/tax and update stock quantities/costs
        total_tax = 0.0
        for idx, item_form in enumerate(form.items.entries):
            # Accept free-text item name and optional unit; resolve or create raw material
            name_typed = (request.form.get(f'items-{idx}-item_name') or '').strip()
            unit_typed = (request.form.get(f'items-{idx}-unit') or '').strip()
            if name_typed:
                qty = float(item_form.quantity.data or 0)
                unit_price = float(item_form.price_before_tax.data or 0)
                discount_pct = max(0.0, min(100.0, float(item_form.discount.data or 0)))  # clamp to 0..100
                try:
                    tax_pct = float(request.form.get(f'items-{idx}-tax_pct') or 0)
                except Exception:
                    tax_pct = 0.0
                tax_pct = max(0.0, min(100.0, tax_pct))

                from sqlalchemy import func
                # Try to resolve existing material by name
                txt = name_typed
                lower = txt.lower()
                parts = [p.strip() for p in txt.split('/') if p.strip()]
                en = (parts[0].lower() if parts else lower)
                ar = (parts[1].lower() if len(parts) > 1 else None)

                raw_material = RawMaterial.query.filter(func.lower(RawMaterial.name) == en).first()
                if not raw_material and ar:
                    raw_material = RawMaterial.query.filter(func.lower(RawMaterial.name_ar) == ar).first()
                if not raw_material:
                    raw_material = RawMaterial.query.filter(func.lower(RawMaterial.name) == lower).first()

                # Create if not found
                if not raw_material:
                    rm_name = parts[0] if parts else name_typed
                    rm_name_ar = parts[1] if len(parts) > 1 else None
                    rm_unit = unit_typed or 'unit'
                    raw_material = RawMaterial(name=rm_name, name_ar=rm_name_ar, unit=rm_unit,
                                               cost_per_unit=Decimal(str(unit_price)) if unit_price else Decimal('0'),
                                               stock_quantity=Decimal('0'))
                    db.session.add(raw_material)
                    db.session.flush()

                # compute line totals
                price_before = unit_price * qty
                discount_amt = price_before * (discount_pct / 100.0)
                if discount_amt > price_before:
                    discount_amt = price_before
                base_after_discount = max(price_before - discount_amt, 0.0)
                line_tax = base_after_discount * (tax_pct / 100.0)
                line_total = base_after_discount + line_tax

                # Aggregate invoice totals
                total_before_tax += price_before
                total_discount += discount_amt
                total_tax += line_tax

                # Update raw material stock quantity and weighted average cost (Decimal-safe)
                qty_dec = Decimal(str(qty))
                prev_qty = Decimal(str(raw_material.stock_quantity or 0))
                prev_cost = Decimal(str(raw_material.cost_per_unit or 0))
                new_total_qty = prev_qty + qty_dec
                if new_total_qty > 0:
                    new_total_cost = (prev_cost * prev_qty) + Decimal(str(unit_price)) * qty_dec
                    raw_material.cost_per_unit = (new_total_cost / new_total_qty).quantize(Decimal('0.0001'))
                    raw_material.stock_quantity = new_total_qty
                else:
                    raw_material.stock_quantity = prev_qty + qty_dec

                # Create invoice item
                display_name = f"{raw_material.name}{(' / ' + (raw_material.name_ar or '')) if raw_material.name_ar else ''}"
                inv_item = PurchaseInvoiceItem(
                    invoice_id=invoice.id,
                    raw_material_id=raw_material.id,
                    raw_material_name=display_name,
                    quantity=qty,
                    price_before_tax=unit_price,
                    tax=line_tax,
                    discount=discount_amt,
                    total_price=line_total
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

        safe_db_commit()

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

            # Always record purchases as payable at creation; payment will be registered later
            db.session.add(LedgerEntry(date=invoice.date, account_id=inv_acc.id, debit=invoice.total_before_tax, credit=0, description=f'Purchase {invoice.invoice_number}'))
            db.session.add(LedgerEntry(date=invoice.date, account_id=vat_in_acc.id, debit=invoice.tax_amount, credit=0, description=f'VAT Input {invoice.invoice_number}'))
            db.session.add(LedgerEntry(date=invoice.date, account_id=ap_acc.id, credit=invoice.total_after_tax_discount, debit=0, description=f'AP for {invoice.invoice_number}'))
            safe_db_commit()
        except Exception as e:
            db.session.rollback()
            logging.error('Ledger posting (purchase) failed: %s', e, exc_info=True)


        safe_db_commit()

        # Emit real-time update
        if socketio:
            socketio.emit('purchase_update', {
                'invoice_number': invoice_number,
                'supplier': form.supplier_name.data,
                'total': float(total_after_tax_discount)
            })

        flash(_('Purchase invoice created and stock updated successfully / تم إنشاء فاتورة الشراء وتحديث المخزون بنجاح'), 'success')
        return redirect(url_for('purchases'))

    # Set default date for new form
    if request.method == 'GET':
        form.date.data = datetime.now(timezone.utc).date()

    # Pagination for purchase invoices
    page = int(request.args.get('page') or 1)
    per_page = min(100, int(request.args.get('per_page') or 25))
    pag = PurchaseInvoice.query.order_by(PurchaseInvoice.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('purchases.html', form=form, invoices=pag.items, pagination=pag, materials_json=materials_json, suppliers_list=suppliers_list, suppliers_json=suppliers_json)

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    form = ExpenseInvoiceForm()

    if form.validate_on_submit():
        # Generate invoice number
        last_invoice = ExpenseInvoice.query.order_by(ExpenseInvoice.id.desc()).first()
        if last_invoice and last_invoice.invoice_number and '-' in last_invoice.invoice_number:
            try:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                invoice_number = f'EXP-{datetime.now(timezone.utc).year}-{last_num + 1:03d}'
            except Exception:
                invoice_number = f'EXP-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'
        else:
            invoice_number = f'EXP-{datetime.now(timezone.utc).year}-001'

        # Calculate totals
        total_before_tax = 0
        total_tax = 0
        total_discount = 0

        # Create invoice
        invoice = ExpenseInvoice(
            invoice_number=invoice_number,
            date=form.date.data,
            payment_method=form.payment_method.data,
            status='unpaid',  # Will remain unpaid until user registers a payment
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
            # Note: 'description' conflicts with WTForms Field.description (a string); use the nested form explicitly
            if item_form.form.description.data:  # Only process items with description
                qty = float(item_form.quantity.data)
                price = float(item_form.price_before_tax.data)
                tax = float(item_form.tax.data or 0)
                discount_pct = float(item_form.discount.data or 0)

                # Calculate amounts
                item_before_tax = price * qty
                discount = (item_before_tax + tax) * (discount_pct/100.0)
                total_item = item_before_tax + tax - discount

                # Create expense item
                expense_item = ExpenseInvoiceItem(
                    invoice_id=invoice.id,
                    description=item_form.form.description.data,
                    quantity=qty,
                    price_before_tax=price,
                    tax=tax,
                    discount=discount,
                    total_price=total_item
                )
                db.session.add(expense_item)

                # Update totals
                total_before_tax += item_before_tax
                total_tax += tax
                total_discount += discount

        # Update invoice totals
        invoice.total_before_tax = total_before_tax
        invoice.tax_amount = total_tax
        invoice.discount_amount = total_discount
        invoice.total_after_tax_discount = total_before_tax + total_tax - total_discount

        # Do not create payment automatically; will remain unpaid until user registers a payment

        if safe_db_commit("expense invoice creation"):
            flash(_('Expense invoice created successfully / تم إنشاء فاتورة المصروفات بنجاح'), 'success')
            return redirect(url_for('expenses'))
        else:
            flash(_('Error creating expense invoice / خطأ في إنشاء فاتورة المصروفات'), 'danger')

    # GET request - show form and existing invoices
    page = request.args.get('page', 1, type=int)
    per_page = 20
    pag = ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('expenses.html', form=form, invoices=pag.items, pagination=pag)


@app.route('/expenses/<int:invoice_id>/view')
@login_required
def view_expense_invoice(invoice_id):
    """View expense invoice details"""
    from models import ExpenseInvoice, ExpenseInvoiceItem
    
    invoice = ExpenseInvoice.query.get_or_404(invoice_id)
    items = ExpenseInvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    
    return render_template('expenses_view.html', invoice=invoice, items=items)

@app.route('/expenses/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense_invoice(invoice_id):
    """Edit expense invoice"""
    from models import ExpenseInvoice, ExpenseInvoiceItem
    from forms import ExpenseInvoiceForm
    
    invoice = ExpenseInvoice.query.get_or_404(invoice_id)
    
    if request.method == 'POST':
        try:
            # Update invoice basic info
            invoice.date = request.form.get('date', invoice.date)
            invoice.payment_method = request.form.get('payment_method', invoice.payment_method)
            invoice.status = request.form.get('status', invoice.status)
            
            # Recalculate totals if items were updated
            # For now, just update the basic info
            # TODO: Add full item editing functionality
            
            if safe_db_commit("expense invoice update"):
                flash(_('Expense invoice updated successfully / تم تحديث فاتورة المصروفات بنجاح'), 'success')
                return redirect(url_for('expenses'))
            else:
                flash(_('Error updating expense invoice / خطأ في تحديث فاتورة المصروفات'), 'danger')
                
        except Exception as e:
            db.session.rollback()
            flash(_('Error updating expense invoice / خطأ في تحديث فاتورة المصروفات') + f': {str(e)}', 'danger')
    
    # GET request - show edit form
    items = ExpenseInvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    return render_template('expenses_edit.html', invoice=invoice, items=items)

@app.route('/delete_expense_invoice/<int:invoice_id>', methods=['POST'])
@login_required
def delete_expense_invoice(invoice_id):
    """Delete expense invoice"""
    from models import ExpenseInvoice, ExpenseInvoiceItem
    
    try:
        invoice = ExpenseInvoice.query.get_or_404(invoice_id)
        
        # Delete associated items first
        ExpenseInvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
        
        # Delete the invoice
        db.session.delete(invoice)
        
        if safe_db_commit("expense invoice deletion"):
            flash(_('Expense invoice deleted successfully / تم حذف فاتورة المصروفات بنجاح'), 'success')
        else:
            flash(_('Error deleting expense invoice / خطأ في حذف فاتورة المصروفات'), 'danger')
            
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting expense invoice / خطأ في حذف فاتورة المصروفات') + f': {str(e)}', 'danger')
    
    return redirect(url_for('expenses'))
@app.route('/import_meals', methods=['POST'])
@login_required
def import_meals():
    try:
        if 'file' not in request.files:
            flash(_('No file selected / لم يتم اختيار ملف'), 'danger')
            return redirect(url_for('meals'))

        file = request.files['file']
        if file.filename == '':
            flash(_('No file selected / لم يتم اختيار ملف'), 'danger')
            return redirect(url_for('meals'))

        if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
            flash(_('Invalid file format / صيغة ملف غير صالحة'), 'danger')
            return redirect(url_for('meals'))

        # Read file using pandas
        try:
            import pandas as pd
            print(f"DEBUG: pandas version: {pd.__version__}")  # Debug info
            if file.filename.lower().endswith('.csv'):
                df = pd.read_csv(file)
            else:
                # For Excel files, we need openpyxl
                df = pd.read_excel(file, engine='openpyxl')
        except ImportError as e:
            print(f"DEBUG: ImportError details: {e}")  # Debug info
            if 'pandas' in str(e):
                flash(_('pandas library not installed / مكتبة pandas غير مثبتة'), 'danger')
            elif 'openpyxl' in str(e):
                flash(_('openpyxl library required for Excel files / مكتبة openpyxl مطلوبة لملفات Excel'), 'danger')
            else:
                flash(_('Required library not installed: %(error)s / مكتبة مطلوبة غير مثبتة: %(error)s', error=str(e)), 'danger')
            return redirect(url_for('meals'))
        except Exception as e:
            print(f"DEBUG: General error: {e}")  # Debug info
            flash(_('Error reading file / خطأ في قراءة الملف: %(error)s', error=str(e)), 'danger')
            return redirect(url_for('meals'))

        # Normalize column names (case-insensitive matching)
        df.columns = df.columns.str.strip()  # Remove extra spaces
        col_mapping = {}

        # Map actual columns to expected columns (case-insensitive)
        for col in df.columns:
            col_lower = col.lower()
            if col_lower == 'name':
                col_mapping['Name'] = col
            elif col_lower in ['name (arabic)', 'name(arabic)', 'arabic name', 'arabic_name']:
                col_mapping['Name (Arabic)'] = col
            elif col_lower == 'category':
                col_mapping['Category'] = col
            elif col_lower == 'cost':
                col_mapping['Cost'] = col
            elif col_lower in ['selling price', 'selling_price', 'price']:
                col_mapping['Selling Price'] = col

        # Check if we have the required columns
        required_cols = ['Name', 'Cost', 'Selling Price']  # Arabic name and category are optional
        missing_cols = [col for col in required_cols if col not in col_mapping]

        if missing_cols:
            flash(_('Missing required columns: %(cols)s / أعمدة مطلوبة مفقودة: %(cols)s. Available columns: %(available)s',
                   cols=', '.join(missing_cols), available=', '.join(df.columns)), 'danger')
            return redirect(url_for('meals'))

        # Import meals
        imported_count = 0
        from models import Meal

        for idx, row in df.iterrows():
            try:
                name = str(row[col_mapping['Name']]).strip()
                name_ar = str(row[col_mapping.get('Name (Arabic)', '')]).strip() if col_mapping.get('Name (Arabic)') and pd.notna(row[col_mapping.get('Name (Arabic)', '')]) else ''
                category = str(row[col_mapping.get('Category', '')]).strip() if col_mapping.get('Category') and pd.notna(row[col_mapping.get('Category', '')]) else 'General'
                cost = float(row[col_mapping['Cost']]) if pd.notna(row[col_mapping['Cost']]) else 0.0
                selling_price = float(row[col_mapping['Selling Price']]) if pd.notna(row[col_mapping['Selling Price']]) else 0.0

                if not name or name.lower() in ['nan', 'none', '']:
                    continue

                # Check if meal already exists
                existing = Meal.query.filter_by(name=name).first()
                if existing:
                    continue  # Skip duplicates

                meal = Meal(
                    name=name,
                    name_ar=name_ar,
                    category=category,
                    total_cost=cost,  # Fixed: use total_cost instead of cost
                    selling_price=selling_price,
                    profit_margin_percent=((selling_price - cost) / cost * 100) if cost > 0 else 0,
                    user_id=current_user.id  # Required field
                )
                db.session.add(meal)
                imported_count += 1

            except Exception as e:
                logging.warning(f'Error importing meal row {idx}: {e}')
                continue

        commit_success = safe_db_commit("meal import")
        if commit_success:
            flash(_('Successfully imported %(count)s meals / تم استيراد %(count)s وجبة بنجاح', count=imported_count), 'success')
        else:
            flash(_('Failed to save meals to database / فشل حفظ الوجبات في قاعدة البيانات'), 'danger')

    except Exception as e:
        db.session.rollback()
        logging.exception('Import meals failed')
        flash(_('Import failed / فشل الاستيراد: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('meals'))

# API: Cancel draft order
@csrf_exempt
@app.route('/api/draft_orders/<int:draft_id>/cancel', methods=['POST'])
@login_required
def cancel_draft_order(draft_id):
    try:
        from models import DraftOrder, DraftOrderItem, Table

        draft = DraftOrder.query.get_or_404(draft_id)

        # Require supervisor password for cancellation (same as invoice void password)
        try:
            payload = request.get_json(silent=True) or {}
            pwd = (payload.get('supervisor_password') or '').strip()
            # Fixed password for cancellation: 1991 (same as invoice void)
            expected = '1991'
            if pwd != expected:
                return jsonify({'success': False, 'error': _('Incorrect password / كلمة السر غير صحيحة')}), 400
        except Exception:
            return jsonify({'success': False, 'error': _('Password check failed / فشل التحقق من كلمة السر')}), 400

        # Permission: password is sufficient for cancellation (supervisor override)
        # We allow any logged-in user to cancel if supervisor_password is correct.

        branch_code = draft.branch_code
        # Safe handling of table_number
        table_number = safe_table_number(draft.table_number)

        # Delete ALL draft orders for this table (not just this ID) and their items safely
        table_no_str = str(table_number)
        try:
            tbl_int = int(table_number)
        except Exception:
            tbl_int = None
        from sqlalchemy import or_
        drafts_same_table = DraftOrder.query.filter(
            DraftOrder.branch_code == branch_code,
            DraftOrder.status == 'draft',
            or_(
                DraftOrder.table_number == table_no_str,
                *([DraftOrder.table_no == tbl_int] if tbl_int is not None else [])
            )
        ).all()
        for d in drafts_same_table:
            try:
                DraftOrderItem.query.filter_by(draft_order_id=d.id).delete(synchronize_session=False)
            except Exception:
                pass
            db.session.delete(d)
        # Update table status to available
        table = Table.query.filter_by(branch_code=branch_code, table_number=table_no_str).first()
        if table:
            table.status = 'available'
            table.updated_at = get_saudi_now()

        safe_db_commit()
        # Also clear in-memory open marker so tables page reflects availability immediately
        try:
            OPEN_INVOICES_MEM.pop(f"{branch_code}:{table_number}", None)
            OPEN_INVOICES_MEM.pop(f"{branch_code}:{str(table_number)}", None)
        except Exception:
            pass
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        logging.exception('Cancel draft order failed')
        return jsonify({'success': False, 'error': str(e)}), 500

from app import create_app
app = create_app()

# NOTE: Do not run the development server from within this module to avoid
# spawning multiple processes and lingering servers. Use dedicated launchers
# like `run.py` or `run_app.py` instead.
def add_item_to_draft(draft_id):
    try:
        from models import DraftOrder, DraftOrderItem, Meal, Table

        draft = DraftOrder.query.get_or_404(draft_id)
        data = request.get_json() or {}

        meal_id = data.get('meal_id')
        quantity = float(data.get('quantity', 1))

        if not meal_id or quantity <= 0:
            return jsonify({'success': False, 'error': 'Invalid meal or quantity'}), 400

        meal = Meal.query.get_or_404(meal_id)

        # Calculate pricing
        settings = get_settings_safe()
        vat_rate = float(settings.vat_rate) if settings and settings.vat_rate else 15.0

        price_before_tax = float(meal.selling_price or 0)
        line_subtotal = price_before_tax * quantity
        line_tax = line_subtotal * (vat_rate / 100.0)
        total_price = line_subtotal + line_tax

        # Add item to draft
        draft_item = DraftOrderItem(
            draft_order_id=draft.id,
            meal_id=meal.id,
            product_name=meal.display_name,
            quantity=quantity,
            price_before_tax=price_before_tax,
            tax=line_tax,
            total_price=total_price
        )
        db.session.add(draft_item)

        # Update table status to reserved if this is the first item
        if len(draft.items) == 0:  # First item being added
            table_num_int = safe_table_number(draft.table_number)
            table = Table.query.filter_by(branch_code=draft.branch_code, table_number=table_num_int).first()
            if not table:
                table = Table(branch_code=draft.branch_code, table_number=table_num_int, status='occupied')
                db.session.add(table)
            else:
                table.status = 'occupied'
                table.updated_at = get_saudi_now()

        safe_db_commit()
        return jsonify({'success': True, 'item_id': draft_item.id})

    except Exception as e:
        db.session.rollback()
        logging.exception('Add item to draft failed')
        return jsonify({'success': False, 'error': str(e)}), 500
# API: Update draft order with all items
@app.route('/api/draft_orders/<int:draft_id>/update', methods=['POST'])
@login_required
def update_draft_order(draft_id):
    try:
        from models import DraftOrder, DraftOrderItem, Meal, Table

        draft = DraftOrder.query.get_or_404(draft_id)
        data = request.get_json() or {}

        # Get items from request
        items_data = data.get('items', [])
        customer_name = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        payment_method = data.get('payment_method', 'CASH')

        # Update draft order info
        if customer_name:
            draft.customer_name = customer_name
        if customer_phone:
            draft.customer_phone = customer_phone
        draft.payment_method = payment_method

        # Security: require supervisor_password when removing any existing items
        existing_ids = {it.meal_id for it in draft.items}
        new_ids = {int(x.get('meal_id')) for x in (items_data or []) if x.get('meal_id')}
        removed_ids = existing_ids - new_ids
        if removed_ids:
            pwd = (data.get('supervisor_password') or '').strip()
            if pwd != '1991':
                return jsonify({'success': False, 'error': _('Supervisor password required to remove items / كلمة مرور المشرف مطلوبة لحذف العناصر')}), 403

        # Clear existing items
        DraftOrderItem.query.filter_by(draft_order_id=draft.id).delete()

        # Add new items
        settings = get_settings_safe()
        vat_rate = float(settings.vat_rate) if settings and settings.vat_rate else 15.0

        for item_data in items_data:
            meal_id = item_data.get('meal_id')
            quantity = float(item_data.get('qty', 1))

            if not meal_id or quantity <= 0:
                continue

            meal = Meal.query.get(meal_id)
            if not meal:
                continue

            # Calculate pricing
            price_before_tax = float(meal.selling_price or 0)
            line_subtotal = price_before_tax * quantity
            line_tax = line_subtotal * (vat_rate / 100.0)
            total_price = line_subtotal + line_tax

            # Create draft item
            draft_item = DraftOrderItem(
                draft_order_id=draft.id,
                meal_id=meal.id,
                product_name=meal.display_name,
                quantity=quantity,
                price_before_tax=price_before_tax,
                tax=line_tax,
                total_price=total_price
            )
            db.session.add(draft_item)

        # Update table status to reserved if items exist
        if items_data:
            table_num_int = safe_table_number(draft.table_number)
            table = Table.query.filter_by(branch_code=draft.branch_code, table_number=table_num_int).first()
            if not table:
                table = Table(branch_code=draft.branch_code, table_number=table_num_int, status='occupied')
                db.session.add(table)
            else:
                table.status = 'occupied'
                table.updated_at = get_saudi_now()

        safe_db_commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        logging.exception('Update draft order failed')
        return jsonify({'success': False, 'error': str(e)}), 500

# Checkout draft order (convert to final invoice)
@app.route('/sales/<branch_code>/draft/<int:draft_id>/checkout', methods=['GET', 'POST'])
@login_required
def checkout_draft_order(branch_code, draft_id):
    from models import DraftOrder, SalesInvoice, SalesInvoiceItem, Payment, Table

    draft = DraftOrder.query.get_or_404(draft_id)

# API: Direct draft checkout (no additional screens)
@csrf_exempt
@app.route('/api/draft/checkout', methods=['POST'])
@login_required
def api_draft_checkout():
    try:
        from models import DraftOrder, SalesInvoice, SalesInvoiceItem, Payment, Table

        data = request.get_json() or {}
        current_app.logger.debug('api_draft_checkout payload: %s', data)

        # Debug logging
        print(f"DEBUG: api_draft_checkout called with data: {data}")

        draft_id = data.get('draft_id')

        if not draft_id:
            print(f"DEBUG: No draft_id provided in data: {data}")
            return jsonify({'ok': False, 'error': 'Draft ID required'}), 400

        draft = DraftOrder.query.get_or_404(draft_id)

        # Debug logging
        print(f"DEBUG: Draft order {draft_id} status: '{draft.status}', items count: {len(draft.items)}")

        if draft.status != 'draft':
            print(f"DEBUG: Invalid draft status - expected 'draft', got '{draft.status}'")
            return jsonify({'ok': False, 'error': f'Invalid draft order status: {draft.status}'}), 400

        # Get form data
        customer_name = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        payment_method = data.get('payment_method', 'CASH')
        discount_pct = float(data.get('discount_pct') or 0)



        # Calculate totals
        subtotal = sum(float(item.price_before_tax * item.quantity) for item in draft.items)
        tax_total = sum(float(item.tax) for item in draft.items)

        # Calculate discount and grand total
        discount_val = (subtotal + tax_total) * (discount_pct / 100.0)
        grand_total = (subtotal + tax_total) - discount_val



        # Generate branch/year sequential invoice number with CT/PI prefix
        _now = get_saudi_now()
        invoice_number = generate_branch_invoice_number(draft.branch_code)

        # Create final invoice
        invoice = SalesInvoice(
            invoice_number=invoice_number,
            date=_now.date(),
            payment_method=payment_method,
            branch=draft.branch_code,
            table_number=draft.table_number,
            customer_name=customer_name or None,
            customer_phone=customer_phone or None,
            total_before_tax=subtotal,
            tax_amount=tax_total,
            discount_amount=discount_val,  # Fixed: use calculated discount
            total_after_tax_discount=grand_total,
            status='unpaid',
            user_id=current_user.id,
            created_at=_now  # Explicitly set Saudi time
        )
        db.session.add(invoice)
        db.session.flush()



        # Copy items from draft to invoice
        for draft_item in draft.items:
            invoice_item = SalesInvoiceItem(
                invoice_id=invoice.id,

                product_name=draft_item.product_name,
                quantity=draft_item.quantity,
                price_before_tax=draft_item.price_before_tax,
                tax=draft_item.tax,
                discount=draft_item.discount,
                total_price=draft_item.total_price
            )
            db.session.add(invoice_item)


        # Mark draft as completed
        draft.status = 'completed'

        # Update table status
        remaining_drafts = DraftOrder.query.filter_by(
            branch_code=draft.branch_code,
            table_number=str(draft.table_number),
            status='draft'
        ).count()

        table_num_int = safe_table_number(draft.table_number)
        table = Table.query.filter_by(branch_code=draft.branch_code, table_number=table_num_int).first()
        if table:
            if remaining_drafts <= 1:  # This draft will be completed
                table.status = 'available'
            else:
                table.status = 'reserved'  # Still has other drafts
            table.updated_at = _now

        safe_db_commit()

        # Return success with print URL
        print_url = url_for('sales_receipt', invoice_id=invoice.id)
        return jsonify({
            'ok': True,
            'status': 'success',
            'invoice_id': invoice.id,
            'print_url': print_url,
            'total_amount': float(grand_total),
            'payment_method': payment_method
        })

    except Exception as e:
        db.session.rollback()
        logging.exception('API draft checkout failed')
        return jsonify({'ok': False, 'error': str(e)}), 500


# API: Confirm print completion and register payment
@app.route('/api/invoice/confirm-print', methods=['POST'])
@login_required
def confirm_print_and_pay():
    """Confirm that invoice was printed and register payment"""
    try:

        data = request.get_json() or {}
        invoice_id = data.get('invoice_id')
        payment_method = data.get('payment_method', 'CASH')
        total_amount = float(data.get('total_amount', 0))
        logging.info("confirm-print start: invoice_id=%s method=%s amount=%.2f", invoice_id, payment_method, total_amount)

        if not invoice_id or not total_amount:
            return jsonify({'ok': False, 'error': 'Missing invoice_id or total_amount'}), 400

        # Get the invoice
        from models import SalesInvoice, Payment
        invoice = SalesInvoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'ok': False, 'error': 'Invoice not found'}), 404

        # Check if already paid; if so, still run cleanup below
        already_paid = (invoice.status == 'paid')
        if not already_paid:
            # Create payment record (align with Payment model fields)
            payment = Payment(
                invoice_type='sales',
                invoice_id=invoice_id,
                amount_paid=total_amount,
                payment_method=payment_method,
                payment_date=get_saudi_now()
            )
            db.session.add(payment)

            # Update invoice status to paid
            invoice.status = 'paid'

            db.session.commit()
        else:
            logging.info("confirm-print: invoice already paid, proceeding with table cleanup anyway")

        # After successful payment: mark table available, clear drafts and in-memory flags
        try:
            from models import Table, DraftOrder
            branch_code = (invoice.branch or '').lower()
            table_no_str = str(getattr(invoice, 'table_number', '') or '')
            if table_no_str:
                # Normalize branch naming similar to other cleanup paths
                canonical_branch = 'place_india' if any(k in branch_code for k in ('place_india','palace_india','india','palace','pi','2')) else 'china_town'

                # Update table status to available (robust branch + int/string table match)
                from sqlalchemy import or_
                branch_l = (branch_code or '').replace(' ', '_')
                branch_opts = {canonical_branch, branch_l}
                if 'india' in branch_l:
                    branch_opts |= {'place_india', 'palace_india'}
                elif 'china' in branch_l:
                    branch_opts |= {'china_town'}
                try:
                    tbl_int = int(table_no_str)
                except Exception:
                    tbl_int = None
                tables = Table.query.filter(
                    Table.branch_code.in_(list(branch_opts)),
                    or_(
                        Table.table_number == str(table_no_str),
                        *( [Table.table_number == tbl_int] if tbl_int is not None else [] )
                    )
                ).all()
                if tables:
                    for t in tables:
                        t.status = 'available'
                        t.updated_at = get_saudi_now()
                else:
                    # Create table record as available if it doesn't exist
                    t = Table(branch_code=canonical_branch, table_number=str(table_no_str), status='available')
                    db.session.add(t)

                # Delete any remaining draft orders for this table (handle int/str mismatch and legacy table_no)
                try:
                    from sqlalchemy import or_, and_
                    tbl_int = None
                    try:
                        tbl_int = int(table_no_str)
                    except Exception:
                        tbl_int = None
                    # Be liberal in branch matching to cover legacy values
                    branch_opts = {canonical_branch}
                    try:
                        if branch_code:
                            branch_opts |= {branch_code, branch_code.lower(), branch_code.replace(' ', '_')}
                    except Exception:
                        pass
                    q = DraftOrder.query.filter(
                        DraftOrder.branch_code.in_(list(branch_opts)),

                        or_(
                            DraftOrder.table_number == str(table_no_str),
                            *( [DraftOrder.table_no == tbl_int] if tbl_int is not None else [] )
                        )
                    )
                    drafts = q.all()
                    # Try to delete items first if FK constraints exist
                    logging.info("confirm-print cleanup: drafts_to_delete=%d branch=%s table=%s", len(drafts), canonical_branch, table_no_str)

                    try:
                        from models import DraftOrderItem
                        for d in drafts:
                            DraftOrderItem.query.filter_by(draft_order_id=d.id).delete(synchronize_session=False)
                    except Exception:
                        pass
                    for d in drafts:
                        db.session.delete(d)
                except Exception:
                    pass

                # Clear in-memory open markers
                try:
                    for b in {canonical_branch, branch_code.replace(' ', '_'), 'palace_india', 'place_india'}:
                        OPEN_INVOICES_MEM.pop(f"{b}:{table_no_str}", None)
                        # Also try int format
                        try:
                            OPEN_INVOICES_MEM.pop(f"{b}:{int(table_no_str)}", None)
                        except Exception:
                            pass
                except Exception:
                    pass

                safe_db_commit()
        except Exception:
            # Do not fail the API because of cleanup
            db.session.rollback()

        logging.info("confirm-print done: invoice_id=%s -> paid; table cleanup attempted", invoice_id)

        return jsonify({'ok': True, 'message': 'Payment registered successfully'})

    except Exception as e:
        db.session.rollback()
        logging.exception('confirm_print_and_pay failed')
        return jsonify({'ok': False, 'error': str(e)}), 500
@app.route('/admin/fix_database', methods=['GET'])
@login_required
def fix_database_route():
    """Comprehensive database fix route"""
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    try:
        from sqlalchemy import text

        results = []

        # 1. Add table_number column to sales_invoices if missing
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'sales_invoices'
                    AND column_name = 'table_number'
                """))

                if not result.fetchone():
                    conn.execute(text("ALTER TABLE sales_invoices ADD COLUMN table_number INTEGER"))
                    conn.commit()
                    results.append("✅ Added table_number column to sales_invoices")
                else:
                    results.append("✅ table_number column already exists")
        except Exception as e:
            results.append(f"⚠️ Error with table_number: {e}")

        # 2. Create tables table if missing
        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS tables (
                        id SERIAL PRIMARY KEY,
                        branch_code VARCHAR(20) NOT NULL,
                        table_number INTEGER NOT NULL,
                        status VARCHAR(20) DEFAULT 'available',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(branch_code, table_number)
                    )
                """))
                conn.commit()
            results.append("✅ tables table created/verified")
        except Exception as e:
            results.append(f"⚠️ Error with tables table: {e}")

        # 3. Fix Settings table columns
        try:
            with db.engine.connect() as conn:
                missing_columns = [
                    ("china_town_void_password", "VARCHAR(50) DEFAULT '1991'"),
                    ("place_india_void_password", "VARCHAR(50) DEFAULT '1991'"),
                    ("china_town_vat_rate", "FLOAT DEFAULT 15.0"),
                    ("place_india_vat_rate", "FLOAT DEFAULT 15.0"),
                    ("china_town_discount_rate", "FLOAT DEFAULT 0.0"),
                    ("place_india_discount_rate", "FLOAT DEFAULT 0.0"),
                    ("receipt_paper_width", "VARCHAR(10) DEFAULT '80'"),
                    ("receipt_font_size", "INTEGER DEFAULT 12"),
                    ("receipt_logo_height", "INTEGER DEFAULT 72"),
                    ("receipt_extra_bottom_mm", "INTEGER DEFAULT 15"),
                    ("receipt_show_tax_number", "BOOLEAN DEFAULT TRUE"),
                    ("receipt_footer_text", "TEXT DEFAULT 'شكراً لزيارتكم'"),
                    ("china_town_phone1", "VARCHAR(50)"),
                    ("china_town_phone2", "VARCHAR(50)"),
                    ("place_india_phone1", "VARCHAR(50)"),
                    ("place_india_phone2", "VARCHAR(50)"),
                    ("china_town_logo_url", "VARCHAR(300)"),
                    ("place_india_logo_url", "VARCHAR(300)")
                ]

                for col_name, col_def in missing_columns:
                    try:
                        # Check if column exists
                        result = conn.execute(text(f"""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_name = 'settings'
                            AND column_name = '{col_name}'
                        """))

                        if not result.fetchone():
                            conn.execute(text(f"ALTER TABLE settings ADD COLUMN {col_name} {col_def}"))
                            conn.commit()
                            results.append(f"✅ Added {col_name} to settings")
                        else:
                            results.append(f"✅ {col_name} already exists")
                    except Exception as e:
                        results.append(f"⚠️ Error with {col_name}: {e}")

        except Exception as e:
            results.append(f"⚠️ Error fixing settings table: {e}")

        # 4. Create draft_orders table if missing


        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS draft_orders (
                        id SERIAL PRIMARY KEY,
                        branch_code VARCHAR(20) NOT NULL,
                        table_number INTEGER NOT NULL,
                        customer_name VARCHAR(100),
                        customer_phone VARCHAR(30),
                        payment_method VARCHAR(20) DEFAULT 'CASH',
                        status VARCHAR(20) DEFAULT 'draft',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id INTEGER NOT NULL
                    )
                """))
                conn.commit()
            results.append("✅ draft_orders table created/verified")
        except Exception as e:
            results.append(f"⚠️ Error with draft_orders table: {e}")

        # 4. Create draft_order_items table if missing
        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS draft_order_items (
                        id SERIAL PRIMARY KEY,
                        draft_order_id INTEGER NOT NULL,
                        meal_id INTEGER,
                        product_name VARCHAR(200) NOT NULL,
                        quantity NUMERIC(10,2) NOT NULL,
                        price_before_tax NUMERIC(12,2) NOT NULL,
                        tax NUMERIC(12,2) NOT NULL DEFAULT 0,
                        discount NUMERIC(12,2) NOT NULL DEFAULT 0,
                        total_price NUMERIC(12,2) NOT NULL
                    )
                """))
                conn.commit()
            results.append("✅ draft_order_items table created/verified")
        except Exception as e:
            results.append(f"⚠️ Error with draft_order_items table: {e}")

        # 5. Add foreign key constraints if they don't exist
        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.table_constraints
                            WHERE constraint_name = 'draft_order_items_draft_order_id_fkey'
                        ) THEN
                            ALTER TABLE draft_order_items
                            ADD CONSTRAINT draft_order_items_draft_order_id_fkey
                            FOREIGN KEY (draft_order_id) REFERENCES draft_orders(id) ON DELETE CASCADE;
                        END IF;
                    END $$;
                """))
                conn.commit()
            results.append("✅ Foreign key constraints added/verified")
        except Exception as e:
            results.append(f"⚠️ Error with foreign keys: {e}")

        return jsonify({
            'ok': True,
            'status': 'Database fix completed successfully',
            'results': results
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
@app.route('/admin/seed_branch_users', methods=['GET'])
@login_required
def admin_seed_branch_users():
    """Create or update branch-scoped sales users and permissions.
    Admin-only. Idempotent and safe to re-run.
    Users:
      - place_india / place02563 -> sales perms for branch_scope='place_india'
      - china_town / china02554 -> sales perms for branch_scope='china_town'
    """
    try:
        if getattr(current_user, 'role', '') != 'admin':
            return jsonify({'ok': False, 'error': 'Admin access required'}), 403

        from models import User, UserPermission
        created, updated = [], []

        def ensure_user(username: str, password: str):
            u = User.query.filter_by(username=username).first()
            if u:
                if password:
                    u.set_password(password, bcrypt)
                    updated.append(username)
            else:
                u = User(username=username, role='user', active=True)
                u.set_password(password, bcrypt)
                db.session.add(u)
                created.append(username)
            db.session.flush()
            return u

        place_user = ensure_user('place_india', 'place02563')
        china_user = ensure_user('china_town', 'china02554')

        def grant_sales(u, scope: str):
            # remove existing sales permissions for any scope to avoid duplicates
            UserPermission.query.filter_by(user_id=u.id, screen_key='sales').delete(synchronize_session=False)
            p = UserPermission(user_id=u.id, screen_key='sales', branch_scope=scope,
                               can_view=True, can_add=True, can_edit=False, can_delete=False, can_print=True)
            db.session.add(p)

        grant_sales(place_user, 'place_india')
        grant_sales(china_user, 'china_town')

        db.session.commit()
        return jsonify({'ok': True, 'created': created, 'updated': updated,
                        'credentials': {
                            'place_india': {'username': 'place_india', 'password': 'place02563'},
                            'china_town': {'username': 'china_town', 'password': 'china02554'}
                        }})
    except Exception as e:
        db.session.rollback()
        logging.exception('admin_seed_branch_users failed')
        return jsonify({'ok': False, 'error': str(e)}), 500
def invoices():
    try:
        from sqlalchemy import func, text
        from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice, Payment
        # Normalize type
        raw_type = (request.args.get('type') or 'all').lower()
        if raw_type in ['purchases','purchase']: tfilter = 'purchase'
        elif raw_type in ['expenses','expense']: tfilter = 'expense'
        elif raw_type in ['sales','sale']: tfilter = 'sales'
        else: tfilter = 'all'

        # Build invoices and compute paid amounts from Payments, recompute status
        rows = []
        def paid_map_for(kind, ids):
            if not ids:
                return {}
            mm = db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)) \
                .filter(Payment.invoice_type == kind, Payment.invoice_id.in_(ids)) \
                .group_by(Payment.invoice_id).all()
            return {pid: float(total or 0) for (pid, total) in mm}
        def status_from(total, paid):
            try:
                if paid >= total: return 'paid'
                if paid > 0: return 'partial'
                return 'unpaid'
            except Exception:
                return 'unpaid'

        # Sales invoices
        if tfilter in ['all', 'sales']:
            try:
                sales_list = SalesInvoice.query.order_by(SalesInvoice.date.desc()).all()
                sales_paid = paid_map_for('sales', [s.id for s in sales_list])
                for inv in sales_list:
                    total = float(inv.total_after_tax_discount or 0)
                    # Per business rule: all sales invoices are treated as fully paid
                    paid = total
                    remaining = 0.0
                    rows.append({
                        'id': inv.id,
                        'invoice_number': inv.invoice_number,
                        'invoice_type': 'sales',
                        'customer_supplier': inv.customer_name or 'Customer',
                        'total_amount': total,
                        'paid_amount': paid,
                        'remaining_amount': remaining,
                        'status': 'paid',
                        'due_date': inv.date
                    })
            except Exception as e:
                logging.warning(f'Error loading sales invoices: {e}')

        # Purchase invoices
        if tfilter in ['all', 'purchase']:
            try:
                purchase_list = PurchaseInvoice.query.order_by(PurchaseInvoice.date.desc()).all()
                purchase_paid = paid_map_for('purchase', [p.id for p in purchase_list])
                for inv in purchase_list:
                    total = float(getattr(inv, 'total_after_tax_discount', 0) or 0)
                    paid = purchase_paid.get(inv.id, 0.0)
                    remaining = max(total - paid, 0.0)
                    rows.append({
                        'id': inv.id,
                        'invoice_number': getattr(inv, 'invoice_number', inv.id),
                        'invoice_type': 'purchase',
                        'customer_supplier': getattr(inv, 'supplier_name', 'Supplier'),
                        'total_amount': total,
                        'paid_amount': paid,
                        'remaining_amount': remaining,
                        'status': status_from(total, paid),
                        'due_date': inv.date
                    })
            except Exception as e:
                logging.warning(f'Error loading purchase invoices: {e}')

        # Expense invoices
        if tfilter in ['all', 'expense']:
            try:
                expense_list = ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).all()
                expense_paid = paid_map_for('expense', [x.id for x in expense_list])
                for inv in expense_list:
                    total = float(getattr(inv, 'total_after_tax_discount', 0) or 0)
                    paid = expense_paid.get(inv.id, 0.0)
                    remaining = max(total - paid, 0.0)
                    rows.append({
                        'id': inv.id,
                        'invoice_number': getattr(inv, 'invoice_number', inv.id),
                        'invoice_type': 'expense',
                        'customer_supplier': 'Expense',
                        'total_amount': total,
                        'paid_amount': paid,
                        'remaining_amount': remaining,
                        'status': status_from(total, paid),
                        'due_date': inv.date
                    })
            except Exception as e:
                logging.warning(f'Error loading expense invoices: {e}')

        # Sort by date descending
        rows.sort(key=lambda x: x['due_date'] if x['due_date'] else datetime.min.date(), reverse=True)

        current_type = tfilter
        return render_template('invoices.html', invoices=rows, current_type=current_type)

    except Exception as e:
        logging.exception('Error in invoices route')
        flash(_('Error loading invoices / خطأ في تحميل الفواتير'), 'danger')
        return redirect(url_for('dashboard'))

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


@app.route('/invoices/delete', methods=['POST'])
@login_required
def invoices_delete():
    # Admin-only for safety; can be relaxed later per-type permissions
    if getattr(current_user, 'role', '') != 'admin':
        flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
        return redirect(url_for('invoices', type=request.args.get('type') or 'all'))
    from models import SalesInvoice, SalesInvoiceItem, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Payment
    scope = (request.form.get('scope') or '').lower()
    inv_type = (request.form.get('invoice_type') or '').lower()
    ids = request.form.getlist('invoice_ids') or []
    deleted = 0
    try:
        def delete_sales(ids_list):
            nonlocal deleted
            if ids_list:
                SalesInvoiceItem.query.filter(SalesInvoiceItem.invoice_id.in_(ids_list)).delete(synchronize_session=False)
                Payment.query.filter(Payment.invoice_type=='sales', Payment.invoice_id.in_(ids_list)).delete(synchronize_session=False)
                deleted += SalesInvoice.query.filter(SalesInvoice.id.in_(ids_list)).delete(synchronize_session=False)
            else:
                # Delete all sales
                SalesInvoiceItem.query.delete(synchronize_session=False)
                Payment.query.filter_by(invoice_type='sales').delete(synchronize_session=False)
                deleted += SalesInvoice.query.delete(synchronize_session=False)
        def delete_purchase(ids_list):
            nonlocal deleted
            if ids_list:
                PurchaseInvoiceItem.query.filter(PurchaseInvoiceItem.invoice_id.in_(ids_list)).delete(synchronize_session=False)
                Payment.query.filter(Payment.invoice_type=='purchase', Payment.invoice_id.in_(ids_list)).delete(synchronize_session=False)
                deleted += PurchaseInvoice.query.filter(PurchaseInvoice.id.in_(ids_list)).delete(synchronize_session=False)
            else:
                PurchaseInvoiceItem.query.delete(synchronize_session=False)
                Payment.query.filter_by(invoice_type='purchase').delete(synchronize_session=False)
                deleted += PurchaseInvoice.query.delete(synchronize_session=False)
        def delete_expense(ids_list):
            nonlocal deleted
            if ids_list:
                ExpenseInvoiceItem.query.filter(ExpenseInvoiceItem.invoice_id.in_(ids_list)).delete(synchronize_session=False)
                Payment.query.filter(Payment.invoice_type=='expense', Payment.invoice_id.in_(ids_list)).delete(synchronize_session=False)
                deleted += ExpenseInvoice.query.filter(ExpenseInvoice.id.in_(ids_list)).delete(synchronize_session=False)
            else:
                ExpenseInvoiceItem.query.delete(synchronize_session=False)
                Payment.query.filter_by(invoice_type='expense').delete(synchronize_session=False)
                deleted += ExpenseInvoice.query.delete(synchronize_session=False)

        if scope == 'selected':
            # Expect mixed types? Our table is unified but ids alone don't carry type. Prevent mixed delete for now.
            # Require invoice_type parameter when deleting selected; otherwise assume current tab type
            if not inv_type:
                inv_type = (request.args.get('type') or request.form.get('current_type') or 'all').lower()
            if inv_type == 'sales':
                delete_sales([int(x) for x in ids])
            elif inv_type in ['purchases','purchase']:
                delete_purchase([int(x) for x in ids])
            elif inv_type in ['expenses','expense']:
                delete_expense([int(x) for x in ids])
            else:
                flash(_('Please select a specific type tab before deleting / اختر نوع الفواتير قبل الحذف'), 'warning')
                return redirect(url_for('invoices', type='all'))
        elif scope == 'type':
            if inv_type == 'sales':
                delete_sales([])
            elif inv_type in ['purchases','purchase']:
                delete_purchase([])
            elif inv_type in ['expenses','expense']:
                delete_expense([])
            else:
                flash(_('Unknown invoice type / نوع فواتير غير معروف'), 'danger')
                return redirect(url_for('invoices', type='all'))
        else:
            flash(_('Invalid request / طلب غير صالح'), 'danger')
            return redirect(url_for('invoices', type='all'))
        safe_db_commit()
        flash(_('Deleted %(n)s invoices / تم حذف %(n)s فاتورة', n=deleted), 'success')
    except Exception:
        db.session.rollback()
        logging.exception('invoices_delete failed')
        flash(_('Delete failed / فشل الحذف'), 'danger')
    # Redirect back preserving current tab
    ret_type = inv_type if inv_type in ['sales','purchases','expenses'] else (request.args.get('type') or 'all')
    return redirect(url_for('invoices', type=ret_type))


@app.route('/invoices/<string:kind>/<int:invoice_id>')
@login_required
def view_invoice(kind, invoice_id):
    # Ensure models are available locally to avoid NameError
    from models import SalesInvoice, SalesInvoiceItem, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Payment
    kind = (kind or '').lower()
    inv = None
    items = []
    title = 'Invoice'
    if kind == 'sales':
        inv = SalesInvoice.query.get_or_404(invoice_id)
        if not can_perm('sales','view', branch_scope=inv.branch):
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('invoices'))
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
    # Cost ledger aggregated from purchases into inventory
    from models import RawMaterial, Meal, PurchaseInvoiceItem, PurchaseInvoice
    from sqlalchemy import func
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    meals = Meal.query.filter_by(active=True).all()

    # Summarize purchased quantities and average cost per material, with current stock
    ledger_rows = []
    try:
        q = db.session.query(
            PurchaseInvoiceItem.raw_material_id.label('rm_id'),
            func.max(PurchaseInvoice.date).label('last_date'),
            func.sum(PurchaseInvoiceItem.quantity).label('qty'),
            func.sum(PurchaseInvoiceItem.total_price).label('total_cost')
        ).join(PurchaseInvoice, PurchaseInvoice.id==PurchaseInvoiceItem.invoice_id)
        q = q.group_by(PurchaseInvoiceItem.raw_material_id)
        rm_map = {m.id: m for m in raw_materials}
        for r in q.all():
            rm = rm_map.get(int(r.rm_id)) if r.rm_id is not None else None
            name = (rm.display_name if rm else '-')
            unit = (rm.unit if rm else '-')
            # Quantities and costs
            qty = float(r.qty or 0)
            total_cost = float(r.total_cost or 0)
            avg_cost = (total_cost/qty) if qty else 0.0
            # Current stock equals cumulative purchased quantity (sum of purchases)
            current_stock = qty
            stock_value = current_stock * avg_cost
            ledger_rows.append({
                'material': name,
                'unit': unit,
                'purchased_qty': qty,
                'avg_cost': avg_cost,
                'total_cost': total_cost,
                'current_stock': current_stock,
                'stock_value': stock_value,
                'last_date': r.last_date.strftime('%Y-%m-%d') if r.last_date else ''
            })
        # Sort by material name
        ledger_rows.sort(key=lambda x: (x['material'] or '').lower())
    except Exception:
        ledger_rows = []

    return render_template('inventory.html', raw_materials=raw_materials, meals=meals, ledger_rows=ledger_rows)



@app.route('/employees', methods=['GET', 'POST'])
@login_required


def employees():
    from models import Employee

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
            safe_db_commit()
            # Create default salary row
            try:
                from models import EmployeeSalaryDefault
                d = EmployeeSalaryDefault(
                    employee_id=emp.id,
                    base_salary=form.base_salary.data or 0,
                    allowances=form.allowances.data or 0,
                    deductions=form.deductions.data or 0,
                )
                db.session.add(d)
                safe_db_commit()
            except Exception:
                db.session.rollback()
            flash(_('تم إضافة الموظف بنجاح / Employee added successfully'), 'success')
            return redirect(url_for('employees'))
        except Exception as e:
            db.session.rollback()
            flash(_('تعذرت إضافة الموظف. تحقق من أن رقم الموظف والهوية غير مكررين. / Could not add employee. Ensure code and national id are unique.'), 'danger')

    # Pre-fill from defaults when employee selected
    if request.method == 'POST' and not form.errors:
        from models import EmployeeSalaryDefault
        try:
            d = EmployeeSalaryDefault.query.filter_by(employee_id=form.employee_id.data).first()
            if d:
                if not form.basic_salary.data: form.basic_salary.data = float(d.base_salary or 0)
                if not form.allowances.data: form.allowances.data = float(d.allowances or 0)
                if not form.deductions.data: form.deductions.data = float(d.deductions or 0)
                # Recompute total
                total = (float(form.basic_salary.data or 0) + float(form.allowances.data or 0) - float(form.deductions.data or 0) + float(form.previous_salary_due.data or 0))
                form.total_salary.data = total
        except Exception:
            pass

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
                status='unpaid'
            )
            db.session.add(salary)
            safe_db_commit()
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

    # Initialize all_invoices as empty list to prevent UnboundLocalError
    all_invoices = []

    # Simple approach - get invoices directly from models
    try:
        # Import required models
        from sqlalchemy import func

        from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice

        # Sales invoices
        sales_invoices = []
        try:
            sales_list = SalesInvoice.query.order_by(SalesInvoice.date.desc()).all()
            for inv in sales_list:
                sales_invoices.append({
                    'id': inv.id,
                    'type': 'sales',
                    'party': inv.customer_name or 'Customer',
                    'total': float(inv.total_after_tax_discount or 0),
                    'paid': float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type=='sales', Payment.invoice_id==inv.id).scalar() or 0),
                    'date': inv.date,
                    'status': inv.status or 'unpaid'
                })
        except Exception as e:
            logging.warning(f'Error loading sales invoices: {e}')

        # Purchase invoices
        purchase_invoices = []
        try:
            purchase_list = PurchaseInvoice.query.order_by(PurchaseInvoice.date.desc()).all()
            for inv in purchase_list:
                purchase_invoices.append({
                    'id': inv.id,
                    'type': 'purchase',
                    'party': getattr(inv, 'supplier_name', 'Supplier'),
                    'total': float(getattr(inv, 'total_after_tax_discount', 0) or 0),
                    'paid': float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type=='purchase', Payment.invoice_id==inv.id).scalar() or 0),
                    'date': inv.date,
                    'status': getattr(inv, 'status', 'unpaid')
                })
        except Exception as e:
            logging.warning(f'Error loading purchase invoices: {e}')

        # Expense invoices
        expense_invoices = []
        try:
            expense_list = ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).all()
            for inv in expense_list:
                expense_invoices.append({
                    'id': inv.id,
                    'type': 'expense',
                    'party': 'Expense',
                    'total': float(getattr(inv, 'total_after_tax_discount', 0) or 0),
                    'paid': float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type=='expense', Payment.invoice_id==inv.id).scalar() or 0),
                    'date': inv.date,
                    'status': getattr(inv, 'status', 'unpaid')
                })
        except Exception as e:
            logging.warning(f'Error loading expense invoices: {e}')

        # Combine all invoices into one list with recomputed status from paid
        def compute_status(total, paid):
            try:
                if paid >= total: return 'paid'
                if paid > 0: return 'partial'
                return 'unpaid'
            except Exception:
                return 'unpaid'
        # recompute status per invoice
        for arr in (sales_invoices, purchase_invoices, expense_invoices):
            for it in arr:
                it['status'] = compute_status(float(it['total']), float(it['paid']))
        all_invoices = sales_invoices + purchase_invoices + expense_invoices

        # Apply filters if needed
        if status_filter:
            all_invoices = [inv for inv in all_invoices if inv.get('status') == status_filter]

        if type_filter and type_filter != 'all':
            all_invoices = [inv for inv in all_invoices if inv.get('type') == type_filter]

        return render_template('payments.html', invoices=all_invoices, status_filter=status_filter, type_filter=type_filter)

    except Exception as e:
        # Rollback any failed database transactions and show whatever we have
        try:
            db.session.rollback()
        except Exception:
            pass
        logging.exception('Error in payments route')
        flash(_('Error loading payments / خطأ في تحميل المدفوعات'), 'danger')
        return render_template('payments.html', invoices=all_invoices, status_filter=status_filter, type_filter=type_filter)

app = create_app()

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
def reports():
    try:
        from sqlalchemy import func, cast, Date, text
        from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice, Salary

        period = request.args.get('period', 'this_month')
        start_arg = request.args.get('start_date')
        end_arg = request.args.get('end_date')

        today = get_saudi_today()

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

        # Optional branch filter - with error handling
        branch_filter = request.args.get('branch')
        if branch_filter and branch_filter != 'all':
            sales_place = db.session.query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0)) \
                .filter(SalesInvoice.date.between(start_dt, end_dt), SalesInvoice.branch == branch_filter).scalar() or 0
            sales_china = 0
            total_sales = float(sales_place)
        else:
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

        # Sales totals by branch - with error handling
        sales_place = 0
        sales_china = 0
        total_sales = 0

        try:
            if branch_filter and branch_filter != 'all':
                sales_place = db.session.query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0)) \
                    .filter(SalesInvoice.date.between(start_dt, end_dt), SalesInvoice.branch == branch_filter).scalar() or 0
                sales_china = 0
                total_sales = float(sales_place)
            else:
                # Sales totals by branch
                sales_place = db.session.query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0)) \
                    .filter(SalesInvoice.date.between(start_dt, end_dt), SalesInvoice.branch == 'place_india').scalar() or 0
                sales_china = db.session.query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0)) \
                    .filter(SalesInvoice.date.between(start_dt, end_dt), SalesInvoice.branch == 'china_town').scalar() or 0
                total_sales = float(sales_place) + float(sales_china)
        except Exception as e:
            logging.warning(f'Error calculating sales totals: {e}')
            db.session.rollback()
            sales_place = sales_china = total_sales = 0

        # Purchases and Expenses - with error handling
        total_purchases = 0
        total_expenses = 0
        total_salaries = 0

        try:
            total_purchases = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
                .filter(PurchaseInvoice.date.between(start_dt, end_dt)).scalar() or 0)
        except Exception as e:
            logging.warning(f'Error calculating purchases: {e}')
            db.session.rollback()
            total_purchases = 0

        try:
            total_expenses = float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_after_tax_discount), 0))
                .filter(ExpenseInvoice.date.between(start_dt, end_dt)).scalar() or 0)
        except Exception as e:
            logging.warning(f'Error calculating expenses: {e}')
            db.session.rollback()
            total_expenses = 0

        # Salaries within period: compute by month-year mapping to 1st day of month
        try:
            salaries_rows = Salary.query.all()
            for s in salaries_rows:
                try:
                    s_date = datetime(s.year, s.month, 1).date()
                    if start_dt <= s_date <= end_dt:
                        total_salaries += float(s.total_salary or 0)
                except Exception:
                    continue
        except Exception as e:
            logging.warning(f'Error calculating salaries: {e}')
            db.session.rollback()
            total_salaries = 0

        profit = float(total_sales) - (float(total_purchases) + float(total_expenses) + float(total_salaries))

        # Line chart: daily sales - with error handling
        line_labels = []
        line_values = []

        try:
            daily_rows = db.session.query(SalesInvoice.date.label('d'), func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0).label('t')) \
                .filter(SalesInvoice.date.between(start_dt, end_dt)) \
                .group_by(SalesInvoice.date) \
                .order_by(SalesInvoice.date.asc()).all()
            line_labels = [r.d.strftime('%Y-%m-%d') for r in daily_rows]
            line_values = [float(r.t) if r.t is not None else 0.0 for r in daily_rows]
        except Exception as e:
            logging.warning(f'Error generating daily sales chart: {e}')
            db.session.rollback()
            line_labels = []
            line_values = []

        # Payment method distribution across invoices - with error handling
        def pm_counts(model, date_col, method_col):
            try:
                rows = db.session.query(getattr(model, method_col), func.count('*')) \
                    .filter(getattr(model, date_col).between(start_dt, end_dt)) \
                    .group_by(getattr(model, method_col)).all()
                return {(r[0] or 'unknown'): int(r[1]) for r in rows}
            except Exception as e:
                logging.warning(f'Error getting payment method counts for {model.__name__}: {e}')
                db.session.rollback()
                return {}

        pm_map = {}
        try:
            for d in (pm_counts(SalesInvoice, 'date', 'payment_method'),
                      pm_counts(PurchaseInvoice, 'date', 'payment_method'),
                      pm_counts(ExpenseInvoice, 'date', 'payment_method')):
                for k, v in d.items():
                    pm_map[k] = pm_map.get(k, 0) + v
        except Exception as e:
            logging.warning(f'Error processing payment method data: {e}')
            pm_map = {}

        pm_labels = list(pm_map.keys())
        pm_values = [pm_map[k] for k in pm_labels]

        # Comparison bars: totals
        comp_labels = ['Sales', 'Purchases', 'Expenses+Salaries']
        comp_values = [float(total_sales), float(total_purchases), float(total_expenses) + float(total_salaries)]

        # Cash flows from Payments table - with error handling
        inflow = 0
        outflow = 0
        net_cash = 0

        try:
            start_dt_dt = datetime.combine(start_dt, datetime.min.time())
            end_dt_dt = datetime.combine(end_dt, datetime.max.time())
            inflow = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                Payment.invoice_type == 'sales', Payment.payment_date.between(start_dt_dt, end_dt_dt)
            ).scalar() or 0)
            outflow = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                Payment.invoice_type.in_(['purchase','expense','salary']), Payment.payment_date.between(start_dt_dt, end_dt_dt)
            ).scalar() or 0)
            net_cash = inflow - outflow
        except Exception as e:
            logging.warning(f'Error calculating cash flows: {e}')
            db.session.rollback()
            inflow = outflow = net_cash = 0


        # Top products by quantity - with error handling
        top_labels = []
        top_values = []

        try:
            top_rows = db.session.query(SalesInvoiceItem.product_name, func.coalesce(func.sum(SalesInvoiceItem.quantity), 0)) \
                .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id) \
                .filter(SalesInvoice.date.between(start_dt, end_dt)) \
                .group_by(SalesInvoiceItem.product_name) \
                .order_by(func.sum(SalesInvoiceItem.quantity).desc()) \
                .limit(10).all()
            top_labels = [r[0] for r in top_rows]
            top_values = [float(r[1]) for r in top_rows]
        except Exception as e:
            logging.warning(f'Error getting top products: {e}')
            db.session.rollback()
            top_labels = []
            top_values = []

        # Low stock items - with error handling
        low_stock = []
        try:
            low_stock_rows = RawMaterial.query.filter(RawMaterial.current_stock <= RawMaterial.minimum_stock).all()
            low_stock = [{'name': r.name, 'current': r.current_stock, 'minimum': r.minimum_stock} for r in low_stock_rows]
        except Exception as e:
            logging.warning(f'Error getting low stock items: {e}')
            db.session.rollback()
            low_stock = []

        # Settings for labels/currency
        s = get_settings_safe()
        place_lbl = s.place_india_label if s and s.place_india_label else 'Place India'
        china_lbl = s.china_town_label if s and s.china_town_label else 'China Town'
        currency = s.currency if s and s.currency else 'SAR'

        # Build detailed tables for template (branch-wise sales, purchases, expenses)
        sales_china_rows, sales_india_rows = [], []
        china_total_amount = china_total_tax = china_total_discount = 0.0
        india_total_amount = india_total_tax = india_total_discount = 0.0
        china_payment_stats = india_payment_stats = ''
        purchases_rows = []
        purchases_total_amount = purchases_total_tax = 0.0
        purchases_total_supplier = ''
        expenses_rows = []
        expenses_total = 0.0

        try:
            # Sales rows per branch
            from sqlalchemy import and_
            sales_join = db.session.query(
                SalesInvoice.date.label('date'),
                SalesInvoice.invoice_number.label('invoice_number'),
                SalesInvoice.payment_method.label('payment_method'),
                SalesInvoice.branch.label('branch'),
                SalesInvoiceItem.product_name.label('item_name'),
                SalesInvoiceItem.quantity.label('qty'),
                SalesInvoiceItem.price_before_tax.label('unit_price'),
                SalesInvoiceItem.tax.label('tax'),
                SalesInvoiceItem.discount.label('discount')
            ).join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
            sales_rows = sales_join.filter(
                SalesInvoice.date.between(start_dt, end_dt)
            ).all()

            for r in sales_rows:
                amount_before_tax = float(r.unit_price or 0) * float(r.qty or 0)
                row = {
                    'date': r.date,
                    'invoice_number': r.invoice_number,
                    'item_name': r.item_name,
                    'amount_before_tax': amount_before_tax,
                    'tax_amount': float(r.tax or 0),
                    'payment_method': r.payment_method,
                    'discount': float(r.discount or 0)
                }
                if r.branch == 'china_town':
                    sales_china_rows.append(row)
                    china_total_amount += amount_before_tax
                    china_total_tax += float(r.tax or 0)
                    china_total_discount += float(r.discount or 0)
                elif r.branch == 'place_india':
                    sales_india_rows.append(row)
                    india_total_amount += amount_before_tax
                    india_total_tax += float(r.tax or 0)
                    india_total_discount += float(r.discount or 0)

            # Payment stats per branch (counts by method)
            def payment_stats_str(branch_code):
                rows = db.session.query(SalesInvoice.payment_method, func.count('*')).\
                    filter(and_(SalesInvoice.date.between(start_dt, end_dt), SalesInvoice.branch == branch_code)).\
                    group_by(SalesInvoice.payment_method).all()
                parts = []
                for method, cnt in rows:
                    parts.append(f"{(method or 'unknown').upper()}: {int(cnt)}")
                return ', '.join(parts)

            china_payment_stats = payment_stats_str('china_town')
            india_payment_stats = payment_stats_str('place_india')
        except Exception as e:
            logging.warning(f'Error building sales detail rows: {e}')
            db.session.rollback()
            sales_china_rows, sales_india_rows = [], []
            china_total_amount = china_total_tax = china_total_discount = 0.0
            india_total_amount = india_total_tax = india_total_discount = 0.0
            china_payment_stats = india_payment_stats = ''

        try:
            # Purchases detailed rows
            pur_rows = db.session.query(
                PurchaseInvoice.date.label('date'),
                PurchaseInvoice.invoice_number.label('invoice_number'),
                PurchaseInvoice.payment_method.label('payment_method'),
                PurchaseInvoice.supplier_name.label('supplier'),
                PurchaseInvoiceItem.raw_material_name.label('item_name'),
                PurchaseInvoiceItem.quantity.label('qty'),
                PurchaseInvoiceItem.price_before_tax.label('unit_price'),
                PurchaseInvoiceItem.tax.label('tax')
            ).join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
             .filter(PurchaseInvoice.date.between(start_dt, end_dt)).all()

            for r in pur_rows:
                amount_bt = float(r.unit_price or 0) * float(r.qty or 0)
                purchases_rows.append({
                    'date': r.date,
                    'invoice_number': r.invoice_number,
                    'item_name': r.item_name,
                    'amount_before_tax': amount_bt,
                    'tax_amount': float(r.tax or 0),
                    'supplier_or_payment': f"{(r.payment_method or '').upper()} / {(r.supplier or '')}"
                })
                purchases_total_amount += amount_bt
                purchases_total_tax += float(r.tax or 0)
            # simple supplier summary: count distinct suppliers
            try:
                supplier_cnt = db.session.query(func.count(func.distinct(PurchaseInvoice.supplier_name))). \
                    filter(PurchaseInvoice.date.between(start_dt, end_dt)).scalar() or 0
                purchases_total_supplier = f"Suppliers: {int(supplier_cnt)}"
            except Exception:
                purchases_total_supplier = ''
        except Exception as e:
            logging.warning(f'Error building purchases detail rows: {e}')
            db.session.rollback()
            purchases_rows = []
            purchases_total_amount = purchases_total_tax = 0.0
            purchases_total_supplier = ''

        try:
            # Expenses detailed rows
            exp_rows = db.session.query(
                ExpenseInvoice.date.label('date'),
                ExpenseInvoice.invoice_number.label('invoice_number'),
                ExpenseInvoice.payment_method.label('payment_method'),
                ExpenseInvoiceItem.description.label('desc'),
                ExpenseInvoiceItem.quantity.label('qty'),
                ExpenseInvoiceItem.price_before_tax.label('unit_price'),
                ExpenseInvoiceItem.tax.label('tax'),
                ExpenseInvoiceItem.discount.label('discount')
            ).join(ExpenseInvoice, ExpenseInvoiceItem.invoice_id == ExpenseInvoice.id) \
             .filter(ExpenseInvoice.date.between(start_dt, end_dt)).all()

            for r in exp_rows:
                amount_line = (float(r.unit_price or 0) * float(r.qty or 0)) + float(r.tax or 0) - float(r.discount or 0)
                expenses_rows.append({
                    'date': r.date,
                    'voucher_number': r.invoice_number,
                    'expense_type': r.desc,
                    'amount': amount_line,
                    'payment_method': r.payment_method
                })
                expenses_total += amount_line
        except Exception as e:
            logging.warning(f'Error building expenses detail rows: {e}')
            db.session.rollback()
            expenses_rows = []
            expenses_total = 0.0

        # Return template with detailed rows and totals expected by the template
        return render_template('reports.html',
            period=period, start_date=start_dt, end_date=end_dt,
            # Summary numbers (used for charts/cards)
            sales_place=sales_place, total_sales=total_sales,
            total_purchases=total_purchases, total_expenses=total_expenses, total_salaries=total_salaries, profit=profit,
            line_labels=line_labels, line_values=line_values,
            pm_labels=pm_labels, pm_values=pm_values,
            comp_labels=comp_labels, comp_values=comp_values,
            inflow=inflow, outflow=outflow, net_cash=net_cash,
            top_labels=top_labels, top_values=top_values,
            low_stock=low_stock,
            place_lbl=place_lbl, china_lbl=china_lbl, currency=currency,
            # Detailed tables (branch-wise sales)
            sales_china=sales_china_rows,
            sales_india=sales_india_rows,
            china_total_amount=china_total_amount,
            china_total_tax=china_total_tax,
            china_total_discount=china_total_discount,
            china_payment_stats=china_payment_stats,
            india_total_amount=india_total_amount,
            india_total_tax=india_total_tax,
            india_total_discount=india_total_discount,
            india_payment_stats=india_payment_stats,
            # Purchases table
            purchases=purchases_rows,
            purchases_total_amount=purchases_total_amount,
            purchases_total_tax=purchases_total_tax,
            purchases_total_supplier=purchases_total_supplier,
            # Expenses table
            expenses=expenses_rows,
            expenses_total=expenses_total,
            # Payroll (empty until implemented)
            payroll=[]
        )
    except Exception as e:
        # Rollback any failed database transactions
        try:
            db.session.rollback()
        except Exception:
            pass

        logging.exception('Error in reports route')
        flash(_('Error loading reports / خطأ في تحميل التقارير'), 'danger')

        # Return safe fallback data instead of redirect (use list/dict defaults expected by template)
        return render_template('reports.html',
            period='this_month', start_date=datetime.now().date(), end_date=datetime.now().date(),
            # Summary numbers
            sales_place=0, total_sales=0,
            total_purchases=0, total_expenses=0, total_salaries=0, profit=0,
            line_labels=[], line_values=[],
            pm_labels=[], pm_values=[],
            comp_labels=[], comp_values=[],
            inflow=0, outflow=0, net_cash=0,
            top_labels=[], top_values=[],
            low_stock=[],
            place_lbl='Place India', china_lbl='China Town', currency='SAR',
            # Detailed tables expected by template
            sales_china=[], sales_india=[],
            china_total_amount=0, china_total_tax=0, china_total_discount=0, china_payment_stats='',
            india_total_amount=0, india_total_tax=0, india_total_discount=0, india_payment_stats='',
            purchases=[], purchases_total_amount=0, purchases_total_tax=0, purchases_total_supplier='',
            expenses=[], expenses_total=0,
            payroll=[]
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
    method = (request.form.get('payment_method') or 'CASH').strip().upper()

    # Register payment
    pay = Payment(invoice_id=invoice_id, invoice_type=invoice_type, amount_paid=amount, payment_method=method)
    # Ensure payment_date is set now to avoid None in ledger posting
    try:
        from datetime import datetime as _dt
        if not getattr(pay, 'payment_date', None):
            pay.payment_date = get_saudi_now()
    except Exception:
        pass
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

        # Robust date for ledger (fallback to today if missing)
        try:
            _pdate = pay.payment_date.date() if getattr(pay, 'payment_date', None) else get_saudi_now().date()
        except Exception:
            _pdate = get_saudi_now().date()
        if invoice_type == 'sales':
            # receipt: debit cash, credit AR
            db.session.add(LedgerEntry(date=_pdate, account_id=cash_acc.id, debit=amount, credit=0, description=f'Receipt sales #{invoice_id}'))
            db.session.add(LedgerEntry(date=_pdate, account_id=ar_acc.id, debit=0, credit=amount, description=f'Settle AR sales #{invoice_id}'))
        elif invoice_type in ['purchase','expense','salary']:
            # payment: credit cash, debit AP (or expense/salary direct, but we keep AP)
            db.session.add(LedgerEntry(date=_pdate, account_id=ap_acc.id, debit=amount, credit=0, description=f'Settle AP {invoice_type} #{invoice_id}'))
            db.session.add(LedgerEntry(date=_pdate, account_id=cash_acc.id, debit=0, credit=amount, description=f'Payment {invoice_type} #{invoice_id}'))
        safe_db_commit()
    except Exception as e:
        db.session.rollback()
        logging.error('Ledger posting (payment) failed: %s', e, exc_info=True)


    safe_db_commit()

    # Emit socket event (if desired)
    try:
        if socketio:
            socketio.emit('payment_update', {'invoice_id': invoice_id, 'invoice_type': invoice_type, 'amount': amount})
    except Exception:
        pass

    return jsonify({'status': 'success'})






# Employees: Edit

# Employees: Edit defaults
@app.route('/employees/<int:emp_id>/defaults', methods=['GET','POST'])
@login_required
def edit_employee_defaults(emp_id):
    from models import Employee, EmployeeSalaryDefault
    emp = Employee.query.get_or_404(emp_id)
    d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first()
    if request.method == 'POST':
        try:
            if not d:
                d = EmployeeSalaryDefault(employee_id=emp.id)
                db.session.add(d)
            d.base_salary = float(request.form.get('base_salary') or 0)
            d.allowances = float(request.form.get('allowances') or 0)
            d.deductions = float(request.form.get('deductions') or 0)
            safe_db_commit()
            flash(_('Defaults updated / تم تحديث الافتراضات'), 'success')
            return redirect(url_for('employees'))
        except Exception:
            db.session.rollback()
            flash(_('Failed to update defaults / فشل تحديث الافتراضات'), 'danger')
    return render_template('employee_defaults_edit.html', emp=emp, d=d)


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
            safe_db_commit()
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
        # Delete all related records first
        try:
            # Delete salary defaults
            from models import EmployeeSalaryDefault
            EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).delete(synchronize_session=False)
        except Exception as e:
            print(f"Error deleting salary defaults: {e}")

        try:
            # Delete monthly salaries
            from models import Salary
            Salary.query.filter_by(employee_id=emp.id).delete(synchronize_session=False)
        except Exception as e:
            print(f"Error deleting salaries: {e}")

        try:
            # Delete any other related records if they exist
            from models import EmployeeAttendance
            EmployeeAttendance.query.filter_by(employee_id=emp.id).delete(synchronize_session=False)
        except Exception as e:
            print(f"Error deleting attendance (may not exist): {e}")

        # Finally delete the employee
        db.session.delete(emp)
        db.session.commit()

        flash(_('تم حذف الموظف وجميع بياناته بنجاح / Employee and all related data deleted successfully'), 'success')

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting employee: {e}")
        import traceback
        traceback.print_exc()
        flash(_('تعذر حذف الموظف - يرجى المحاولة مرة أخرى / Could not delete employee - please try again'), 'danger')

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
            safe_db_commit()
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
        year = int(request.args.get('year') or get_saudi_now().year)
    except Exception:
        year = get_saudi_now().year
    try:
        month = int(request.args.get('month') or get_saudi_now().month)
    except Exception:
        month = get_saudi_now().month
    # Optional status filter
    status_f = (request.args.get('status') or '').strip().lower()

    from sqlalchemy import func
    qs = Salary.query.filter_by(year=year, month=month).join(Employee).order_by(Employee.full_name.asc())
    if status_f in ('paid', 'due', 'partial'):
        qs = qs.filter(Salary.status == status_f)
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

    return render_template('salaries_statements.html', year=year, month=month, rows=rows, totals=totals, status_f=status_f)
@app.route('/salaries/<int:salary_id>/delete', methods=['POST'])
@login_required
def delete_salary(salary_id):
    sal = Salary.query.get_or_404(salary_id)
    try:
        db.session.delete(sal)
        safe_db_commit()
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
        year = int(request.values.get('year') or get_saudi_now().year)
    except Exception:
        year = get_saudi_now().year
    try:
        month = int(request.values.get('month') or get_saudi_now().month)
    except Exception:
        month = get_saudi_now().month

    # Ensure salary rows exist for all active employees
    emps = Employee.query.filter_by(status='active').order_by(Employee.full_name.asc()).all()
    existing = {(s.employee_id, s.year, s.month): s for s in Salary.query.filter_by(year=year, month=month).all()}
    created = 0
    from models import EmployeeSalaryDefault
    for e in emps:
        if (e.id, year, month) not in existing:
            d = EmployeeSalaryDefault.query.filter_by(employee_id=e.id).first()
            basic = float(getattr(d, 'base_salary', 0) or 0)
            allow = float(getattr(d, 'allowances', 0) or 0)
            ded = float(getattr(d, 'deductions', 0) or 0)
            total = basic + allow - ded
            s = Salary(employee_id=e.id, year=year, month=month,
                       basic_salary=basic, allowances=allow, deductions=ded, previous_salary_due=0,
                       total_salary=total, status='due')
            db.session.add(s)
            created += 1
    if created:
        safe_db_commit()

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

@app.route('/api/employee/<int:emp_id>/salary_defaults')
@login_required
def api_employee_salary_defaults(emp_id):
    from models import EmployeeSalaryDefault
    d = EmployeeSalaryDefault.query.filter_by(employee_id=emp_id).first()
    if not d:
        return jsonify({'base_salary': 0, 'allowances': 0, 'deductions': 0})
    return jsonify({'base_salary': float(d.base_salary or 0), 'allowances': float(d.allowances or 0), 'deductions': float(d.deductions or 0)})

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
        safe_db_commit()
        flash(_('تم حفظ التعديلات / Changes saved'), 'success')
    else:
        flash(_('No changes / لا توجد تعديلات'), 'info')
    return redirect(url_for('salaries_monthly', year=request.form.get('year'), month=request.form.get('month')))

@app.route('/settings/print', methods=['POST'])
@login_required
def settings_print_save():
    from models import Settings
    s = Settings.query.first()
    if not s:
        s = Settings()
        db.session.add(s)
    s.receipt_paper_width = (request.form.get('receipt_paper_width') or '80')
    s.receipt_margin_top_mm = int(request.form.get('receipt_margin_top_mm') or 5)
    s.receipt_margin_bottom_mm = int(request.form.get('receipt_margin_bottom_mm') or 5)
    s.receipt_margin_left_mm = int(request.form.get('receipt_margin_left_mm') or 3)
    s.receipt_margin_right_mm = int(request.form.get('receipt_margin_right_mm') or 3)
    s.receipt_font_size = int(request.form.get('receipt_font_size') or 12)
    s.receipt_show_logo = bool(request.form.get('receipt_show_logo'))
    s.receipt_show_tax_number = bool(request.form.get('receipt_show_tax_number'))
    s.receipt_footer_text = (request.form.get('receipt_footer_text') or '').strip()
    safe_db_commit()
    flash(_('Print settings saved / تم حفظ إعدادات الطباعة'), 'success')
    return redirect(url_for('settings'))


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

        # Branch-specific settings
        s.china_town_void_password = request.form.get('china_town_void_password') or '1991'
        try:
            s.china_town_vat_rate = float(request.form.get('china_town_vat_rate') or 15)
        except Exception:
            s.china_town_vat_rate = 15.0
        try:
            s.china_town_discount_rate = float(request.form.get('china_town_discount_rate') or 0)
        except Exception:
            s.china_town_discount_rate = 0.0

        s.place_india_void_password = request.form.get('place_india_void_password') or '1991'
        try:
            s.place_india_vat_rate = float(request.form.get('place_india_vat_rate') or 15)
        except Exception:
            s.place_india_vat_rate = 15.0
        try:
            s.place_india_discount_rate = float(request.form.get('place_india_discount_rate') or 0)
        except Exception:
            s.place_india_discount_rate = 0.0
        # Receipt settings
        s.receipt_paper_width = (request.form.get('receipt_paper_width') or s.receipt_paper_width or '80')
        try:
            s.receipt_font_size = int(request.form.get('receipt_font_size') or s.receipt_font_size or 12)
        except Exception:
            pass
        # New configurable fields
        try:
            s.receipt_logo_height = int(request.form.get('receipt_logo_height') or (s.receipt_logo_height or 72))
        except Exception:
            pass
        try:
            s.receipt_extra_bottom_mm = int(request.form.get('receipt_extra_bottom_mm') or (s.receipt_extra_bottom_mm or 15))
        except Exception:
            pass
        # Handle logo upload
        if 'logo_file' in request.files and request.files['logo_file'].filename:
            logo_file = request.files['logo_file']
            if logo_file and logo_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                try:
                    import os
                    from werkzeug.utils import secure_filename

                    # Create uploads directory if it doesn't exist
                    upload_dir = os.path.join(app.static_folder, 'uploads')
                    os.makedirs(upload_dir, exist_ok=True)

                    # Generate unique filename
                    filename = secure_filename(logo_file.filename)
                    timestamp = str(int(time.time()))
                    name, ext = os.path.splitext(filename)
                    unique_filename = f"logo_{timestamp}{ext}"

                    # Save file
                    file_path = os.path.join(upload_dir, unique_filename)
                    logo_file.save(file_path)

                    # Update logo URL to point to uploaded file
                    s.logo_url = f'/static/uploads/{unique_filename}'
                    flash(_('Logo uploaded successfully / تم رفع الشعار بنجاح'), 'success')

                except Exception as e:
                    flash(_('Failed to upload logo / فشل رفع الشعار: %(error)s', error=str(e)), 'danger')
        else:
            # Use URL if no file uploaded
            s.logo_url = (request.form.get('logo_url') or s.logo_url or '/static/chinese-logo.svg')

        s.receipt_show_logo = bool(request.form.get('receipt_show_logo'))
        s.receipt_show_tax_number = bool(request.form.get('receipt_show_tax_number'))
        s.receipt_footer_text = (request.form.get('receipt_footer_text') or s.receipt_footer_text or '')

        # New: printer type, footer message, and currency image
        s.printer_type = (request.form.get('printer_type') or s.printer_type or 'thermal').lower()
        s.footer_message = (request.form.get('footer_message') or s.footer_message or 'THANK YOU FOR VISIT')

        # Handle currency image upload or URL
        curr_file = request.files.get('currency_file')
        if curr_file and curr_file.filename:
            try:
                import os
                import time
                from werkzeug.utils import secure_filename
                upload_dir = os.path.join(app.static_folder, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filename = secure_filename(curr_file.filename)
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                unique_filename = f"currency_{timestamp}{ext}"
                file_path = os.path.join(upload_dir, unique_filename)
                curr_file.save(file_path)
                s.currency_image = f'/static/uploads/{unique_filename}'
                flash(_('Currency image uploaded successfully'), 'success')
            except Exception as e:
                flash(_('Failed to upload currency image: %(error)s', error=str(e)), 'danger')
        else:
            # URL fallback
            url_val = (request.form.get('currency_image_url') or '').strip()
            if url_val:
                s.currency_image = url_val

        safe_db_commit()
        flash(_('Settings saved successfully'), 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html', s=s or Settings())

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current = (request.form.get('current_password') or '').strip()
    new = (request.form.get('new_password') or '').strip()
    confirm = (request.form.get('confirm_password') or '').strip()
    # Validate
    if not current or not new or not confirm:
        flash(_('Please fill all fields / الرجاء تعبئة جميع الحقول'), 'danger')
        return redirect(url_for('settings'))
    if new != confirm:
        flash(_('New passwords do not match / كلمتا المرور غير متطابقتين'), 'danger')
        return redirect(url_for('settings'))
    if new == current:
        flash(_('New password must be different from current / يجب أن تكون كلمة المرور الجديدة مختلفة عن الحالية'), 'danger')
        return redirect(url_for('settings'))
    # Verify current against fresh DB state
    try:
        u = User.query.get(current_user.id)
    except Exception:
        u = None
    if not u or not bcrypt.check_password_hash(u.password_hash, current):
        flash(_('Current password is incorrect / كلمة المرور الحالية غير صحيحة'), 'danger')
        return redirect(url_for('settings'))
    # Update securely
    u.set_password(new, bcrypt)
    try:
        safe_db_commit()
        # Sync session object
        try:
            current_user.password_hash = u.password_hash
        except Exception:
            pass
        flash(_('Password updated successfully / تم تحديث كلمة المرور بنجاح'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Unexpected error. Please try again / حدث خطأ غير متوقع، حاول مرة أخرى'), 'danger')
    return redirect(url_for('settings'))


# ---- Simple permission checker usable in routes (Python scope)
from models import UserPermission

def can_perm(screen, perm, branch_scope=None):
    try:
        if getattr(current_user,'role','') == 'admin':
            return True
        q = UserPermission.query.filter_by(user_id=current_user.id, screen_key=screen)
        # Branch-aware: allow if permission exists for this branch or for 'all'
        for p in q.all():
            if branch_scope and p.branch_scope not in (branch_scope, 'all', None):
                continue
            if perm == 'view' and p.can_view: return True
            if perm == 'add' and p.can_add: return True
            if perm == 'edit' and p.can_edit: return True
            if perm == 'delete' and p.can_delete: return True
            if perm == 'print' and p.can_print: return True
    except Exception:
        pass
    return False

def first_allowed_sales_branch():
    try:
        if getattr(current_user,'role','') == 'admin':
            return 'all'
        perms = UserPermission.query.filter_by(user_id=current_user.id, screen_key='sales').all()
        scopes = [p.branch_scope for p in perms if p.can_view]
        if not scopes:
            return None
        if 'all' in scopes or None in scopes:
            return 'all'
        # return first specific branch
        return scopes[0]
    except Exception:
        return None


BRANCH_CODES = {'china_town': 'China Town', 'place_india': 'Place India'}

def is_valid_branch(code:str)->bool:
    return code in BRANCH_CODES

def branch_label(code:str)->str:
    return BRANCH_CODES.get(code, code)

# ---------------------- Users API ----------------------
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
    safe_db_commit()
    return jsonify({'status':'ok','id':u.id})

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
    safe_db_commit()
    return jsonify({'status':'ok'})

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
    safe_db_commit()
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
    return dict(
        can=lambda screen,perm: (getattr(current_user,'role','')=='admin') or user_has_perm(current_user, screen, perm),
        can_branch=lambda screen,perm,branch_scope: can_perm(screen, perm, branch_scope)
    )
# ---------------------- Permissions API ----------------------
from models import UserPermission

@app.route('/api/users/<int:uid>/permissions', methods=['GET'])
@login_required
def api_user_permissions_get(uid):
    if not can_perm('users','view'):
        return jsonify({'error':'forbidden'}), 403
    User.query.get_or_404(uid)
    scope = (request.args.get('branch_scope') or '').strip().lower()
    # map short scope values to canonical
    scope_map = {'place':'place_india', 'china':'china_town'}
    canon_scope = scope_map.get(scope, scope)
    q = UserPermission.query.filter_by(user_id=uid)
    from sqlalchemy import or_
    if canon_scope and canon_scope != 'all':
        # Include branch-specific, global ('all'), and legacy short scopes to be backward compatible
        q = q.filter(or_(
            UserPermission.branch_scope == canon_scope,
            UserPermission.branch_scope == 'all',
            UserPermission.branch_scope == 'place',
            UserPermission.branch_scope == 'china'
        ))
    perms = q.all()
    # Aggregate by screen_key: effective permission is OR across scopes
    agg = {}
    for p in perms:
        k = p.screen_key
        if k not in agg:
            agg[k] = {'screen_key': k, 'view': False, 'add': False, 'edit': False, 'delete': False, 'print': False}
        agg[k]['view'] = agg[k]['view'] or bool(p.can_view)
        agg[k]['add'] = agg[k]['add'] or bool(p.can_add)
        agg[k]['edit'] = agg[k]['edit'] or bool(p.can_edit)
        agg[k]['delete'] = agg[k]['delete'] or bool(p.can_delete)
        agg[k]['print'] = agg[k]['print'] or bool(p.can_print)
    if not canon_scope or canon_scope == 'all':
        # For 'all' scope: aggregate across all scopes so UI shows effective overall perms
        out = list(agg.values())
    else:
        out = list(agg.values())
    return jsonify({'items': out})

@csrf_exempt
@app.route('/api/users/<int:uid>/permissions', methods=['POST'])
@login_required
def api_user_permissions_save(uid):
    if not can_perm('users','edit'):
        return jsonify({'error':'forbidden'}), 403
    User.query.get_or_404(uid)
    payload = request.get_json(force=True) or {}
    items = payload.get('items') or []
    scope_in = (payload.get('branch_scope') or 'all').strip().lower()
    scope_map = {'place':'place_india', 'china':'china_town'}
    branch_scope = scope_map.get(scope_in, scope_in)
    # Remove existing for this branch scope, then insert new
    UserPermission.query.filter_by(user_id=uid, branch_scope=branch_scope).delete(synchronize_session=False)
    for it in items:
        key = (it.get('screen_key') or '').strip()
        if not key:
            continue
        p = UserPermission(
            user_id=uid, screen_key=key, branch_scope=branch_scope,
            can_view=bool(it.get('view')), can_add=bool(it.get('add')),
            can_edit=bool(it.get('edit')), can_delete=bool(it.get('delete')),
            can_print=bool(it.get('print'))
        )
        db.session.add(p)
    safe_db_commit()
    return jsonify({'status':'ok','count':len(items)})

# Admin-only debug endpoint to inspect effective permissions for a user
@app.route('/api/debug/effective_permissions', methods=['GET'])
@login_required
def debug_effective_permissions():
    # Extra safe: admin only
    if getattr(current_user, 'role', '') != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    try:
        # Identify target user
        uname = (request.args.get('username') or '').strip()
        uid_arg = (request.args.get('uid') or '').strip()
        target = None
        if uname:
            target = User.query.filter_by(username=uname).first()
        elif uid_arg:
            try:
                target = User.query.get(int(uid_arg))
            except Exception:
                target = None
        if not target:
            return jsonify({'error': 'user not found'}), 404
        # Branch scope handling: same canonicalization and aggregation logic as API
        scope = (request.args.get('branch_scope') or '').strip().lower()
        scope_map = {'place':'place_india', 'china':'china_town'}
        canon_scope = scope_map.get(scope, scope)
        from models import UserPermission
        from sqlalchemy import or_
        q = UserPermission.query.filter_by(user_id=target.id)
        if canon_scope and canon_scope != 'all':
            q = q.filter(or_(
                UserPermission.branch_scope == canon_scope,
                UserPermission.branch_scope == 'all',
                UserPermission.branch_scope == 'place',
                UserPermission.branch_scope == 'china'
            ))
        perms = q.all()
        agg = {}
        for p in perms:
            k = p.screen_key
            if k not in agg:
                agg[k] = {'screen_key': k, 'view': False, 'add': False, 'edit': False, 'delete': False, 'print': False}
            agg[k]['view'] = agg[k]['view'] or bool(p.can_view)
            agg[k]['add'] = agg[k]['add'] or bool(p.can_add)
            agg[k]['edit'] = agg[k]['edit'] or bool(p.can_edit)
            agg[k]['delete'] = agg[k]['delete'] or bool(p.can_delete)
            agg[k]['print'] = agg[k]['print'] or bool(p.can_print)
        out = list(agg.values())
        return jsonify({'username': target.username, 'branch_scope': canon_scope or 'all', 'items': out})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'error': 'internal', 'detail': str(e)}), 500
# Retention: 12 months with PDF export
@app.route('/invoices/retention', methods=['GET'], endpoint='invoices_retention')
@login_required
def invoices_retention_view():
    # Show invoices older than 12 months (approx 365 days)
    cutoff = get_saudi_today() - timedelta(days=365)
    sales_old = SalesInvoice.query.filter(SalesInvoice.date < cutoff).order_by(SalesInvoice.date.desc()).limit(200).all()
    purchases_old = PurchaseInvoice.query.filter(PurchaseInvoice.date < cutoff).order_by(PurchaseInvoice.date.desc()).limit(200).all()
    expenses_old = ExpenseInvoice.query.filter(ExpenseInvoice.date < cutoff).order_by(ExpenseInvoice.date.desc()).limit(200).all()
    return render_template('retention.html', cutoff=cutoff, sales=sales_old, purchases=purchases_old, expenses=expenses_old)

@app.route('/invoices/retention/export', endpoint='invoices_retention_export')
@login_required
def invoices_retention_export_view():
    # Export invoices older than 12 months to a single PDF (summary style)
    from flask import send_file
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import io
    cutoff = get_saudi_today() - timedelta(days=365)
    kind = (request.args.get('type') or 'all').lower()
    # Collect
    sales = SalesInvoice.query.filter(SalesInvoice.date < cutoff).order_by(SalesInvoice.date.asc()).all() if kind in ['all','sales'] else []
    purchases = PurchaseInvoice.query.filter(PurchaseInvoice.date < cutoff).order_by(PurchaseInvoice.date.asc()).all() if kind in ['all','purchase','purchases'] else []
    expenses = ExpenseInvoice.query.filter(ExpenseInvoice.date < cutoff).order_by(ExpenseInvoice.date.asc()).all() if kind in ['all','expense','expenses'] else []

    buf = io.BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # Optional Arabic font shaper reused
    def shape_ar(t):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            return get_display(arabic_reshaper.reshape(str(t)))
        except Exception:
            return str(t)

    y = h - 40
    p.setTitle(f"Invoices older than {cutoff}")
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, y, f"Invoices older than {cutoff}")
    y -= 30

    def line(txt, size=10):
        nonlocal y
        if y < 40:
            p.showPage(); y = h - 40; p.setFont("Helvetica", size)
        p.setFont("Helvetica", size)
        p.drawString(40, y, txt)
        y -= 16

    total_count = 0
    for inv in sales:
        total_count += 1
        line(f"[SALES] {inv.invoice_number} | {inv.date} | {inv.branch} | PM: {inv.payment_method} | Total: {float(inv.total_after_tax_discount or 0):.2f}")
    for inv in purchases:
        total_count += 1
        name = getattr(inv, 'supplier_name', '-')
        line(f"[PURCHASE] {inv.invoice_number} | {inv.date} | {shape_ar(name)} | PM: {inv.payment_method} | Total: {float(inv.total_after_tax_discount or 0):.2f}")
    for inv in expenses:
        total_count += 1
        line(f"[EXPENSE] {inv.invoice_number} | {inv.date} | PM: {inv.payment_method} | Total: {float(inv.total_after_tax_discount or 0):.2f}")

    if total_count == 0:
        line("No invoices older than 12 months / لا توجد فواتير أقدم من 12 شهراً", size=12)

    p.showPage(); p.save(); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"invoices_retention_{cutoff}.pdf", mimetype='application/pdf')

@app.route('/users')
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

    # Build rows from specialized invoice tables to avoid reliance on unified Invoice table
    from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice
    section_norm = (section or 'all').lower()
    if section_norm in ['purchases', 'purchase']: section_norm = 'purchase'
    elif section_norm in ['expenses', 'expense']: section_norm = 'expense'
    elif section_norm in ['sales', 'sale']: section_norm = 'sales'
    else: section_norm = 'all'
    rows = []
    if section_norm in ['all','sales']:
        for s in SalesInvoice.query.order_by(SalesInvoice.date.desc()).all():
            rows.append({'invoice_number': s.invoice_number, 'who': s.customer_name or '-', 'total': float(s.total_after_tax_discount or 0), 'status': s.status})
    if section_norm in ['all','purchase']:
        for p in PurchaseInvoice.query.order_by(PurchaseInvoice.date.desc()).all():
            rows.append({'invoice_number': p.invoice_number, 'who': p.supplier_name or '-', 'total': float(p.total_after_tax_discount or 0), 'status': p.status})
    if section_norm in ['all','expense']:
        for e in ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).all():
            rows.append({'invoice_number': e.invoice_number, 'who': '-', 'total': float(e.total_after_tax_discount or 0), 'status': e.status})

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
        p.drawString(40, y, shape_ar(company_name or "Company"))
        y -= 22
        p.setFont(ar_font, 12)
        p.drawString(40, y, shape_ar(f"Invoices - {section_norm.title()}"))
    else:
        p.setFont("Helvetica-Bold", 14)
        p.drawString(40, y, company_name or "Company")
        y -= 22
        p.setFont("Helvetica", 12)
        p.drawString(40, y, f"Invoices - {section_norm.title()}")
    y -= 20

    # Table header
    if ar_font:
        p.setFont(ar_font, 11)
    else:
        p.setFont("Helvetica-Bold", 11)
    p.drawString(40, y, shape_ar("Invoice"))
    p.drawString(140, y, shape_ar("Who"))
    p.drawRightString(380, y, shape_ar("Total"))
    p.drawString(400, y, shape_ar("Status"))
    y -= 14
    p.line(40, y, 520, y)
    y -= 10

    # Body rows
    if ar_font:
        p.setFont(ar_font, 10)
    else:
        p.setFont("Helvetica", 10)
    for r in rows:
        if y < 60:
            p.showPage()
            if ar_font:
                p.setFont(ar_font, 10)
            else:
                p.setFont("Helvetica", 10)
            y = 800
        p.drawString(40, y, shape_ar(str(r.get('invoice_number') or '')))
        p.drawString(140, y, shape_ar(str(r.get('who') or '-')))
        p.drawRightString(380, y, f"{float(r.get('total') or 0):.2f}")
        status = str(r.get('status') or '').title()
        p.drawString(400, y, shape_ar(status))
        y -= 14

    p.showPage()
    p.save()
    buffer.seek(0)
    return make_response(buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'inline; filename="invoices_{section_norm}.pdf"'
    })

@app.route('/sales/<int:invoice_id>/print', methods=['GET'])
@login_required
def print_sales_receipt(invoice_id:int):
    # Receipt-style (80mm) print for a single sales invoice
    inv = SalesInvoice.query.get_or_404(invoice_id)
    items = SalesInvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    try:
        from models import Settings
        s = Settings.query.first()
        company_name = (s.company_name or '').strip() if s and s.company_name else 'Company'
        tax_number = (s.tax_number or '').strip() if s and s.tax_number else None
        phone = (s.phone or '').strip() if s and s.phone else None
        currency = s.currency if s and s.currency else 'SAR'
    except Exception:
        company_name, tax_number, phone, currency = 'Company', None, None, 'SAR'
    logo_url = url_for('static', filename='logo.svg', _external=False)
    return render_template('print/receipt.html',
        company_name=company_name,
        tax_number=tax_number,
        phone=phone,
        currency=currency,
        logo_url=logo_url,
        inv=inv,
        items=items,
    )

    # Body rows
    if ar_font:
        p.setFont(ar_font, 10)
    else:
        p.setFont("Helvetica", 10)
    for r in rows:
        line = f"{r['invoice_number']} | {r['who']} | {r['total']:.2f} | {r['status']}"
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
    # Single payment against unified Invoice table (legacy). If not exists, fall back to specialized tables mapping.
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
    except Exception:
        # Fallback: attempt to locate in specialized invoices (use first match by id) and mirror minimal fields
        from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice
        invoice = SalesInvoice.query.get(invoice_id) or PurchaseInvoice.query.get(invoice_id) or ExpenseInvoice.query.get(invoice_id)
        if not invoice:
            abort(404)
    payment_amount = float(request.form.get('payment_amount', 0))

    if payment_amount > 0:
        invoice.paid_amount += payment_amount
        invoice.update_status()
        safe_db_commit()

        # Emit real-time update
        if socketio:
            socketio.emit('invoice_update', {
                'invoice_id': invoice_id,
                'new_status': invoice.status,
                'paid_amount': invoice.paid_amount
            })

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

        safe_db_commit()

        # Emit real-time update
        if socketio:
            socketio.emit('invoice_update', {
                'bulk_update': True,
                'updated_invoices': invoice_ids
            })

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
        safe_db_commit()

        flash(_('Raw material added successfully / تم إضافة المادة الخام بنجاح'), 'success')
        return redirect(url_for('raw_materials'))

    materials = RawMaterial.query.filter_by(active=True).all()
    return render_template('raw_materials.html', form=form, materials=materials)

# Meals Management
@app.route('/meals', methods=['GET', 'POST'])
@login_required
def meals():
    import json
    # Local imports to avoid NameError when global imports are not executed
    from models import RawMaterial, Meal, MealIngredient

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
        try:
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

            # Add ingredients and calculate total cost (robust parse from POST to support dynamic rows)
            from decimal import Decimal
            total_cost = 0
            # Find all indices in POST like ingredients-<i>-raw_material_id
            idxs = set()
            for k in request.form.keys():
                if k.startswith('ingredients-') and k.endswith('-raw_material_id'):
                    try:
                        idxs.add(int(k.split('-')[1]))
                    except Exception:
                        pass
            for i in sorted(idxs):
                try:
                    rm_id = int(request.form.get(f'ingredients-{i}-raw_material_id') or 0)
                    qty_raw = request.form.get(f'ingredients-{i}-quantity')
                    qty = Decimal(qty_raw) if qty_raw not in (None, '',) else Decimal('0')
                except Exception:
                    rm_id, qty = 0, Decimal('0')
                if rm_id and qty > 0:
                    raw_material = RawMaterial.query.get(rm_id)
                    if raw_material:
                        ingredient = MealIngredient(
                            meal_id=meal.id,
                            raw_material_id=raw_material.id,
                            quantity=qty
                        )
                        # Compute cost directly using the fetched raw_material to avoid lazy-load issues
                        try:
                            from decimal import Decimal
                            ing_cost = qty * raw_material.cost_per_unit
                            ingredient.total_cost = ing_cost
                        except Exception:
                            ingredient.total_cost = 0
                        db.session.add(ingredient)
                        total_cost += float(ingredient.total_cost)

            # Update meal costs
            meal.total_cost = total_cost
            meal.calculate_selling_price()

            safe_db_commit()

            # Emit real-time update
            if socketio:
                socketio.emit('meal_update', {
                    'meal_name': meal.display_name,
                    'total_cost': float(meal.total_cost),
                    'selling_price': float(meal.selling_price)
                })

            flash(_('Meal created successfully / تم إنشاء الوجبة بنجاح'), 'success')
            return redirect(url_for('meals'))
        except Exception as e:
            db.session.rollback()
            logging.exception('Failed to save meal')
            flash(_('Failed to save meal / فشل حفظ الوجبة'), 'danger')

    # Get all meals
    all_meals = Meal.query.filter_by(active=True).all()
    return render_template('meals.html', form=form, meals=all_meals, materials_json=materials_json)

# Delete routes
@app.route('/delete_raw_material/<int:material_id>', methods=['POST'])
@login_required
def delete_raw_material(material_id):
    # Ensure required models are available even if globals change
    from models import RawMaterial, MealIngredient, PurchaseInvoiceItem

    material = RawMaterial.query.get_or_404(material_id)

    # Check if material is used in any meals
    try:
        meals_using_material = MealIngredient.query.filter_by(raw_material_id=material_id).all()
    except Exception:
        meals_using_material = []
    if meals_using_material:
        # Be robust if some relations are missing
        meal_names = []
        for ingredient in meals_using_material:
            try:
                if getattr(ingredient, 'meal', None) and getattr(ingredient.meal, 'display_name', None):
                    meal_names.append(ingredient.meal.display_name)
                else:
                    meal_names.append(str(getattr(ingredient, 'meal_id', 'Unknown')))
            except Exception:
                meal_names.append('Unknown')
        flash(_('Cannot delete material. It is used in meals: {}').format(', '.join(meal_names)), 'warning')
        return redirect(url_for('raw_materials'))

    # Check if material is used in any purchase invoices
    try:
        purchase_items = PurchaseInvoiceItem.query.filter_by(raw_material_id=material_id).all()
    except Exception:
        purchase_items = []
    if purchase_items:
        flash(_('Cannot delete material. It has purchase history. Material will be deactivated instead.'), 'warning')
        material.active = False
    else:
        db.session.delete(material)

    safe_db_commit()
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

    safe_db_commit()
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
    safe_db_commit()

    # Signal UI of purchases page to refresh after deletion when coming from invoices
    referer = request.headers.get('Referer', '')
    if 'invoices' in referer:
        # If user deleted from All Invoices page, go back there but with flash that purchases should update
        return redirect(url_for('invoices', type='purchase'))

    flash(_('Purchase invoice deleted and stock updated / تم حذف فاتورة الشراء وتحديث المخزون'), 'success')
    return redirect(url_for('purchases'))

@app.route('/delete_sales_invoice/<int:invoice_id>', methods=['POST'])
@login_required
def delete_sales_invoice(invoice_id):
    # Check for password in form data
    password = request.form.get('password', '').strip()
    if password != '1991':
        flash(_('Incorrect password / كلمة السر غير صحيحة'), 'danger')
        return redirect(url_for('sales'))

    invoice = SalesInvoice.query.get_or_404(invoice_id)

    # Delete related payments first
    try:
        Payment.query.filter_by(invoice_id=invoice_id, invoice_type='sales').delete()
    except:
        pass  # Payment table might not exist in some setups

    # Delete invoice items first
    SalesInvoiceItem.query.filter_by(invoice_id=invoice_id).delete()

    # Delete invoice
    db.session.delete(invoice)
    safe_db_commit()

    flash(_('Sales invoice deleted successfully / تم حذف فاتورة المبيعات بنجاح'), 'success')

    # Check if request came from payments page
    referer = request.headers.get('Referer', '')
    if 'payments' in referer:
        return redirect(url_for('payments'))
    else:
        return redirect(url_for('sales'))

@app.route('/delete_expense_invoice/<int:invoice_id>', methods=['POST'])
@login_required
def delete_expense_invoice(invoice_id):
    invoice = ExpenseInvoice.query.get_or_404(invoice_id)

    # Delete related payments first
    try:
        Payment.query.filter_by(invoice_id=invoice_id, invoice_type='expense').delete()
    except:
        pass

    # Delete invoice items first
    ExpenseInvoiceItem.query.filter_by(invoice_id=invoice_id).delete()

    # Delete invoice
    db.session.delete(invoice)
    safe_db_commit()

    flash(_('Expense invoice deleted successfully / تم حذف فاتورة المصروفات بنجاح'), 'success')

    # Check if request came from payments page
    referer = request.headers.get('Referer', '')
    if 'payments' in referer:
        return redirect(url_for('payments'))
    else:
        return redirect(url_for('expenses'))

# Health check endpoint
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'message': 'App is running'})

# Optional local-only debug endpoint to view recent error logs
if os.getenv('ENABLE_DEBUG_LOGS_ROUTE', '0').lower() in ('1', 'true', 'yes'):
    @app.route('/__debug/logs')
    def debug_logs():
        try:
            from flask import request, Response
            # Restrict in production: allow only localhost or when not production
            if app.config.get('ENV') == 'production' and request.remote_addr not in ('127.0.0.1', '::1'):
                return "Forbidden", 403
            log_path = os.path.join('logs', 'local-errors.log')
            lines = int(request.args.get('n', 200))
            if not os.path.exists(log_path):
                return jsonify({'ok': True, 'message': 'log file not found yet', 'path': log_path}), 200
            # Read last N lines efficiently
            def tail(fname, n):
                try:
                    with open(fname, 'rb') as f:
                        f.seek(0, os.SEEK_END)
                        size = f.tell()
                        block = -1024
                        data = b''
                        while n > 0 and -block < size:
                            f.seek(block, os.SEEK_END)
                            data = f.read(-block) + data
                            n -= data.count(b'\n')
                            block *= 2
                        return b"\n".join(data.splitlines()[-int(request.args.get('n', 200)):]).decode('utf-8', errors='replace')
                except Exception as e:
                    return f"error reading log: {e}"
            content = tail(log_path, lines)
            return Response(content, mimetype='text/plain')
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

# Test endpoint for debugging dependencies
@app.route('/test-dependencies')
def test_dependencies():
    """Test endpoint to check if pandas and other dependencies are available"""
    results = {}

    # Test pandas
    try:
        import pandas as pd
        results['pandas'] = {'status': 'OK', 'version': pd.__version__}
    except ImportError as e:
        results['pandas'] = {'status': 'MISSING', 'error': str(e)}
    except Exception as e:
        results['pandas'] = {'status': 'ERROR', 'error': str(e)}

    # Test openpyxl
    try:
        import openpyxl
        results['openpyxl'] = {'status': 'OK', 'version': openpyxl.__version__}
    except ImportError as e:
        results['openpyxl'] = {'status': 'MISSING', 'error': str(e)}
    except Exception as e:
        results['openpyxl'] = {'status': 'ERROR', 'error': str(e)}

    # Test Flask-Babel
    try:
        from flask_babel import gettext as _
        test_msg = _('Test message')
        results['flask_babel'] = {'status': 'OK', 'test': test_msg}
    except ImportError as e:
        results['flask_babel'] = {'status': 'MISSING', 'error': str(e)}
    except Exception as e:
        results['flask_babel'] = {'status': 'ERROR', 'error': str(e)}

    return jsonify(results)

# App is already initialized above

# =========================
# Protected Delete API Routes
# =========================

@app.route('/api/items/<int:item_id>/delete', methods=['POST'])
@login_required
def api_delete_item(item_id):
    """Delete a single menu item with password protection"""
    try:
        data = request.get_json(silent=True) or request.form
        if not verify_admin_password(data.get('password')):
            return jsonify({'ok': False, 'error': 'invalid_password'}), 403

        from models import MenuItem
        item = MenuItem.query.get_or_404(item_id)
        db.session.delete(item)
        safe_db_commit()
        return jsonify({'ok': True, 'message': 'Item deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/items/delete-all', methods=['POST'])
@login_required
def api_delete_all_items():
    """Delete all menu items with password protection"""
    try:
        data = request.get_json(silent=True) or request.form
        if not verify_admin_password(data.get('password')):
            return jsonify({'ok': False, 'error': 'invalid_password'}), 403

        from models import MenuItem
        count = MenuItem.query.count()
        MenuItem.query.delete()
        safe_db_commit()
        return jsonify({'ok': True, 'deleted': count, 'message': f'Deleted {count} items'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/meals/<int:meal_id>/delete', methods=['POST'])
@login_required
def api_delete_meal(meal_id):
    """Delete a single meal with password protection"""
    try:
        data = request.get_json(silent=True) or request.form
        if not verify_admin_password(data.get('password')):
            return jsonify({'ok': False, 'error': 'invalid_password'}), 403

        meal = Meal.query.get_or_404(meal_id)

        # Check if meal is used in any sales invoices
        sales_items = SalesInvoiceItem.query.filter_by(product_name=meal.display_name).all()
        if sales_items:
            meal.active = False
            safe_db_commit()
            return jsonify({'ok': True, 'deactivated': True, 'message': 'Meal deactivated (has sales history)'})
        else:
            # Delete meal ingredients first
            MealIngredient.query.filter_by(meal_id=meal_id).delete()
            db.session.delete(meal)
            safe_db_commit()
            return jsonify({'ok': True, 'deleted': True, 'message': 'Meal deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/meals/delete-all', methods=['POST'])
@login_required
def api_delete_all_meals():
    """Delete all meals with password protection"""
    try:
        data = request.get_json(silent=True) or request.form
        if not verify_admin_password(data.get('password')):
            return jsonify({'ok': False, 'error': 'invalid_password'}), 403

        # Get count before deletion
        count = Meal.query.count()

        # Delete all meal ingredients first
        MealIngredient.query.delete()
        # Delete all meals
        Meal.query.delete()
        safe_db_commit()
        return jsonify({'ok': True, 'deleted': count, 'message': f'Deleted {count} meals'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
# =========================
# Print and Payment API Routes
# =========================

@app.route('/invoice/<int:invoice_id>/print', methods=['GET'])
@login_required
def print_invoice(invoice_id: int):
    """Print thermal receipt with ZATCA QR, KSA time, and branch-prefixed invoice number."""
    # Local import to avoid NameError in some environments
    from models import SalesInvoice, SalesInvoiceItem

    inv = SalesInvoice.query.get_or_404(invoice_id)
    items = SalesInvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    settings = get_settings_safe()

    # Mark invoice as paid upon print (to match live behavior)
    try:
        if (inv.status or '').lower() != 'paid':
            inv.status = 'paid'
            safe_db_commit()
    except Exception:
        reset_db_session()

    # Saudi local time for display
    try:
        dt_obj = getattr(inv, 'created_at', None)
        if dt_obj:
            dt_ksa = dt_obj.astimezone(KSA_TZ)
        else:
            dt_ksa = get_saudi_now()
        date_time = dt_ksa.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        from datetime import datetime as _dt
        import pytz as _pytz
        date_time = _dt.now(_pytz.timezone('Asia/Riyadh')).strftime('%Y-%m-%d %H:%M:%S')

    # Branch name (UPPERCASE for print) and branch/year sequence-based invoice number
    branch_upper_map = {'china_town': 'CHINA TOWN', 'place_india': 'PALACE INDIA'}
    branch_name = branch_upper_map.get(inv.branch, (inv.branch or '').upper())
    prefix = 'CT' if inv.branch == 'china_town' else ('PI' if inv.branch == 'place_india' else 'INV')
    try:
        year = inv.date.year if getattr(inv, 'date', None) else get_saudi_now().year
    except Exception:
        year = get_saudi_now().year
    # Compute sequential number per branch/year up to this invoice
    try:
        from datetime import date as _date
        from sqlalchemy import func
        start_date = _date(year, 1, 1)
        end_date = _date(year, 12, 31)
        seq = db.session.query(func.count(SalesInvoice.id)).filter(
            SalesInvoice.branch == inv.branch,
            SalesInvoice.date >= start_date,
            SalesInvoice.date <= end_date,
            SalesInvoice.id <= inv.id
        ).scalar() or 1
    except Exception:
        seq = int(inv.id or 1)
    display_invoice_number = f"{prefix}-{year}-{int(seq):03d}"

    # ZATCA TLV QR (seller(1), vat(2), timestamp(3), total(4), vat amount(5))
    qr_data_url = None
    try:
        import base64, io, qrcode
        def _tlv(tag, b):
            return bytes([tag & 0xFF, len(b) & 0xFF]) + b
        seller = (getattr(settings, 'company_name', '') or '').encode('utf-8')
        vat_no = (getattr(settings, 'tax_number', '') or '').encode('utf-8')
        ts = dt_ksa.isoformat(timespec='seconds').encode('utf-8')
        total_b = (f"{float(inv.total_after_tax_discount or 0):.2f}").encode('utf-8')
        vat_b = (f"{float(inv.tax_amount or 0):.2f}").encode('utf-8')
        payload_b64 = base64.b64encode(_tlv(1, seller) + _tlv(2, vat_no) + _tlv(3, ts) + _tlv(4, total_b) + _tlv(5, vat_b)).decode('ascii')
        img = qrcode.make(payload_b64)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_data_url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        qr_data_url = None

    return render_template(
        'print/receipt.html',
        inv=inv,
        items=items,
        settings=settings,
        date_time=date_time,
        branch_name=branch_name,
        display_invoice_number=display_invoice_number,
        qr_data_url=qr_data_url
    )
@app.route('/invoices/<int:invoice_id>/print-preview')
@login_required
def print_unpaid_invoice(invoice_id):
    # Local import to avoid NameError in some deployments
    from models import SalesInvoice, SalesInvoiceItem

    """Print preview before payment without marking invoice as paid."""
    try:
        inv = SalesInvoice.query.get_or_404(invoice_id)
        items = SalesInvoiceItem.query.filter_by(invoice_id=invoice_id).all()
        settings = get_settings_safe()

        # Saudi local time for display (without changing invoice status)
        try:
            dt_obj = getattr(inv, 'created_at', None)
            if dt_obj:
                dt_ksa = dt_obj.astimezone(KSA_TZ)
            else:
                dt_ksa = get_saudi_now()
            date_time = dt_ksa.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            from datetime import datetime as _dt
            import pytz as _pytz
            date_time = _dt.now(_pytz.timezone('Asia/Riyadh')).strftime('%Y-%m-%d %H:%M:%S')

        branch_upper_map = {'china_town': 'CHINA TOWN', 'place_india': 'PALACE INDIA'}
        branch_name = branch_upper_map.get(inv.branch, (inv.branch or '').upper())
        prefix = 'CT' if inv.branch == 'china_town' else ('PI' if inv.branch == 'place_india' else 'INV')
        try:
            year = inv.date.year if getattr(inv, 'date', None) else get_saudi_now().year
        except Exception:
            year = get_saudi_now().year
        try:
            from datetime import date as _date
            from sqlalchemy import func
            start_date = _date(year, 1, 1)
            end_date = _date(year, 12, 31)
            seq = db.session.query(func.count(SalesInvoice.id)).filter(
                SalesInvoice.branch == inv.branch,
                SalesInvoice.date >= start_date,
                SalesInvoice.date <= end_date,
                SalesInvoice.id <= inv.id
            ).scalar() or 1
        except Exception:
            seq = int(inv.id or 1)
        display_invoice_number = f"{prefix}-{year}-{int(seq):03d}"

        # Build ZATCA TLV QR (same as print_invoice)
        qr_data_url = None
        try:
            import base64, io, qrcode
            def _tlv(tag, b):
                return bytes([tag & 0xFF, len(b) & 0xFF]) + b
            seller = (getattr(settings, 'company_name', '') or '').encode('utf-8')
            vat_no = (getattr(settings, 'tax_number', '') or '').encode('utf-8')
            ts = dt_ksa.isoformat(timespec='seconds').encode('utf-8')
            total_b = (f"{float(inv.total_after_tax_discount or 0):.2f}").encode('utf-8')
            vat_b = (f"{float(inv.tax_amount or 0):.2f}").encode('utf-8')
            payload_b64 = base64.b64encode(_tlv(1, seller) + _tlv(2, vat_no) + _tlv(3, ts) + _tlv(4, total_b) + _tlv(5, vat_b)).decode('ascii')
            img = qrcode.make(payload_b64)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            qr_data_url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
        except Exception:
            qr_data_url = None

        return render_template(
            'print/receipt.html',
            inv=inv,
            items=items,
            settings=settings,
            date_time=date_time,
            branch_name=branch_name,
            display_invoice_number=display_invoice_number,
            qr_data_url=qr_data_url,
            preview=True
        )
    except Exception as e:
        flash(_('Error loading invoice / خطأ في تحميل الفاتورة'), 'danger')
        return redirect(url_for('invoices'))

@app.route('/invoices/<int:invoice_id>/pay-and-print', methods=['POST'])
@login_required
def pay_and_print_invoice(invoice_id):
    """Process payment and return print URL"""
    # Local import to avoid NameError
    from models import SalesInvoice
    try:
        invoice = SalesInvoice.query.get_or_404(invoice_id)

        # Mark as paid if not already
        if invoice.status != 'paid':
            invoice.status = 'paid'
            safe_db_commit()

        return jsonify({
            'ok': True,
            'print_url': url_for('print_unpaid_invoice', invoice_id=invoice_id),
            'message': 'Payment processed successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/fix-db-complete')
def fix_database_complete():
    """Complete database fix without login requirement"""
    try:
        from sqlalchemy import text

        # Complete list of missing Settings columns
        missing_columns = [
            ("default_theme", "VARCHAR(50) DEFAULT 'light'"),
            ("china_town_void_password", "VARCHAR(50) DEFAULT '1991'"),
            ("place_india_void_password", "VARCHAR(50) DEFAULT '1991'"),
            ("china_town_vat_rate", "FLOAT DEFAULT 15.0"),
            ("place_india_vat_rate", "FLOAT DEFAULT 15.0"),
            ("china_town_discount_rate", "FLOAT DEFAULT 0.0"),
            ("place_india_discount_rate", "FLOAT DEFAULT 0.0"),
            ("receipt_paper_width", "VARCHAR(10) DEFAULT '80'"),
            ("receipt_margin_top_mm", "INTEGER DEFAULT 5"),
            ("receipt_margin_bottom_mm", "INTEGER DEFAULT 5"),
            ("receipt_margin_left_mm", "INTEGER DEFAULT 5"),
            ("receipt_margin_right_mm", "INTEGER DEFAULT 5"),
            ("receipt_font_size", "INTEGER DEFAULT 12"),
            ("receipt_show_logo", "BOOLEAN DEFAULT TRUE"),
            ("receipt_show_tax_number", "BOOLEAN DEFAULT TRUE"),
            ("receipt_footer_text", "TEXT DEFAULT 'شكراً لزيارتكم'"),
            ("logo_url", "VARCHAR(255)"),
                    ("china_town_logo_url", "VARCHAR(255)"),
                    ("place_india_logo_url", "VARCHAR(255)"),
            ("receipt_logo_height", "INTEGER DEFAULT 72"),
            ("receipt_extra_bottom_mm", "INTEGER DEFAULT 15"),
            ("china_town_phone1", "VARCHAR(50)"),
            ("china_town_phone2", "VARCHAR(50)"),
            ("place_india_phone1", "VARCHAR(50)"),
            ("place_india_phone2", "VARCHAR(50)")
        ]

        results = []

        # Add missing columns
        for col_name, col_def in missing_columns:
            try:
                sql = f"ALTER TABLE settings ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                db.session.execute(text(sql))
                db.session.commit()
                results.append(f"✅ Added column: {col_name}")
            except Exception as e:
                db.session.rollback()
                results.append(f"⚠️ Column {col_name}: {str(e)[:50]}...")

        # Create default settings if none exist
        try:
            settings_count = db.session.execute(text("SELECT COUNT(*) FROM settings")).scalar()
            if settings_count == 0:
                insert_sql = """
                INSERT INTO settings (
                    company_name, tax_number, address, phone, email, vat_rate, currency,
                    china_town_label, place_india_label, default_theme,
                    china_town_void_password, place_india_void_password,
                    china_town_vat_rate, place_india_vat_rate,
                    china_town_discount_rate, place_india_discount_rate,
                    receipt_paper_width, receipt_font_size, receipt_show_logo, receipt_show_tax_number,
                    receipt_footer_text, receipt_logo_height, receipt_extra_bottom_mm
                ) VALUES (
                    'مطعم الصين وقصر الهند', '123456789', 'الرياض، المملكة العربية السعودية',
                    '0112345678', 'info@restaurant.com', 15.0, 'SAR',
                    'CHINA TOWN', 'PLACE INDIA', 'light',
                    'thermal', '/static/currency.png', 'THANK YOU FOR VISIT',
                    '1991', 15.0, 0.0,
                    '1991', 15.0, 0.0,
                    '80', 5, 5, 3, 3, 12, TRUE, TRUE, 'THANK YOU FOR VISIT', 72, 15
                )
                """
                db.session.execute(text(insert_sql))
                db.session.commit()
                results.append("✅ Created default settings record")
            else:
                results.append(f"✅ Settings record exists ({settings_count} records)")
        except Exception as e:
            db.session.rollback()
            results.append(f"⚠️ Settings creation error: {str(e)[:50]}...")

        return jsonify({
            'success': True,
            'message': 'Complete database schema fixed',
            'results': results
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/create-sample-data')
def create_sample_data_route():
    """Route to create sample data for testing - No login required for testing"""
    try:
        from models import Settings, Employee, RawMaterial, User
        create_sample_data()
        return jsonify({
            'success': True,
            'message': 'Sample data created successfully / تم إنشاء البيانات التجريبية بنجاح',
            'data': {
                'settings': Settings.query.count(),
                'employees': Employee.query.count(),
                'raw_materials': RawMaterial.query.count(),
                'meals': Meal.query.count()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
def create_sample_data():
    """Create comprehensive sample data for testing"""
    try:
        # Create default settings if none exist
        from models import Settings, Employee, RawMaterial, User
        if not Settings.query.first():
            settings = Settings(
                company_name='مطعم الصين وقصر الهند',
                tax_number='123456789',
                address='الرياض، المملكة العربية السعودية',
                phone='0112345678',
                email='info@restaurant.com',
                vat_rate=15.0,
                currency='SAR',
                china_town_label='China Town',
                place_india_label='Palace India',
                china_town_void_password='1991',
                place_india_void_password='1991',
                china_town_vat_rate=15.0,
                place_india_vat_rate=15.0,
                china_town_discount_rate=0.0,
                place_india_discount_rate=0.0,
                receipt_paper_width='80',
                receipt_font_size=12,
                receipt_logo_height=72,
                receipt_extra_bottom_mm=15,
                receipt_show_tax_number=True,
                receipt_footer_text='شكراً لزيارتكم - Thank you for visiting',
                # New unified print/currency settings
                printer_type='thermal',
                currency_image='static/images/sar-currency.svg',
                footer_message='THANK YOU FOR VISIT'
            )
            db.session.add(settings)
            print("✅ Default settings created")

        # Create sample employees if none exist
        if Employee.query.count() == 0:
            from models import EmployeeSalaryDefault

            sample_employees = [
                {
                    'employee_code': 'EMP001',
                    'full_name': 'أحمد محمد علي',
                    'national_id': '1234567890',
                    'department': 'المطبخ',
                    'position': 'طباخ رئيسي',
                    'phone': '0501234567',
                    'email': 'ahmed@restaurant.com',
                    'hire_date': datetime.now().date(),
                    'status': 'active'
                },
                {
                    'employee_code': 'EMP002',
                    'full_name': 'فاطمة أحمد',
                    'national_id': '0987654321',
                    'department': 'الخدمة',
                    'position': 'نادلة',
                    'phone': '0509876543',
                    'email': 'fatima@restaurant.com',
                    'hire_date': datetime.now().date(),
                    'status': 'active'
                },
                {
                    'employee_code': 'EMP003',
                    'full_name': 'محمد سالم',
                    'national_id': '1122334455',
                    'department': 'الإدارة',
                    'position': 'مشرف',
                    'phone': '0501122334',
                    'email': 'mohammed@restaurant.com',
                    'hire_date': datetime.now().date(),
                    'status': 'active'
                },
                {
                    'employee_code': 'EMP004',
                    'full_name': 'سارة خالد',
                    'national_id': '5566778899',
                    'department': 'المحاسبة',
                    'position': 'محاسبة',
                    'phone': '0505566778',
                    'email': 'sara@restaurant.com',
                    'hire_date': datetime.now().date(),
                    'status': 'active'
                }
            ]

            for emp_data in sample_employees:
                emp = Employee(**emp_data)
                db.session.add(emp)
                db.session.flush()  # Get the ID

                # Add default salary
                salary_default = EmployeeSalaryDefault(
                    employee_id=emp.id,
                    base_salary=5000.0,
                    allowances=500.0,
                    deductions=100.0
                )
                db.session.add(salary_default)

            print("✅ Sample employees created")

        # Add some raw materials for inventory
        if RawMaterial.query.count() < 5:
            raw_materials = [
                {
                    'name': 'Rice',
                    'name_ar': 'أرز',
                    'unit': 'kg',
                    'cost_per_unit': 5.0,
                    'stock_quantity': 100.0,
                    'category': 'Grains',
                    'active': True
                },
                {
                    'name': 'Chicken',
                    'name_ar': 'دجاج',
                    'unit': 'kg',
                    'cost_per_unit': 15.0,
                    'stock_quantity': 50.0,
                    'category': 'Meat',
                    'active': True
                }
            ]

            for material_data in raw_materials:
                if not RawMaterial.query.filter_by(name=material_data['name']).first():
                    material = RawMaterial(**material_data)
                    db.session.add(material)

            print("✅ Raw materials added")

        # Create admin user if none exists - FORCE CREATE
        existing_admin = User.query.filter_by(username='admin').first()
        if not existing_admin:
            admin = User(
                username='admin',
                email='admin@restaurant.com',
                role='admin',
                active=True
            )
            admin.set_password('admin', bcrypt)
            db.session.add(admin)
            print("✅ Admin user created (username: admin, password: admin)")
        else:
            # Update existing admin password to ensure it works
            existing_admin.set_password('admin', bcrypt)
            print("✅ Admin password updated (username: admin, password: admin)")

        # Ensure POS menu categories, meals, and menu items exist for testing/demo
        try:
            from models import MenuCategory, MenuItem, Meal, User
            # Ensure at least a creator user exists
            creator = User.query.filter_by(username='admin').first() or User.query.first()
            if MenuCategory.query.count() == 0:
                cats = [
                    MenuCategory(name='Main Dishes', active=True),
                    MenuCategory(name='Appetizers', active=True),
                    MenuCategory(name='Drinks', active=True),
                ]
                for c in cats:
                    db.session.add(c)
                db.session.flush()
                print("✅ Menu categories created")
            # Create a few meals if none exist
            if Meal.query.count() == 0 and creator:
                sample_meals = [
                    dict(name='Chicken Biryani', name_ar='برياني دجاج', category='Main Dishes', selling_price=25.0),
                    dict(name='Spring Rolls', name_ar='سبرنغ رولز', category='Appetizers', selling_price=12.0),
                    dict(name='Lemon Mint', name_ar='ليمون بالنعناع', category='Drinks', selling_price=10.0),
                ]
                for m in sample_meals:
                    meal = Meal(
                        name=m['name'], name_ar=m['name_ar'], category=m['category'],
                        total_cost=0.0, profit_margin_percent=30.0, selling_price=m['selling_price'],
                        active=True, user_id=creator.id
                    )
                    db.session.add(meal)
                db.session.flush()
                print("✅ Sample meals created")
            # Link meals to categories via MenuItem if none exist
            if MenuItem.query.count() == 0:
                # Build category map
                cat_map = {c.name: c.id for c in MenuCategory.query.all()}
                for meal in Meal.query.filter_by(active=True).all():
                    cat_id = cat_map.get(meal.category) or next(iter(cat_map.values()), None)
                    if not cat_id:
                        continue
                    exists = MenuItem.query.filter_by(category_id=cat_id, meal_id=meal.id).first()
                    if not exists:
                        db.session.add(MenuItem(category_id=cat_id, meal_id=meal.id, price_override=None, display_order=meal.id))
                print("✅ Menu items linked")
        except Exception as _e:
            print(f"⚠️ POS menu seed warning: {_e}")

        # Commit all changes
        db.session.commit()
        print("✅ All sample data created successfully")

    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        db.session.rollback()
        raise e

# Monthly PDF report for all branches
@app.route('/reports/invoices/monthly/pdf', endpoint='all_branches_invoices_pdf_monthly')
@login_required
def all_branches_invoices_pdf_monthly():
    month_str = request.args.get('month')  # YYYY-MM
    if not month_str:
        return 'Month parameter is required', 400
    try:
        year, month = map(int, month_str.split('-'))
    except Exception:
        return 'Invalid month format', 400

    # KSA timezone window
    from datetime import datetime as _dt
    import pytz as _pytz
    tz = _pytz.timezone('Asia/Riyadh')
    start_date = _dt(year, month, 1, 0, 0, 0, tzinfo=tz)
    end_date = _dt(year + (1 if month == 12 else 0), (1 if month == 12 else month + 1), 1, 0, 0, 0, tzinfo=tz)

    # Build PDF
    from collections import defaultdict
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Branch list
    try:
        branches = db.session.query(SalesInvoice.branch).distinct().all()
        branch_list = [b[0] for b in branches if b and b[0]]
    except Exception:
        branch_list = ['china_town', 'place_india']

    for bcode in branch_list:
        invoices = SalesInvoice.query.filter(
            SalesInvoice.branch == bcode,
            SalesInvoice.created_at >= start_date,
            SalesInvoice.created_at < end_date,
            SalesInvoice.status.in_(['paid', 'posted'])
        ).all()
        if not invoices:
            continue

        bname = {'china_town': 'CHINA TOWN', 'place_india': 'PALACE INDIA'}.get(bcode, (bcode or '').upper())
        elements.append(Paragraph(f'Branch: {bname}', styles['Title']))
        elements.append(Paragraph(f"Month: {start_date.strftime('%B %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        table_data = [["Invoice No", "Date", "Product", "Qty", "Price Before Tax", "Tax", "Total", "Payment Method"]]
        total_qty = 0.0
        total_before_tax = 0.0
        total_tax = 0.0
        total_amount = 0.0
        payment_summary = defaultdict(float)
        item_summary = defaultdict(float)

        for inv in invoices:
            pm = inv.payment_method or (inv.payments[0].payment_method if getattr(inv, 'payments', None) else '-')
            for it in inv.items:
                table_data.append([
                    inv.invoice_number,
                    (inv.created_at.astimezone(KSA_TZ).strftime('%Y-%m-%d %H:%M') if getattr(inv, 'created_at', None) else str(inv.date)),
                    it.product_name,
                    float(it.quantity or 0),
                    f"{float(it.price_before_tax or 0):.2f}",
                    f"{float(it.tax or 0):.2f}",
                    f"{float(it.total_price or 0):.2f}",
                    pm
                ])
                total_qty += float(it.quantity or 0)
                total_before_tax += float(it.price_before_tax or 0) * float(it.quantity or 0)
                total_tax += float(it.tax or 0)
                total_amount += float(it.total_price or 0)
                payment_summary[pm] += float(it.total_price or 0)
                item_summary[it.product_name] += float(it.quantity or 0)

        table_data.append(["TOTAL", "", "", total_qty, f"{total_before_tax:.2f}", f"{total_tax:.2f}", f"{total_amount:.2f}", ""])
        table = Table(table_data, colWidths=[70, 80, 120, 40, 60, 60, 60, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Payment method summary
        elements.append(Paragraph('Summary by Payment Method', styles['Heading2']))
        pm_data = [["Payment Method", "Total"]] + [[m, f"{a:.2f}"] for m, a in payment_summary.items()]
        pm_table = Table(pm_data, colWidths=[200, 100])
        pm_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(pm_table)
        elements.append(Spacer(1, 12))

        # Product summary
        elements.append(Paragraph('Summary by Product', styles['Heading2']))
        item_data = [["Product", "Total Qty"]] + [[p, q] for p, q in item_summary.items()]
        it_table = Table(item_data, colWidths=[200, 100])
        it_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(it_table)
        elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)
    from flask import send_file
    filename = f"all_branches_invoices_{month_str}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/sales-report')
def sales_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    china_sales = db.session.execute("""
        SELECT date, invoice_no, item, amount, discount, tax, payment_method
        FROM sales
        WHERE branch = 'CHINA TOWN'
    """).fetchall()
    palace_sales = db.session.execute("""
        SELECT date, invoice_no, item, amount, discount, tax, payment_method
        FROM sales
        WHERE branch = 'PALACE INDIA'
    """).fetchall()
    payment_totals = db.session.execute("""
        SELECT payment_method, SUM(amount - discount + tax) as total
        FROM sales
        GROUP BY payment_method
    """).fetchall()
    item_totals = db.session.execute("""
        SELECT item, SUM(amount - discount + tax) as total
        FROM sales
        GROUP BY item
    """).fetchall()
    grand_totals = db.session.execute("""
        SELECT
            SUM(amount) as total_amount,
            SUM(discount) as total_discount,
            SUM(tax) as total_tax,
            SUM(amount - discount + tax) as net_sales
        FROM sales
    """).fetchone()
    return render_template("sales_report.html",
                           china_sales=china_sales,
                           palace_sales=palace_sales,
                           payment_totals=payment_totals,
                           item_totals=item_totals,
                           grand_totals=grand_totals,
                           start_date=start_date,
                           end_date=end_date)

if __name__ == '__main__':
    # Create database tables and sample data first
    with app.app_context():
        try:
            db.create_all()
            create_sample_data()
            print("✅ Database and sample data ready")
        except Exception as e:
            print(f"⚠️ Database setup warning: {e}")

    # Import eventlet and socketio only when running the server
    try:
        if _USE_EVENTLET:
            import eventlet
            eventlet.monkey_patch()

        from flask_socketio import SocketIO
        socketio = SocketIO(app, cors_allowed_origins="*")

        import os as _os
        port = int(_os.getenv('PORT', '5000'))
        print(f"🚀 Starting server on http://127.0.0.1:{port}")
        socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)

    except Exception as e:
        print(f"⚠️ SocketIO failed: {e}")
        print("🔄 Falling back to standard Flask server...")
        import os as _os
        port = int(_os.getenv('PORT', '5000'))
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)