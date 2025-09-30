import json
import os
from datetime import datetime, date, timedelta
from datetime import date as _date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import IntegrityError

from app import db, csrf
from app import __init__ as app_init  # for template globals, including can()
ext_db = None
from app.models import User, AppKV, TableLayout
from models import OrderInvoice
from models import MenuCategory, MenuItem, SalesInvoice, SalesInvoiceItem, Customer, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Settings, Meal, MealIngredient, RawMaterial, Supplier, Employee, Salary, Payment, EmployeeSalaryDefault, DepartmentRate, EmployeeHours
from forms import SalesInvoiceForm, EmployeeForm, ExpenseInvoiceForm, PurchaseInvoiceForm, MealForm, RawMaterialForm

main = Blueprint('main', __name__)
# --- Employees: Detailed Payroll Report (across months with totals) ---
@main.route('/employees/payroll/detailed', methods=['GET'], endpoint='payroll_detailed')
@login_required
def payroll_detailed():
    from datetime import date

    def ym_num(y: int, m: int) -> int:
        return (int(y) * 100) + int(m)

    # Filters
    year_from = int(request.args.get('year_from', date.today().year))
    month_from = int(request.args.get('month_from', 1))
    year_to = int(request.args.get('year_to', date.today().year))
    month_to = int(request.args.get('month_to', date.today().month))
    try:
        employee_ids = [int(eid) for eid in (request.args.getlist('employee_id') or []) if str(eid).isdigit()]
    except Exception:
        employee_ids = []

    start_ym = ym_num(year_from, month_from)
    end_ym = ym_num(year_to, month_to)

    # Employees scope
    try:
        emp_q = Employee.query.order_by(Employee.full_name.asc())
        if employee_ids:
            emp_q = emp_q.filter(Employee.id.in_(employee_ids))
        employees_in_scope = emp_q.all()
    except Exception:
        employees_in_scope = []

    # Defaults map
    try:
        from models import EmployeeSalaryDefault
        defaults_map = {int(d.employee_id): d for d in EmployeeSalaryDefault.query.all()}
    except Exception:
        defaults_map = {}

    # Helper: iterate months
    def month_iter(y0, m0, y1, m1):
        y, m = y0, m0
        cnt = 0
        while (y < y1) or (y == y1 and m <= m1):
            yield y, m
            m += 1
            if m > 12:
                m = 1; y += 1
            cnt += 1
            if cnt > 240:
                break

    by_emp = {}
    totals = {'basic': 0.0, 'allowances': 0.0, 'deductions': 0.0, 'prev_due': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0}

    for emp in (employees_in_scope or []):
        # Determine start from hire date (or start of range if missing)
        if getattr(emp, 'hire_date', None):
            y0, m0 = int(emp.hire_date.year), int(emp.hire_date.month)
        else:
            y0, m0 = year_from, month_from

        # Build dues from hire date to end of range
        dues = []
        sal_ids = []
        for yy, mm in month_iter(y0, m0, year_to, month_to):
            srow = Salary.query.filter_by(employee_id=emp.id, year=yy, month=mm).first()
            if srow:
                base = float(srow.basic_salary or 0.0)
                allow = float(srow.allowances or 0.0)
                ded = float(srow.deductions or 0.0)
                sal_ids.append(int(srow.id))
            else:
                d = defaults_map.get(int(emp.id))
                base = float(getattr(d, 'base_salary', 0.0) or 0.0)
                allow = float(getattr(d, 'allowances', 0.0) or 0.0)
                ded = float(getattr(d, 'deductions', 0.0) or 0.0)
            due_amt = max(0.0, base + allow - ded)
            dues.append({'y': yy, 'm': mm, 'base': base, 'allow': allow, 'ded': ded, 'due': due_amt})

        # Total paid across all salary rows for this employee
        total_paid_all = 0.0
        if sal_ids:
            total_paid_all = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                                   .filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_ids))
                                   .scalar() or 0.0)

        remaining_payment = total_paid_all

        # Allocate payments from hire date; track carry to start of range
        running_prev = 0.0
        # First, months before selected range
        for d in dues:
            ym = ym_num(d['y'], d['m'])
            if ym >= start_ym:
                break
            total_for_row = running_prev + float(d['due'] or 0.0)
            pay = min(remaining_payment, total_for_row)
            remaining_payment -= pay
            running_prev = max(0.0, total_for_row - pay)

        # Now, months within selected range -> build rows
        emp_key = int(emp.id)
        by_emp[emp_key] = {
            'employee': emp,
            'months': [],
            'sum': {'basic': 0.0, 'allowances': 0.0, 'deductions': 0.0, 'prev_due': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0},
            'unpaid_months': 0,
        }
        for d in dues:
            ym = ym_num(d['y'], d['m'])
            if ym < start_ym or ym > end_ym:
                continue
            prev_for_row = running_prev
            month_due = float(d['due'] or 0.0)
            total_for_row = prev_for_row + month_due
            pay = min(remaining_payment, total_for_row)
            remaining_payment -= pay
            remaining_amount = max(0.0, total_for_row - pay)

            # Status
            tol = 0.01
            if total_for_row <= tol and pay <= tol:
                status = 'paid'
            elif remaining_amount <= tol:
                status = 'paid'
            elif pay > tol:
                status = 'partial'
            else:
                status = 'due'

            vm = type('Row', (), {
                'employee': emp,
                'year': int(d['y']),
                'month': int(d['m']),
                'basic': float(d['base'] or 0.0),
                'allowances': float(d['allow'] or 0.0),
                'deductions': float(d['ded'] or 0.0),
                'prev_due': float(prev_for_row or 0.0),
                'total': float(total_for_row or 0.0),
                'paid': float(pay or 0.0),
                'remaining': float(remaining_amount or 0.0),
                'status': status,
            })
            by_emp[emp_key]['months'].append(vm)
            by_emp[emp_key]['sum']['basic'] += vm.basic
            by_emp[emp_key]['sum']['allowances'] += vm.allowances
            by_emp[emp_key]['sum']['deductions'] += vm.deductions
            by_emp[emp_key]['sum']['prev_due'] += vm.prev_due
            by_emp[emp_key]['sum']['total'] += vm.total
            by_emp[emp_key]['sum']['paid'] += vm.paid
            by_emp[emp_key]['sum']['remaining'] += vm.remaining
            if vm.remaining > 0.001:
                by_emp[emp_key]['unpaid_months'] += 1

            totals['basic'] += vm.basic
            totals['allowances'] += vm.allowances
            totals['deductions'] += vm.deductions
            totals['prev_due'] += vm.prev_due
            totals['total'] += vm.total
            totals['paid'] += vm.paid
            totals['remaining'] += vm.remaining

            # Carry forward
            running_prev = remaining_amount

    # Employees for filter UI
    try:
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        employees = []

    years = list(range(2023, 2032))
    months = [{'value': i, 'label': date(2000, i, 1).strftime('%B')} for i in range(1, 13)]

    return render_template('payroll_detailed.html',
                           by_emp=by_emp,
                           totals=totals,
                           employees=employees,
                           years=years,
                           months=months,
                           year_from=year_from,
                           month_from=month_from,
                           year_to=year_to,
                           month_to=month_to,
                           selected_employee_ids=employee_ids)



@main.route('/suppliers/edit/<int:sid>', methods=['GET', 'POST'], endpoint='suppliers_edit')
@login_required
def suppliers_edit(sid):
    supplier = Supplier.query.get_or_404(sid)
    if request.method == 'POST':
        supplier.name = request.form.get('name', supplier.name)
        supplier.contact_person = request.form.get('contact_person', supplier.contact_person)
        supplier.phone = request.form.get('phone', supplier.phone)
        supplier.email = request.form.get('email', supplier.email)
        supplier.tax_number = request.form.get('tax_number', supplier.tax_number)
        supplier.address = request.form.get('address', supplier.address)
        supplier.notes = request.form.get('notes', supplier.notes)
        supplier.active = True if str(request.form.get('active', supplier.active)).lower() in ['1','true','yes','on'] else False
        try:
            db.session.commit()
            flash('✅ Supplier updated successfully', 'success')
            return redirect(url_for('main.suppliers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating supplier: {e}', 'danger')
    return render_template('supplier_edit.html', supplier=supplier)

# --- Simple helpers / constants ---
BRANCH_LABELS = {
    'place_india': 'Place India',
    'china_town': 'China Town',
}

# --- Helper functions ---
def safe_table_number(table_number) -> int:
    """Safely convert table_number to int, default to 0 if None/invalid"""
    try:
        return int(table_number or 0)
    except (ValueError, TypeError):
        return 0

# --- Permission helpers (reuse AppKV like template can()) ---
def _normalize_scope(s: str) -> str:
    s = (s or '').strip().lower()
    if s in ('place','palace','india','palace_india'): return 'place_india'
    if s in ('china','china town','chinatown'): return 'china_town'
    return s or 'all'


def _read_user_perms(uid: int, scope: str):
    try:
        k = f"user_perms:{scope}:{int(uid)}"
        row = AppKV.query.filter_by(k=k).first()
        if not row:
            return {}
        data = json.loads(row.v)
        items = data.get('items') or []
        out = {}
        for it in items:
            key = (it.get('screen_key') or '').strip()
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


def user_can(screen: str, action: str = 'view', branch_scope: str = None) -> bool:
    try:
        if not getattr(current_user, 'is_authenticated', False):
            return False
        # Admin bypass
        if getattr(current_user, 'username', '') == 'admin' or getattr(current_user, 'id', None) == 1:
            return True
        if getattr(current_user, 'role', '') == 'admin':
            return True
        scopes = []
        if branch_scope:
            scopes = [_normalize_scope(branch_scope), 'all']
        else:
            scopes = ['all']
        for sc in scopes:
            perms = _read_user_perms(current_user.id, sc)
            scr = perms.get(screen)
            if scr and scr.get(action):
                return True
        return False
    except Exception:
        return False



# Safe helper: current time in Saudi Arabia timezone
try:
    import pytz as _pytz
except Exception:  # pragma: no cover
    _pytz = None
from datetime import datetime as _dt

def get_saudi_now():
    """Return timezone-aware now() in Asia/Riyadh; falls back to UTC naive on error."""
    try:
        if _pytz is not None:
            return _dt.now(_pytz.timezone("Asia/Riyadh"))
    except Exception:
        pass
    return _dt.utcnow()

def kv_get(key, default=None):
    rec = AppKV.query.filter_by(k=key).first()
    if not rec:
        return default
    try:
        return json.loads(rec.v)
    except Exception:
        return default

def kv_set(key, value):
    data = json.dumps(value or {})
    rec = AppKV.query.filter_by(k=key).first()
    if rec:
        rec.v = data
    else:
        rec = AppKV(k=key, v=data)
        db.session.add(rec)
    db.session.commit()


# Ensure tables exist (safe for first runs) and seed a demo menu if empty
_DEF_MENU = {
    'Starters': [
        ('Spring Rolls', 8.0), ('Samosa', 6.5)
    ],
    'Main Courses': [
        ('Butter Chicken', 18.0), ('Chicken Chow Mein', 16.0)
    ],
    'Biryani': [
        ('Chicken Biryani', 15.0), ('Veg Biryani', 13.0)
    ],
    'Noodles': [
        ('Hakka Noodles', 12.0), ('Singapore Noodles', 13.5)
    ],
    'Drinks': [
        ('Lassi', 5.0), ('Iced Tea', 4.0)
    ],
    'Desserts': [
        ('Gulab Jamun', 6.0), ('Ice Cream', 4.5)
    ],
}

def ensure_menu_sort_order_column():
    """Ensure menu_categories.sort_order exists; add it if missing (safe no-op otherwise)."""
    try:
        insp = inspect(db.engine)
        cols = [c['name'] for c in insp.get_columns('menu_categories')]
        if 'sort_order' not in cols:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE menu_categories ADD COLUMN sort_order INTEGER DEFAULT 0'))
                    conn.execute(text('UPDATE menu_categories SET sort_order = COALESCE(sort_order, 0)'))
            except Exception:
                # If ALTER fails (e.g., permissions), just continue; fallbacks in queries handle it
                pass
    except Exception:
        pass
def ensure_menuitem_compat_columns():
    """Ensure menu_items has backward-compatible columns (name, price, display_order)."""
    try:
        insp = inspect(db.engine)
        cols = {c['name'] for c in insp.get_columns('menu_items')}
        with db.engine.begin() as conn:
            if 'name' not in cols:
                try:
                    conn.execute(text('ALTER TABLE menu_items ADD COLUMN name VARCHAR(150)'))
                except Exception:
                    pass
            if 'price' not in cols:
                try:
                    conn.execute(text('ALTER TABLE menu_items ADD COLUMN price FLOAT DEFAULT 0.0'))
                except Exception:
                    pass
            if 'display_order' not in cols:
                try:
                    conn.execute(text('ALTER TABLE menu_items ADD COLUMN display_order INTEGER'))
                except Exception:
                    pass
    except Exception:
        # If introspection fails, ignore; query fallbacks may still work
        pass


def ensure_tables():
    try:
        db.create_all()
    except Exception:
        pass
    # Ensure new columns exist for compatibility with older DBs
    ensure_menu_sort_order_column()
    ensure_menuitem_compat_columns()


def seed_menu_if_empty():
    try:
        if MenuCategory.query.count() > 0:
            return
        # create categories in a deterministic order
        order = 0
        for cat_name, items in _DEF_MENU.items():
            order += 10
            cat = MenuCategory(name=cat_name, sort_order=order)
            db.session.add(cat)
            db.session.flush()
            for nm, pr in items:
                db.session.add(MenuItem(name=nm, price=float(pr), category_id=cat.id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        # ignore seed errors in production path
        pass


# Warmup DB only once per process to avoid heavy create_all/seed on hot paths
_DB_WARMED_UP = False

def warmup_db_once():
    global _DB_WARMED_UP
    if _DB_WARMED_UP:
        return
    try:
        ensure_tables()
        seed_menu_if_empty()
    except Exception:
        # ignore errors to avoid blocking requests
        pass
    finally:
        _DB_WARMED_UP = True

@main.route('/')
@login_required
def home():
    # Redirect authenticated users to dashboard for main control screen
    return redirect(url_for('main.dashboard'))

@csrf.exempt
@main.route('/login', methods=['GET', 'POST'])
def login():
    # Ensure DB tables exist on first local run to avoid 'no such table: user'
    try:
        ensure_tables()
    except Exception:
        pass
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        # Safe bootstrap: if DB has no users at all, allow creating default admin/admin123 on first login
        if not user:
            try:
                total_users = User.query.count()
            except Exception:
                total_users = 0
            if total_users == 0 and username == 'admin' and password == 'admin123':
                try:
                    new_admin = User(username='admin')
                    new_admin.set_password('admin123')
                    db.session.add(new_admin)
                    db.session.commit()
                    login_user(new_admin)
                    flash('تم إنشاء مستخدم المدير الافتراضي بنجاح', 'success')
                    return redirect(url_for('main.dashboard'))
                except Exception:
                    db.session.rollback()
                    flash('خطأ في تهيئة المستخدم الافتراضي', 'danger')

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور', 'danger')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


# ---------- Main application pages (simple render-only) ----------
@main.route('/dashboard', endpoint='dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# Orders Invoices screen
@main.route('/orders', endpoint='order_invoices_list')
@login_required
def order_invoices_list():
    # Enforce permission on Orders screen
    # Note: Permission checks for this screen are enforced in the UI via Jinja 'can()'.
    # Avoid calling can() directly here to prevent NameError in Python context.
    try:
        # Optional branch filter
        branch_f = (request.args.get('branch') or '').strip()
        # Fetch orders (limit for safety)
        q_orders = OrderInvoice.query
        if branch_f:
            q_orders = q_orders.filter(OrderInvoice.branch == branch_f)
        orders = q_orders.order_by(OrderInvoice.invoice_date.desc()).limit(500).all()

        # Totals using SQL functions
        from sqlalchemy import func
        q_totals = OrderInvoice.query.with_entities(
            func.coalesce(func.sum(OrderInvoice.subtotal), 0).label('subtotal_sum'),
            func.coalesce(func.sum(OrderInvoice.discount), 0).label('discount_sum'),
            func.coalesce(func.sum(OrderInvoice.vat), 0).label('vat_sum'),
            func.coalesce(func.sum(OrderInvoice.total), 0).label('total_sum'),
        )
        if branch_f:
            q_totals = q_totals.filter(OrderInvoice.branch == branch_f)
        totals_row = q_totals.first()
        totals = {
            'subtotal_sum': float(getattr(totals_row, 'subtotal_sum', 0) or 0),
            'discount_sum': float(getattr(totals_row, 'discount_sum', 0) or 0),
            'vat_sum': float(getattr(totals_row, 'vat_sum', 0) or 0),
            'total_sum': float(getattr(totals_row, 'total_sum', 0) or 0),
        }

        # Items summary in Python (DB-agnostic)
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

        return render_template('order_invoices.html', orders=orders, totals=totals, items_summary=items_summary, current_branch=branch_f)
    except Exception as e:
        current_app.logger.error('order_invoices_list error: %s', e)
        flash('Failed to load order invoices', 'danger')
        return render_template('order_invoices.html', orders=[], totals={'subtotal_sum':0,'discount_sum':0,'vat_sum':0,'total_sum':0}, items_summary=[])

@main.route('/orders/clear', methods=['POST'], endpoint='order_invoices_clear_all')
@login_required
def order_invoices_clear_all():
    try:
        from models import OrderInvoice
        num = db.session.query(OrderInvoice).delete(synchronize_session=False)
        db.session.commit()
        try:
            flash(f'تم حذف {num} من فواتير الطلبات نهائياً', 'success')
        except Exception:
            flash('تم حذف جميع فواتير الطلبات نهائياً', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error('order_invoices_clear_all error: %s', e)
        flash('فشل حذف فواتير الطلبات', 'danger')
    return redirect(url_for('main.order_invoices_list'))

@main.route('/sales', endpoint='sales')
@login_required
def sales():
    # Modern flow: show branches, then tables, then table invoice
    branches = [
        {'code': 'china_town', 'label': 'CHINA TOWN', 'url': url_for('main.sales_tables', branch_code='china_town')},
        {'code': 'place_india', 'label': 'PALACE INDIA', 'url': url_for('main.sales_tables', branch_code='place_india')},
    ]
    # Filter branches by user permissions (allow via specific branch or global 'all')
    branches = [b for b in branches if user_can('sales', 'view', b['code'])]
    return render_template('sales_branches.html', branches=branches)

@main.route('/purchases', methods=['GET','POST'], endpoint='purchases')
@login_required
def purchases():
    # Prepare form and lists
    form = PurchaseInvoiceForm()
    try:
        if not form.date.data:
            form.date.data = datetime.utcnow().date()
    except Exception:
        pass
    suppliers = []
    try:
        if 'Supplier' in globals():
            suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    except Exception:
        suppliers = []
    suppliers_json = []
    for s in suppliers:
        suppliers_json.append({
            'id': s.id,
            'name': s.name,
            'phone': getattr(s, 'phone', None),
            'tax_number': getattr(s, 'tax_number', None),
            'address': getattr(s, 'address', None),
            'cr_number': getattr(s, 'cr_number', None),
            'iban': getattr(s, 'iban', None),
            'active': getattr(s, 'active', True),
        })
    try:
        materials = RawMaterial.query.filter_by(active=True).order_by(RawMaterial.name.asc()).all() if 'RawMaterial' in globals() else []
    except Exception:
        materials = []
    materials_json = []
    for m in materials:
        disp = getattr(m, 'display_name', None)
        if callable(disp):
            name = disp()
        else:
            name = disp if isinstance(disp, str) else m.name
        materials_json.append({
            'id': m.id,
            'name': name,
            'unit': m.unit,
            'cost_per_unit': float(m.cost_per_unit or 0),
            'stock_quantity': float(m.stock_quantity or 0),
        })

    if request.method == 'POST':
        # Parse minimal fields
        pm = (request.form.get('payment_method') or 'cash').strip().lower()
        date_str = request.form.get('date') or datetime.utcnow().date().isoformat()
        supplier_name = (request.form.get('supplier_name') or '').strip() or None
        supplier_id = request.form.get('supplier_id', type=int)
        try:
            inv = PurchaseInvoice(
                invoice_number=f"INV-PUR-{datetime.utcnow().year}-{(PurchaseInvoice.query.count()+1):04d}",
                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                supplier_name=supplier_name,
                supplier_id=supplier_id,
                payment_method=pm,
                user_id=getattr(current_user, 'id', 1)
            )
            # Payment status from form (paid / partial / unpaid)
            inv.status = (request.form.get('status') or (getattr(PurchaseInvoice, 'status', None) and 'unpaid') or 'unpaid').strip().lower()
            if inv.status not in ('paid','partial','unpaid'):
                inv.status = 'unpaid'
            # Collect items
            idx = 0
            total_before = 0.0
            total_tax = 0.0
            total_disc = 0.0
            items_created = 0
            while True:
                prefix = f"items-{idx}-"
                name = request.form.get(prefix + 'item_name')
                unit = (request.form.get(prefix + 'unit') or '').strip() or None
                qty = request.form.get(prefix + 'quantity')
                price = request.form.get(prefix + 'price_before_tax')
                disc_pct = request.form.get(prefix + 'discount')
                tax_pct = request.form.get(prefix + 'tax_pct')
                if name is None and qty is None and price is None and disc_pct is None and tax_pct is None:
                    break
                # Skip empty rows
                if not name and not qty and not price:
                    idx += 1
                    continue
                try:
                    q = float(qty or 0)
                    p = float(price or 0)
                    d_pct = float(disc_pct or 0)
                    t_pct = float(tax_pct or 0)
                except Exception:
                    q = p = 0.0
                    d_pct = t_pct = 0.0
                before = q * p
                disc_amt = max(0.0, min(before, before * (d_pct/100.0)))
                base = max(0.0, before - disc_amt)
                tax_amt = max(0.0, base * (t_pct/100.0))
                line_total = base + tax_amt
                total_before += before
                total_disc += disc_amt
                total_tax += tax_amt

                # Resolve RawMaterial by name; create if not exists
                rm = None
                try:
                    n = (name or '').strip().lower()
                    if n:
                        rm = RawMaterial.query.filter(func.lower(RawMaterial.name) == n).first()
                        if not rm:
                            rm = RawMaterial.query.filter(func.lower(RawMaterial.name_ar) == n).first()
                except Exception:
                    rm = None
                if not rm and name:
                    # Create minimal RawMaterial to satisfy FK
                    try:
                        rm = RawMaterial(name=name.strip(), unit=(unit or 'unit'), cost_per_unit=p or 0)
                        db.session.add(rm)
                        db.session.flush()
                    except Exception:
                        # As a last resort, set unit to 'unit'
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                        db.session.add(RawMaterial(name=name.strip(), unit='unit', cost_per_unit=p or 0))
                        db.session.flush()
                        rm = RawMaterial.query.filter(func.lower(RawMaterial.name) == n).first()

                it = PurchaseInvoiceItem(
                    raw_material_name=name or 'Item',
                    quantity=q,
                    price_before_tax=p,
                    discount=d_pct,
                    tax=tax_amt,
                    total_price=line_total,
                )
                if rm:
                    it.raw_material_id = rm.id
                inv.items.append(it)
                items_created += 1
                idx += 1
            inv.total_before_tax = total_before
            inv.tax_amount = total_tax
            inv.discount_amount = total_disc
            inv.total_after_tax_discount = max(0.0, total_before - total_disc + total_tax)
            if ext_db is not None:
                ext_db.session.add(inv)
                ext_db.session.commit()
            else:
                db.session.add(inv)
                db.session.commit()
            # Auto-create payment if status is 'paid' or 'partial'
            try:
                st = (getattr(inv, 'status', '') or '').lower()
                total_amt = float(inv.total_after_tax_discount or 0.0)
                if st == 'paid' and total_amt > 0:
                    db.session.add(Payment(
                        invoice_id=inv.id,
                        invoice_type='purchase',
                        amount_paid=total_amt,
                        payment_method=(pm or 'CASH').upper()
                    ))
                    db.session.commit()
                elif st == 'partial':
                    amt_raw = request.form.get('partial_paid_amount')
                    try:
                        amt = float(amt_raw or 0.0)
                    except Exception:
                        amt = 0.0
                    if total_amt > 0 and amt > 0:
                        if amt > total_amt:
                            amt = total_amt
                        db.session.add(Payment(
                            invoice_id=inv.id,
                            invoice_type='purchase',
                            amount_paid=amt,
                            payment_method=(pm or 'CASH').upper()
                        ))
                        db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
            flash('Purchase invoice saved', 'success')
        except Exception as e:
            if ext_db is not None:
                ext_db.session.rollback()
            else:
                db.session.rollback()
            flash(f'Could not save purchase invoice: {e}', 'danger')
        return redirect(url_for('main.purchases'))

    return render_template('purchases.html', form=form, suppliers_list=suppliers, suppliers_json=suppliers_json, materials_json=materials_json)

@main.route('/raw-materials', methods=['GET', 'POST'], endpoint='raw_materials')
@login_required
def raw_materials():
    form = RawMaterialForm()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            rm = RawMaterial(
                name=form.name.data,
                name_ar=form.name_ar.data,
                unit=form.unit.data,
                cost_per_unit=form.cost_per_unit.data,
                category=form.category.data,
            )
            db.session.add(rm)
            db.session.commit()
            flash('تم حفظ المادة الخام بنجاح', 'success')
            return redirect(url_for('main.raw_materials'))
        except Exception as e:
            db.session.rollback()
            flash('فشل حفظ المادة الخام', 'danger')
    materials = RawMaterial.query.filter_by(active=True).all()
    return render_template('raw_materials.html', form=form, materials=materials)

@main.route('/meals', methods=['GET', 'POST'], endpoint='meals')
@login_required
def meals():
    # Build form and context similar to monolith, but within blueprint
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    material_choices = [(m.id, m.display_name) for m in raw_materials]

    form = MealForm()
    # Ensure ingredient subforms have choices
    for ingredient_form in form.ingredients:
        ingredient_form.raw_material_id.choices = material_choices

    materials_json = json.dumps([
        {
            'id': m.id,
            'name': m.display_name,
            'cost_per_unit': float(m.cost_per_unit),
            'unit': m.unit,
        }
        for m in raw_materials
    ])

    if form.validate_on_submit():
        try:
            from decimal import Decimal
            meal = Meal(
                name=form.name.data,
                name_ar=form.name_ar.data,
                description=form.description.data,
                category=form.category.data,
                profit_margin_percent=form.profit_margin_percent.data,
                user_id=current_user.id,
            )
            db.session.add(meal)
            db.session.flush()  # get meal.id

            total_cost = 0
            # Parse dynamic ingredient rows from POST keys
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
                    qty = Decimal(qty_raw) if qty_raw not in (None, '') else Decimal('0')
                except Exception:
                    rm_id, qty = 0, Decimal('0')
                if rm_id and qty > 0:
                    raw_material = RawMaterial.query.get(rm_id)
                    if raw_material:
                        ing = MealIngredient(meal_id=meal.id, raw_material_id=raw_material.id, quantity=qty)
                        try:
                            ing_cost = qty * raw_material.cost_per_unit
                            ing.total_cost = ing_cost
                        except Exception:
                            ing.total_cost = 0
                        db.session.add(ing)
                        total_cost += float(ing.total_cost)

            meal.total_cost = total_cost
            meal.calculate_selling_price()
            db.session.commit()
            flash('تم إنشاء الوجبة بنجاح', 'success')
            return redirect(url_for('main.meals'))
        except Exception as e:
            db.session.rollback()
            flash('فشل حفظ الوجبة', 'danger')

    all_meals = Meal.query.filter_by(active=True).all()
    return render_template('meals.html', form=form, meals=all_meals, materials_json=materials_json)

# -------- Meals import (Excel/CSV): Name, Name (Arabic), Selling Price --------
@main.route('/meals/import', methods=['POST'], endpoint='meals_import')
@login_required
def meals_import():
    import os, csv
    from io import TextIOWrapper
    file = request.files.get('file')
    if not file or not file.filename:
        flash('لم يتم اختيار ملف', 'warning')
        return redirect(url_for('main.menu'))

    # إن وُجد قسم حالي مرسل من النموذج نعيد التوجيه إليه بعد الاستيراد
    cat_id = request.form.get('cat_id', type=int)

    ext = os.path.splitext(file.filename)[1].lower()

    def upsert_meal(name_en, name_ar, price_val):
        name_en = (name_en or '').strip()
        name_ar = (name_ar or '').strip() or None
        try:
            price = float(str(price_val).replace(',', '').strip()) if price_val is not None else 0.0
        except Exception:
            price = 0.0
        # محاولة إيجاد وجبة موجودة بنفس الاسم (و/أو الاسم العربي)
        existing = None
        if name_en and name_ar:
            existing = Meal.query.filter_by(name=name_en, name_ar=name_ar).first()
        if not existing and name_en:
            existing = Meal.query.filter_by(name=name_en).first()
        if existing:
            # تأكد من وجود user_id، ثم حدّث سعر البيع فقط
            try:
                if getattr(existing, 'user_id', None) is None:
                    existing.user_id = current_user.id
            except Exception:
                pass
            try:
                existing.selling_price = price
            except Exception:
                pass
            return existing
        # إنشاء وجبة جديدة مع تعيين user_id
        m = Meal(name=name_en or 'Unnamed', name_ar=name_ar, description=None, category=None, user_id=current_user.id)
        try:
            m.selling_price = price
        except Exception:
            pass
        db.session.add(m)
        return m

    imported, errors = 0, 0

    if ext == '.csv':
        try:
            stream = TextIOWrapper(file.stream, encoding='utf-8')
            reader = csv.DictReader(stream)
            def norm(s):
                return (s or '').strip().lower()
            for row in reader:
                cols = {norm(k): v for k, v in row.items()}
                name = cols.get('name') or cols.get('اسم') or cols.get('product')
                name_ar = cols.get('name (arabic)') or cols.get('name_ar') or cols.get('arabic') or cols.get('الاسم العربي')
                price = cols.get('selling price') or cols.get('price') or cols.get('السعر')
                if not name and not name_ar:
                    continue
                try:
                    upsert_meal(name, name_ar, price)
                    imported += 1
                except Exception:
                    errors += 1
            db.session.commit()
            flash(f'تم استيراد {imported} وجبة بنجاح' + (f'، أخطاء: {errors}' if errors else ''), 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'فشل استيراد CSV: {e}', 'danger')
        return redirect(url_for('main.menu', cat_id=cat_id) if cat_id else url_for('main.menu'))

    elif ext in ('.xlsx', '.xls'):
        try:
            try:
                import openpyxl
            except Exception:
                flash('لا يمكن قراءة ملفات Excel بدون تثبيت openpyxl. يمكنك رفع CSV بدلاً من ذلك أو اسمح لي بتثبيت openpyxl.', 'warning')
                return redirect(url_for('main.menu', cat_id=cat_id) if cat_id else url_for('main.menu'))
            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active
            headers = []
            for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True)):
                headers.append((cell or '').strip().lower())
            index = {h: i for i, h in enumerate(headers)}
            def get_val(row, keys):
                for k in keys:
                    if k in index:
                        return row[index[k]]
                return None
            for row in ws.iter_rows(min_row=2, values_only=True):
                name = get_val(row, ['name', 'اسم'])
                name_ar = get_val(row, ['name (arabic)', 'name_ar', 'arabic', 'الاسم العربي'])
                price = get_val(row, ['selling price', 'price', 'السعر'])
                if not name and not name_ar:
                    continue
                try:
                    upsert_meal(name, name_ar, price)
                    imported += 1
                except Exception:
                    errors += 1
            db.session.commit()
            flash(f'تم استيراد {imported} وجبة من Excel' + (f'، أخطاء: {errors}' if errors else ''), 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'فشل استيراد Excel: {e}', 'danger')
        return redirect(url_for('main.menu', cat_id=cat_id) if cat_id else url_for('main.menu'))

    else:
        flash('صيغة الملف غير مدعومة. الرجاء رفع ملف CSV أو Excel (.xlsx/.xls).', 'warning')
        return redirect(url_for('main.menu', cat_id=cat_id) if cat_id else url_for('main.menu'))

@main.route('/inventory', endpoint='inventory')
@login_required
def inventory():
    from sqlalchemy import func
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    meals = Meal.query.filter_by(active=True).all()

    # Build inventory cost ledger from purchases
    ledger_rows = []
    try:
        q = db.session.query(
            PurchaseInvoiceItem.raw_material_id.label('rm_id'),
            func.max(PurchaseInvoice.date).label('last_date'),
            func.sum(PurchaseInvoiceItem.quantity).label('qty'),
            func.sum(PurchaseInvoiceItem.total_price).label('total_cost')
        ).join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
        q = q.group_by(PurchaseInvoiceItem.raw_material_id)
        rm_map = {m.id: m for m in raw_materials}
        for r in q.all():
            rm = rm_map.get(int(r.rm_id)) if r.rm_id is not None else None
            name = (rm.display_name if rm else '-')
            unit = (rm.unit if rm else '-')
            # Quantities and costs
            qty = float(r.qty or 0)
            total_cost = float(r.total_cost or 0)
            avg_cost = (total_cost / qty) if qty else 0.0
            # Current stock equals cumulative purchased quantity (no consumption tracking here)
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
        ledger_rows.sort(key=lambda x: (x['material'] or '').lower())
    except Exception:
        ledger_rows = []

    return render_template('inventory.html', raw_materials=raw_materials, meals=meals, ledger_rows=ledger_rows)

@main.route('/expenses', methods=['GET', 'POST'], endpoint='expenses')
@login_required
def expenses():
	form = ExpenseInvoiceForm()
	try:
		form.date.data = datetime.utcnow().date()
	except Exception:
		pass
	if request.method == 'POST':
		try:
			date_str = request.form.get('date') or datetime.utcnow().date().isoformat()
			pm = (request.form.get('payment_method') or 'CASH').strip().upper()
			if pm not in ('CASH','BANK','TRANSFER'):
				pm = 'CASH'
			# normalize status first
			status_val = (request.form.get('status') or 'paid').strip().lower()
			if status_val not in ('paid','partial','unpaid'):
				status_val = 'paid'
			# Collect items first to avoid NOT NULL flush errors on invoice totals
			idx = 0
			total_before = 0.0
			total_tax = 0.0
			total_disc = 0.0
			items_buffer = []
			while True:
				prefix = f"items-{idx}-"
				desc = request.form.get(prefix + 'description')
				qty = request.form.get(prefix + 'quantity')
				price = request.form.get(prefix + 'price_before_tax')
				tax = request.form.get(prefix + 'tax')
				disc = request.form.get(prefix + 'discount')
				if desc is None and qty is None and price is None and tax is None and disc is None:
					break
				if not desc and not qty and not price:
					idx += 1
					continue
				try:
					qf = float(qty or 0.0); pf = float(price or 0.0); tf = float(tax or 0.0); df = float(disc or 0.0)
				except Exception:
					qf = 0.0; pf = 0.0; tf = 0.0; df = 0.0
				line_total = (qf * pf) - df + tf
				total_before += (qf * pf)
				total_tax += tf
				total_disc += df
				items_buffer.append({
					'description': (desc or '').strip(),
					'quantity': qf,
					'price_before_tax': pf,
					'tax': tf,
					'discount': df,
					'total_price': line_total,
				})
				idx += 1
			# Create invoice with totals populated, then flush and add items
			inv = ExpenseInvoice(
				invoice_number=f"INV-EXP-{datetime.utcnow().year}-{(ExpenseInvoice.query.count()+1):04d}",
				date=datetime.strptime(date_str, '%Y-%m-%d').date(),
				payment_method=pm,
				total_before_tax=total_before,
				tax_amount=total_tax,
				discount_amount=total_disc,
				total_after_tax_discount=max(0.0, total_before - total_disc + total_tax),
				status=status_val,
				user_id=getattr(current_user, 'id', 1)
			)
			db.session.add(inv)
			db.session.flush()
			for row in items_buffer:
				item = ExpenseInvoiceItem(
					invoice_id=inv.id,
					description=row['description'],
					quantity=row['quantity'],
					price_before_tax=row['price_before_tax'],
					tax=row['tax'],
					discount=row['discount'],
					total_price=row['total_price']
				)
				db.session.add(item)
			db.session.commit()
			flash('Expense saved', 'success')
		except Exception as e:
			db.session.rollback()
			flash('Failed to save expense', 'danger')
		return redirect(url_for('main.expenses'))
	return render_template('expenses.html', form=form, invoices=ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).limit(50).all())

@main.route('/expenses/delete/<int:eid>', methods=['POST'], endpoint='expense_delete')
@login_required
def expense_delete(eid):
	try:
		inv = ExpenseInvoice.query.get(int(eid))
		if not inv:
			flash('Expense invoice not found', 'warning')
			return redirect(url_for('main.expenses'))
		# Delete children items first
		for it in (inv.items or []):
			try:
				db.session.delete(it)
			except Exception:
				pass
		db.session.delete(inv)
		db.session.commit()
		flash('Expense invoice deleted', 'success')
	except Exception:
		db.session.rollback()
		flash('Failed to delete expense invoice', 'danger')
	return redirect(url_for('main.expenses'))

@main.route('/invoices', endpoint='invoices')
@login_required
def invoices():
    t = (request.args.get('type') or 'sales').strip().lower()
    if t not in ('sales','purchases','expenses','all'):
        t = 'sales'
    return render_template('invoices.html', current_type=t)
@main.route('/reports/print/payments', methods=['GET'], endpoint='reports_print_payments')
@login_required
def reports_print_payments():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import PurchaseInvoice, ExpenseInvoice, Payment, Settings

        inv_type = (request.args.get('type') or 'purchase').strip().lower()
        if inv_type not in ('purchase','expense'):
            inv_type = 'purchase'

        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max

        rows = []
        totals_by_party = {}

        if inv_type == 'purchase':
            q = PurchaseInvoice.query.filter(PurchaseInvoice.date.between(start_d, end_d))
            for inv in q.order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc()).all():
                total = float(inv.total_after_tax_discount or 0.0)
                paid = float(
                    db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                      .filter(Payment.invoice_type=='purchase', Payment.invoice_id==inv.id).scalar() or 0.0
                )
                remaining = max(total - paid, 0.0)
                party = getattr(inv, 'supplier_name', '-') or '-'
                rows.append({
                    'BILL NO': inv.invoice_number,
                    'DATE': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                    'SUPPLIER': party,
                    'ITEMS/QTY/TOTAL': f"{len(getattr(inv,'items',[]) or [])} items",
                    'PAID': paid,
                    'REMAINING': remaining,
                    'METHOD': (inv.payment_method or '').upper(),
                    'STATUS': (inv.status or '').upper()
                })
                t = totals_by_party.setdefault(party, {'TOTAL':0.0,'PAID':0.0,'REMAINING':0.0})
                t['TOTAL'] += total; t['PAID'] += paid; t['REMAINING'] += remaining
        else:
            q = ExpenseInvoice.query.filter(ExpenseInvoice.date.between(start_d, end_d))
            for inv in q.order_by(ExpenseInvoice.date.desc(), ExpenseInvoice.id.desc()).all():
                total = float(inv.total_after_tax_discount or 0.0)
                paid = float(
                    db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                      .filter(Payment.invoice_type=='expense', Payment.invoice_id==inv.id).scalar() or 0.0
                )
                remaining = max(total - paid, 0.0)
                party = 'Expense'
                rows.append({
                    'BILL NO': inv.invoice_number,
                    'DATE': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                    'SUPPLIER': party,
                    'ITEMS/QTY/TOTAL': f"{len(getattr(inv,'items',[]) or [])} items",
                    'PAID': paid,
                    'REMAINING': remaining,
                    'METHOD': (inv.payment_method or '').upper(),
                    'STATUS': (inv.status or '').upper()
                })
                t = totals_by_party.setdefault(party, {'TOTAL':0.0,'PAID':0.0,'REMAINING':0.0})
                t['TOTAL'] += total; t['PAID'] += paid; t['REMAINING'] += remaining

        columns = ['BILL NO','DATE','SUPPLIER','ITEMS/QTY/TOTAL','PAID','REMAINING','METHOD','STATUS']
        data = rows
        totals = {
            'PAID': sum(r.get('PAID',0.0) for r in rows),
            'REMAINING': sum(r.get('REMAINING',0.0) for r in rows),
        }
        settings = Settings.query.first()
        # Render with payment totals by method per the template optional block
        payment_totals = {}
        for r in rows:
            pm = r.get('METHOD') or 'UNKNOWN'
            payment_totals[pm] = payment_totals.get(pm, 0.0) + float(r.get('PAID') or 0.0)

        # Supplier totals: show remaining by supplier; adapt labels
        supplier_totals = { k: v['REMAINING'] for k, v in totals_by_party.items() }

        return render_template('print_report.html',
                               report_title=("Purchases" if inv_type=='purchase' else "Expenses"),
                               columns=columns,
                               data=data,
                               totals=totals,
                               totals_columns=['PAID','REMAINING'],
                               totals_colspan=4,
                               settings=settings,
                               start_date=start_s, end_date=end_s,
                               payment_method=request.args.get('payment_method') or 'all',
                               generated_at=_dt.now().strftime('%Y-%m-%d %H:%M'),
                               item_totals=supplier_totals,
                               item_totals_title=('Supplier Totals' if inv_type=='purchase' else 'Expense Totals'),
                               item_totals_name_label=('Supplier' if inv_type=='purchase' else 'Expense'),
                               item_totals_value_label='Remaining',
                               payment_totals=payment_totals)
    except Exception:
        return redirect(url_for('payments'))


@main.route('/invoices/delete', methods=['POST'], endpoint='invoices_delete')
@login_required
def invoices_delete():
    scope = (request.form.get('scope') or 'selected').strip().lower()
    inv_type = (request.form.get('invoice_type') or request.form.get('current_type') or 'sales').strip().lower()
    ids = [int(x) for x in request.form.getlist('invoice_ids') if str(x).isdigit()]
    deleted = 0
    try:
        if inv_type == 'sales':
            q = SalesInvoice.query
            if scope == 'selected' and ids:
                q = q.filter(SalesInvoice.id.in_(ids))
            rows = q.all()
            for inv in rows:
                try:
                    SalesInvoiceItem.query.filter_by(invoice_id=inv.id).delete(synchronize_session=False)
                except Exception:
                    pass
                try:
                    Payment.query.filter(Payment.invoice_id == inv.id, Payment.invoice_type == 'sales').delete(synchronize_session=False)
                except Exception:
                    pass
                db.session.delete(inv)
                deleted += 1
        elif inv_type == 'purchases':
            q = PurchaseInvoice.query
            if scope == 'selected' and ids:
                q = q.filter(PurchaseInvoice.id.in_(ids))
            rows = q.all()
            for inv in rows:
                try:
                    PurchaseInvoiceItem.query.filter_by(invoice_id=inv.id).delete(synchronize_session=False)
                except Exception:
                    pass
                try:
                    Payment.query.filter(Payment.invoice_id == inv.id, Payment.invoice_type == 'purchase').delete(synchronize_session=False)
                except Exception:
                    pass
                db.session.delete(inv)
                deleted += 1
        elif inv_type == 'expenses':
            q = ExpenseInvoice.query
            if scope == 'selected' and ids:
                q = q.filter(ExpenseInvoice.id.in_(ids))
            rows = q.all()
            for inv in rows:
                try:
                    ExpenseInvoiceItem.query.filter_by(invoice_id=inv.id).delete(synchronize_session=False)
                except Exception:
                    pass
                try:
                    Payment.query.filter(Payment.invoice_id == inv.id, Payment.invoice_type == 'expense').delete(synchronize_session=False)
                except Exception:
                    pass
                db.session.delete(inv)
                deleted += 1
        db.session.commit()
        flash(f"Deleted {deleted} invoice(s)", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Delete failed: {e}", 'danger')
    return redirect(url_for('main.invoices', type=inv_type))

@main.route('/employees', methods=['GET','POST'], endpoint='employees')
@login_required
def employees():
    if not user_can('employees','view'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.home'))
    form = EmployeeForm()
    if request.method == 'POST':
        try:
            # generate employee_code automatically if not provided
            emp_code = form.employee_code.data if (form.employee_code.data and str(form.employee_code.data).strip()) else None
            e = Employee(
                employee_code=emp_code,
                full_name=form.full_name.data,
                national_id=form.national_id.data,
                department=form.department.data,
                position=form.position.data,
                phone=form.phone.data,
                email=form.email.data,
                hire_date=form.hire_date.data,
                status=form.status.data or 'active',
            )
            if ext_db is not None:
                ext_db.session.add(e)
                ext_db.session.commit()
            else:
                db.session.add(e)
                db.session.commit()
            # Save defaults if provided
            try:
                from models import EmployeeSalaryDefault
                base = form.base_salary.data or 0
                allow = form.allowances.data or 0
                ded = form.deductions.data or 0
                if (base or allow or ded):
                    d = EmployeeSalaryDefault.query.filter_by(employee_id=e.id).first()
                    if not d:
                        d = EmployeeSalaryDefault(employee_id=e.id)
                        if ext_db is not None:
                            ext_db.session.add(d)
                        else:
                            db.session.add(d)
                    d.base_salary = base
                    d.allowances = allow
                    d.deductions = ded
                    if ext_db is not None:
                        ext_db.session.commit()
                    else:
                        db.session.commit()
            except Exception:
                pass
            flash('Employee saved', 'success')
        except Exception as ex:
            if ext_db is not None:
                ext_db.session.rollback()
            else:
                db.session.rollback()
            flash(f'Could not save employee: {ex}', 'danger')
        return redirect(url_for('main.employees'))
    # List employees
    try:
        emps_raw = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        emps_raw = []
    # Build simplified view model per provided template
    employees_vm = []
    active_count = 0
    inactive_count = 0
    for e in (emps_raw or []):
        try:
            st = (e.status or 'active').lower()
        except Exception:
            st = 'active'
        if st == 'active':
            active_count += 1
        elif st == 'inactive':
            inactive_count += 1
        employees_vm.append(type('EmpVM', (), {
            'id': int(getattr(e, 'id', 0) or 0),
            'code': getattr(e, 'employee_code', None) or '',
            'full_name': getattr(e, 'full_name', '') or '',
            'national_id': getattr(e, 'national_id', '') or '',
            'department': getattr(e, 'department', '') or '',
            'position': getattr(e, 'position', '') or '',
            'phone': getattr(e, 'phone', None),
            'email': getattr(e, 'email', None),
            'hire_date': (getattr(e, 'hire_date', None).strftime('%Y-%m-%d') if getattr(e, 'hire_date', None) else ''),
            'status': st,
        }))
    # Prefill next employee code for convenience
    try:
        next_code = Employee.generate_code()
        if not form.employee_code.data:
            form.employee_code.data = next_code
    except Exception:
        next_code = ''
    return render_template(
        'employees.html',
        employees=employees_vm,
        active_count=active_count,
        inactive_count=inactive_count,
        current_year=datetime.utcnow().year,
        current_month=datetime.utcnow().month,
    )


@main.route('/employees/add', methods=['GET','POST'], endpoint='add_employee')
@login_required
def add_employee():
    if not user_can('employees','add'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.employees'))
    if request.method == 'POST':
        try:
            code = (request.form.get('code') or '').strip()
            full_name = (request.form.get('name') or '').strip()
            national_id = (request.form.get('national_id') or '').strip()
            department = (request.form.get('department') or '').strip() or None
            position = (request.form.get('position') or '').strip() or None
            phone = (request.form.get('phone') or '').strip() or None
            email = (request.form.get('email') or '').strip() or None
            hire_date_s = (request.form.get('hire_date') or '').strip()
            try:
                hire_date = datetime.strptime(hire_date_s, '%Y-%m-%d').date() if hire_date_s else None
            except Exception:
                hire_date = None
            base = float(request.form.get('basic') or 0.0)
            allow = float(request.form.get('allowances') or 0.0)
            ded = float(request.form.get('deductions') or 0.0)

            # Auto-generate employee code if not provided
            try:
                if not code:
                    code = Employee.generate_code()
            except Exception:
                pass

            e = Employee(
                employee_code=code if code else None,
                full_name=full_name,
                national_id=national_id or None,
                department=department,
                position=position,
                phone=phone,
                email=email,
                hire_date=hire_date,
                status='active',
            )
            if ext_db is not None:
                ext_db.session.add(e)
                ext_db.session.commit()
            else:
                db.session.add(e)
                db.session.commit()

            # Save default salary values
            try:
                from models import EmployeeSalaryDefault
                d = EmployeeSalaryDefault.query.filter_by(employee_id=e.id).first()
                if not d:
                    d = EmployeeSalaryDefault(employee_id=e.id)
                    if ext_db is not None:
                        ext_db.session.add(d)
                    else:
                        db.session.add(d)
                d.base_salary = base
                d.allowances = allow
                d.deductions = ded
                if ext_db is not None:
                    ext_db.session.commit()
                else:
                    db.session.commit()
            except Exception:
                pass

            # Create current month salary row
            try:
                today = datetime.utcnow()
                total = max(0.0, float(base or 0) + float(allow or 0) - float(ded or 0))
                sal = Salary(
                    employee_id=e.id,
                    year=int(today.year),
                    month=int(today.month),
                    basic_salary=base,
                    allowances=allow,
                    deductions=ded,
                    previous_salary_due=0.0,
                    total_salary=total,
                    status='due'
                )
                if ext_db is not None:
                    ext_db.session.add(sal)
                    ext_db.session.commit()
                else:
                    db.session.add(sal)
                    db.session.commit()
            except Exception:
                pass

            flash('Employee saved', 'success')
            return redirect(url_for('main.employees'))
        except Exception as ex:
            try:
                if ext_db is not None:
                    ext_db.session.rollback()
                else:
                    db.session.rollback()
            except Exception:
                pass
            flash(f'Could not save employee: {ex}', 'danger')
    # GET: prefill next employee code and departments list from settings
    try:
        next_code = ''
        try:
            next_code = Employee.generate_code()
        except Exception:
            next_code = ''
        from models import DepartmentRate
        departments = [dr.name for dr in DepartmentRate.query.order_by(DepartmentRate.name.asc()).all()]
    except Exception:
        next_code = ''
        departments = []
    return render_template('add_employee.html', next_code=next_code, departments=departments)

@main.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'], endpoint='edit_employee')
@main.route('/employees/edit', methods=['GET'], endpoint='edit_employee_by_query')
@login_required
def edit_employee(emp_id=None):
    if not user_can('employees','edit'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.employees'))
    if emp_id is None:
        emp_id = request.args.get('id', type=int)
    emp = Employee.query.get_or_404(int(emp_id))
    if request.method == 'POST':
        emp.employee_code = request.form.get('employee_code', emp.employee_code)
        emp.full_name = request.form.get('full_name', emp.full_name)
        emp.national_id = request.form.get('national_id', emp.national_id)
        emp.department = request.form.get('department', emp.department)
        emp.position = request.form.get('position', emp.position)
        # active checkbox
        try:
            emp.active = bool(request.form.get('active'))
        except Exception:
            pass
        # work hours
        try:
            wh = request.form.get('work_hours')
            if wh is not None and wh != '':
                emp.work_hours = int(wh)
        except Exception:
            pass
        emp.phone = request.form.get('phone', emp.phone)
        emp.email = request.form.get('email', emp.email)
        # hire_date handled by form/input; attempt to parse if provided
        try:
            hd = request.form.get('hire_date')
            if hd:
                emp.hire_date = datetime.strptime(hd, '%Y-%m-%d').date()
        except Exception:
            pass
        emp.status = request.form.get('status', emp.status)
        # Salary default fields: base_salary, allowances, deductions
        try:
            base = float(request.form.get('base_salary') or 0)
            allow = float((request.form.get('default_allowances') if request.form.get('default_allowances') is not None else request.form.get('allowances')) or 0)
            ded = float((request.form.get('default_deductions') if request.form.get('default_deductions') is not None else request.form.get('deductions')) or 0)
            # upsert EmployeeSalaryDefault
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first()
            if d:
                d.base_salary = base
                d.allowances = allow
                d.deductions = ded
            else:
                d = EmployeeSalaryDefault(employee_id=emp.id, base_salary=base, allowances=allow, deductions=ded)
                db.session.add(d)
        except Exception:
            pass
        try:
            db.session.commit()
            flash('✅ Employee updated successfully', 'success')
            return redirect(url_for('main.employees'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating employee: {e}', 'danger')
    # Provide departments list for dropdowns
    try:
        from models import DepartmentRate
        departments = [dr.name for dr in DepartmentRate.query.order_by(DepartmentRate.name.asc()).all()]
    except Exception:
        departments = []
    return render_template('employee_edit.html', employee=emp, departments=departments)


@main.route('/employees/<int:eid>/delete', methods=['POST'], endpoint='employee_delete')
@main.route('/employees/delete', methods=['POST'], endpoint='employee_delete_by_query')
@login_required
def employee_delete(eid=None):
    if not user_can('employees','delete'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.employees'))
    if eid is None:
        eid = request.args.get('id', type=int)
    eid = int(eid)
    try:
        emp = Employee.query.get_or_404(eid)
        # Delete related salary payments, salaries, and defaults, then employee
        sal_rows = Salary.query.filter_by(employee_id=eid).all()
        sal_ids = [s.id for s in sal_rows]
        if sal_ids:
            try:
                Payment.query.filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_ids)).delete(synchronize_session=False)
            except Exception:
                pass
            Salary.query.filter(Salary.id.in_(sal_ids)).delete(synchronize_session=False)
        try:
            EmployeeSalaryDefault.query.filter_by(employee_id=eid).delete(synchronize_session=False)
        except Exception:
            pass
        db.session.delete(emp)
        db.session.commit()
        flash('Employee and all related records deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting employee: {e}', 'danger')
    return redirect(url_for('main.employees'))

@main.route('/employees/create-salary', methods=['POST'], endpoint='employees_create_salary')
@login_required
def employees_create_salary():
    if not user_can('employees','add') and not user_can('salaries','add'):
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    try:
        emp_id = int(request.form.get('employee_id') or 0)
        year = int(request.form.get('year') or datetime.utcnow().year)
        month = int(request.form.get('month') or datetime.utcnow().month)
        base = float(request.form.get('basic_salary') or 0)
        allow = float(request.form.get('allowances') or 0)
        ded = float(request.form.get('deductions') or 0)
        prev_due = float(request.form.get('previous_salary_due') or 0)
        total = base + allow - ded + prev_due
        if total < 0:
            total = 0
        emp = None
        try:
            emp = Employee.query.get(emp_id)
        except Exception:
            emp = None
        if not emp:
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 400
        sal = Salary(employee_id=emp_id, year=year, month=month,
                     basic_salary=base, allowances=allow, deductions=ded,
                     previous_salary_due=prev_due, total_salary=total,
                     status='due')
        try:
            session = Employee.query.session
        except Exception:
            try:
                session = Salary.query.session
            except Exception:
                session = (ext_db.session if ext_db is not None else db.session)
        session.add(sal)
        session.commit()
        return jsonify({'ok': True, 'salary_id': sal.id}), 200
    except Exception as e:
        try:
            (ext_db.session if ext_db is not None else db.session).rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/salaries/pay', methods=['GET','POST'], endpoint='salaries_pay')
@login_required
def salaries_pay():
    # Create/update salary for a month and optionally record a payment
    if request.method == 'POST':
        try:
            emp_id_raw = request.form.get('employee_id')
            month_str = (request.form.get('month') or request.form.get('pay_month') or datetime.utcnow().strftime('%Y-%m')).strip()
            y, m = month_str.split('-')
            year = int(y); month = int(m)
            amount = float(request.form.get('paid_amount') or 0)
            method = (request.form.get('payment_method') or 'cash').strip().lower()
            # Ignore client overrides for salary details; use stored/default values only
            basic_override = None
            allow_override = None
            ded_override   = None
            prev_override  = None

            # Helper: ensure salary exists for a given employee for the target period
            def _ensure_salary_for(emp_id: int):
                sal = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
                if not sal:
                    base = allow = ded = prev = 0.0
                    try:
                        from models import EmployeeSalaryDefault, DepartmentRate, EmployeeHours
                        d = EmployeeSalaryDefault.query.filter_by(employee_id=emp_id).first()
                        # defaults
                        allow = float(getattr(d, 'allowances', 0) or 0)
                        ded = float(getattr(d, 'deductions', 0) or 0)
                        # prefer hour-based base when available for the period
                        hrs_row = EmployeeHours.query.filter_by(employee_id=emp_id, year=year, month=month).first()
                        emp_obj = Employee.query.get(emp_id)
                        dept_name = (getattr(emp_obj, 'department', '') or '').lower()
                        rate_row = DepartmentRate.query.filter(DepartmentRate.name == dept_name).first()
                        hourly_rate = float(getattr(rate_row, 'hourly_rate', 0) or 0)
                        hour_based_base = float(getattr(hrs_row, 'hours', 0) or 0) * hourly_rate if hrs_row else 0.0
                        default_base = float(getattr(d, 'base_salary', 0) or 0)
                        base = hour_based_base if hour_based_base > 0 else default_base
                    except Exception:
                        pass
                    # Previous due up to previous month
                    try:
                        emp_obj = Employee.query.get(emp_id)
                    except Exception:
                        emp_obj = None
                    try:
                        rem_q = db.session.query(
                            func.coalesce(func.sum(Salary.total_salary), 0),
                            func.coalesce(func.sum(Payment.amount_paid), 0)
                        ).outerjoin(Payment, (Payment.invoice_type=='salary') & (Payment.invoice_id==Salary.id)) \
                         .filter(Salary.employee_id==emp_id) \
                         .filter((Salary.year < year) | ((Salary.year==year) & (Salary.month < month)))
                        if getattr(emp_obj, 'hire_date', None):
                            hd_y = int(emp_obj.hire_date.year)
                            hd_m = int(emp_obj.hire_date.month)
                            rem_q = rem_q.filter((Salary.year > hd_y) | ((Salary.year==hd_y) & (Salary.month >= hd_m)))
                        tot_sum, paid_sum = rem_q.first()
                        prev = max(0.0, float(tot_sum or 0) - float(paid_sum or 0))
                    except Exception:
                        prev = 0.0
                    total = max(0.0, base + allow - ded + prev)
                    sal = Salary(employee_id=emp_id, year=year, month=month,
                                 basic_salary=base, allowances=allow, deductions=ded,
                                 previous_salary_due=prev, total_salary=total, status='due')
                    db.session.add(sal)
                    db.session.flush()
                return sal

            # Determine employees to pay: single or all
            if (emp_id_raw or '').strip().lower() == 'all':
                employee_ids = [int(e.id) for e in Employee.query.all()]
            else:
                employee_ids = [int(emp_id_raw)]

            created_payment_ids = []

            # FIFO distribute payment across arrears -> current -> advance
            if amount > 0:
                # Build ordered list of months from hire date up to current month
                def _start_from(emp_id: int):
                    try:
                        emp_obj = Employee.query.get(emp_id)
                    except Exception:
                        emp_obj = None
                    sy, sm = year, month
                    try:
                        if getattr(emp_obj, 'hire_date', None):
                            sy = int(emp_obj.hire_date.year)
                            sm = int(emp_obj.hire_date.month)
                    except Exception:
                        pass
                    return sy, sm
                # helper iterate months
                def month_iter(y0, m0, y1, m1):
                    y, m = y0, m0
                    cnt = 0
                    while (y < y1) or (y == y1 and m <= m1):
                        yield y, m
                        m += 1
                        if m > 12:
                            m = 1; y += 1
                        cnt += 1
                        if cnt > 240:
                            break
                for _emp_id in employee_ids:
                    remaining_payment = float(amount or 0)
                    start_y, start_m = _start_from(_emp_id)
                    for yy, mm in month_iter(start_y, start_m, year, month):
                        row = Salary.query.filter_by(employee_id=_emp_id, year=yy, month=mm).first()
                        if not row:
                            base = allow = ded = 0.0
                            try:
                                from models import EmployeeSalaryDefault, DepartmentRate, EmployeeHours
                                d = EmployeeSalaryDefault.query.filter_by(employee_id=_emp_id).first()
                                allow = float(getattr(d, 'allowances', 0) or 0)
                                ded = float(getattr(d, 'deductions', 0) or 0)
                                # prefer hour-based base when available for that month
                                hrs_row = EmployeeHours.query.filter_by(employee_id=_emp_id, year=yy, month=mm).first()
                                emp_o = Employee.query.get(_emp_id)
                                dept_name = (getattr(emp_o, 'department', '') or '').lower()
                                rate_row = DepartmentRate.query.filter(DepartmentRate.name == dept_name).first()
                                hourly_rate = float(getattr(rate_row, 'hourly_rate', 0) or 0)
                                hour_based_base = float(getattr(hrs_row, 'hours', 0) or 0) * hourly_rate if hrs_row else 0.0
                                default_base = float(getattr(d, 'base_salary', 0) or 0)
                                base = hour_based_base if hour_based_base > 0 else default_base
                            except Exception:
                                pass
                            prev_component = 0.0
                            total_amount = max(0.0, base + allow - ded + prev_component)
                            row = Salary(employee_id=_emp_id, year=yy, month=mm,
                                         basic_salary=base, allowances=allow, deductions=ded,
                                         previous_salary_due=prev_component, total_salary=total_amount,
                                         status='due')
                            db.session.add(row)
                            db.session.flush()
                        already_paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).
                            filter(Payment.invoice_type=='salary', Payment.invoice_id==row.id).scalar() or 0.0)
                        month_due = max(0.0, float(row.total_salary or 0) - already_paid)
                        if month_due <= 0:
                            row.status = 'paid'
                            continue
                        if remaining_payment <= 0:
                            break
                        pay_amount = remaining_payment if remaining_payment < month_due else month_due
                        if pay_amount > 0:
                            p = Payment(invoice_id=row.id, invoice_type='salary', amount_paid=pay_amount, payment_method=method)
                            db.session.add(p)
                            db.session.flush()
                            try:
                                created_payment_ids.append(int(p.id))
                            except Exception:
                                pass
                            remaining_payment -= pay_amount
                            already_paid += pay_amount
                            if already_paid >= float(row.total_salary or 0) and float(row.total_salary or 0) > 0:
                                row.status = 'paid'
                            else:
                                row.status = 'partial'
                    if remaining_payment > 0:
                        adv_y = year + (1 if month == 12 else 0)
                        adv_m = 1 if month == 12 else month + 1
                        adv_row = Salary.query.filter_by(employee_id=_emp_id, year=adv_y, month=adv_m).first()
                        if not adv_row:
                            base = allow = ded = 0.0
                            try:
                                from models import EmployeeSalaryDefault
                                d = EmployeeSalaryDefault.query.filter_by(employee_id=_emp_id).first()
                                if d:
                                    base = float(d.base_salary or 0)
                                    allow = float(d.allowances or 0)
                                    ded = float(d.deductions or 0)
                            except Exception:
                                pass
                            adv_row = Salary(employee_id=_emp_id, year=adv_y, month=adv_m,
                                             basic_salary=base, allowances=allow, deductions=ded,
                                             previous_salary_due=0.0,
                                             total_salary=max(0.0, base + allow - ded), status='partial')
                            db.session.add(adv_row)
                            db.session.flush()
                        p2 = Payment(invoice_id=adv_row.id, invoice_type='salary', amount_paid=remaining_payment, payment_method=method)
                        db.session.add(p2)
                        db.session.flush()
                        try:
                            created_payment_ids.append(int(p2.id))
                        except Exception:
                            pass

            # Recompute current month sal status for immediate UI feedback
            # Recompute status for the current salary of the first employee (for UI feedback)
            try:
                first_emp = employee_ids[0]
                sal = Salary.query.filter_by(employee_id=first_emp, year=year, month=month).first() or _ensure_salary_for(first_emp)
                paid_sum = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).
                    filter(Payment.invoice_type == 'salary', Payment.invoice_id == sal.id).scalar() or 0)
                total_due = float(sal.total_salary or 0)
                if paid_sum >= total_due and total_due > 0:
                    sal.status = 'paid'
                elif paid_sum > 0:
                    sal.status = 'partial'
                else:
                    sal.status = 'due'
            except Exception:
                pass

            db.session.commit()
            flash('تم تسجيل السداد', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving salary/payment: {e}', 'danger')
        # Redirect back to logical screen
        try:
            if (emp_id_raw or '').strip().lower() != 'all' and str(emp_id_raw).isdigit():
                return redirect(url_for('main.pay_salary', emp_id=int(emp_id_raw), year=year, month=month))
        except Exception:
            pass
        return redirect(url_for('main.payroll', year=year, month=month))

    # GET
    try:
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        employees = []
    selected_month = request.args.get('month') or datetime.utcnow().strftime('%Y-%m')
    selected_employee = request.args.get('employee', type=int)
    # Build defaults map and previous due per employee for the selected month
    defaults_map = {}
    prev_due_map = {}
    try:
        from models import EmployeeSalaryDefault
        for d in EmployeeSalaryDefault.query.all():
            defaults_map[int(d.employee_id)] = {
                'basic_salary': float(d.base_salary or 0.0),
                'allowances': float(d.allowances or 0.0),
                'deductions': float(d.deductions or 0.0)
            }
    except Exception:
        defaults_map = {}
    try:
        y, m = selected_month.split('-'); end_y, end_m = int(y), int(m)
        # previous period is the month before selected
        if end_m == 1:
            prev_y, prev_m = end_y - 1, 12
        else:
            prev_y, prev_m = end_y, end_m - 1

        # Preload defaults for fallback months without Salary rows
        try:
            from models import EmployeeSalaryDefault
            defaults = {int(d.employee_id): d for d in EmployeeSalaryDefault.query.all()}
        except Exception:
            defaults = {}

        def month_iter(y0, m0, y1, m1):
            y, m = y0, m0
            count = 0
            while (y < y1) or (y == y1 and m <= m1):
                yield y, m
                m += 1
                if m > 12:
                    m = 1; y += 1
                count += 1
                if count > 240:  # guard: max 20 years
                    break

        for emp in (employees or []):
            try:
                # No hire date -> no arrears
                if not getattr(emp, 'hire_date', None):
                    prev_due_map[int(emp.id)] = 0.0
                    continue
                start_y, start_m = int(emp.hire_date.year), int(emp.hire_date.month)
                # If hire date after previous period -> nothing due
                if (start_y > prev_y) or (start_y == prev_y and start_m > prev_m):
                    prev_due_map[int(emp.id)] = 0.0
                    continue

                due_sum = 0.0
                paid_sum = 0.0
                for yy, mm in month_iter(start_y, start_m, prev_y, prev_m):
                    s = Salary.query.filter_by(employee_id=emp.id, year=yy, month=mm).first()
                    if s:
                        basic = float(s.basic_salary or 0.0)
                        allow = float(s.allowances or 0.0)
                        ded = float(s.deductions or 0.0)
                        # Monthly gross for the period only (exclude carry-over to avoid double counting)
                        total = max(0.0, basic + allow - ded)
                        due_sum += total
                        paid = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)). \
                            filter(Payment.invoice_type == 'salary', Payment.invoice_id == s.id).scalar() or 0.0
                        paid_sum += float(paid or 0.0)
                    else:
                        d = defaults.get(int(emp.id))
                        if d:
                            base = float(getattr(d, 'base_salary', 0.0) or 0.0)
                            allow = float(getattr(d, 'allowances', 0.0) or 0.0)
                            ded = float(getattr(d, 'deductions', 0.0) or 0.0)
                            due_sum += max(0.0, base + allow - ded)
                        # if no defaults, count as 0 for that month
                prev_due_map[int(emp.id)] = max(0.0, due_sum - paid_sum)
            except Exception:
                prev_due_map[int(emp.id)] = 0.0
    except Exception:
        prev_due_map = {}

    # Optional: list current month salaries
    try:
        y, m = selected_month.split('-'); year = int(y); month = int(m)
        current_salaries = Salary.query.filter_by(year=year, month=month).all()
    except Exception:
        current_salaries = []

    # Selected employee's salary for this month (to prefill form with existing values)
    selected_salary = None
    try:
        if selected_employee and current_salaries:
            for s in current_salaries:
                if int(getattr(s, 'employee_id', 0) or 0) == int(selected_employee):
                    selected_salary = s
                    break
    except Exception:
        selected_salary = None

    # Compute paid sum per salary for coloring Paid/Remaining columns
    paid_map = {}
    try:
        if current_salaries:
            ids = [int(s.id) for s in current_salaries if getattr(s, 'id', None)]
            if ids:
                rows = db.session.query(
                    Payment.invoice_id,
                    func.coalesce(func.sum(Payment.amount_paid), 0)
                ).filter(
                    Payment.invoice_type == 'salary',
                    Payment.invoice_id.in_(ids)
                ).group_by(Payment.invoice_id).all()
                for sid, paid in rows:
                    paid_map[int(sid)] = float(paid or 0.0)
    except Exception:
        paid_map = {}

    return render_template(
        'salaries_pay.html',
        employees=employees,
        month=selected_month,
        salaries=current_salaries,
        selected_employee=selected_employee,
        selected_salary=selected_salary,
        defaults_map=defaults_map,
        prev_due_map=prev_due_map,
        paid_map=paid_map
    )


@main.route('/print/salary-receipt')
@login_required
def salary_receipt():
    # Accept multiple payment ids: ?pids=1,2,3
    pids_param = (request.args.get('pids') or '').strip()
    try:
        ids = [int(x) for x in pids_param.split(',') if x.strip().isdigit()]
    except Exception:
        ids = []
    payments = []
    if ids:
        try:
            payments = Payment.query.filter(Payment.id.in_(ids)).all()
        except Exception:
            payments = []
    # Group by employee and month for display
    items = []
    try:
        for p in (payments or []):
            s = Salary.query.get(int(p.invoice_id)) if getattr(p, 'invoice_type', '') == 'salary' else None
            if not s:
                continue
            emp = Employee.query.get(int(s.employee_id)) if getattr(s, 'employee_id', None) else None
            items.append({
                'employee': getattr(emp, 'full_name', 'Employee'),
                'year': int(getattr(s, 'year', 0) or 0),
                'month': int(getattr(s, 'month', 0) or 0),
                'amount': float(getattr(p, 'amount_paid', 0) or 0),
                'method': getattr(p, 'payment_method', '-') or '-',
                'payment_date': getattr(p, 'payment_date', None),
            })
    except Exception:
        items = []
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    return render_template('print/payroll.html', items=items, settings=settings)


@main.route('/salaries/statements', methods=['GET'], endpoint='salaries_statements')
@login_required
def salaries_statements():
    # Accept either ?month=YYYY-MM or ?year=&month=
    month_param = (request.args.get('month') or '').strip()
    status_f = (request.args.get('status') or '').strip().lower()
    if '-' in month_param:
        try:
            y, m = month_param.split('-'); year = int(y); month = int(m)
        except Exception:
            year = datetime.utcnow().year; month = datetime.utcnow().month
    else:
        year = request.args.get('year', type=int) or datetime.utcnow().year
        month = request.args.get('month', type=int) or datetime.utcnow().month

    from sqlalchemy import func
    rows = []
    totals = {'basic': 0.0, 'allow': 0.0, 'ded': 0.0, 'prev': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0}

    try:
        # Load all employees to always show everyone
        employees = Employee.query.order_by(Employee.full_name.asc()).all()

        # Defaults map
        try:
            from models import EmployeeSalaryDefault
            defaults_map = {d.employee_id: d for d in EmployeeSalaryDefault.query.all()}
        except Exception:
            defaults_map = {}

        # Helper month iterator
        def month_iter(y0, m0, y1, m1):
            y, m = y0, m0
            cnt = 0
            while (y < y1) or (y == y1 and m <= m1):
                yield y, m
                m += 1
                if m > 12:
                    m = 1; y += 1
                cnt += 1
                if cnt > 240:
                    break

        for emp in (employees or []):
            # Determine start month
            if getattr(emp, 'hire_date', None):
                y0, m0 = int(emp.hire_date.year), int(emp.hire_date.month)
            else:
                y0, m0 = year, month

            # Build dues per month from hire date to current
            dues_map = {}
            month_keys = []
            sal_ids = []
            for yy, mm in month_iter(y0, m0, year, month):
                month_keys.append((yy, mm))
                srow = Salary.query.filter_by(employee_id=emp.id, year=yy, month=mm).first()
                if srow:
                    base = float(srow.basic_salary or 0.0)
                    allow = float(srow.allowances or 0.0)
                    ded = float(srow.deductions or 0.0)
                    due_amt = max(0.0, base + allow - ded)
                    sal_ids.append(int(srow.id))
                else:
                    d = defaults_map.get(int(emp.id))
                    base = float(getattr(d, 'base_salary', 0.0) or 0.0)
                    allow = float(getattr(d, 'allowances', 0.0) or 0.0)
                    ded = float(getattr(d, 'deductions', 0.0) or 0.0)
                    due_amt = max(0.0, base + allow - ded)
                dues_map[(yy, mm)] = {'base': base, 'allow': allow, 'ded': ded, 'due': due_amt}

            # Total payments recorded across all months for this employee
            total_paid_all = 0.0
            if sal_ids:
                total_paid_all = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                                       .filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_ids))
                                       .scalar() or 0.0)

            # FIFO allocation: previous months first, then current
            remaining_payment = total_paid_all
            # previous months
            prev_due_sum = 0.0
            prev_paid_alloc = 0.0
            for yy, mm in month_keys[:-1]:
                due_amt = float(dues_map[(yy, mm)]['due'] or 0.0)
                prev_due_sum += due_amt
                if remaining_payment <= 0:
                    continue
                pay = due_amt if remaining_payment >= due_amt else remaining_payment
                prev_paid_alloc += pay
                remaining_payment -= pay

            # current month
            c_base = float(dues_map[(year, month)]['base'] or 0.0)
            c_allow = float(dues_map[(year, month)]['allow'] or 0.0)
            c_ded = float(dues_map[(year, month)]['ded'] or 0.0)
            c_due = float(dues_map[(year, month)]['due'] or 0.0)
            c_paid_alloc = 0.0
            if remaining_payment > 0 and c_due > 0:
                c_paid_alloc = c_due if remaining_payment >= c_due else remaining_payment
                remaining_payment -= c_paid_alloc

            prev_remaining = max(0.0, prev_due_sum - prev_paid_alloc)
            total = max(0.0, c_due + prev_remaining)
            paid_display = c_paid_alloc
            remaining_total = max(0.0, total - paid_display)

            status = 'paid' if (total > 0 and remaining_total <= 0.01) else ('partial' if paid_display > 0 else ('paid' if total == 0 else 'due'))

            rows.append({
                'employee_id': int(emp.id),
                'employee_name': emp.full_name,
                'basic': c_base,
                'allow': c_allow,
                'ded': c_ded,
                'prev': prev_remaining,
                'total': total,
                'paid': paid_display,
                'remaining': remaining_total,
                'status': status,
                'prev_details': []
            })
            totals['basic'] += c_base
            totals['allow'] += c_allow
            totals['ded'] += c_ded
            totals['prev'] += prev_remaining
            totals['total'] += total
            totals['paid'] += paid_display
            totals['remaining'] += remaining_total
    except Exception:
        pass

    # Apply optional status filter after computing per-employee rows
    if status_f in ('paid','due','partial'):
        try:
            rows = [r for r in rows if (str(r.get('status') or '').lower() == status_f)]
            totals = {
                'basic': sum(float(r.get('basic') or 0) for r in rows),
                'allow': sum(float(r.get('allow') or 0) for r in rows),
                'ded': sum(float(r.get('ded') or 0) for r in rows),
                'prev': sum(float(r.get('prev') or 0) for r in rows),
                'total': sum(float(r.get('total') or 0) for r in rows),
                'paid': sum(float(r.get('paid') or 0) for r in rows),
                'remaining': sum(float(r.get('remaining') or 0) for r in rows),
            }
        except Exception:
            pass

    return render_template('salaries_statements.html', year=year, month=month, rows=rows, totals=totals, status_f=status_f)



@main.route('/reports/print/salaries', methods=['GET'], endpoint='reports_print_salaries')
@login_required
def reports_print_salaries():
    # Redirect to detailed payroll statement to ensure new screen is used everywhere
    try:
        q = request.query_string.decode('utf-8') if request.query_string else ''
    except Exception:
        q = ''
    target = url_for('main.reports_print_salaries_detailed')
    if q:
        target = f"{target}?{q}"
    return redirect(target)


@main.route('/reports/print/salaries_detailed', methods=['GET'], endpoint='reports_print_salaries_detailed')
@login_required
def reports_print_salaries_detailed():
    # period input
    month_param = (request.args.get('month') or '').strip()
    if '-' in month_param:
        try:
            y, m = month_param.split('-'); year = int(y); month = int(m)
        except Exception:
            year = datetime.utcnow().year; month = datetime.utcnow().month
    else:
        year = request.args.get('year', type=int) or datetime.utcnow().year
        month = request.args.get('month', type=int) or datetime.utcnow().month

    # header
    try:
        settings = Settings.query.first()
        company_name = settings.company_name or 'Company'
    except Exception:
        company_name = 'Company'
    period_label = f"{year:04d}-{month:02d}"

    # Build detailed month-by-month allocations (FIFO: pay oldest dues first)
    employees_data = []
    try:
        # defaults
        try:
            from models import EmployeeSalaryDefault
            defaults_map = {d.employee_id: d for d in EmployeeSalaryDefault.query.all()}
        except Exception:
            defaults_map = {}

        # helper iterator
        def month_iter(y0, m0, y1, m1):
            y, m = y0, m0
            cnt = 0
            while (y < y1) or (y == y1 and m <= m1):
                yield y, m
                m += 1
                if m > 12:
                    m = 1; y += 1
                cnt += 1
                if cnt > 240:
                    break

        for emp in Employee.query.order_by(Employee.full_name.asc()).all():
            # range from hire to current+1 (to place credit if needed)
            if getattr(emp, 'hire_date', None):
                y0, m0 = int(emp.hire_date.year), int(emp.hire_date.month)
            else:
                y0, m0 = year, month

            # gather dues per month and salary ids
            dues = []
            sal_ids = []
            for yy, mm in month_iter(y0, m0, year, month):
                srow = Salary.query.filter_by(employee_id=emp.id, year=yy, month=mm).first()
                if srow:
                    base = float(srow.basic_salary or 0.0)
                    allow = float(srow.allowances or 0.0)
                    ded = float(srow.deductions or 0.0)
                    due_amt = max(0.0, base + allow - ded)
                    sal_ids.append(int(srow.id))
                else:
                    d = defaults_map.get(int(emp.id))
                    base = float(getattr(d, 'base_salary', 0.0) or 0.0)
                    allow = float(getattr(d, 'allowances', 0.0) or 0.0)
                    ded = float(getattr(d, 'deductions', 0.0) or 0.0)
                    due_amt = max(0.0, base + allow - ded)
                dues.append({'y': yy, 'm': mm, 'base': base, 'allow': allow, 'ded': ded, 'due': due_amt})

            total_paid_all = 0.0
            if sal_ids:
                total_paid_all = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                                       .filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_ids))
                                       .scalar() or 0.0)

            # FIFO allocate against previous dues first
            remaining_payment = total_paid_all
            detailed_rows = []
            prev_running_due = 0.0
            for d in dues:
                month_due = float(d['due'] or 0.0)
                prev_for_row = float(prev_running_due or 0.0)
                total_for_row = prev_for_row + month_due

                pay = 0.0
                if remaining_payment > 0 and total_for_row > 0:
                    pay = total_for_row if remaining_payment >= total_for_row else remaining_payment
                    remaining_payment -= pay

                remaining = total_for_row - pay

                # Status with tolerance for tiny residuals
                tol = 0.01
                if total_for_row <= tol and pay <= tol:
                    status = 'paid'
                elif remaining <= tol:
                    status = 'paid'
                elif pay > tol:
                    status = 'partial'
                else:
                    status = 'due'

                detailed_rows.append(type('Row', (), {
                    'month': date(d['y'], d['m'], 1),
                    'basic': d['base'],
                    'allowances': d['allow'],
                    'deductions': d['ded'],
                    'prev_due': prev_for_row,
                    'total': total_for_row,
                    'paid_amount': pay,
                    'remaining_amount': remaining,
                    'status': status,
                }))

                # Carry forward any unpaid balance as previous due for next month
                prev_running_due = remaining

            # leftover payment -> credit month (next month)
            if remaining_payment > 0:
                from calendar import monthrange
                nm_y = year + (1 if month == 12 else 0)
                nm_m = 1 if month == 12 else month + 1
                detailed_rows.append(type('Row', (), {
                    'month': date(nm_y, nm_m, 1),
                    'basic': 0.0,
                    'allowances': 0.0,
                    'deductions': 0.0,
                    'prev_due': 0.0,
                    'total': 0.0,
                    'paid_amount': remaining_payment,
                    'remaining_amount': -remaining_payment,
                    'status': 'credit',
                }))

            employees_data.append(type('Emp', (), {
                'name': emp.full_name,
                'salaries': detailed_rows
            }))
    except Exception:
        employees_data = []

    return render_template(
        'print/payroll_statement.html',
        company_name=company_name,
        period_label=period_label,
        generated_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
        employees=employees_data
    )



@main.route('/employees/payroll', methods=['GET'], endpoint='payroll')
@login_required
def payroll():
    # Exact context and data shape per provided template
    from calendar import month_name
    years = list(range(datetime.utcnow().year - 2, datetime.utcnow().year + 3))
    year = request.args.get('year', type=int) or datetime.utcnow().year
    month = request.args.get('month', type=int) or datetime.utcnow().month
    status = (request.args.get('status') or 'all').strip().lower()

    # months as value/label pairs
    months = [{ 'value': i, 'label': month_name[i] } for i in range(1, 13)]

    # Build payrolls rows
    payrolls = []
    try:
        from sqlalchemy import func
        emps = Employee.query.order_by(Employee.full_name.asc()).all()
        from models import EmployeeSalaryDefault
        defaults_map = {int(d.employee_id): d for d in EmployeeSalaryDefault.query.all()}
        for emp in (emps or []):
            # current month components
            s = Salary.query.filter_by(employee_id=emp.id, year=year, month=month).first()
            if s:
                basic = float(s.basic_salary or 0)
                allow = float(s.allowances or 0)
                ded = float(s.deductions or 0)
            else:
                d = defaults_map.get(int(emp.id))
                basic = float(getattr(d, 'base_salary', 0) or 0)
                allow = float(getattr(d, 'allowances', 0) or 0)
                ded = float(getattr(d, 'deductions', 0) or 0)
            current_due = max(0.0, basic + allow - ded)

            # previous dues sum (exclude current)
            prev_due = 0.0
            if getattr(emp, 'hire_date', None):
                sy, sm = int(emp.hire_date.year), int(emp.hire_date.month)
            else:
                sy, sm = year, month
            yy, mm = sy, sm
            guard = 0
            while (yy < year) or (yy == year and mm < month):
                s2 = Salary.query.filter_by(employee_id=emp.id, year=yy, month=mm).first()
                if s2:
                    bb = float(s2.basic_salary or 0); aa = float(s2.allowances or 0); dd = float(s2.deductions or 0)
                else:
                    d2 = defaults_map.get(int(emp.id))
                    bb = float(getattr(d2, 'base_salary', 0) or 0)
                    aa = float(getattr(d2, 'allowances', 0) or 0)
                    dd = float(getattr(d2, 'deductions', 0) or 0)
                prev_due += max(0.0, bb + aa - dd)
                mm += 1
                if mm > 12:
                    mm = 1; yy += 1
                guard += 1
                if guard > 240:
                    break

            # total paid overall across existing salary rows
            sal_ids = [int(x.id) for x in Salary.query.filter_by(employee_id=emp.id).all() if getattr(x, 'id', None)]
            paid_all = 0.0
            if sal_ids:
                paid_all = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                                 .filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_ids)).scalar() or 0.0)

            # FIFO: allocate to previous first
            remaining_payment = paid_all
            prev_alloc = min(prev_due, remaining_payment)
            remaining_payment -= prev_alloc
            current_alloc = min(current_due, remaining_payment)

            total = current_due + max(0.0, prev_due - prev_alloc)
            remaining = max(0.0, total - current_alloc)
            status_v = 'paid' if (total > 0 and remaining <= 0.01) else ('partial' if current_alloc > 0 else ('paid' if total == 0 else 'due'))

            payrolls.append(type('Row', (), {
                'employee': type('E', (), {'id': int(emp.id), 'full_name': emp.full_name}),
                'basic': basic,
                'allowances': allow,
                'deductions': ded,
                'prev_due': max(0.0, prev_due - prev_alloc),
                'total': total,
                'paid': current_alloc,
                'remaining': remaining,
                'status': status_v,
            }))
    except Exception:
        payrolls = []

    if status in ('paid','due','partial'):
        payrolls = [r for r in payrolls if (str(getattr(r, 'status', '')).lower() == status)]

    return render_template('payroll.html', years=years, months=months, year=year, month=month, status=status, payrolls=payrolls)


@main.route('/employees/<int:emp_id>/pay', methods=['GET', 'POST'], endpoint='pay_salary')
@login_required
def pay_salary(emp_id):
    emp = Employee.query.get_or_404(emp_id)

    # Support provided template shape and query params (employee_id, year, month)
    selected_employee_id = request.args.get('employee_id', type=int) or int(emp.id)
    year = request.args.get('year', type=int) or datetime.utcnow().year
    month = request.args.get('month', type=int) or datetime.utcnow().month

    if request.method == 'POST':
        amount = request.form.get('paid_amount', type=float) or 0.0
        method = (request.form.get('payment_method') or 'cash')
        month_str = f"{year:04d}-{month:02d}"
        with current_app.test_request_context('/salaries/pay', method='POST', data={
            'employee_id': str(int(selected_employee_id)),
            'month': month_str,
            'paid_amount': str(amount),
            'payment_method': method,
        }):
            try:
                return salaries_pay()
            except Exception as e:
                flash(f'Error saving salary/payment: {e}', 'danger')
                return redirect(url_for('main.pay_salary', emp_id=emp.id, employee_id=selected_employee_id, year=year, month=month))

    # Build employees list for dropdown
    try:
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        employees = []

    # Build salary summary for selected employee
    # Prefer hour-based calculation for the selected period if available
    from models import EmployeeSalaryDefault, DepartmentRate, EmployeeHours
    d = EmployeeSalaryDefault.query.filter_by(employee_id=selected_employee_id).first()
    # Defaults
    default_allow = float(getattr(d, 'allowances', 0) or 0)
    default_ded = float(getattr(d, 'deductions', 0) or 0)
    default_base = float(getattr(d, 'base_salary', 0) or 0)
    # Hour-based override
    try:
        hrs_row = EmployeeHours.query.filter_by(employee_id=selected_employee_id, year=year, month=month).first()
        dept_name = (emp.department or '').lower()
        rate_row = DepartmentRate.query.filter(DepartmentRate.name == dept_name).first()
        hourly_rate = float(getattr(rate_row, 'hourly_rate', 0) or 0)
        hour_based_base = float(getattr(hrs_row, 'hours', 0) or 0) * hourly_rate if hrs_row else 0.0
    except Exception:
        hour_based_base = 0.0
    base = hour_based_base if hour_based_base > 0 else default_base
    allow = default_allow
    ded = default_ded
    # Previous due: sum of previous months' totals minus sum of payments (outstanding arrears)
    from sqlalchemy import func as _func
    try:
        # Sum totals and paid amounts for months strictly before the selected month
        rem_q = db.session.query(
            _func.coalesce(_func.sum(Salary.total_salary), 0),
            _func.coalesce(_func.sum(Payment.amount_paid), 0)
        ).outerjoin(
            Payment, (Payment.invoice_type == 'salary') & (Payment.invoice_id == Salary.id)
        ).filter(
            Salary.employee_id == selected_employee_id
        ).filter(
            (Salary.year < year) | ((Salary.year == year) & (Salary.month < month))
        )
        # Respect hire date if available
        try:
            emp_obj = Employee.query.get(selected_employee_id)
            if getattr(emp_obj, 'hire_date', None):
                hd_y = int(emp_obj.hire_date.year)
                hd_m = int(emp_obj.hire_date.month)
                rem_q = rem_q.filter((Salary.year > hd_y) | ((Salary.year == hd_y) & (Salary.month >= hd_m)))
        except Exception:
            pass
        tot_sum, paid_sum = rem_q.first()
        prev_due = max(0.0, float(tot_sum or 0) - float(paid_sum or 0))
    except Exception:
        prev_due = 0.0

    salary_vm = {
        'basic': base,
        'allowances': allow,
        'deductions': ded,
        'prev_due': prev_due,
        'total': max(0.0, base + allow - ded + prev_due),
    }

    # Determine oldest unpaid month for this employee (FIFO across months)
    next_due_year = year
    next_due_month = month
    try:
        # Determine start (hire date or current selection)
        if getattr(emp, 'hire_date', None):
            start_y, start_m = int(emp.hire_date.year), int(emp.hire_date.month)
        else:
            start_y, start_m = year, month

        # Sum of all payments against this employee's salary rows
        sal_ids_q = Salary.query.with_entities(Salary.id).filter_by(employee_id=selected_employee_id).all()
        sal_id_list = [int(sid) for (sid,) in sal_ids_q] if sal_ids_q else []
        total_paid_all = 0.0
        if sal_id_list:
            total_paid_all = float(db.session.query(_func.coalesce(_func.sum(Payment.amount_paid), 0))
                                   .filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_id_list))
                                   .scalar() or 0.0)

        # Iterate months from start to selected period; carry previous remaining
        def _month_iter(y0, m0, y1, m1):
            y, m = y0, m0
            cnt = 0
            while (y < y1) or (y == y1 and m <= m1):
                yield y, m
                m += 1
                if m > 12:
                    m = 1; y += 1
                cnt += 1
                if cnt > 240:
                    break

        remaining_payment = total_paid_all
        prev_running = 0.0
        found = False
        for yy, mm in _month_iter(start_y, start_m, year, month):
            srow = Salary.query.filter_by(employee_id=selected_employee_id, year=yy, month=mm).first()
            if srow:
                _b = float(srow.basic_salary or 0.0)
                _a = float(srow.allowances or 0.0)
                _d = float(srow.deductions or 0.0)
                month_due = max(0.0, _b + _a - _d)
            else:
                # Fallback to defaults for months without a stored Salary row
                month_due = max(0.0, base + allow - ded)

            total_for_row = prev_running + month_due
            pay_here = min(remaining_payment, total_for_row)
            remaining_payment -= pay_here
            remaining_row = max(0.0, total_for_row - pay_here)
            if (remaining_row > 0) and (not found):
                next_due_year, next_due_month = yy, mm
                found = True
                break
            prev_running = remaining_row
    except Exception:
        next_due_year, next_due_month = year, month

    from calendar import month_name as _mn
    next_due_label = f"{_mn[next_due_month]}, {next_due_year}"

    # Current month salaries table
    current_month_salaries = []
    try:
        rows = Salary.query.filter_by(year=year, month=month).all()
    except Exception:
        rows = []
    # Build paid map for current month rows
    paid_map = {}
    try:
        ids = [int(r.id) for r in rows if getattr(r, 'id', None)]
        if ids:
            for sid, paid in db.session.query(Payment.invoice_id, _func.coalesce(_func.sum(Payment.amount_paid), 0)).\
                    filter(Payment.invoice_type=='salary', Payment.invoice_id.in_(ids)).group_by(Payment.invoice_id):
                paid_map[int(sid)] = float(paid or 0)
    except Exception:
        paid_map = {}
    for r in (rows or []):
        bb = float(r.basic_salary or 0); aa = float(r.allowances or 0); dd = float(r.deductions or 0)
        prev = float(r.previous_salary_due or 0)
        net = max(0.0, bb + aa - dd + prev)
        paid = float(paid_map.get(int(r.id), 0) or 0)
        remaining = max(0.0, net - paid)
        st = (r.status or '-')
        emp_obj = Employee.query.get(int(r.employee_id)) if getattr(r, 'employee_id', None) else None
        current_month_salaries.append(type('Row', (), {
            'employee': type('E', (), {'full_name': getattr(emp_obj, 'full_name', f'#{r.employee_id}') }),
            'basic': bb,
            'allowances': aa,
            'deductions': dd,
            'prev_due': prev,
            'total': net,
            'paid': paid,
            'remaining': remaining,
            'status': st,
        }))

    from calendar import month_name
    month_name_str = month_name[month]
    return render_template('pay_salary.html',
                           employees=employees,
                           selected_employee_id=selected_employee_id,
                           salary=salary_vm,
                           year=year,
                           month=month,
                           month_name=month_name_str,
                           current_month_salaries=current_month_salaries,
                           next_due_year=next_due_year,
                           next_due_month=next_due_month,
                           next_due_label=next_due_label)


# --- Printing: Payroll summary for a month ---
@main.route('/payroll/print/<int:year>/<int:month>', methods=['GET'], endpoint='payroll_print')
@login_required
def payroll_print(year: int, month: int):
    try:
        rows = Salary.query.filter_by(year=year, month=month).all()
    except Exception:
        rows = []
    # Map Salary rows to view rows expected by template (basic, allowances, deductions, prev_due, total, paid, remaining, status)
    from sqlalchemy import func as _func
    view_rows = []
    try:
        ids = [int(r.id) for r in rows if getattr(r, 'id', None)]
        paid_map = {}
        if ids:
            for sid, paid in db.session.query(Payment.invoice_id, _func.coalesce(_func.sum(Payment.amount_paid), 0)).\
                    filter(Payment.invoice_type=='salary', Payment.invoice_id.in_(ids)).group_by(Payment.invoice_id):
                paid_map[int(sid)] = float(paid or 0)
        for r in (rows or []):
            emp_obj = Employee.query.get(int(r.employee_id)) if getattr(r, 'employee_id', None) else None
            base = float(r.basic_salary or 0); allow = float(r.allowances or 0); ded = float(r.deductions or 0)
            prev = float(r.previous_salary_due or 0)
            total = max(0.0, float(r.total_salary or (base + allow - ded + prev)))
            paid = float(paid_map.get(int(r.id), 0) or 0)
            remaining = max(0.0, total - paid)
            status_v = 'paid' if (total > 0 and remaining <= 0.01) else ('partial' if paid > 0 else ('paid' if total == 0 else 'due'))
            view_rows.append(type('Row', (), {
                'employee': type('E', (), {'full_name': getattr(emp_obj, 'full_name', f'#{r.employee_id}') }),
                'basic': base,
                'allowances': allow,
                'deductions': ded,
                'prev_due': prev,
                'total': total,
                'paid': paid,
                'remaining': remaining,
                'status': status_v,
            }))
    except Exception:
        view_rows = []
    return render_template('payroll-reports.html',
                           mode='monthly',
                           payrolls=view_rows,
                           year=year,
                           month=month,
                           report_title='🧾 Monthly Payroll Statement / كشف رواتب الشهر')


# --- Employees Settings: Hour-based payroll ---
@main.route('/employees/settings', methods=['GET', 'POST'], endpoint='employees_settings')
@login_required
def employees_settings():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month

    # Department management: add/update/delete
    mode = (request.form.get('mode') or '').strip().lower() if request.method == 'POST' else ''
    if request.method == 'POST' and mode in ('add_dept','delete_dept',''):
        # add/update via form (empty mode or add_dept), delete via delete_dept
        name = (request.form.get('dept_name') or request.form.get('new_dept_name') or '').strip().lower()
        rate = request.form.get('hourly_rate', type=float)
        if rate is None:
            rate = request.form.get('new_hourly_rate', type=float) or 0.0
        y_recalc = request.form.get('year', type=int) or year
        m_recalc = request.form.get('month', type=int) or month
        if name:
            if mode == 'delete_dept':
                row = DepartmentRate.query.filter_by(name=name).first()
                if row:
                    db.session.delete(row)
                    db.session.commit()
            else:
                row = DepartmentRate.query.filter_by(name=name).first()
                if row:
                    row.hourly_rate = rate
                else:
                    row = DepartmentRate(name=name, hourly_rate=rate)
                    db.session.add(row)
                db.session.commit()
        # Recalculate all employees for selected period using updated rates
        dept_rates = {dr.name: float(dr.hourly_rate or 0.0) for dr in DepartmentRate.query.all()}
        emps = Employee.query.order_by(Employee.full_name.asc()).all()
        for emp in emps:
            hrs = EmployeeHours.query.filter_by(employee_id=emp.id, year=y_recalc, month=m_recalc).first()
            rate_emp = dept_rates.get((emp.department or '').lower(), 0.0)
            total_basic = float(hrs.hours) * float(rate_emp) if hrs else 0.0
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first()
            allow = float(getattr(d, 'allowances', 0.0) or 0.0)
            ded = float(getattr(d, 'deductions', 0.0) or 0.0)
            prev_due = 0.0
            total = max(0.0, total_basic + allow - ded + prev_due)
            s = Salary.query.filter_by(employee_id=emp.id, year=y_recalc, month=m_recalc).first()
            if not s:
                s = Salary(employee_id=emp.id, year=y_recalc, month=m_recalc,
                           basic_salary=total_basic, allowances=allow,
                           deductions=ded, previous_salary_due=prev_due,
                           total_salary=total, status='due')
                db.session.add(s)
            else:
                s.basic_salary = total_basic
                s.allowances = allow
                s.deductions = ded
                s.previous_salary_due = prev_due
                s.total_salary = total
        db.session.commit()
        return redirect(url_for('main.employees_settings', year=y_recalc, month=m_recalc))

    # Save monthly hours and recalc salaries
    if request.method == 'POST' and mode == 'hours':
        year = request.form.get('year', type=int) or year
        month = request.form.get('month', type=int) or month
        # Department map
        dept_rates = {dr.name: float(dr.hourly_rate or 0.0) for dr in DepartmentRate.query.all()}
        # Process each employee field hours_<id>
        emps = Employee.query.order_by(Employee.full_name.asc()).all()
        for emp in emps:
            hours_val = request.form.get(f'hours_{emp.id}', type=float)
            if hours_val is None:
                continue
            rec = EmployeeHours.query.filter_by(employee_id=emp.id, year=year, month=month).first()
            if not rec:
                rec = EmployeeHours(employee_id=emp.id, year=year, month=month, hours=hours_val)
                db.session.add(rec)
            else:
                rec.hours = hours_val
        db.session.commit()

        # Recalculate Salary rows for this period from hours and department rate
        for emp in emps:
            hrs = EmployeeHours.query.filter_by(employee_id=emp.id, year=year, month=month).first()
            rate = dept_rates.get((emp.department or '').lower(), 0.0)
            total_basic = float(hrs.hours) * float(rate) if hrs else 0.0
            # Use defaults for allowances/deductions
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first()
            allow = float(getattr(d, 'allowances', 0.0) or 0.0)
            ded = float(getattr(d, 'deductions', 0.0) or 0.0)
            prev_due = 0.0
            total = max(0.0, total_basic + allow - ded + prev_due)

            s = Salary.query.filter_by(employee_id=emp.id, year=year, month=month).first()
            if not s:
                s = Salary(employee_id=emp.id, year=year, month=month,
                           basic_salary=total_basic, allowances=allow,
                           deductions=ded, previous_salary_due=prev_due,
                           total_salary=total, status='due')
                db.session.add(s)
            else:
                s.basic_salary = total_basic
                s.allowances = allow
                s.deductions = ded
                s.previous_salary_due = prev_due
                s.total_salary = total
        db.session.commit()

        flash('تم حفظ الساعات وتحديث الرواتب', 'success')
        return redirect(url_for('main.employees_settings', year=year, month=month))

    # GET: render settings
    dept_rates = DepartmentRate.query.order_by(DepartmentRate.name.asc()).all()
    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    hours = EmployeeHours.query.filter_by(year=year, month=month).all()
    hours_map = {h.employee_id: float(h.hours or 0.0) for h in hours}
    dept_rate_map = {dr.name: float(dr.hourly_rate or 0.0) for dr in dept_rates}
    return render_template('employees_settings.html',
                           dept_rates=dept_rates,
                           employees=employees,
                           hours_map=hours_map,
                           dept_rate_map=dept_rate_map,
                           year=year, month=month)

# --- Printing: Bulk salary receipt for selected employees (current period) ---
@main.route('/salary/receipt', methods=['POST'], endpoint='salary_receipt_bulk')
@login_required
@csrf.exempt
def salary_receipt_bulk():
    from calendar import month_name as _month_name
    # Determine target period
    year = request.form.get('year', type=int) or datetime.utcnow().year
    month = request.form.get('month', type=int) or datetime.utcnow().month
    selected_ids = request.form.getlist('employee_ids') or []
    try:
        employee_ids = [int(i) for i in selected_ids if str(i).isdigit()]
    except Exception:
        employee_ids = []

    # Build payments-like rows for printing only
    payments = []
    try:
        # Defaults map
        try:
            from models import EmployeeSalaryDefault
            defaults_map = {int(d.employee_id): d for d in EmployeeSalaryDefault.query.all()}
        except Exception:
            defaults_map = {}

        for emp_id in (employee_ids or []):
            emp = Employee.query.get(emp_id)
            if not emp:
                continue
            # Current month salary components
            s = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
            if s:
                base = float(s.basic_salary or 0)
                allow = float(s.allowances or 0)
                ded = float(s.deductions or 0)
                prev = float(s.previous_salary_due or 0)
                total = max(0.0, base + allow - ded + prev)
                # Sum paid against this salary record
                from sqlalchemy import func as _func
                paid = float(db.session.query(_func.coalesce(_func.sum(Payment.amount_paid), 0))
                             .filter(Payment.invoice_type=='salary', Payment.invoice_id==s.id)
                             .scalar() or 0.0)
            else:
                d = defaults_map.get(emp_id)
                base = float(getattr(d, 'base_salary', 0) or 0)
                allow = float(getattr(d, 'allowances', 0) or 0)
                ded = float(getattr(d, 'deductions', 0) or 0)
                prev = 0.0
                total = max(0.0, base + allow - ded)
                paid = 0.0
            net_remaining = max(0.0, total - paid)

            payments.append(type('P', (), {
                'employee': emp,
                'basic': base,
                'allowances': allow,
                'deductions': ded,
                'prev_due': prev,
                'paid_amount': paid,
                # In receipt, "Net Salary" should reflect the month's net total (not remaining)
                'net_salary': total,
                # Optionally expose remaining for templates that may show it later
                'remaining': net_remaining,
                'method': 'cash',
            }))
    except Exception:
        payments = []

    # Company name
    try:
        settings = Settings.query.first()
        company_name = settings.company_name or 'Company'
    except Exception:
        company_name = 'Company'

    from datetime import datetime as _dt
    return render_template(
        'payroll-reports.html',
        mode='receipt',
        payments=payments,
        company_name=company_name,
        payment_date=_date.today(),
        now=_dt.now().strftime('%Y-%m-%d %H:%M'),
        report_title='🧾 Salary Payment Receipt / إيصال سداد رواتب'
    )
@main.route('/reports/print/salaries', methods=['GET'], endpoint='reports_print_salaries_legacy')
@login_required
def reports_print_salaries_legacy():
    """Back-compat: redirect to new detailed payroll statement with same query params."""
    try:
        q = request.query_string.decode('utf-8') if request.query_string else ''
    except Exception:
        q = ''
    target = url_for('main.reports_print_salaries_detailed')
    if q:
        target = f"{target}?{q}"
    return redirect(target)

@main.route('/payments', endpoint='payments')
@login_required
def payments():
    # Build unified list of purchase and expense invoices with paid totals
    status_f = (request.args.get('status') or '').strip().lower()
    type_f = (request.args.get('type') or '').strip().lower()
    invoices = []
    PAYMENT_METHODS = ['CASH','CARD','BANK','ONLINE','MADA','VISA']

    try:
        # Use decimal rounding to avoid float precision issues causing wrong statuses
        from decimal import Decimal, ROUND_HALF_UP
        def to_cents(value):
            try:
                return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return Decimal('0.00')
        def compute_status(total_amt, paid_amt):
            total_c = to_cents(total_amt)
            paid_c = to_cents(paid_amt)
            # Treat small residuals (<= 0.01) as fully paid
            if (total_c - paid_c) <= Decimal('0.01'):
                return 'paid'
            if paid_c > Decimal('0.00'):
                return 'partial'
            return 'unpaid'
        # Purchases
        q = PurchaseInvoice.query
        for inv in q.order_by(PurchaseInvoice.created_at.desc()).limit(1000).all():
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                         .filter(Payment.invoice_id == inv.id, Payment.invoice_type == 'purchase').scalar() or 0.0)
            status_calc = compute_status(total, paid)
            invoices.append({
                'id': inv.id,
                'invoice_number': getattr(inv, 'invoice_number', None) or inv.id,
                'type': 'purchase',
                'party': inv.supplier_name or 'Supplier',
                'total': total,
                'paid': paid,
                'status': status_calc,
                'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            })
    except Exception:
        pass

    try:
        # Expenses
        q = ExpenseInvoice.query
        for inv in q.order_by(ExpenseInvoice.created_at.desc()).limit(1000).all():
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                         .filter(Payment.invoice_id == inv.id, Payment.invoice_type == 'expense').scalar() or 0.0)
            status_calc = compute_status(total, paid)
            invoices.append({
                'id': inv.id,
                'invoice_number': getattr(inv, 'invoice_number', None) or inv.id,
                'type': 'expense',
                'party': 'Expense',
                'total': total,
                'paid': paid,
                'status': status_calc,
                'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            })



    except Exception:
        pass

    # Apply filters
    if status_f:
        invoices = [i for i in invoices if (i.get('status') or '').lower() == status_f]
    if type_f:
        # normalize: purchases->purchase, expenses->expense, sales ignored
        if type_f == 'purchases': type_f = 'purchase'
        if type_f == 'expenses': type_f = 'expense'
        invoices = [i for i in invoices if (i.get('type') or '') == type_f]

    return render_template('payments.html', invoices=invoices, PAYMENT_METHODS=PAYMENT_METHODS, status_f=status_f, type_f=type_f)

@main.route('/reports', endpoint='reports')
@login_required
def reports():
    return render_template('reports.html')

# ---------- POS/Tables: basic navigation ----------
@main.route('/sales/<branch_code>/tables', endpoint='sales_tables')
@login_required
def sales_tables(branch_code):
    if not user_can('sales','view', branch_code):
        flash('لا تملك صلاحية الوصول لفرع المبيعات هذا', 'warning')
        return redirect(url_for('main.sales'))
    branch_label = BRANCH_LABELS.get(branch_code, branch_code)

    grouped_tables = []
    tables = []

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
                    layout = bracket[:-1].strip()
                except Exception:
                    pass
            return visible, layout

        sections = TableSection.query.filter_by(branch_code=branch_code).order_by(TableSection.sort_order, TableSection.id).all()
        assignments = TableSectionAssignment.query.filter_by(branch_code=branch_code).all()

        # Build status map based on draft orders (occupied / available)
        status_map = {}
        for assignment in assignments:
            number = safe_table_number(assignment.table_number)
            if number <= 0:
                continue
            draft = kv_get(f'draft:{branch_code}:{number}', {}) or {}
            status_map[number] = 'occupied' if (draft.get('items') or []) else 'available'

        assignments_by_section = {}
        for assignment in assignments:
            assignments_by_section.setdefault(assignment.section_id, []).append(assignment)

        # Build grouped tables honoring saved layout and showing empty sections as headers
        for section in sections:
            visible, layout = decode_name(section.name)

            # Collect tables for this section (sorted by table number)
            section_tables = []
            section_assignments = assignments_by_section.get(section.id, [])
            section_assignments.sort(key=lambda a: safe_table_number(a.table_number))
            for assignment in section_assignments:
                number = safe_table_number(assignment.table_number)
                if number <= 0:
                    continue
                section_tables.append({
                    'number': number,
                    'status': status_map.get(number, 'available')
                })

            # Split into rows according to saved layout "1,3,4" etc.
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
                    rows.append(section_tables[i:i+cnt])
                    i += cnt
                if i < len(section_tables):
                    rows.append(section_tables[i:])
            else:
                # If no layout saved and tables exist, place all tables in a single row
                if section_tables:
                    rows = [section_tables]
                else:
                    rows = []

            section_entry = {
                'section': visible or branch_label,
                'rows': rows,
                # Keep flat list for template fallback when rows is empty
                'tables': section_tables
            }

            # Always append the section so saved sections appear even without assignments
            grouped_tables.append(section_entry)

    except Exception as e:
        print(f"[sales_tables] Error loading grouped tables for {branch_code}: {e}")
        grouped_tables = []
        tables = []

    if not grouped_tables:
        settings = kv_get('table_settings', {}) or {}
        default_count = 20
        if branch_code == 'china_town':
            count = int((settings.get('china') or {}).get('count', default_count))
        elif branch_code == 'place_india':
            count = int((settings.get('india') or {}).get('count', default_count))
        else:
            count = default_count
        for i in range(1, count + 1):
            draft = kv_get(f'draft:{branch_code}:{i}', {}) or {}
            status = 'occupied' if (draft.get('items') or []) else 'available'
            tables.append({'number': i, 'status': status})

    return render_template('sales_tables.html', branch_code=branch_code, branch_label=branch_label, tables=tables, grouped_tables=grouped_tables or None)

@main.route('/sales/china_town', endpoint='sales_china')
@login_required
def sales_china():
    return redirect(url_for('main.sales_tables', branch_code='china_town'))


@main.route('/sales/place_india', endpoint='sales_india')
@login_required
def sales_india():
    return redirect(url_for('main.sales_tables', branch_code='place_india'))


@main.route('/pos/<branch_code>', endpoint='pos_home')
@login_required
def pos_home(branch_code):
    if not user_can('sales','view', branch_code):
        flash('\u0644\u0627 \u062a\u0645\u0644\u0643 \u0635\u0644\u0627\u062d\u064a\u0629 \u0627\u0644\u0648\u0635\u0648\u0644 \u0644\u0641\u0631\u0639 \u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a \u0647\u0630\u0627', 'warning')
        return redirect(url_for('main.sales'))

    return redirect(url_for('main.sales_tables', branch_code=branch_code))


@main.route('/pos/<branch_code>/table/<int:table_number>', endpoint='pos_table')
@login_required
def pos_table(branch_code, table_number):
    if not user_can('sales','view', branch_code):
        flash('\u0644\u0627 \u062a\u0645\u0644\u0643 \u0635\u0644\u0627\u062d\u064a\u0629 \u0627\u0644\u0648\u0635\u0648\u0644 \u0644\u0641\u0631\u0639 \u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a \u0647\u0630\u0627', 'warning')
        return redirect(url_for('main.sales'))
    branch_label = BRANCH_LABELS.get(branch_code, branch_code)
    vat_rate = 15
    # Load any existing draft for this table
    draft = kv_get(f'draft:{branch_code}:{table_number}', {}) or {}
    draft_items = json.dumps(draft.get('items') or [])
    current_draft = type('Obj', (), {'id': draft.get('draft_id')}) if draft.get('draft_id') else None
    # Warmup DB (avoid heavy create_all/seed on every request)
    warmup_db_once()
    # Load categories from DB for UI and provide a name->id map
    try:


        cats = MenuCategory.query.order_by(MenuCategory.sort_order, MenuCategory.name).all()
    except Exception:
        try:


            cats = MenuCategory.query.order_by(MenuCategory.name).all()
        except Exception:
            cats = MenuCategory.query.all()
    categories = [c.name for c in cats]
    cat_map = {}
    for c in cats:
        cat_map[c.name] = c.id
        cat_map[c.name.upper()] = c.id
    cat_map_json = json.dumps(cat_map)
    today = datetime.utcnow().date().isoformat()
    # Load settings for currency icon, etc.
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    return render_template('sales_table_invoice.html',
                           branch_code=branch_code,
                           branch_label=branch_label,
                           table_number=table_number,
                           vat_rate=vat_rate,
                           draft_items=draft_items,
                           current_draft=current_draft,
                           categories=categories,
                           cat_map_json=cat_map_json,
                           today=today,
                           settings=s)


# ---------- Lightweight APIs used by front-end JS ----------
@main.route('/api/table-settings', methods=['GET', 'POST'], endpoint='api_table_settings')
@login_required
def api_table_settings():
    if request.method == 'GET':
        settings = kv_get('table_settings', {}) or {}
        if not settings:
            settings = {'china': {'count': 20, 'numbering': 'numeric'}, 'india': {'count': 20, 'numbering': 'numeric'}}
        return jsonify({'success': True, 'settings': settings})
    # POST
    try:
        data = request.get_json(force=True) or {}

        kv_set('table_settings', data)
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@main.route('/api/table-sections/<branch_code>', methods=['GET', 'POST'], endpoint='api_table_sections')
@login_required
def api_table_sections(branch_code):
    if not user_can('sales','view', branch_code):
        return jsonify({'success': False, 'error': 'forbidden'}), 403
    
    if request.method == 'GET':
        # Read from the same system as table-layout
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
                        layout = bracket[:-1].strip()
                    except Exception:
                        pass
                return visible, layout

            sections = TableSection.query.filter_by(branch_code=branch_code).order_by(TableSection.sort_order, TableSection.id).all()
            assignments = TableSectionAssignment.query.filter_by(branch_code=branch_code).all()
            
            sections_data = []
            for s in sections:
                visible, layout = decode_name(s.name)
                sections_data.append({
                    'id': s.id,
                    'name': visible,
                    'sort_order': s.sort_order,
                    'layout': layout
                })
            
            assignments_data = []
            for a in assignments:
                assignments_data.append({
                    'table_number': a.table_number,
                    'section_id': a.section_id
                })
            
            return jsonify({'success': True, 'sections': sections_data, 'assignments': assignments_data})
        except Exception as e:
            return jsonify({'success': True, 'sections': [], 'assignments': []})
    
    try:
        # Save to the same system as table-layout
        from models import TableSection, TableSectionAssignment
        
        payload = request.get_json(force=True) or {}
        sections_data = payload.get('sections') or []
        assignments_data = payload.get('assignments') or []
        
        # Clear existing sections and assignments for this branch
        TableSectionAssignment.query.filter_by(branch_code=branch_code).delete()
        TableSection.query.filter_by(branch_code=branch_code).delete()
        
        # Create new sections
        for section_idx, section in enumerate(sections_data):
            section_name = section.get('name', '')
            layout = section.get('layout', '')
            encoded_name = f"{section_name} [rows:{layout}]" if layout else section_name
            
            new_section = TableSection(
                branch_code=branch_code,
                name=encoded_name,
                sort_order=section.get('sort_order', section_idx)
            )
            db.session.add(new_section)
            db.session.flush()
            
            # Create assignments for this section
            for assignment in assignments_data:
                if assignment.get('section_id') == section.get('id'):
                    assignment_obj = TableSectionAssignment(
                        branch_code=branch_code,
                        table_number=str(assignment.get('table_number')),
                        section_id=new_section.id
                    )
                    db.session.add(assignment_obj)
        
        db.session.commit()
        return jsonify({'success': True, 'sections': sections_data})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@main.route('/api/tables/<branch_code>', methods=['GET'], endpoint='api_tables_status')
@login_required

def api_tables_status(branch_code):
    # Read drafts to mark occupied tables
    if not user_can('sales','view', branch_code):
        return jsonify({'success': False, 'error': 'forbidden'}), 403
    settings = kv_get('table_settings', {}) or {}
    if branch_code == 'china_town':
        count = int((settings.get('china') or {}).get('count', 20))
    elif branch_code == 'place_india':
        count = int((settings.get('india') or {}).get('count', 20))
    else:
        count = 20
    items = []
    for i in range(1, count+1):
        draft = kv_get(f'draft:{branch_code}:{i}', {}) or {}
        status = 'occupied' if (draft.get('items') or []) else 'available'


        items.append({'table_number': i, 'status': status})
    return jsonify(items)


@main.route('/api/menu/<cat_id>/items', methods=['GET'], endpoint='api_menu_items')
@login_required
def api_menu_items(cat_id):
    # Prefer DB; fallback to KV/demo — warm up once
    warmup_db_once()
    cat = None
    try:
        cid = int(cat_id)
        cat = MenuCategory.query.get(cid)
    except Exception:
        pass
    if not cat:
        try:
            cat = MenuCategory.query.filter(db.func.lower(MenuCategory.name) == (cat_id or '').lower()).first()
        except Exception:
            cat = None
    if cat:
        items = MenuItem.query.filter_by(category_id=cat.id).order_by(MenuItem.name).all()
        return jsonify([{'id': m.id, 'name': m.name, 'price': float(m.price)} for m in items])
    # KV fallback
    data = kv_get(f'menu:items:{cat_id}', None)
    if isinstance(data, list):
        return jsonify(data)
    # Demo fallback
    demo_items = [{'id': None, 'name': nm, 'price': float(pr)} for (nm, pr) in _DEF_MENU.get(cat_id, [])]


    return jsonify(demo_items)

# ---------- Branch Settings API used by POS ----------
@main.route('/api/branch-settings/<branch_code>', methods=['GET'], endpoint='api_branch_settings')
@login_required
def api_branch_settings(branch_code):
    try:
        from models import Settings
        try:
            s = Settings.query.first()
        except Exception:
            s = None

        # Defaults
        void_pwd = '1991'
        vat_rate = 15.0
        discount_rate = 0.0

        if s:
            if branch_code == 'china_town':
                try:
                    void_pwd = (getattr(s, 'china_town_void_password', void_pwd) or void_pwd)
                except Exception:
                    pass
                try:
                    vat_rate = float(getattr(s, 'china_town_vat_rate', vat_rate) or vat_rate)
                except Exception:
                    pass
                try:
                    discount_rate = float(getattr(s, 'china_town_discount_rate', discount_rate) or discount_rate)
                except Exception:
                    pass
            elif branch_code == 'place_india':
                try:
                    void_pwd = (getattr(s, 'place_india_void_password', void_pwd) or void_pwd)
                except Exception:
                    pass
                try:
                    vat_rate = float(getattr(s, 'place_india_vat_rate', vat_rate) or vat_rate)
                except Exception:
                    pass
                try:
                    discount_rate = float(getattr(s, 'place_india_discount_rate', discount_rate) or discount_rate)
                except Exception:
                    pass

        return jsonify({
            'branch': branch_code,
            'void_password': str(void_pwd),
            'vat_rate': vat_rate,
            'discount_rate': discount_rate
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/draft-order/<branch_code>/<int:table_number>', methods=['POST'], endpoint='api_draft_create_or_update')
@login_required
def api_draft_create_or_update(branch_code, table_number):
    if not user_can('sales','view', branch_code):
        return jsonify({'success': False, 'error': 'forbidden'}), 403

    try:
        payload = request.get_json(force=True) or {}
        items = payload.get('items') or []
        draft_id = f"{branch_code}:{table_number}"
        kv_set(f'draft:{branch_code}:{table_number}', {
            'draft_id': draft_id,
            'items': items,
            'customer': payload.get('customer') or {},
            'discount_pct': float((payload.get('discount_pct') or 0) or 0),
            'tax_pct': float((payload.get('tax_pct') or 15) or 15),
            'payment_method': (payload.get('payment_method') or '')
        })
        return jsonify({'success': True, 'draft_id': draft_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


def _parse_draft_id(draft_id):


    # supports both branch:table and branch-table
    if ':' in draft_id:
        branch, num = draft_id.split(':', 1)
    elif '-' in draft_id:
        branch, num = draft_id.rsplit('-', 1)
    else:
        return None, None
    try:
        return branch, int(num)
    except Exception:
        return None, None


@main.route('/api/draft_orders/<draft_id>/update', methods=['POST'], endpoint='api_draft_update')
@login_required
def api_draft_update(draft_id):
    try:
        branch, table = _parse_draft_id(draft_id)
        if not branch:
            return jsonify({'success': False, 'error': 'invalid_draft_id'}), 400
        payload = request.get_json(force=True) or {}
        if not user_can('sales','view', branch):
            return jsonify({'success': False, 'error': 'forbidden'}), 403

        rec = kv_get(f'draft:{branch}:{table}', {}) or {}
        # map items to unified structure while preserving name/price
        items = payload.get('items') or []
        existing = rec.get('items') or []
        by_id = {}
        for eit in existing:
            key = eit.get('meal_id') or eit.get('id')
            if key is not None:
                by_id[int(key)] = {
                    'name': eit.get('name') or '',
                    'price': float(eit.get('price') or eit.get('unit') or 0.0)
                }
        norm = []
        for it in items:
            mid = it.get('meal_id') or it.get('id')
            qty = it.get('qty') or it.get('quantity') or 1
            nm = it.get('name')
            pr = it.get('price') or it.get('unit')
            if (not nm or pr in [None, '', 0, 0.0]) and mid:
                try:
                    cached = by_id.get(int(mid))
                except Exception:
                    cached = None
                if cached:
                    nm = nm or cached.get('name')
                    pr = pr or cached.get('price')
            if (not nm or pr in [None, '', 0, 0.0]) and mid:
                try:
                    m = db.session.get(MenuItem, int(mid))
                    if m:
                        nm = nm or m.name
                        pr = pr or float(m.price)
                except Exception:
                    pass
            norm.append({
                'meal_id': mid,
                'name': nm or '',
                'price': float(pr or 0.0),
                'qty': qty
            })
        rec['items'] = norm
        # update optional fields
        if 'customer_name' in payload or 'customer_phone' in payload:
            rec['customer'] = {
                'name': (payload.get('customer_name') or '').strip(),
                'phone': (payload.get('customer_phone') or '').strip(),
            }
        if 'payment_method' in payload:
            rec['payment_method'] = payload.get('payment_method') or ''
        if 'discount_pct' in payload:
            try: rec['discount_pct'] = float(payload.get('discount_pct') or 0)
            except Exception: rec['discount_pct'] = 0.0
        if 'tax_pct' in payload:
            try: rec['tax_pct'] = float(payload.get('tax_pct') or 15)
            except Exception: rec['tax_pct'] = 15.0
        kv_set(f'draft:{branch}:{table}', rec)
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@main.route('/api/draft_orders/<draft_id>/cancel', methods=['POST'], endpoint='api_draft_cancel')
@login_required
def api_draft_cancel(draft_id):
    try:
        branch, table = _parse_draft_id(draft_id)


        if not branch:
            return jsonify({'success': False, 'error': 'invalid_draft_id'}), 400
        if not user_can('sales','view', branch):
            return jsonify({'success': False, 'error': 'forbidden'}), 403

        # clear draft
        kv_set(f'draft:{branch}:{table}', {'draft_id': draft_id, 'items': []})
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@main.route('/api/draft/checkout', methods=['POST'], endpoint='api_draft_checkout')


@login_required
def api_draft_checkout():
    payload = request.get_json(force=True) or {}
    draft_id = payload.get('draft_id') or ''
    branch, table = _parse_draft_id(draft_id)
    if not branch:
        return jsonify({'error': 'invalid_draft_id'}), 400
    if not user_can('sales','view', branch):
        return jsonify({'success': False, 'error': 'forbidden'}), 403

    warmup_db_once()
    draft = kv_get(f'draft:{branch}:{table}', {}) or {}
    items = draft.get('items') or []
    subtotal = 0.0
    for it in items:
        qty = float(it.get('qty') or it.get('quantity') or 1)
        price = float(it.get('price') or it.get('unit') or 0.0)
        if price <= 0 and it.get('meal_id'):
            m = MenuItem.query.get(int(it.get('meal_id')))
            if m:
                price = float(m.price)
        subtotal += qty * (price or 0.0)
    discount_pct = float(payload.get('discount_pct') or 0)
    tax_pct = float(payload.get('tax_pct') or 15)
    vat_amount = subtotal * (tax_pct/100.0)
    discount_amount = subtotal * (discount_pct/100.0)
    total_after = subtotal + vat_amount - discount_amount
    payment_method = (payload.get('payment_method') or '').strip().upper()
    if payment_method not in ['CASH','CARD']:
        return jsonify({'success': False, 'error': 'اختر طريقة الدفع (CASH أو CARD)'}), 400
    # Reuse preview invoice number if present to keep display number consistent
    draft_data = kv_get(f'draft:{branch}:{table}', {}) or {}
    preview_no = (draft_data.get('preview_invoice_number') or '').strip()
    invoice_number = preview_no if preview_no else f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    try:
        inv = SalesInvoice(
            invoice_number=invoice_number,
            branch=branch,
            table_number=int(table),
            customer_name=(payload.get('customer_name') or '').strip(),
            customer_phone=(payload.get('customer_phone') or '').strip(),
            payment_method=payment_method,
            total_before_tax=round(subtotal, 2),
            tax_amount=round(vat_amount, 2),
            discount_amount=round(discount_amount, 2),
            total_after_tax_discount=round(total_after, 2),
            user_id=int(getattr(current_user, 'id', 1) or 1),
        )
        db.session.add(inv)
        db.session.flush()
        for it in items:
            qty = float(it.get('qty') or it.get('quantity') or 1)
            price = float(it.get('price') or it.get('unit') or 0.0)
            if price <= 0 and it.get('meal_id'):
                m = MenuItem.query.get(int(it.get('meal_id')))
                if m:
                    price = float(m.price)
            db.session.add(SalesInvoiceItem(
                invoice_id=inv.id,
                product_name=(it.get('name') or ''),
                quantity=qty,
                price_before_tax=price or 0.0,
                tax=0,
                discount=0,
                total_price=round((price or 0.0) * qty, 2),
            ))
        db.session.commit()
    except Exception as e:


        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'ok': True, 'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_after, 2), 'print_url': url_for('main.print_receipt', invoice_number=invoice_number), 'branch_code': branch, 'table_number': int(table)})


@main.route('/api/sales/checkout', methods=['POST'], endpoint='api_sales_checkout')
@login_required
def api_sales_checkout():
    payload = request.get_json(force=True) or {}
    warmup_db_once()
    branch = (payload.get('branch_code') or '').strip() or 'unknown'
    table = int(payload.get('table_number') or 0)
    if not user_can('sales','view', branch):
        return jsonify({'success': False, 'error': 'forbidden'}), 403

    items = payload.get('items') or []
    # get prices from DB when missing
    subtotal = 0.0
    resolved = []
    for it in items:
        qty = float(it.get('qty') or 1)
        price = float(it.get('price') or 0.0)
        if price <= 0 and it.get('meal_id'):
            m = MenuItem.query.get(int(it.get('meal_id')))
            if m:
                price = float(m.price)
                name = m.name
            else:
                name = it.get('name') or ''
        else:
            name = it.get('name') or ''
        subtotal += qty * (price or 0.0)
        resolved.append({'meal_id': it.get('meal_id'), 'name': name, 'price': price or 0.0, 'qty': qty})
    discount_pct = float(payload.get('discount_pct') or 0)
    tax_pct = float(payload.get('tax_pct') or 15)
    vat_amount = subtotal * (tax_pct/100.0)
    discount_amount = subtotal * (discount_pct/100.0)
    total_after = subtotal + vat_amount - discount_amount
    payment_method = (payload.get('payment_method') or '').strip().upper()
    if payment_method not in ['CASH','CARD']:
        return jsonify({'success': False, 'error': '\u0627\u062e\u062a\u0631 \u0637\u0631\u064a\u0642\u0629 \u0627\u0644\u062f\u0641\u0639 (CASH \u0623\u0648 CARD)'}), 400
    invoice_number = f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    try:
        inv = SalesInvoice(
            invoice_number=invoice_number,
            branch=branch,
            table_number=table,
            customer_name=(payload.get('customer_name') or '').strip(),
            customer_phone=(payload.get('customer_phone') or '').strip(),
            payment_method=payment_method,
            total_before_tax=round(subtotal, 2),
            tax_amount=round(vat_amount, 2),
            discount_amount=round(discount_amount, 2),
            total_after_tax_discount=round(total_after, 2),
            user_id=int(getattr(current_user, 'id', 1) or 1),
        )
        db.session.add(inv)
        db.session.flush()
        for it in resolved:
            db.session.add(SalesInvoiceItem(
                invoice_id=inv.id,
                product_name=it.get('name'),
                quantity=float(it.get('qty') or 1),
                price_before_tax=float(it.get('price') or 0.0),
                tax=0,
                discount=0,
                total_price=round(float(it.get('price') or 0.0) * float(it.get('qty') or 1), 2),
            ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'ok': True, 'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_after, 2), 'print_url': url_for('main.print_receipt', invoice_number=invoice_number), 'branch_code': branch, 'table_number': table})


@main.route('/api/invoice/confirm-print', methods=['POST'], endpoint='api_invoice_confirm_print')
@login_required
def api_invoice_confirm_print():
    # Mark invoice paid and free the table. Create payment record.
    try:
        from models import SalesInvoice, Payment
        payload = request.get_json(force=True) or {}
        branch = (payload.get('branch_code') or '').strip()
        table = int(payload.get('table_number') or 0)
        raw_invoice_id = payload.get('invoice_id')
        payment_method = (payload.get('payment_method') or '').upper() or None
        total_amount = float(payload.get('total_amount') or 0)

        # Resolve invoice by number or numeric id
        inv = None
        if isinstance(raw_invoice_id, str) and not raw_invoice_id.isdigit():
            inv = SalesInvoice.query.filter_by(invoice_number=raw_invoice_id).first()
        else:
            try:
                inv = SalesInvoice.query.get(int(raw_invoice_id))
            except Exception:
                inv = None
        if not inv:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        if (inv.status or '').lower() != 'paid':
            if payment_method:
                db.session.add(Payment(
                    invoice_id=inv.id,
                    invoice_type='sales',
                    amount_paid=total_amount or float(inv.total_after_tax_discount or 0),
                    payment_method=payment_method,
                    payment_date=get_saudi_now()
                ))
            inv.status = 'paid'
            db.session.commit()

        # Clear draft to free the table
        if branch and table:
            kv_set(f'draft:{branch}:{table}', {'draft_id': f'{branch}:{table}', 'items': []})
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@main.route('/api/sales/void-check', methods=['POST'], endpoint='api_sales_void_check')
@login_required
def api_sales_void_check():
    payload = request.get_json(force=True) or {}
    ok = (str(payload.get('password') or '').strip() == '1991')
    return jsonify({'ok': ok})


@main.route('/api/payments/register', methods=['POST'], endpoint='register_payment_ajax')
@login_required
def register_payment_ajax():
    # Accept both form and JSON
    payload = request.get_json(silent=True) or {}
    invoice_id = request.form.get('invoice_id') or payload.get('invoice_id')
    invoice_type = (request.form.get('invoice_type') or payload.get('invoice_type') or '').strip().lower()
    amount = request.form.get('amount') or payload.get('amount')
    payment_method = (request.form.get('payment_method') or payload.get('payment_method') or 'CASH').strip().upper()
    try:
        inv_id = int(invoice_id)
        amt = float(amount or 0)
    except Exception:
        return jsonify({'status': 'error', 'message': 'Invalid invoice id or amount'}), 400
    if amt <= 0:
        return jsonify({'status': 'error', 'message': 'Amount must be > 0'}), 400
    if invoice_type not in ('purchase','expense'):
        return jsonify({'status': 'error', 'message': 'Unsupported invoice type'}), 400

    try:
        # Create payment record
        p = Payment(invoice_id=inv_id, invoice_type=invoice_type, amount_paid=amt, payment_method=payment_method)
        db.session.add(p)
        db.session.flush()

        # Fetch invoice and totals
        if invoice_type == 'purchase':
            inv = PurchaseInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0
        else:
            inv = ExpenseInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0

        # Sum paid so far (including this payment)
        paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_id == inv_id, Payment.invoice_type == invoice_type).scalar() or 0.0)

        # Robust status calculation with rounding tolerance (0.01)
        from decimal import Decimal, ROUND_HALF_UP
        def to_cents(value):
            try:
                return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return Decimal('0.00')
        total_c = to_cents(total)
        paid_c = to_cents(paid)
        if inv:
            if (total_c - paid_c) <= Decimal('0.01') and total_c > Decimal('0.00'):
                inv.status = 'paid'
            elif paid_c > Decimal('0.00'):
                inv.status = 'partial'
            else:
                inv.status = inv.status or ('unpaid' if invoice_type=='purchase' else 'paid')
        db.session.commit()
        return jsonify({'status': 'success', 'invoice_id': inv_id, 'amount': amt, 'paid': paid, 'total': total, 'new_status': getattr(inv, 'status', None)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400



@main.route('/api/payments/pay_all', methods=['POST'], endpoint='api_payments_pay_all')
@login_required
def api_payments_pay_all():
    # Bulk pay remaining for filtered invoices
    payload = request.get_json(silent=True) or {}
    type_f = (payload.get('type') or request.form.get('type') or '').strip().lower()
    method = (payload.get('payment_method') or request.form.get('payment_method') or 'CASH').strip().upper()
    # Supported: purchase, expense
    kinds = []
    if type_f in ('purchase','expense'):
        kinds = [type_f]
    else:
        kinds = ['purchase','expense']

    from decimal import Decimal, ROUND_HALF_UP
    def to_cents(value):
        try:
            return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal('0.00')

    affected = []
    try:
        for k in kinds:
            if k == 'purchase':
                rows = PurchaseInvoice.query.order_by(PurchaseInvoice.created_at.desc()).all()
            else:
                rows = ExpenseInvoice.query.order_by(ExpenseInvoice.created_at.desc()).all()
            for inv in rows:
                total = to_cents(float(getattr(inv, 'total_after_tax_discount', 0) or 0))
                paid = to_cents(float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                          .filter(Payment.invoice_id == inv.id, Payment.invoice_type == k).scalar() or 0.0))
                remaining = total - paid
                if remaining > Decimal('0.01'):
                    amt = float(remaining)
                    db.session.add(Payment(invoice_id=inv.id, invoice_type=k, amount_paid=amt, payment_method=method))
                    inv.status = 'paid'
                    affected.append({'id': inv.id, 'type': k, 'amount': amt})
        db.session.commit()
        return jsonify({'status':'success', 'count': len(affected), 'items': affected})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error', 'message': str(e)}), 400


# ---- Customers lightweight search API ----
@main.route('/api/customers/search', methods=['GET'], endpoint='api_customers_search')
@login_required
def api_customers_search():
    q = (request.args.get('q') or '').strip()
    if not q:
        rows = Customer.query.filter_by(active=True).order_by(Customer.name.asc()).limit(10).all()
    else:
        like = f"%{q}%"
        rows = Customer.query.filter(
            Customer.active == True,
            (Customer.name.ilike(like)) | (Customer.phone.ilike(like))
        ).order_by(Customer.name.asc()).limit(20).all()
    data = [{
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'discount_percent': float(c.discount_percent or 0)
    } for c in rows]
    return jsonify({'results': data})


# ---- Print routes for sales receipts ----
@main.route('/print/receipt/<invoice_number>', methods=['GET'], endpoint='print_receipt')
@login_required
def print_receipt(invoice_number):
    inv = SalesInvoice.query.filter_by(invoice_number=invoice_number).first()
    if not inv:
        return 'Invoice not found', 404
    items = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).all()
    # compute items context and use stored totals
    items_ctx = []
    for it in items:
        line = float(it.price_before_tax or 0) * float(it.quantity or 0)
        items_ctx.append({
            'product_name': it.product_name or '',
            'quantity': float(it.quantity or 0),
            'total_price': line,
        })

    inv_ctx = {
        'invoice_number': inv.invoice_number,
        'table_number': inv.table_number,
        'customer_name': inv.customer_name,
        'customer_phone': inv.customer_phone,
        'payment_method': inv.payment_method,
        'status': 'PAID',
        'total_before_tax': float(inv.total_before_tax or 0.0),
        'tax_amount': float(inv.tax_amount or 0.0),
        'discount_amount': float(inv.discount_amount or 0.0),
        'total_after_tax_discount': float(inv.total_after_tax_discount or 0.0),
    }
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    branch_name = BRANCH_LABELS.get(getattr(inv, 'branch', None) or '', getattr(inv, 'branch', ''))
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Prepare embedded logo as data URL for more reliable thermal printing
    logo_data_url = None
    try:
        if s and getattr(s, 'receipt_show_logo', False) and (s.logo_url or '').strip():
            url = s.logo_url.strip()
            import base64, mimetypes, os
            fpath = None
            # Static folder
            if url.startswith('/static/'):
                rel = url.split('/static/', 1)[1]
                fpath = os.path.join(current_app.static_folder, rel)
            # Persistent uploads folder
            elif url.startswith('/uploads/'):
                upload_dir = os.getenv('UPLOAD_DIR') or os.path.join(current_app.static_folder, 'uploads')
                rel = url.split('/uploads/', 1)[1]
                fpath = os.path.join(upload_dir, rel)
            if fpath and os.path.exists(fpath):
                with open(fpath, 'rb') as f:
                    b = f.read()
                mime = mimetypes.guess_type(fpath)[0] or 'image/png'
                logo_data_url = f'data:{mime};base64,' + base64.b64encode(b).decode('ascii')
    except Exception:
        logo_data_url = None
    # Generate ZATCA-compliant QR (server-side) if possible
    qr_data_url = None
    try:
        from utils.qr import generate_zatca_qr_from_invoice
        b64 = generate_zatca_qr_from_invoice(inv, s, None)
        if b64:
            qr_data_url = 'data:image/png;base64,' + b64
    except Exception:
        qr_data_url = None
    return render_template('print/receipt.html', inv=inv_ctx, items=items_ctx,
                           settings=s, branch_name=branch_name, date_time=dt_str,
                           display_invoice_number=inv.invoice_number,
                           qr_data_url=qr_data_url,
                           logo_data_url=logo_data_url,
                           paid=True)


@main.route('/print/order-preview/<branch>/<int:table>', methods=['GET'], endpoint='print_order_preview')
@login_required
def print_order_preview(branch, table):
    # Read draft
    rec = kv_get(f'draft:{branch}:{table}', {}) or {}
    raw_items = rec.get('items') or []
    items_ctx = []
    subtotal = 0.0
    for it in raw_items:
        meal_id = it.get('meal_id') or it.get('id')
        qty = float(it.get('qty') or it.get('quantity') or 1)
        name = it.get('name') or ''
        price = it.get('price') or 0.0
        if (not name) or (not price) and meal_id:
            m = MenuItem.query.get(int(meal_id))
            if m:
                name = name or m.name
                price = price or float(m.price)
        line = float(price or 0) * qty
        subtotal += line
        items_ctx.append({'product_name': name, 'quantity': qty, 'total_price': line})

    tax_pct = float(rec.get('tax_pct') or 15)
    discount_pct = float(rec.get('discount_pct') or 0)
    vat_amount = subtotal * (tax_pct/100.0)
    discount_amount = (subtotal + vat_amount) * (discount_pct/100.0)
    total_after = subtotal + vat_amount - discount_amount

    inv_ctx = {
        'invoice_number': '',  # no real invoice number for preview
        'table_number': table,
        'customer_name': (rec.get('customer') or {}).get('name') or '',
        'customer_phone': (rec.get('customer') or {}).get('phone') or '',
        'payment_method': '',
        'status': 'DRAFT',
        'total_before_tax': round(subtotal, 2),
        'tax_amount': round(vat_amount, 2),
        'discount_amount': round(discount_amount, 2),
        'total_after_tax_discount': round(total_after, 2),
        'branch': branch,
        'branch_code': branch,
    }
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    branch_name = BRANCH_LABELS.get(branch, branch)
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Keep preview number generation as before, but with INV prefix to match final
    order_no = f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    # Persist this preview number so checkout reuses exactly the same value
    try:
        rec['preview_invoice_number'] = order_no
        kv_set(f'draft:{branch}:{table}', rec)
    except Exception:
        pass
    # Save an OrderInvoice record to track pre-payment prints
    try:
        from models import OrderInvoice
        # Create table if missing (first run)
        try:
            OrderInvoice.__table__.create(bind=db.engine, checkfirst=True)
        except Exception:
            pass

        # Avoid duplicates if user reopens/refreshes preview
        existing = OrderInvoice.query.filter_by(invoice_no=order_no).first()
        if not existing:
            # Build items JSON with name, qty, unit, line_total
            items_json = []
            try:
                for it in raw_items:
                    name = it.get('name') or ''
                    qty = float(it.get('qty') or it.get('quantity') or 1)
                    price = it.get('price')
                    if (not price):
                        meal_id = it.get('meal_id') or it.get('id')
                        if meal_id:
                            m = MenuItem.query.get(int(meal_id))
                            price = float(getattr(m, 'price', 0) or 0)
                    unit = float(price or 0)
                    line_total = unit * qty
                    items_json.append({'name': name, 'qty': qty, 'unit': unit, 'line_total': line_total})
            except Exception:
                # Fallback from items_ctx if needed
                for r in items_ctx:
                    q = float(r.get('quantity') or 1)
                    t = float(r.get('total_price') or 0)
                    u = (t / q) if q else 0
                    items_json.append({'name': r.get('product_name') or '-', 'qty': q, 'unit': u, 'line_total': t})

            order = OrderInvoice(
                branch=branch,
                invoice_no=order_no,
                customer=((rec.get('customer') or {}).get('name') or None),
                items=items_json,
                subtotal=float(subtotal),
                discount=float(discount_amount),
                vat=float(vat_amount),
                total=float(total_after),
                payment_method='PENDING'
            )
            db.session.add(order)
            db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        current_app.logger.error('Failed to save order invoice (preview): %s', e)
    # Generate ZATCA QR as base64 PNG and pass to template
    qr_data_url = None
    try:
        from utils.qr import generate_zatca_qr_base64
        b64 = generate_zatca_qr_base64(
            getattr(s, 'company_name', 'Restaurant'),
            getattr(s, 'tax_number', '123456789012345'),
            datetime.now(),
            float(total_after),
            float(vat_amount)
        )
        if b64:
            qr_data_url = 'data:image/png;base64,' + b64
    except Exception:
        qr_data_url = None

    return render_template('print/receipt.html', inv=inv_ctx, items=items_ctx,
                           settings=s, branch_name=branch_name, date_time=dt_str,
                           display_invoice_number=order_no,
                           qr_data_url=qr_data_url,
                           paid=False)



@main.route('/customers', methods=['GET', 'POST'], endpoint='customers')
@login_required
def customers():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        phone = (request.form.get('phone') or '').strip() or None
        discount = request.form.get('discount_percent', type=float) or 0.0
        if not name:
            flash('Name is required', 'danger')
        else:
            try:
                c = Customer(name=name, phone=phone, discount_percent=float(discount or 0))
                db.session.add(c)
                db.session.commit()
                flash('Customer added', 'success')
            except Exception as e:
                db.session.rollback()
                flash('Error adding customer', 'danger')
        return redirect(url_for('main.customers'))
    # GET
    q = (request.args.get('q') or '').strip()
    qry = Customer.query.filter_by(active=True)
    if q:
        like = f"%{q}%"
        qry = qry.filter((Customer.name.ilike(like)) | (Customer.phone.ilike(like)))
    customers = qry.order_by(Customer.name.asc()).all()
    return render_template('customers.html', customers=customers, q=q)

@main.route('/customers/<int:cid>/toggle', methods=['POST'], endpoint='customer_toggle')
@login_required
def customer_toggle(cid):
    try:
        c = db.session.get(Customer, cid)
        if not c:
            flash('Customer not found', 'warning')
            return redirect(url_for('main.customers'))
        c.active = not bool(getattr(c, 'active', True))
        db.session.commit()
        flash('Customer status updated', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating customer: {e}', 'danger')
    return redirect(url_for('main.customers'))


@main.route('/customers/<int:cid>/delete', methods=['POST'], endpoint='customer_delete')
@login_required
def customer_delete(cid):
    # Try hard delete; if constrained, fall back to soft deactivate
    try:
        c = db.session.get(Customer, cid)
        if not c:
            flash('Customer not found', 'warning')
        else:
            try:
                db.session.delete(c)
                db.session.commit()
                flash('Customer deleted', 'success')
            except IntegrityError:
                db.session.rollback()
                c.active = False
                db.session.commit()
                flash('Customer has related records; deactivated instead', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: {e}', 'danger')
    return redirect(url_for('main.customers'))


# ---- Customers: POS-friendly search alias and AJAX create ----
@main.route('/api/pos/<branch>/customers/search', methods=['GET'], endpoint='api_pos_customers_search')
@login_required
def api_pos_customers_search(branch):
    q = (request.args.get('q') or '').strip()
    if not q:
        rows = Customer.query.filter_by(active=True).order_by(Customer.name.asc()).limit(10).all()
    else:
        like = f"%{q}%"
        rows = Customer.query.filter(
            Customer.active == True,
            (Customer.name.ilike(like)) | (Customer.phone.ilike(like))
        ).order_by(Customer.name.asc()).limit(20).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'discount_percent': float(c.discount_percent or 0)
    } for c in rows])


@main.route('/api/customers', methods=['POST'], endpoint='api_customers_create')
@login_required
@csrf.exempt
def api_customers_create():
    try:
        if request.is_json:
            data = request.get_json() or {}
            name = (data.get('name') or '').strip()
            phone = (data.get('phone') or '').strip() or None
            discount = float((data.get('discount_percent') or 0) or 0)
        else:
            name = (request.form.get('name') or '').strip()
            phone = (request.form.get('phone') or '').strip() or None
            discount = request.form.get('discount_percent', type=float) or 0.0
        if not name:
            return jsonify({'ok': False, 'error': 'Name is required'}), 400
        c = Customer(name=name, phone=phone, discount_percent=float(discount or 0))
        db.session.add(c)
        db.session.commit()
        return jsonify({'ok': True, 'customer': {
            'id': c.id, 'name': c.name, 'phone': c.phone,
            'discount_percent': float(c.discount_percent or 0)
        }})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400


@main.route('/suppliers', methods=['GET','POST'], endpoint='suppliers')
@login_required
def suppliers():
    if request.method == 'POST':
        try:
            # Accept optional CR/IBAN even if model lacks fields; store in notes
            cr = (request.form.get('cr_number') or '').strip() or None
            iban = (request.form.get('iban') or '').strip() or None
            notes_in = (request.form.get('notes') or '').strip() or None
            notes_extra = []
            if notes_in:
                notes_extra.append(notes_in)
            if cr:
                notes_extra.append(f"CR: {cr}")
            if iban:
                notes_extra.append(f"IBAN: {iban}")
            notes_text = ' | '.join(notes_extra) if notes_extra else None

            s = Supplier(
                name=(request.form.get('name') or '').strip(),
                contact_person=request.form.get('contact_person') or None,
                phone=request.form.get('phone') or None,
                email=request.form.get('email') or None,
                tax_number=request.form.get('tax_number') or None,
                address=request.form.get('address') or None,
                payment_method=(request.form.get('payment_method') or 'CASH').strip().upper(),
                notes=notes_text,
                active=True if str(request.form.get('active')).lower() in ['1','true','yes','on'] else False,
            )
            if not s.name:
                raise ValueError('Name is required')
            if ext_db is not None:
                ext_db.session.add(s)
                ext_db.session.commit()
            else:
                db.session.add(s)
                db.session.commit()
            flash('Supplier added', 'success')
        except Exception as e:
            if ext_db is not None:
                ext_db.session.rollback()
            else:
                db.session.rollback()
            flash(f'Could not add supplier: {e}', 'danger')
        return redirect(url_for('main.suppliers'))
    try:
        q = (request.args.get('q') or '').strip()
        query = Supplier.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Supplier.name.ilike(like)) |
                (Supplier.contact_person.ilike(like)) |
                (Supplier.phone.ilike(like)) |
                (Supplier.email.ilike(like)) |
                (Supplier.tax_number.ilike(like)) |
                (Supplier.address.ilike(like)) |
                (Supplier.notes.ilike(like))
            )
        all_suppliers = query.order_by(Supplier.name.asc()).all()
    except Exception:
        all_suppliers = []
    return render_template('suppliers.html', suppliers=all_suppliers)

@main.route('/suppliers/list', methods=['GET'], endpoint='suppliers_list')
@login_required
def suppliers_list():
    try:
        q = (request.args.get('q') or '').strip()
        query = Supplier.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Supplier.name.ilike(like)) |
                (Supplier.contact_person.ilike(like)) |
                (Supplier.phone.ilike(like)) |
                (Supplier.email.ilike(like)) |
                (Supplier.tax_number.ilike(like)) |
                (Supplier.address.ilike(like)) |
                (Supplier.notes.ilike(like))
            )
        all_suppliers = query.order_by(Supplier.name.asc()).all()
    except Exception:
        all_suppliers = []
    return render_template('suppliers_list.html', suppliers=all_suppliers)

@main.route('/suppliers/<int:sid>/toggle', methods=['POST'], endpoint='supplier_toggle')
@login_required
def supplier_toggle(sid):
    try:
        s = Supplier.query.get(sid)
        if not s:
            flash('Supplier not found', 'warning')
            return redirect(url_for('main.suppliers'))
        s.active = not bool(getattr(s, 'active', True))
        if ext_db is not None:
            ext_db.session.commit()
        else:
            db.session.commit()
        flash('Supplier status updated', 'success')
    except Exception as e:
        if ext_db is not None:
            ext_db.session.rollback()
        else:
            db.session.rollback()
        flash(f'Error updating supplier: {e}', 'danger')
    return redirect(url_for('main.suppliers'))

@main.route('/suppliers/export', methods=['GET'], endpoint='suppliers_export')
@login_required
def suppliers_export():
    try:
        q = (request.args.get('q') or '').strip()
        query = Supplier.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Supplier.name.ilike(like)) |
                (Supplier.contact_person.ilike(like)) |
                (Supplier.phone.ilike(like)) |
                (Supplier.email.ilike(like)) |
                (Supplier.tax_number.ilike(like)) |
                (Supplier.address.ilike(like)) |
                (Supplier.notes.ilike(like))
            )
        rows = query.order_by(Supplier.name.asc()).all()

        def escape_csv(val: str) -> str:
            if val is None:
                return ''
            s = str(val)
            if any(c in s for c in [',','"','\n','\r']):
                s = '"' + s.replace('"','""') + '"'
            return s

        parts = []
        header = [
            'Name','Contact Person','Phone','Email','Tax Number','CR Number','IBAN','Address','Notes','Active'
        ]
        parts.append(','.join(header))
        for s in rows:
            cr = getattr(s, 'cr_number', None)
            iban = getattr(s, 'iban', None)
            if (not cr or not iban) and (s.notes):
                try:
                    for part in (s.notes or '').split('|'):
                        p = (part or '').strip()
                        if (not cr) and p[:3] == 'CR:':
                            cr = p[3:].strip()
                        if (not iban) and p[:5] == 'IBAN:':
                            iban = p[5:].strip()
                except Exception:
                    pass
            row = [
                escape_csv(s.name),
                escape_csv(s.contact_person or ''),
                escape_csv(s.phone or ''),
                escape_csv(s.email or ''),
                escape_csv(s.tax_number or ''),
                escape_csv(cr or ''),
                escape_csv(iban or ''),
                escape_csv(s.address or ''),
                escape_csv(s.notes or ''),
                '1' if getattr(s, 'active', True) else '0'
            ]
            parts.append(','.join(row))
        csv_data = '\n'.join(parts)
        return current_app.response_class(csv_data, mimetype='text/csv; charset=utf-8', headers={
            'Content-Disposition': 'attachment; filename="suppliers.csv"'
        })
    except Exception as e:
        flash(f'Failed to export suppliers: {e}', 'danger')
        return redirect(url_for('main.suppliers'))

@main.route('/suppliers/<int:sid>/delete', methods=['POST'], endpoint='supplier_delete')
@login_required
def supplier_delete(sid):
    # Try hard delete; if constrained, fall back to soft deactivate
    try:
        s = Supplier.query.get(sid)
        if not s:
            flash('Supplier not found', 'warning')
        else:
            try:
                if ext_db is not None:
                    ext_db.session.delete(s)
                    ext_db.session.commit()
                else:
                    db.session.delete(s)
                    db.session.commit()
                flash('Supplier deleted', 'success')
            except IntegrityError:
                # Rollback then soft deactivate
                if ext_db is not None:
                    ext_db.session.rollback()
                    s.active = False
                    ext_db.session.commit()
                else:
                    db.session.rollback()
                    s.active = False
                    db.session.commit()
                flash('Supplier has related records; deactivated instead', 'warning')
    except Exception as e:
        if ext_db is not None:
            ext_db.session.rollback()
        else:
            db.session.rollback()
        flash(f'Error deleting supplier: {e}', 'danger')
    return redirect(url_for('main.suppliers'))

@main.route('/menu', methods=['GET'], endpoint='menu')
@login_required
def menu():
    warmup_db_once()
    try:
        cats = MenuCategory.query.order_by(MenuCategory.sort_order, MenuCategory.name).all()
    except Exception:
        try:
            cats = MenuCategory.query.order_by(MenuCategory.name).all()
        except Exception:
            cats = MenuCategory.query.all()
    current = None
    cat_id = request.args.get('cat_id', type=int)
    if cat_id:
        try:
            current = db.session.get(MenuCategory, int(cat_id))
        except Exception:
            current = None
    if not current and cats:
        current = cats[0]

    # Cleanup exact duplicates (same name and same price) within the current section
    if current:
        try:
            seen = {}
            dups = []
            for it in MenuItem.query.filter_by(category_id=current.id).order_by(MenuItem.id.asc()).all():
                key = ((it.name or '').strip().lower(), round(float(it.price or 0), 2))
                if key in seen:
                    dups.append(it)
                else:
                    seen[key] = it.id
            if dups:
                for it in dups:
                    db.session.delete(it)
                db.session.commit()
        except Exception:
            db.session.rollback()

    items = []
    if current:
        items = MenuItem.query.filter_by(category_id=current.id).order_by(MenuItem.name).all()
    # meals for dropdown (active first; fallback to all)
    try:
        meals = Meal.query.filter_by(active=True).order_by(Meal.name.asc()).all()
        if not meals:
            meals = Meal.query.order_by(Meal.name.asc()).all()
    except Exception:
        meals = []
    # counts per category
    item_counts = {c.id: MenuItem.query.filter_by(category_id=c.id).count() for c in cats}
    return render_template('menu.html', sections=cats, current_section=current, items=items, item_counts=item_counts, meals=meals)


@main.route('/menu/category/add', methods=['POST'], endpoint='menu_category_add')
@login_required
def menu_category_add():
    warmup_db_once()
    name = (request.form.get('name') or '').strip()
    sort = request.form.get('display_order', type=int) or 0
    if not name:
        flash('Name is required', 'danger')
        return redirect(url_for('main.menu'))
    try:
        c = MenuCategory(name=name, sort_order=sort)
        db.session.add(c)
        db.session.commit()
        return redirect(url_for('main.menu', cat_id=c.id))
    except Exception as e:
        db.session.rollback()
        flash('Error creating category', 'danger')
        return redirect(url_for('main.menu'))


@main.route('/menu/category/<int:cat_id>/delete', methods=['POST'], endpoint='menu_category_delete')
@login_required
def menu_category_delete(cat_id):
    warmup_db_once()
    try:
        c = db.session.get(MenuCategory, int(cat_id))
        if c:
            MenuItem.query.filter_by(category_id=c.id).delete()
            db.session.delete(c)
            db.session.commit()
            flash('Category deleted', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting category', 'danger')
    return redirect(url_for('main.menu'))


@main.route('/menu/item/add', methods=['POST'], endpoint='menu_item_add')
@login_required
def menu_item_add():
    warmup_db_once()
    cat_id = request.form.get('section_id', type=int)
    meal_id = request.form.get('meal_id', type=int)
    name = (request.form.get('name') or '').strip()
    price_raw = request.form.get('price')
    # parse price robustly (support comma decimal)
    try:
        price = float((price_raw or '').replace(',', '.')) if price_raw not in [None, ''] else None
    except Exception:
        price = None
    if not cat_id:
        flash('Missing category', 'danger')
        return redirect(url_for('main.menu'))
    try:
        # Resolve meal if provided
        meal = db.session.get(Meal, int(meal_id)) if meal_id else None
        if meal:
            disp_name = f"{meal.name} / {meal.name_ar}" if getattr(meal, 'name_ar', None) else (meal.name or name)
            final_name = (name or '').strip() or disp_name
            final_price = float(price) if price is not None else float(meal.selling_price or 0.0)
        else:
            final_name = name
            final_price = float(price or 0.0)
        final_name = (final_name or '').strip()[:150]
        if not final_name:
            flash('Missing item name', 'danger')
            return redirect(url_for('main.menu', cat_id=cat_id))
        it = MenuItem(name=final_name, price=final_price, category_id=int(cat_id), meal_id=(meal.id if meal else None))
        db.session.add(it)
        db.session.commit()
        return redirect(url_for('main.menu', cat_id=cat_id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating item: {e}', 'danger')
        return redirect(url_for('main.menu', cat_id=cat_id))


@main.route('/menu/item/<int:item_id>/update', methods=['POST'], endpoint='menu_item_update')
@login_required
def menu_item_update(item_id):
    warmup_db_once()
    name = (request.form.get('name') or '').strip()
    price = request.form.get('price', type=float)
    try:
        it = db.session.get(MenuItem, int(item_id))
        if not it:
            flash('Item not found', 'warning')
            return redirect(url_for('main.menu'))
        if name:
            it.name = name
        if price is not None:
            it.price = float(price)
        db.session.commit()
        return redirect(url_for('main.menu', cat_id=it.category_id))
    except Exception:
        db.session.rollback()
        flash('Error updating item', 'danger')
        return redirect(url_for('main.menu'))


@main.route('/menu/item/<int:item_id>/delete', methods=['POST'], endpoint='menu_item_delete')
@login_required
def menu_item_delete(item_id):
    warmup_db_once()
    try:
        it = db.session.get(MenuItem, int(item_id))
        if it:
            cat_id = it.category_id
            db.session.delete(it)
            db.session.commit()
            flash('Item deleted', 'info')
            return redirect(url_for('main.menu', cat_id=cat_id))
    except Exception:
        db.session.rollback()
        flash('Error deleting item', 'danger')
    return redirect(url_for('main.menu'))


# API endpoints for JS delete flows (optional)
@main.route('/api/items/<int:item_id>/delete', methods=['POST'], endpoint='api_item_delete')
@login_required
def api_item_delete(item_id):
    payload = request.get_json(silent=True) or {}
    if (payload.get('password') or '') != '1991':
        return jsonify({'ok': False, 'error': 'invalid_password'}), 403
    try:
        it = db.session.get(MenuItem, int(item_id))
        if not it:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        db.session.delete(it)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400


@main.route('/api/items/delete-all', methods=['POST'], endpoint='api_item_delete_all')
@login_required
def api_item_delete_all():
    payload = request.get_json(silent=True) or {}
    if (payload.get('password') or '') != '1991':
        return jsonify({'ok': False, 'error': 'invalid_password'}), 403
    try:
        deleted = db.session.query(MenuItem).delete()
        db.session.commit()
        return jsonify({'ok': True, 'deleted': int(deleted or 0)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400



# --- Users Management API (minimal) ---
@main.route('/api/users', methods=['POST'], endpoint='api_users_create')
@login_required
def api_users_create():
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()
        active = bool(data.get('active', True))
        if not username or not password:
            return jsonify({'ok': False, 'error': 'username_password_required'}), 400
        # uniqueness
        if User.query.filter_by(username=username).first():
            return jsonify({'ok': False, 'error': 'username_taken'}), 400
        u = User(username=username)
        u.set_password(password)
        db.session.add(u)
        db.session.flush()  # to get u.id before commit
        try:
            kv_set(f"user_active:{u.id}", {'active': bool(active)})
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True, 'id': u.id, 'active': bool(active)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/users/<int:uid>', methods=['PATCH'], endpoint='api_users_update')
@login_required
def api_users_update(uid):
    try:
        u = db.session.get(User, uid)
        if not u:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        data = request.get_json(silent=True) or {}
        # Optional: allow password change
        pw = (data.get('password') or '').strip()
        if pw:
            u.set_password(pw)
        # Active status persisted in AppKV to avoid schema change
        if 'active' in data:
            try:
                kv_set(f"user_active:{u.id}", {'active': bool(data.get('active'))})
            except Exception:
                pass
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/users', methods=['DELETE'], endpoint='api_users_delete')
@login_required
def api_users_delete():
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or []
        if not isinstance(ids, list):
            return jsonify({'ok': False, 'error': 'invalid_ids'}), 400
        deleted = 0
        for i in ids:
            try:
                i = int(i)
            except Exception:
                continue
            if hasattr(current_user, 'id') and i == current_user.id:
                continue
            u = db.session.get(User, i)
            if u:
                db.session.delete(u)
                deleted += 1
        db.session.commit()
        return jsonify({'ok': True, 'deleted': deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400

# Permissions: persist to AppKV to avoid schema changes
PERM_SCREENS = ['dashboard','sales','purchases','inventory','expenses','employees','salaries','financials','vat','reports','invoices','payments','customers','menu','settings','suppliers','table_settings','users','sample_data']

def _perms_k(uid, scope):
    return f"user_perms:{scope or 'all'}:{int(uid)}"

@main.route('/api/users/<int:uid>/permissions', methods=['GET'], endpoint='api_users_permissions_get')
@login_required
def api_users_permissions_get(uid):
    try:
        scope = (request.args.get('branch_scope') or 'all').strip().lower()
        k = _perms_k(uid, scope)
        row = AppKV.query.filter_by(k=k).first()
        if row:
            try:
                saved = json.loads(row.v)
                items = saved.get('items') or []
            except Exception:
                items = []
        else:
            items = [{ 'screen_key': s, 'view': False, 'add': False, 'edit': False, 'delete': False, 'print': False } for s in PERM_SCREENS]
        return jsonify({'ok': True, 'items': items})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/users/<int:uid>/permissions', methods=['POST'], endpoint='api_users_permissions_set')
@login_required
def api_users_permissions_set(uid):
    try:
        data = request.get_json(silent=True) or {}
        scope = (data.get('branch_scope') or 'all').strip().lower()
        items = data.get('items') or []
        # Basic validation
        norm_items = []
        for it in items:
            key = (it.get('screen_key') or '').strip()
            if not key:
                continue
            norm_items.append({
                'screen_key': key,
                'view': bool(it.get('view')),
                'add': bool(it.get('add')),
                'edit': bool(it.get('edit')),
                'delete': bool(it.get('delete')),
                'print': bool(it.get('print')),
            })
        payload = {'items': norm_items, 'saved_at': datetime.utcnow().isoformat()}
        k = _perms_k(uid, scope)
        row = AppKV.query.filter_by(k=k).first()
        if not row:
            row = AppKV(k=k, v=json.dumps(payload, ensure_ascii=False))
            db.session.add(row)
        else:
            row.v = json.dumps(payload, ensure_ascii=False)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/settings', methods=['GET', 'POST'], endpoint='settings')
@login_required
def settings():
    # Load first (and only) settings row
    s = None
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    if request.method == 'POST':
        try:
            if not s:
                s = Settings()
                (ext_db.session.add(s) if ext_db is not None else db.session.add(s))

            form_data = request.form if request.form else (request.get_json(silent=True) or {})

            # Helpers for coercion
            def as_bool(val):
                return True if str(val).lower() in ['1','true','yes','on'] else False
            def as_int(val, default=None):
                try:
                    return int(str(val).strip())
                except Exception:
                    return default
            def as_float(val, default=None):
                try:
                    return float(str(val).strip())
                except Exception:
                    return default

            # Strings (do not overwrite with empty string)
            for fld in ['company_name','tax_number','phone','address','email','currency','place_india_label','china_town_label','logo_url','default_theme','printer_type','footer_message','receipt_footer_text','china_town_phone1','china_town_phone2','place_india_phone1','place_india_phone2','china_town_logo_url','place_india_logo_url']:
                if hasattr(s, fld) and fld in form_data:
                    val = (form_data.get(fld) or '').strip()
                    if val != '':
                        setattr(s, fld, val)

            # Booleans (explicitly set False when absent)
            if hasattr(s, 'receipt_show_logo'):
                s.receipt_show_logo = as_bool(form_data.get('receipt_show_logo'))
            if hasattr(s, 'receipt_show_tax_number'):
                s.receipt_show_tax_number = as_bool(form_data.get('receipt_show_tax_number'))

            # Integers
            if hasattr(s, 'receipt_font_size'):
                s.receipt_font_size = as_int(form_data.get('receipt_font_size'), s.receipt_font_size if s.receipt_font_size is not None else 12)
            if hasattr(s, 'receipt_logo_height'):
                s.receipt_logo_height = as_int(form_data.get('receipt_logo_height'), s.receipt_logo_height if s.receipt_logo_height is not None else 40)
            if hasattr(s, 'receipt_extra_bottom_mm'):
                s.receipt_extra_bottom_mm = as_int(form_data.get('receipt_extra_bottom_mm'), s.receipt_extra_bottom_mm if s.receipt_extra_bottom_mm is not None else 15)

            # Keep as string for width ('80' or '58')
            if hasattr(s, 'receipt_paper_width') and 'receipt_paper_width' in form_data:
                s.receipt_paper_width = (form_data.get('receipt_paper_width') or '80').strip()

            # Floats / numerics
            if hasattr(s, 'vat_rate') and 'vat_rate' in form_data:
                s.vat_rate = as_float(form_data.get('vat_rate'), s.vat_rate if s.vat_rate is not None else 15.0)
            # Branch-specific
            if hasattr(s, 'china_town_vat_rate') and 'china_town_vat_rate' in form_data:
                s.china_town_vat_rate = as_float(form_data.get('china_town_vat_rate'), s.china_town_vat_rate if s.china_town_vat_rate is not None else 15.0)
            if hasattr(s, 'china_town_discount_rate') and 'china_town_discount_rate' in form_data:
                s.china_town_discount_rate = as_float(form_data.get('china_town_discount_rate'), s.china_town_discount_rate if s.china_town_discount_rate is not None else 0.0)
            if hasattr(s, 'place_india_vat_rate') and 'place_india_vat_rate' in form_data:
                s.place_india_vat_rate = as_float(form_data.get('place_india_vat_rate'), s.place_india_vat_rate if s.place_india_vat_rate is not None else 15.0)
            if hasattr(s, 'place_india_discount_rate') and 'place_india_discount_rate' in form_data:
                s.place_india_discount_rate = as_float(form_data.get('place_india_discount_rate'), s.place_india_discount_rate if s.place_india_discount_rate is not None else 0.0)
            # Passwords (strings)
            # Passwords: do not overwrite with empty string (avoid accidental clearing)
            if hasattr(s, 'china_town_void_password') and 'china_town_void_password' in form_data:
                _pwd = (form_data.get('china_town_void_password') or '').strip()
                if _pwd != '':
                    s.china_town_void_password = _pwd
            if hasattr(s, 'place_india_void_password') and 'place_india_void_password' in form_data:
                _pwd2 = (form_data.get('place_india_void_password') or '').strip()
                if _pwd2 != '':
                    s.place_india_void_password = _pwd2

            # Map currency_image_url -> currency_image
            if hasattr(s, 'currency_image'):
                cur_url = (form_data.get('currency_image_url') or '').strip()
                if cur_url:
                    s.currency_image = cur_url

            # Handle file uploads (logo, currency PNG)
            try:
                # Support persistent uploads directory via env var
                upload_dir = os.getenv('UPLOAD_DIR') or os.path.join(current_app.static_folder, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                path_prefix = '/uploads/' if os.getenv('UPLOAD_DIR') else '/static/uploads/'
                # Logo file (global)
                logo_file = request.files.get('logo_file')
                if logo_file and getattr(logo_file, 'filename', ''):
                    ext = os.path.splitext(logo_file.filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.svg', '.gif']:
                        fname = f"logo_{int(datetime.utcnow().timestamp())}{ext}"
                        fpath = os.path.join(upload_dir, fname)
                        logo_file.save(fpath)
                        s.logo_url = f"{path_prefix}{fname}"
                # China Town branch logo
                china_logo = request.files.get('china_logo_file')
                if china_logo and getattr(china_logo, 'filename', ''):
                    ext = os.path.splitext(china_logo.filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.svg', '.gif']:
                        fname = f"china_logo_{int(datetime.utcnow().timestamp())}{ext}"
                        fpath = os.path.join(upload_dir, fname)
                        china_logo.save(fpath)
                        if hasattr(s, 'china_town_logo_url'):
                            s.china_town_logo_url = f"{path_prefix}{fname}"
                # Palace India branch logo
                india_logo = request.files.get('india_logo_file')
                if india_logo and getattr(india_logo, 'filename', ''):
                    ext = os.path.splitext(india_logo.filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.svg', '.gif']:
                        fname = f"india_logo_{int(datetime.utcnow().timestamp())}{ext}"
                        fpath = os.path.join(upload_dir, fname)
                        india_logo.save(fpath)
                        if hasattr(s, 'place_india_logo_url'):
                            s.place_india_logo_url = f"{path_prefix}{fname}"
                # Currency PNG
                cur_file = request.files.get('currency_file')
                if cur_file and getattr(cur_file, 'filename', ''):


                    ext = os.path.splitext(cur_file.filename)[1].lower()
                    if ext == '.png':
                        fname = f"currency_{int(datetime.utcnow().timestamp())}{ext}"
                        fpath = os.path.join(upload_dir, fname)
                        cur_file.save(fpath)
                        if hasattr(s, 'currency_image'):
                            s.currency_image = f"{path_prefix}{fname}"
            except Exception:
                # Ignore upload errors but continue saving other fields
                pass

            (ext_db.session.commit() if ext_db is not None else db.session.commit())
            flash('Settings saved', 'success')
        except Exception as e:
            (ext_db.session.rollback() if ext_db is not None else db.session.rollback())
            flash(f'Could not save settings: {e}', 'danger')
        return redirect(url_for('main.settings'))
    return render_template('settings.html', s=s)

@main.route('/table-settings', endpoint='table_settings')
@login_required
def table_settings():
    # Define branches for table management
    branches = {
        'china_town': 'CHINA TOWN',
        'place_india': 'PALACE INDIA'
    }
    return render_template('table_settings.html', branches=branches)

@main.route('/table-manager/<branch_code>', endpoint='table_manager')
@login_required
def table_manager(branch_code):
    # Define branch labels
    branch_labels = {
        'china_town': 'CHINA TOWN',
        'place_india': 'PALACE INDIA'
    }
    
    # Check if branch exists
    if branch_code not in branch_labels:
        flash('Branch not found', 'error')
        return redirect(url_for('main.table_settings'))
    
    branch_label = branch_labels[branch_code]
    return render_template('table_manager.html', branch_code=branch_code, branch_label=branch_label)

@csrf.exempt
@main.route('/api/table-layout/<branch_code>', methods=['GET', 'POST'], endpoint='api_table_layout_fixed')
@login_required
def api_table_layout_fixed(branch_code):
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

            # Convert to table manager format (preserve actual table numbers; do not synthesize placeholders)
            layout_sections = []
            for s in sections:
                visible, layout = decode_name(s.name)
                section_data = {
                    'id': s.id,
                    'name': visible,
                    'rows': []
                }

                # Collect actual tables assigned to this section (preserve string numbers)
                assigned = [a for a in assignments if a.section_id == s.id]
                # Sort by natural order: numeric if possible, else lexicographic
                def _key(a):
                    try:
                        return (0, int(str(a.table_number).strip()))
                    except Exception:
                        return (1, str(a.table_number) or '')
                assigned.sort(key=_key)

                # Map to table objects
                tables = [{ 'id': f'table_{idx+1}', 'number': a.table_number, 'seats': 4 } for idx, a in enumerate(assigned)]

                if layout:
                    try:
                        counts = [int(x.strip()) for x in layout.split(',') if x.strip()]
                    except Exception:
                        counts = []
                    i = 0
                    for cnt in counts:
                        if cnt <= 0: continue
                        row_tables = tables[i:i+cnt]
                        section_data['rows'].append({ 'id': f'row_{len(section_data["rows"])+1}', 'tables': row_tables })
                        i += cnt
                    if i < len(tables):
                        section_data['rows'].append({ 'id': f'row_{len(section_data["rows"])+1}', 'tables': tables[i:] })
                else:
                    # Single row with all assigned tables
                    section_data['rows'].append({ 'id': 'row_1', 'tables': tables })

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
                    sort_order=section.get('sort_order', section_idx)
                )
                db.session.add(new_section)
                db.session.flush()  # Get the ID
                
                # Create assignments for tables
                for row in rows:
                    for table in row.get('tables', []):
                        table_number = table.get('number')
                        if table_number:
                            assignment = TableSectionAssignment(
                                branch_code=branch_code,
                                table_number=str(table_number),
                                section_id=new_section.id
                            )
                            db.session.add(assignment)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Layout saved successfully'})
        except Exception as e:
            db.session.rollback()
            print(f"Error saving layout: {e}")
            return jsonify({'error': f'Failed to save layout: {str(e)}'}), 500


# Serve uploaded files from a persistent directory when UPLOAD_DIR is set
@main.route('/uploads/<path:filename>', methods=['GET'], endpoint='serve_uploads')
def serve_uploads(filename):
    try:
        upload_dir = os.getenv('UPLOAD_DIR') or os.path.join(current_app.static_folder, 'uploads')
        return send_from_directory(upload_dir, filename)
    except Exception:
        return 'File not found', 404

@main.route('/users', endpoint='users')
@login_required
def users():
    # Provide users list to template so toolbar/actions work
    try:
        users_list = User.query.order_by(User.id.asc()).all()
    except Exception:
        users_list = []
    # Populate 'active' per user from AppKV (default True)
    for u in users_list:
        try:
            info = kv_get(f"user_active:{u.id}", {'active': True}) or {}
            setattr(u, 'active', bool(info.get('active', True)))
        except Exception:
            setattr(u, 'active', True)
    return render_template('users.html', users=users_list)

@main.route('/create-sample-data', endpoint='create_sample_data_route')
@login_required
def create_sample_data_route():
    flash('تم إنشاء بيانات تجريبية (وهمية) لأغراض العرض فقط', 'info')

    return redirect(url_for('main.dashboard'))

# ---------- VAT blueprint ----------
vat = Blueprint('vat', __name__, url_prefix='/vat')

@vat.route('/', endpoint='vat_dashboard')
@login_required
def vat_dashboard():
    # Period handling (quarterly default; supports monthly as well)
    period = (request.args.get('period') or 'quarterly').strip().lower()
    branch = (request.args.get('branch') or 'all').strip()

    try:
        y = request.args.get('year', type=int) or datetime.utcnow().year
    except Exception:
        y = datetime.utcnow().year

    start_date: date
    end_date: date
    if period == 'monthly':
        ym = (request.args.get('month') or '').strip()  # 'YYYY-MM'
        try:
            if ym and '-' in ym:
                yy, mm = ym.split('-')
                yy = int(yy); mm = int(mm)
                start_date = date(yy, mm, 1)
                nm_y = yy + (1 if mm == 12 else 0)
                nm_m = 1 if mm == 12 else mm + 1
                end_date = date(nm_y, nm_m, 1) - timedelta(days=1)
            else:
                # Fallback to current month
                today = datetime.utcnow().date()
                start_date = date(today.year, today.month, 1)
                nm_y = today.year + (1 if today.month == 12 else 0)
                nm_m = 1 if today.month == 12 else today.month + 1
                end_date = date(nm_y, nm_m, 1) - timedelta(days=1)
        except Exception:
            today = datetime.utcnow().date()
            start_date = date(today.year, today.month, 1)
            nm_y = today.year + (1 if today.month == 12 else 0)
            nm_m = 1 if today.month == 12 else today.month + 1
            end_date = date(nm_y, nm_m, 1) - timedelta(days=1)
        q = None
    else:
        # Quarterly
        try:
            q = request.args.get('quarter', type=int) or 1
        except Exception:
            q = 1
        q = q if q in (1, 2, 3, 4) else 1
        start_month = {1: 1, 2: 4, 3: 7, 4: 10}[q]
        end_month = {1: 3, 2: 6, 3: 9, 4: 12}[q]
        start_date = date(y, start_month, 1)
        next_month_first = date(y + (1 if end_month == 12 else 0), 1 if end_month == 12 else end_month + 1, 1)
        end_date = next_month_first - timedelta(days=1)

    # VAT rate and header info from Settings
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    vat_rate = float(getattr(s, 'vat_rate', 15) or 15) / 100.0

    # SALES: category breakdown (based on tax_amount presence)
    sales_standard_base = sales_standard_vat = sales_standard_total = 0.0
    sales_zero_base = sales_zero_vat = sales_zero_total = 0.0
    sales_exempt_base = sales_exempt_vat = sales_exempt_total = 0.0
    sales_exports_base = sales_exports_vat = sales_exports_total = 0.0

    if hasattr(SalesInvoice, 'total_before_tax') and hasattr(SalesInvoice, 'tax_amount') and hasattr(SalesInvoice, 'total_after_tax_discount') and hasattr(SalesInvoice, 'date'):
        q_sales = db.session.query(SalesInvoice).filter(SalesInvoice.date.between(start_date, end_date))
        if hasattr(SalesInvoice, 'branch') and branch in ('place_india', 'china_town'):
            q_sales = q_sales.filter(SalesInvoice.branch == branch)

        # Standard rated: tax_amount > 0
        sales_standard_base = float((db.session
            .query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0))
            .filter(SalesInvoice.date.between(start_date, end_date))
            .filter((SalesInvoice.tax_amount > 0))
            .filter((SalesInvoice.branch == branch) if hasattr(SalesInvoice, 'branch') and branch in ('place_india','china_town') else True)
            .scalar() or 0.0))
        sales_standard_vat = float((db.session
            .query(func.coalesce(func.sum(SalesInvoice.tax_amount), 0))
            .filter(SalesInvoice.date.between(start_date, end_date))
            .filter((SalesInvoice.tax_amount > 0))
            .filter((SalesInvoice.branch == branch) if hasattr(SalesInvoice, 'branch') and branch in ('place_india','china_town') else True)
            .scalar() or 0.0))
        sales_standard_total = float((db.session
            .query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0))
            .filter(SalesInvoice.date.between(start_date, end_date))
            .filter((SalesInvoice.tax_amount > 0))
            .filter((SalesInvoice.branch == branch) if hasattr(SalesInvoice, 'branch') and branch in ('place_india','china_town') else True)
            .scalar() or 0.0))

        # Zero rated: tax_amount == 0 (we cannot distinguish exempt/exports without extra fields)
        sales_zero_base = float((db.session
            .query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0))
            .filter(SalesInvoice.date.between(start_date, end_date))
            .filter((SalesInvoice.tax_amount == 0))
            .filter((SalesInvoice.branch == branch) if hasattr(SalesInvoice, 'branch') and branch in ('place_india','china_town') else True)
            .scalar() or 0.0))
        sales_zero_vat = 0.0
        sales_zero_total = float((db.session
            .query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0))
            .filter(SalesInvoice.date.between(start_date, end_date))
            .filter((SalesInvoice.tax_amount == 0))
            .filter((SalesInvoice.branch == branch) if hasattr(SalesInvoice, 'branch') and branch in ('place_india','china_town') else True)
            .scalar() or 0.0))

    # PURCHASES & EXPENSES: combine into deductible vs non-deductible
    purchases_deductible_base = purchases_deductible_vat = purchases_deductible_total = 0.0
    purchases_non_deductible_base = purchases_non_deductible_vat = purchases_non_deductible_total = 0.0

    try:
        # Purchases (items)
        # Deductible: items with tax > 0
        p_ded_base = db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.total_price - PurchaseInvoiceItem.tax), 0)) \
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
            .filter(PurchaseInvoice.date.between(start_date, end_date)) \
            .filter(PurchaseInvoiceItem.tax > 0).scalar() or 0.0
        p_ded_vat = db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.tax), 0)) \
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
            .filter(PurchaseInvoice.date.between(start_date, end_date)) \
            .filter(PurchaseInvoiceItem.tax > 0).scalar() or 0.0
        # Non-deductible: items with tax == 0
        p_nd_base = db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0)) \
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
            .filter(PurchaseInvoice.date.between(start_date, end_date)) \
            .filter(PurchaseInvoiceItem.tax == 0).scalar() or 0.0

        # Expenses
        e_ded_base = db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0)) \
            .filter(ExpenseInvoice.date.between(start_date, end_date)) \
            .filter(ExpenseInvoice.tax_amount > 0).scalar() or 0.0
        e_ded_vat = db.session.query(func.coalesce(func.sum(ExpenseInvoice.tax_amount), 0)) \
            .filter(ExpenseInvoice.date.between(start_date, end_date)) \
            .filter(ExpenseInvoice.tax_amount > 0).scalar() or 0.0
        e_nd_base = db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0)) \
            .filter(ExpenseInvoice.date.between(start_date, end_date)) \
            .filter(ExpenseInvoice.tax_amount == 0).scalar() or 0.0

        purchases_deductible_base = float(p_ded_base or 0.0) + float(e_ded_base or 0.0)
        purchases_deductible_vat = float(p_ded_vat or 0.0) + float(e_ded_vat or 0.0)
        purchases_deductible_total = purchases_deductible_base + purchases_deductible_vat

        purchases_non_deductible_base = float(p_nd_base or 0.0) + float(e_nd_base or 0.0)
        purchases_non_deductible_vat = 0.0
        purchases_non_deductible_total = purchases_non_deductible_base
    except Exception:
        purchases_deductible_base = purchases_deductible_vat = purchases_deductible_total = 0.0
        purchases_non_deductible_base = purchases_non_deductible_vat = purchases_non_deductible_total = 0.0

    # Summary
    output_vat = float(sales_standard_vat or 0.0)
    input_vat = float(purchases_deductible_vat or 0.0)
    net_vat = output_vat - input_vat

    data = {
        'period': period,
        'year': y,
        'quarter': q,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'branch': branch,
        # Sales breakdown
        'sales_standard_base': float(sales_standard_base or 0.0),
        'sales_standard_vat': float(sales_standard_vat or 0.0),
        'sales_standard_total': float(sales_standard_total or 0.0),
        'sales_zero_base': float(sales_zero_base or 0.0),
        'sales_zero_vat': float(sales_zero_vat or 0.0),
        'sales_zero_total': float(sales_zero_total or 0.0),
        'sales_exempt_base': float(sales_exempt_base or 0.0),
        'sales_exempt_vat': float(sales_exempt_vat or 0.0),
        'sales_exempt_total': float(sales_exempt_total or 0.0),
        'sales_exports_base': float(sales_exports_base or 0.0),
        'sales_exports_vat': float(sales_exports_vat or 0.0),
        'sales_exports_total': float(sales_exports_total or 0.0),
        # Purchases/Expenses breakdown (combined)
        'purchases_deductible_base': float(purchases_deductible_base or 0.0),
        'purchases_deductible_vat': float(purchases_deductible_vat or 0.0),
        'purchases_deductible_total': float(purchases_deductible_total or 0.0),
        'purchases_non_deductible_base': float(purchases_non_deductible_base or 0.0),
        'purchases_non_deductible_total': float(purchases_non_deductible_total or 0.0),
        # Summary
        'output_vat': float(output_vat or 0.0),
        'input_vat': float(input_vat or 0.0),
        'net_vat': float(net_vat or 0.0),
        # Header info
        'company_name': (getattr(s, 'company_name', '') or ''),
        'tax_number': (getattr(s, 'tax_number', '') or ''),
        'vat_rate': vat_rate,
    }

    return render_template('vat/vat_dashboard.html', data=data)

@vat.route('/print', methods=['GET'])
@login_required
def vat_print():
    # Compute quarter boundaries
    from datetime import date as _date
    try:
        year = int(request.args.get('year') or 0) or _date.today().year
    except Exception:
        year = _date.today().year
    try:
        quarter = int(request.args.get('quarter') or 0) or ((_date.today().month - 1)//3 + 1)
    except Exception:
        quarter = ((_date.today().month - 1)//3 + 1)

    if quarter not in (1,2,3,4):
        quarter = 1
    start_month = {1:1, 2:4, 3:7, 4:10}[quarter]
    end_month = {1:3, 2:6, 3:9, 4:12}[quarter]
    start_date = _date(year, start_month, 1)
    next_month_first = _date(year + (1 if end_month == 12 else 0), 1 if end_month == 12 else end_month + 1, 1)
    end_date = next_month_first
    from datetime import timedelta as _td
    end_date = end_date - _td(days=1)

    # Aggregate totals safely across possible model variants
    sales_place_india = 0
    sales_china_town = 0

    try:
        if hasattr(SalesInvoice, 'total_amount') and hasattr(SalesInvoice, 'created_at') and hasattr(SalesInvoice, 'branch_code'):
            # Simplified POS model (app.models)
            sales_place_india = db.session.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)) \
                .filter(SalesInvoice.branch_code == 'place_india') \
                .filter(SalesInvoice.created_at.between(start_date, end_date)).scalar()
            sales_china_town = db.session.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)) \
                .filter(SalesInvoice.branch_code == 'china_town') \
                .filter(SalesInvoice.created_at.between(start_date, end_date)).scalar()
        elif hasattr(SalesInvoice, 'total_before_tax') and hasattr(SalesInvoice, 'date') and hasattr(SalesInvoice, 'branch'):
            # Rich model (models.py)
            sales_place_india = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
                .filter(SalesInvoice.branch == 'place_india') \
                .filter(SalesInvoice.date.between(start_date, end_date)).scalar()
            sales_china_town = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
                .filter(SalesInvoice.branch == 'china_town') \
                .filter(SalesInvoice.date.between(start_date, end_date)).scalar()
    except Exception:
        sales_place_india = 0
        sales_china_town = 0

    # Branch filter for sales total
    branch = (request.args.get('branch') or 'all').strip()
    if branch == 'place_india':
        sales_total = float(sales_place_india or 0)
    elif branch == 'china_town':
        sales_total = float(sales_china_town or 0)
    else:
        sales_total = float(sales_place_india or 0) + float(sales_china_town or 0)

    # Aggregate purchases and expenses within the period
    try:
        purchases_total = float(db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0))
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id)
            .filter(PurchaseInvoice.date.between(start_date, end_date)).scalar() or 0.0)
    except Exception:
        purchases_total = 0.0
    try:
        expenses_total = float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_after_tax_discount), 0))
            .filter(ExpenseInvoice.date.between(start_date, end_date)).scalar() or 0.0)
    except Exception:
        expenses_total = 0.0

    s = None
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    vat_rate = float(getattr(s, 'vat_rate', 15) or 15)/100.0

    output_vat = float(sales_total or 0) * vat_rate
    input_vat = float((purchases_total or 0) + (expenses_total or 0)) * vat_rate
    net_vat = output_vat - input_vat

    # Render unified print report (support CSV export)
    report_title = f"VAT Report — Q{quarter} {year}"
    if branch and branch != 'all':
        report_title += f" — {branch}"
    columns = ['Metric', 'Amount']
    data_rows = [
        {'Metric': 'Sales (Net Base)', 'Amount': float(sales_total or 0.0)},
        {'Metric': 'Purchases', 'Amount': float(purchases_total or 0.0)},
        {'Metric': 'Expenses', 'Amount': float(expenses_total or 0.0)},
        {'Metric': 'Output VAT', 'Amount': float(output_vat or 0.0)},
        {'Metric': 'Input VAT', 'Amount': float(input_vat or 0.0)},
        {'Metric': 'Net VAT', 'Amount': float(net_vat or 0.0)},
    ]
    totals = {'Amount': float(net_vat or 0.0)}
    fmt = (request.args.get('format') or '').strip().lower()
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Metric','Amount'])
            for r in data_rows:
                writer.writerow([r.get('Metric',''), r.get('Amount',0.0)])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': f'attachment; filename="vat_q{quarter}_{year}.csv"'})
        except Exception:
            pass
    return render_template('print_report.html', report_title=report_title, settings=s,
                           generated_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                           start_date=start_date.isoformat(), end_date=end_date.isoformat(),
                           payment_method=None, branch=branch or 'all',
                           columns=columns, data=data_rows, totals=totals, totals_columns=['Amount'],
                           totals_colspan=1, payment_totals=None)

# ---------- Financials blueprint ----------
financials = Blueprint('financials', __name__, url_prefix='/financials')

@financials.route('/income-statement', endpoint='income_statement')
@login_required
def income_statement():
    period = (request.args.get('period') or 'today').strip()
    today = datetime.utcnow().date()
    if period == 'today':
        start_date = end_date = today
    elif period == 'this_week':
        start_date = today - timedelta(days=today.isoweekday() - 1)
        end_date = start_date + timedelta(days=6)
    elif period == 'this_month':
        start_date = date(today.year, today.month, 1)
        nm = date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)
        end_date = nm - timedelta(days=1)
    elif period == 'this_year':
        start_date = date(today.year, 1, 1)
        end_date = date(today.year, 12, 31)
    else:
        sd = request.args.get('start_date')
        ed = request.args.get('end_date')
        try:
            start_date = datetime.strptime(sd, '%Y-%m-%d').date() if sd else today
            end_date = datetime.strptime(ed, '%Y-%m-%d').date() if ed else today
        except Exception:
            start_date = end_date = today
        period = 'custom'

    # Branch filter (optional)
    branch = (request.args.get('branch') or 'all').strip()

    # Revenue from Sales (net of invoice discount; excludes VAT)
    revenue = 0.0
    try:
        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(
            SalesInvoiceItem, SalesInvoiceItem.invoice_id == SalesInvoice.id
        )
        if hasattr(SalesInvoice, 'created_at'):
            q = q.filter(SalesInvoice.created_at.between(start_date, end_date))
        elif hasattr(SalesInvoice, 'date'):
            q = q.filter(SalesInvoice.date.between(start_date, end_date))
        if branch and branch != 'all':
            if hasattr(SalesInvoice, 'branch_code'):
                q = q.filter(SalesInvoice.branch_code == branch)
            elif hasattr(SalesInvoice, 'branch'):
                q = q.filter(SalesInvoice.branch == branch)
        for inv, it in q.all():
            if hasattr(it, 'unit_price') and hasattr(it, 'qty'):
                line = float((it.unit_price or 0.0) * (it.qty or 0.0))
            elif hasattr(it, 'price_before_tax') and hasattr(it, 'quantity'):
                line = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            else:
                line = 0.0
            disc_pct = float(getattr(inv, 'discount_pct', 0.0) or 0.0)
            revenue += line * (1.0 - disc_pct/100.0)
    except Exception:
        revenue = 0.0

    # COGS approximated by purchase costs in period (before tax)
    cogs = 0.0
    try:
        q_p = db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.price_before_tax * PurchaseInvoiceItem.quantity), 0)) \
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
            .filter(PurchaseInvoice.date.between(start_date, end_date))
        cogs = float(q_p.scalar() or 0.0)
    except Exception:
        cogs = 0.0

    # Operating expenses from Expense invoices (after tax and discount)
    operating_expenses = 0.0
    try:
        q_e = db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_after_tax_discount), 0)) \
            .filter(ExpenseInvoice.date.between(start_date, end_date))
        operating_expenses = float(q_e.scalar() or 0.0)
    except Exception:
        operating_expenses = 0.0

    gross_profit = max(revenue - cogs, 0.0)
    operating_profit = gross_profit - operating_expenses
    other_income = 0.0
    other_expenses = 0.0
    net_profit_before_tax = operating_profit + other_income - other_expenses
    tax = 0.0
    net_profit_after_tax = net_profit_before_tax - tax

    data = {
        'period': period,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'branch': branch,
        'revenue': float(revenue or 0.0),
        'cogs': float(cogs or 0.0),
        'gross_profit': float(gross_profit or 0.0),
        'operating_expenses': float(operating_expenses or 0.0),
        'operating_profit': float(operating_profit or 0.0),
        'other_income': float(other_income or 0.0),
        'other_expenses': float(other_expenses or 0.0),
        'net_profit_before_tax': float(net_profit_before_tax or 0.0),
        'tax': float(tax or 0.0),
        'net_profit_after_tax': float(net_profit_after_tax or 0.0),
    }
    return render_template('financials/income_statement.html', data=data)


@financials.route('/print/income_statement', methods=['GET'], endpoint='print_income_statement')
@login_required
def print_income_statement():
    # Period params
    period = (request.args.get('period') or 'today').strip()
    today = datetime.utcnow().date()
    if period == 'today':
        start_date = end_date = today
    elif period == 'this_week':
        start_date = today - timedelta(days=today.isoweekday() - 1)
        end_date = start_date + timedelta(days=6)
    elif period == 'this_month':
        start_date = date(today.year, today.month, 1)
        nm = date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)
        end_date = nm - timedelta(days=1)
    elif period == 'this_year':
        start_date = date(today.year, 1, 1)
        end_date = date(today.year, 12, 31)
    else:
        sd = request.args.get('start_date')
        ed = request.args.get('end_date')
        try:
            start_date = datetime.strptime(sd, '%Y-%m-%d').date() if sd else today
            end_date = datetime.strptime(ed, '%Y-%m-%d').date() if ed else today
        except Exception:
            start_date = end_date = today
        period = 'custom'

    branch = (request.args.get('branch') or 'all').strip()

    # Compute revenue
    revenue = 0.0
    try:
        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(
            SalesInvoiceItem, SalesInvoiceItem.invoice_id == SalesInvoice.id
        )
        if hasattr(SalesInvoice, 'created_at'):
            q = q.filter(SalesInvoice.created_at.between(start_date, end_date))
        elif hasattr(SalesInvoice, 'date'):
            q = q.filter(SalesInvoice.date.between(start_date, end_date))
        if branch and branch != 'all':
            if hasattr(SalesInvoice, 'branch_code'):
                q = q.filter(SalesInvoice.branch_code == branch)
            elif hasattr(SalesInvoice, 'branch'):
                q = q.filter(SalesInvoice.branch == branch)
        for inv, it in q.all():
            if hasattr(it, 'unit_price') and hasattr(it, 'qty'):
                line = float((it.unit_price or 0.0) * (it.qty or 0.0))
            elif hasattr(it, 'price_before_tax') and hasattr(it, 'quantity'):
                line = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            else:
                line = 0.0
            disc_pct = float(getattr(inv, 'discount_pct', 0.0) or 0.0)
            revenue += line * (1.0 - disc_pct/100.0)
    except Exception:
        revenue = 0.0

    # COGS
    cogs = 0.0
    try:
        q_p = db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.price_before_tax * PurchaseInvoiceItem.quantity), 0)) \
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
            .filter(PurchaseInvoice.date.between(start_date, end_date))
        cogs = float(q_p.scalar() or 0.0)
    except Exception:
        cogs = 0.0

    # Operating expenses
    operating_expenses = 0.0
    try:
        q_e = db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_after_tax_discount), 0)) \
            .filter(ExpenseInvoice.date.between(start_date, end_date))
        operating_expenses = float(q_e.scalar() or 0.0)
    except Exception:
        operating_expenses = 0.0

    gross_profit = max(revenue - cogs, 0.0)
    operating_profit = gross_profit - operating_expenses
    other_income = 0.0
    other_expenses = 0.0
    net_profit_before_tax = operating_profit + other_income - other_expenses
    tax = 0.0
    net_profit_after_tax = net_profit_before_tax - tax

    # Settings for header
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None

    # Prepare print data
    report_title = 'Income Statement'
    if branch and branch != 'all':
        report_title += f' — {branch}'
    columns = ['Item', 'Amount']
    rows = [
        {'Item': 'Revenue', 'Amount': float(revenue or 0.0)},
        {'Item': 'COGS', 'Amount': float(cogs or 0.0)},
        {'Item': 'Gross Profit', 'Amount': float(gross_profit or 0.0)},
        {'Item': 'Operating Expenses', 'Amount': float(operating_expenses or 0.0)},
        {'Item': 'Operating Profit', 'Amount': float(operating_profit or 0.0)},
        {'Item': 'Other Income', 'Amount': float(other_income or 0.0)},
        {'Item': 'Other Expenses', 'Amount': float(other_expenses or 0.0)},
        {'Item': 'Net Profit Before Tax', 'Amount': float(net_profit_before_tax or 0.0)},
        {'Item': 'Tax', 'Amount': float(tax or 0.0)},
        {'Item': 'Net Profit After Tax', 'Amount': float(net_profit_after_tax or 0.0)},
    ]
    totals = {'Amount': float(net_profit_after_tax or 0.0)}

    return render_template('print_report.html', report_title=report_title, settings=settings,
                           generated_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                           start_date=start_date.isoformat(), end_date=end_date.isoformat(),
                           payment_method=None, branch=branch or 'all',
                           columns=columns, data=rows, totals=totals, totals_columns=['Amount'],
                           totals_colspan=1, payment_totals=None)



@financials.route('/balance-sheet', endpoint='balance_sheet')
@login_required
def balance_sheet():
    d = (request.args.get('date') or date.today().isoformat())
    data = {
        'date': d,
        'assets': 0.0,
        'liabilities': 0.0,
        'equity': 0.0,
    }
    return render_template('financials/balance_sheet.html', data=data)

@financials.route('/trial-balance', endpoint='trial_balance')
@login_required
def trial_balance():
    d = (request.args.get('date') or date.today().isoformat())
    data = {
        'date': d,
        'rows': [],
        'total_debit': 0.0,
        'total_credit': 0.0,
    }
    return render_template('financials/trial_balance.html', data=data)


@financials.route('/balance-sheet/print', endpoint='print_balance_sheet')
@login_required
def print_balance_sheet():
    d = (request.args.get('date') or date.today().isoformat())
    # Simple placeholders (until full ledger is implemented)
    assets = 0.0
    liabilities = 0.0
    equity = float(assets - liabilities)
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    columns = ['Metric', 'Amount']
    data_rows = [
        {'Metric': 'Assets', 'Amount': float(assets or 0.0)},
        {'Metric': 'Liabilities', 'Amount': float(liabilities or 0.0)},
        {'Metric': 'Equity', 'Amount': float(equity or 0.0)},
    ]
    totals = {'Amount': float(equity or 0.0)}
    return render_template('print_report.html', report_title=f"Balance Sheet — {d}", settings=settings,
                           generated_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                           start_date=d, end_date=d,
                           payment_method=None, branch='all',
                           columns=columns, data=data_rows, totals=totals, totals_columns=['Amount'],
                           totals_colspan=1, payment_totals=None)

@financials.route('/trial-balance/print', endpoint='print_trial_balance')
@login_required
def print_trial_balance():
    d = (request.args.get('date') or date.today().isoformat())
    rows = []
    total_debit = 0.0
    total_credit = 0.0
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    columns = ['Code', 'Account', 'Debit', 'Credit']
    data_rows = [
        {'Code': r.get('code', ''), 'Account': r.get('name', ''),
         'Debit': float(r.get('debit') or 0.0), 'Credit': float(r.get('credit') or 0.0)}
        for r in rows
    ]
    totals = {'Debit': float(total_debit or 0.0), 'Credit': float(total_credit or 0.0)}
    return render_template('print_report.html', report_title=f"Trial Balance — {d}", settings=settings,
                           generated_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                           start_date=d, end_date=d,
                           payment_method=None, branch='all',
                           columns=columns, data=data_rows, totals=totals, totals_columns=['Debit','Credit'],
                           totals_colspan=2, payment_totals=None)


# --------- Minimal report APIs to avoid 404s and support UI tables/prints ---------
@main.route('/api/all-invoices', methods=['GET'], endpoint='api_all_invoices')
@login_required
def api_all_invoices():
    try:
        payment_method = (request.args.get('payment_method') or '').strip().lower()
        rows = []
        branch_totals = {}
        overall = {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0}

        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(
            SalesInvoiceItem, SalesInvoiceItem.invoice_id == SalesInvoice.id
        )
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(SalesInvoice.payment_method) == payment_method)
        # Optional branch filter (sales only)
        branch = (request.args.get('branch') or '').strip().lower()
        if branch and branch != 'all':
            q = q.filter(func.lower(SalesInvoice.branch) == branch)
        if hasattr(SalesInvoice, 'created_at'):
            q = q.order_by(SalesInvoice.created_at.desc())
        elif hasattr(SalesInvoice, 'date'):
            q = q.order_by(SalesInvoice.date.desc())
        q = q.limit(1000)

        results = q.all()
        # اجمع أساس البنود لكل فاتورة لتوزيع الخصم والضريبة بشكل نسبي
        inv_base = {}
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results:
            branch = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
            if getattr(inv, 'created_at', None):
                date_s = inv.created_at.date().isoformat()
            elif getattr(inv, 'date', None):
                date_s = inv.date.isoformat()
            else:
                date_s = ''
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            disc_share = 0.0
            vat_share = 0.0
            if base_total > 0:
                disc_share = float(getattr(inv, 'discount_amount', 0.0) or 0.0) * (amount / base_total)
                vat_share = float(getattr(inv, 'tax_amount', 0.0) or 0.0) * (amount / base_total)
            base_after_disc = max(amount - disc_share, 0.0)
            total = base_after_disc + vat_share
            pm = (inv.payment_method or '').upper()
            rows.append({
                'branch': branch,
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.product_name,
                'quantity': float(it.quantity or 0.0),
                'price': float(it.price_before_tax or 0.0),
                'amount': amount,
                'discount': round(disc_share, 2),
                'vat': round(vat_share, 2),
                'total': round(total, 2),
                'payment_method': pm,
            })
            bt = branch_totals.setdefault(branch, {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0})
            bt['amount'] += amount; bt['discount'] += disc_share; bt['vat'] += vat_share; bt['total'] += total
            overall['amount'] += amount; overall['discount'] += disc_share; overall['vat'] += vat_share; overall['total'] += total

        return jsonify({'invoices': rows, 'branch_totals': branch_totals, 'overall_totals': overall})
    except Exception as e:
        # Log the error for diagnosis, but return empty to avoid UI breaking
        try:
            current_app.logger.exception(f"/api/all-invoices failed: {e}")
        except Exception:
            pass
        return jsonify({'invoices': [], 'branch_totals': {}, 'overall_totals': {'amount':0,'discount':0,'vat':0,'total':0}, 'note': 'stub', 'error': str(e)}), 200


@main.route('/api/reports/all-purchases', methods=['GET'], endpoint='api_reports_all_purchases')
@login_required
def api_reports_all_purchases():
    try:
        payment_method = (request.args.get('payment_method') or '').strip().lower()
        rows = []
        overall = {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0}
        q = db.session.query(PurchaseInvoice, PurchaseInvoiceItem).join(
            PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id
        )
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(PurchaseInvoice.payment_method) == payment_method)
        # ترتيب آمن
        if hasattr(PurchaseInvoice, 'created_at'):
            q = q.order_by(PurchaseInvoice.created_at.desc())
        elif hasattr(PurchaseInvoice, 'date'):
            q = q.order_by(PurchaseInvoice.date.desc())
        q = q.limit(1000)

        results = q.all()
        # اجمع أساس البنود لكل فاتورة لتوزيع الخصم/الضريبة من رأس الفاتورة
        inv_base = {}
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results:
            date_s = (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            # استخدم خصم وضريبة رأس الفاتورة إن توفّرا، وإلا ارجع لقيم البند
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat = inv_vat * (amount / base_total)
            else:
                disc = float(it.discount or 0.0)
                base = max(amount - disc, 0.0)
                vat = float(it.tax or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            total = float(getattr(inv, 'total_after_tax_discount', 0.0) or 0.0)
            if total <= 0:
                total = base_after_disc + vat
            rows.append({
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.raw_material_name,
                'quantity': float(it.quantity or 0.0),
                'price': float(it.price_before_tax or 0.0),
                'amount': amount,
                'discount': round(disc, 2),
                'vat': round(vat, 2),
                'total': round(base_after_disc + vat, 2),
                'payment_method': (inv.payment_method or '').upper(),
            })
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += (base_after_disc + vat)
        return jsonify({'purchases': rows, 'overall_totals': overall})
    except Exception:
        return jsonify({'purchases': [], 'overall_totals': {'amount':0,'discount':0,'vat':0,'total':0}, 'note': 'stub'}), 200


@main.route('/api/all-expenses', methods=['GET'], endpoint='api_all_expenses')
@login_required
def api_all_expenses():
    try:
        payment_method = (request.args.get('payment_method') or '').strip().lower()
        rows = []
        overall = {'amount': 0.0}
        q = ExpenseInvoice.query
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(ExpenseInvoice.payment_method) == payment_method)
        q = q.order_by(ExpenseInvoice.created_at.desc()).limit(1000)
        for exp in q.all():
            # Build full items list for this expense invoice
            items_list = []
            try:
                for it in ExpenseInvoiceItem.query.filter_by(invoice_id=exp.id).all():
                    qty = float(getattr(it, 'quantity', 0.0) or 0.0)
                    price = float(getattr(it, 'price_before_tax', 0.0) or 0.0)
                    tax = float(getattr(it, 'tax', 0.0) or 0.0)
                    disc = float(getattr(it, 'discount', 0.0) or 0.0)
                    line_total = float(getattr(it, 'total_price', None) or (max(price*qty - disc, 0.0) + tax) or 0.0)
                    items_list.append({
                        'description': getattr(it, 'description', '') or '',
                        'quantity': qty,
                        'price': price,
                        'tax': tax,
                        'discount': disc,
                        'total': line_total,
                    })
            except Exception:
                items_list = []
            rows.append({
                'date': (exp.date.strftime('%Y-%m-%d') if getattr(exp, 'date', None) else ''),
                'expense_number': exp.invoice_number,
                'items': items_list,
                'amount': float(exp.total_after_tax_discount or 0.0),
                'payment_method': (exp.payment_method or '').upper(),
            })
            overall['amount'] += float(exp.total_after_tax_discount or 0.0)
        return jsonify({'expenses': rows, 'overall_totals': overall})
    except Exception:
        return jsonify({'expenses': [], 'overall_totals': {'amount':0}, 'note': 'stub'}), 200


@main.route('/reports/print/all-invoices/sales', methods=['GET'], endpoint='reports_print_all_invoices_sales')
@login_required
def reports_print_all_invoices_sales():
    # Reuse same data generation as api_all_invoices but render print template
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    fmt = (request.args.get('format') or '').strip().lower()
    rows = []
    branch_totals = {}
    overall = {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0}
    try:
        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(
            SalesInvoiceItem, SalesInvoiceItem.invoice_id == SalesInvoice.id
        )
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(SalesInvoice.payment_method) == payment_method)
        # Optional branch filter (sales only)
        branch = (request.args.get('branch') or 'all').strip().lower()
        if branch and branch != 'all':
            q = q.filter(func.lower(SalesInvoice.branch) == branch)
        # Optional date range filter
        if start_date:
            try:
                if hasattr(SalesInvoice, 'created_at'):
                    q = q.filter(func.date(SalesInvoice.created_at) >= start_date)
                elif hasattr(SalesInvoice, 'date'):
                    q = q.filter(SalesInvoice.date >= start_date)
            except Exception:
                pass
        if end_date:
            try:
                if hasattr(SalesInvoice, 'created_at'):
                    q = q.filter(func.date(SalesInvoice.created_at) <= end_date)
                elif hasattr(SalesInvoice, 'date'):
                    q = q.filter(SalesInvoice.date <= end_date)
            except Exception:
                pass
        if hasattr(SalesInvoice, 'created_at'):
            q = q.order_by(SalesInvoice.created_at.desc())
        elif hasattr(SalesInvoice, 'date'):
            q = q.order_by(SalesInvoice.date.desc())
        q = q.limit(1000)

        results = q.all()
        # اجمع أساس البنود لكل فاتورة لتوزيع الخصم/الضريبة من رأس الفاتورة
        inv_base = {}
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results:
            branch = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
            if getattr(inv, 'created_at', None):
                date_s = inv.created_at.date().isoformat()
            elif getattr(inv, 'date', None):
                date_s = inv.date.isoformat()
            else:
                date_s = ''
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat  = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat  = inv_vat  * (amount / base_total)
            else:
                disc = float(getattr(it, 'discount', 0.0) or 0.0)
                base = max(amount - disc, 0.0)
                vat  = float(getattr(it, 'tax', 0.0) or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            total = base_after_disc + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'branch': branch,
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.product_name,
                'quantity': float(it.quantity or 0.0),
                'amount': amount,
                'discount': round(disc, 2),
                'vat': round(vat, 2),
                'total': round(total, 2),
                'payment_method': pm,
            })
            bt = branch_totals.setdefault(branch, {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0})
            bt['amount'] += amount; bt['discount'] += disc; bt['vat'] += vat; bt['total'] += total
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += total
    except Exception:
        pass

    # Settings for header
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None

    # Payment method totals
    payment_totals = {}
    for r in rows:
        pm = (r.get('payment_method') or '').upper()
        payment_totals[pm] = payment_totals.get(pm, 0.0) + float(r.get('total') or 0.0)

    # Aggregate item totals (by quantity) for display
    item_totals = {}
    try:
        for r in rows:
            name = (r.get('item_name') or '').strip()
            qty = float(r.get('quantity') or 0.0)
            if name:
                item_totals[name] = item_totals.get(name, 0.0) + qty
    except Exception:
        item_totals = {}

    meta = {
        'title': 'Sales Invoices (All) — Print',
        'payment_method': payment_method or 'all',
        'branch': (branch or 'all'),
        'start_date': request.args.get('start_date') or '',
        'end_date': request.args.get('end_date') or '',
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    # Use unified print_report.html like purchases/expenses
    columns = ['Branch','Date','Invoice No.','Item','Qty','Amount','Discount','VAT','Total','Payment']
    data = []
    for r in rows:
        data.append({
            'Branch': r.get('branch') or '',
            'Date': r.get('date') or '',
            'Invoice No.': r.get('invoice_number') or '',
            'Item': r.get('item_name') or '',
            'Qty': float(r.get('quantity') or 0.0),
            'Amount': float(r.get('amount') or 0.0),
            'Discount': float(r.get('discount') or 0.0),
            'VAT': float(r.get('vat') or 0.0),
            'Total': float(r.get('total') or 0.0),
            'Payment': r.get('payment_method') or '',
        })
    totals = {
        'Amount': float(overall.get('amount') or 0.0),
        'Discount': float(overall.get('discount') or 0.0),
        'VAT': float(overall.get('vat') or 0.0),
        'Total': float(overall.get('total') or 0.0),
    }
    totals_columns = ['Amount','Discount','VAT','Total']
    totals_colspan = len(columns) - len(totals_columns)
    # CSV export
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for r in data:
                writer.writerow([r.get('Branch',''), r.get('Date',''), r.get('Invoice No.',''), r.get('Item',''),
                                 r.get('Qty',0.0), r.get('Amount',0.0), r.get('Discount',0.0), r.get('VAT',0.0),
                                 r.get('Total',0.0), r.get('Payment','')])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="sales_invoices.csv"'})
        except Exception:
            pass

    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=data, totals=totals, totals_columns=totals_columns,
                           totals_colspan=totals_colspan, payment_totals=payment_totals,
                           item_totals=item_totals)


@main.route('/reports/print/all-invoices/purchases', methods=['GET'], endpoint='reports_print_all_invoices_purchases')
@login_required
def reports_print_all_invoices_purchases():
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip().lower()
    fmt = (request.args.get('format') or '').strip().lower()
    rows = []
    totals = {'Amount': 0.0, 'Discount': 0.0, 'VAT': 0.0, 'Total': 0.0}
    payment_totals = {}
    try:
        q = db.session.query(PurchaseInvoice, PurchaseInvoiceItem).join(
            PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id
        )
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(PurchaseInvoice.payment_method) == payment_method)
        # Date filtering if fields exist
        if start_date:
            try:
                q = q.filter(PurchaseInvoice.date >= start_date)
            except Exception:
                pass
        if end_date:
            try:
                q = q.filter(PurchaseInvoice.date <= end_date)
            except Exception:
                pass
        if branch and branch != 'all' and hasattr(PurchaseInvoice, 'branch'):
            q = q.filter(func.lower(PurchaseInvoice.branch) == branch)
        if hasattr(PurchaseInvoice, 'created_at'):
            q = q.order_by(PurchaseInvoice.created_at.desc())
        elif hasattr(PurchaseInvoice, 'date'):
            q = q.order_by(PurchaseInvoice.date.desc())
        q = q.limit(2000)

        results = q.all()
        # Aggregate base per invoice for proportional discount/VAT allocation
        inv_base = {}
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results:
            d = (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat = inv_vat * (amount / base_total)
            else:
                disc = float(it.discount or 0.0)
                base = max(amount - disc, 0.0)
                vat = float(it.tax or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            line_total = base_after_disc + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'Date': d,
                'Invoice No.': inv.invoice_number,
                'Item': it.raw_material_name,
                'Qty': float(it.quantity or 0.0),
                'Amount': amount,
                'Discount': round(disc, 2),
                'VAT': round(vat, 2),
                'Total': round(line_total, 2),
                'Payment': pm,
            })
            totals['Amount'] += amount; totals['Discount'] += disc; totals['VAT'] += vat; totals['Total'] += line_total
            payment_totals[pm] = payment_totals.get(pm, 0.0) + line_total
    except Exception:
        pass

    # Settings & meta
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    meta = {
        'title': 'Purchase Invoices — Print',
        'payment_method': payment_method or 'all',
        'branch': branch or 'all',
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    columns = ['Date','Invoice No.','Item','Qty','Amount','Discount','VAT','Total','Payment']
    # CSV export
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for r in rows:
                writer.writerow([r.get('Date',''), r.get('Invoice No.',''), r.get('Item',''), r.get('Qty',0.0),
                                 r.get('Amount',0.0), r.get('Discount',0.0), r.get('VAT',0.0), r.get('Total',0.0),
                                 r.get('Payment','')])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="purchase_invoices.csv"'})
        except Exception:
            pass
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=['Amount','Discount','VAT','Total'],
                           totals_colspan=4, payment_totals=payment_totals)


@main.route('/reports/print/daily-items-summary', methods=['GET'], endpoint='reports_print_daily_items_summary')
@login_required
def reports_print_daily_items_summary():
    """Print a daily summary of items (by quantity) for a given day.
    By default, summarizes from Order Invoices (pre-payment) so printed orders show up.
    Optional source param: source=orders (default) or source=sales.
    """
    from sqlalchemy import func
    source = (request.args.get('source') or 'orders').strip().lower()
    branch_f = (request.args.get('branch') or '').strip()

    # Determine target date (YYYY-MM-DD) - defaults to today
    date_str = (request.args.get('date') or '').strip()
    from datetime import date as _date, datetime as _dt, time as _time
    try:
        target_date = _date.fromisoformat(date_str) if date_str else _date.today()
    except Exception:
        target_date = _date.today()

    # Compute start/end of day (00:00:00 -> 23:59:59)
    start_dt = _dt.combine(target_date, _time.min)
    end_dt = _dt.combine(target_date, _time.max)

    data = []
    try:
        if source == 'orders':
            from models import OrderInvoice
            # Fetch orders within day window and aggregate from JSON items
            q = OrderInvoice.query.filter(
                OrderInvoice.invoice_date >= start_dt,
                OrderInvoice.invoice_date <= end_dt
            )
            if branch_f:
                q = q.filter(OrderInvoice.branch == branch_f)
            orders = q.limit(5000).all()

            totals_map = {}
            for o in orders:
                try:
                    for it in (o.items or []):
                        name = (it.get('name') if isinstance(it, dict) else None) or '-'
                        qty_val = it.get('qty') if isinstance(it, dict) else 0
                        try:
                            qty = float(qty_val or 0)
                        except Exception:
                            qty = 0.0
                        totals_map[name] = totals_map.get(name, 0.0) + qty
                except Exception:
                    continue
            data = [
                {'Item': k, 'Total Qty': float(v)}
                for k, v in sorted(totals_map.items(), key=lambda x: (-x[1], x[0]))
            ]
        else:
            from models import SalesInvoice, SalesInvoiceItem
            # Sales invoices use date (Date) column; filter by equality if Date only
            q = db.session.query(
                SalesInvoiceItem.product_name.label('item_name'),
                func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label('total_qty')
            ).join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
            q = q.filter(SalesInvoice.date == target_date)
            if branch_f and hasattr(SalesInvoice, 'branch'):
                q = q.filter(SalesInvoice.branch == branch_f)
            if hasattr(SalesInvoice, 'status'):
                q = q.filter(func.lower(SalesInvoice.status) == 'paid')
            q = q.group_by(SalesInvoiceItem.product_name).order_by(func.sum(SalesInvoiceItem.quantity).desc())
            rows = q.all()
            data = [
                {'Item': (r.item_name or '-'), 'Total Qty': float(r.total_qty or 0.0)} for r in rows
            ]
    except Exception:
        data = []

    # Settings & meta
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    meta_title = f"Daily Items Summary — {target_date.isoformat()} ({'orders' if source=='orders' else 'sales'})"
    columns = ['Item', 'Total Qty']

    return render_template(
        'print_report.html',
        report_title=meta_title,
        settings=settings,
        generated_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
        start_date=target_date.isoformat(),
        end_date=target_date.isoformat(),
        payment_method=source,
        branch=(branch_f or 'all'),
        columns=columns,
        data=data,
        totals={},
        totals_columns=[],
        totals_colspan=len(columns)
    )

@main.route('/reports/print/all-invoices/expenses', methods=['GET'], endpoint='reports_print_all_invoices_expenses')
@login_required
def reports_print_all_invoices_expenses():
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip().lower()
    fmt = (request.args.get('format') or '').strip().lower()
    rows = []
    totals = {'Amount': 0.0}
    payment_totals = {}
    try:
        q = ExpenseInvoice.query
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(ExpenseInvoice.payment_method) == payment_method)
        if start_date:
            try:
                q = q.filter(ExpenseInvoice.date >= start_date)
            except Exception:
                pass
        if end_date:
            try:
                q = q.filter(ExpenseInvoice.date <= end_date)
            except Exception:
                pass
        if branch and branch != 'all' and hasattr(ExpenseInvoice, 'branch'):
            q = q.filter(func.lower(ExpenseInvoice.branch) == branch)
        q = q.order_by(ExpenseInvoice.created_at.desc()).limit(2000)
        for exp in q.all():
            d = (exp.date.strftime('%Y-%m-%d') if getattr(exp, 'date', None) else '')
            pm = (exp.payment_method or '').upper()
            # Print per item
            try:
                items = ExpenseInvoiceItem.query.filter_by(invoice_id=exp.id).all()
            except Exception:
                items = []
            for it in items:
                qty = float(getattr(it, 'quantity', 0.0) or 0.0)
                price = float(getattr(it, 'price_before_tax', 0.0) or 0.0)
                tax = float(getattr(it, 'tax', 0.0) or 0.0)
                disc = float(getattr(it, 'discount', 0.0) or 0.0)
                line_total = float(getattr(it, 'total_price', None) or (max(price*qty - disc, 0.0) + tax) or 0.0)
                rows.append({
                    'Date': d,
                    'Expense No.': exp.invoice_number,
                    'Description': getattr(it, 'description', '') or '',
                    'Qty': qty,
                    'Amount': price * qty,
                    'Tax': tax,
                    'Discount': disc,
                    'Line Total': line_total,
                    'Payment': pm,
                })
                totals['Amount'] += (price * qty)
                totals['Tax'] = float(totals.get('Tax', 0.0) or 0.0) + tax
                totals['Discount'] = float(totals.get('Discount', 0.0) or 0.0) + disc
                totals['Line Total'] = float(totals.get('Line Total', 0.0) or 0.0) + line_total
                payment_totals[pm] = payment_totals.get(pm, 0.0) + line_total
    except Exception:
        pass

    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    meta = {
        'title': 'Expenses — Print',
        'payment_method': payment_method or 'all',
        'branch': branch or 'all',
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    columns = ['Date','Expense No.','Description','Qty','Amount','Tax','Discount','Line Total','Payment']
    totals_columns = ['Amount','Tax','Discount','Line Total']
    totals_colspan = len(columns) - len(totals_columns)
    # CSV export
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for r in rows:
                writer.writerow([r.get('Date',''), r.get('Expense No.',''), r.get('Description',''), r.get('Qty',0.0),
                                 r.get('Amount',0.0), r.get('Tax',0.0), r.get('Discount',0.0), r.get('Line Total',0.0), r.get('Payment','')])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="expense_invoices.csv"'})
        except Exception:
            pass

    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=totals_columns,
                           totals_colspan=totals_colspan, payment_totals=payment_totals)


# ================= Salaries/Payroll Print Reports =================
@main.route('/reports/print/payroll', methods=['GET'], endpoint='print_payroll')
@login_required
def print_payroll():
    # Params
    from datetime import date as _date
    try:
        y_from = int(request.args.get('year_from') or 0) or _date.today().year
    except Exception:
        y_from = _date.today().year
    try:
        m_from = int(request.args.get('month_from') or 0) or 1
    except Exception:
        m_from = 1
    try:
        y_to = int(request.args.get('year_to') or 0) or _date.today().year
    except Exception:
        y_to = _date.today().year
    try:
        m_to = int(request.args.get('month_to') or 0) or _date.today().month
    except Exception:
        m_to = _date.today().month
    raw_codes = (request.args.get('employee_codes') or '').strip()
    selected_codes = [c.strip() for c in raw_codes.split(',') if c.strip()] if raw_codes else []

    # Models
    try:
        from models import Employee, EmployeeSalaryDefault, Salary, Payment
    except Exception:
        try:
            from app.models import Employee, EmployeeSalaryDefault, Salary, Payment
        except Exception:
            Employee = None; Salary = None; Payment = None; EmployeeSalaryDefault = None

    if not Employee or not Salary or not Payment:
        flash('Payroll models not available', 'danger')
        return redirect(url_for('main.employees'))

    def iter_months(y1, m1, y2, m2):
        y = int(y1); m = int(m1)
        end_key = (int(y2) * 100 + int(m2))
        while (y * 100 + m) <= end_key:
            yield y, m
            if m == 12:
                y += 1; m = 1
            else:
                m += 1

    # Resolve employees
    emp_q = Employee.query
    if selected_codes:
        try:
            emp_q = emp_q.filter(Employee.employee_code.in_(selected_codes))
        except Exception:
            pass
    employees = emp_q.order_by(Employee.full_name.asc()).all()

    # Helper: defaults
    def get_defaults(emp_id):
        try:
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp_id).first()
            if d:
                return float(d.base_salary or 0.0), float(d.allowances or 0.0), float(d.deductions or 0.0)
        except Exception:
            pass
        return 0.0, 0.0, 0.0

    employees_ctx = []
    grand = {'basic': 0.0, 'allowances': 0.0, 'deductions': 0.0, 'prev_due': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0}
    for emp in employees:
        basic_sum = allow_sum = ded_sum = prev_sum = total_sum = paid_sum = 0.0
        months_rows = []
        unpaid_count = 0
        for (yy, mm) in iter_months(y_from, m_from, y_to, m_to):
            s = Salary.query.filter_by(employee_id=emp.id, year=int(yy), month=int(mm)).first()
            if not s:
                b, a, d = get_defaults(emp.id)
                prev = 0.0
                tot = float(b + a - d + prev)
                sal_id = None
            else:
                b = float(s.basic_salary or 0.0)
                a = float(s.allowances or 0.0)
                d = float(s.deductions or 0.0)
                prev = float(s.previous_salary_due or 0.0)
                tot = float(s.total_salary or (b + a - d + prev))
                sal_id = int(s.id)
            # Paid for this month
            if sal_id:
                paid = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                              .filter(Payment.invoice_type == 'salary', Payment.invoice_id == sal_id).scalar() or 0.0)
            else:
                paid = 0.0
            remaining = max(tot - paid, 0.0)
            status = 'paid' if remaining <= 0.01 and tot > 0 else ('partial' if paid > 0 else 'due')
            if status != 'paid':
                unpaid_count += 1
            months_rows.append({
                'year': yy, 'month': mm,
                'basic': b, 'allowances': a, 'deductions': d,
                'prev_due': prev, 'total': tot, 'paid': paid, 'remaining': remaining, 'status': status
            })
            basic_sum += b; allow_sum += a; ded_sum += d; prev_sum += prev; total_sum += tot; paid_sum += paid
        emp_row = {
            'name': getattr(emp, 'full_name', '') or getattr(emp, 'employee_code', ''),
            'unpaid_months': unpaid_count,
            'basic_total': basic_sum,
            'allowances_total': allow_sum,
            'deductions_total': ded_sum,
            'prev_due': prev_sum,
            'total': total_sum,
            'paid': paid_sum,
            'remaining': max(total_sum - paid_sum, 0.0),
            'months': months_rows,
        }
        employees_ctx.append(emp_row)
        grand['basic'] += basic_sum; grand['allowances'] += allow_sum; grand['deductions'] += ded_sum
        grand['prev_due'] += prev_sum; grand['total'] += total_sum; grand['paid'] += paid_sum
    grand['remaining'] = max(grand['total'] - grand['paid'], 0.0)

    return render_template('payroll_report.html',
                           employees=employees_ctx,
                           grand=grand,
                           mode=('all' if len(employees_ctx) != 1 else 'single'),
                           start_year=y_from, start_month=m_from,
                           end_year=y_to, end_month=m_to,
                           selected_codes=(','.join(selected_codes) if selected_codes else ''),
                           auto_print=True,
                           close_after_print=False)


@main.route('/reports/print/payroll/selected', methods=['POST'], endpoint='print_selected')
@login_required
def print_selected():
    # Accept codes (employee_code) from text field, split by comma
    raw = (request.form.get('employee_ids') or '').strip()
    y_from = request.form.get('year_from') or request.args.get('year_from') or ''
    m_from = request.form.get('month_from') or request.args.get('month_from') or ''
    y_to = request.form.get('year_to') or request.args.get('year_to') or ''
    m_to = request.form.get('month_to') or request.args.get('month_to') or ''
    qs = {
        'year_from': y_from or '',
        'month_from': m_from or '',
        'year_to': y_to or '',
        'month_to': m_to or '',
    }
    if raw:
        qs['employee_codes'] = ','.join([c.strip() for c in raw.split(',') if c.strip()])
    # Redirect to GET printer with params to avoid resubmission issues
    return redirect(url_for('main.print_payroll', **qs))
