import json
import os
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import IntegrityError

from app import db, csrf
ext_db = None
from app.models import User, AppKV
from models import MenuCategory, MenuItem, SalesInvoice, SalesInvoiceItem, Customer, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Settings, Meal, MealIngredient, RawMaterial, Supplier, Employee, Salary, Payment, EmployeeSalaryDefault
from forms import SalesInvoiceForm, EmployeeForm, ExpenseInvoiceForm, PurchaseInvoiceForm, MealForm, RawMaterialForm

main = Blueprint('main', __name__)


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
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    meals = Meal.query.filter_by(active=True).all()
    return render_template('inventory.html', raw_materials=raw_materials, meals=meals)

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
            pm = (request.form.get('payment_method') or 'cash').strip().lower()
            inv = ExpenseInvoice(
                invoice_number=f"INV-EXP-{datetime.utcnow().year}-{(ExpenseInvoice.query.count()+1):04d}",
                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                payment_method=pm,
                user_id=getattr(current_user, 'id', 1)
            )
            # Payment status from form (paid / partial / unpaid)
            inv.status = (request.form.get('status') or inv.status or 'paid').strip().lower()
            if inv.status not in ('paid','partial','unpaid'):
                inv.status = 'paid'
            # Collect items
            idx = 0
            total_before = 0.0
            total_tax = 0.0
            total_disc = 0.0
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
                    q = float(qty or 0)
                    p = float(price or 0)
                    t = float(tax or 0)
                    d = float(disc or 0)
                except Exception:
                    q = p = t = d = 0.0
                before = q * p
                line_total = max(0.0, before + t - d)
                total_before += before
                total_tax += max(0.0, t)
                total_disc += max(0.0, d)
                inv.items.append(ExpenseInvoiceItem(
                    description=desc or 'Expense Item',
                    quantity=q,
                    price_before_tax=p,
                    tax=t,
                    discount=d,
                    total_price=line_total
                ))
                idx += 1
            inv.total_before_tax = total_before
            inv.tax_amount = total_tax
            inv.discount_amount = total_disc
            inv.total_after_tax_discount = max(0.0, total_before + total_tax - total_disc)
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
                        invoice_type='expense',
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
                            invoice_type='expense',
                            amount_paid=amt,
                            payment_method=(pm or 'CASH').upper()
                        ))
                        db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
            flash('Expense saved', 'success')
        except Exception as ex:
            if ext_db is not None:
                ext_db.session.rollback()
            else:
                db.session.rollback()
            flash(f'Could not save expense: {ex}', 'danger')
        return redirect(url_for('main.expenses'))
    # Show recent invoices if possible; otherwise empty list
    try:
        invoices = ExpenseInvoice.query.order_by(ExpenseInvoice.id.desc()).limit(10).all()
    except Exception:
        invoices = []
    return render_template('expenses.html', form=form, invoices=invoices)

@main.route('/invoices', endpoint='invoices')
@login_required
def invoices():
    t = (request.args.get('type') or 'sales').strip().lower()
    if t not in ('sales','purchases','expenses','all'):
        t = 'sales'
    return render_template('invoices.html', current_type=t)


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
        emps = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        emps = []
    return render_template('employees.html', form=form, employees=emps)


@main.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'], endpoint='edit_employee')
@login_required
def edit_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
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
            allow = float(request.form.get('default_allowances') or 0)
            ded = float(request.form.get('default_deductions') or 0)
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
    return render_template('employee_edit.html', employee=emp)


@main.route('/employees/<int:eid>/delete', methods=['POST'], endpoint='employee_delete')
@login_required
def employee_delete(eid):
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
            emp_id = request.form.get('employee_id', type=int)
            month_str = (request.form.get('month') or request.form.get('pay_month') or datetime.utcnow().strftime('%Y-%m')).strip()
            y, m = month_str.split('-')
            year = int(y); month = int(m)
            amount = float(request.form.get('paid_amount') or 0)
            method = (request.form.get('payment_method') or 'cash').strip().lower()

            # Ensure salary exists for this period
            sal = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
            if not sal:
                base = allow = ded = prev = 0.0
                try:
                    from models import EmployeeSalaryDefault
                    d = EmployeeSalaryDefault.query.filter_by(employee_id=emp_id).first()
                    if d:
                        base = float(d.base_salary or 0)
                        allow = float(d.allowances or 0)
                        ded = float(d.deductions or 0)
                except Exception:
                    pass
                total = max(0.0, base + allow - ded + prev)
                sal = Salary(employee_id=emp_id, year=year, month=month,
                             basic_salary=base, allowances=allow, deductions=ded,
                             previous_salary_due=prev, total_salary=total, status='due')
                db.session.add(sal)
                db.session.flush()

            # Record payment if provided
            if amount > 0:
                pay = Payment(invoice_id=sal.id, invoice_type='salary', amount_paid=amount, payment_method=method)
                db.session.add(pay)

            # Update status by paid sum
            paid_sum = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).\
                filter(Payment.invoice_type == 'salary', Payment.invoice_id == sal.id).scalar() or 0
            paid_sum = float(paid_sum or 0)
            total_due = float(sal.total_salary or 0)
            if paid_sum >= total_due and total_due > 0:
                sal.status = 'paid'
            elif paid_sum > 0:
                sal.status = 'partial'
            else:
                sal.status = 'due'

            db.session.commit()
            flash('Salary payment recorded', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving salary/payment: {e}', 'danger')
        return redirect(url_for('main.salaries_pay', month=month_str))

    # GET
    try:
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        employees = []
    selected_month = request.args.get('month') or datetime.utcnow().strftime('%Y-%m')

    # Optional: list current month salaries
    try:
        y, m = selected_month.split('-'); year = int(y); month = int(m)
        current_salaries = Salary.query.filter_by(year=year, month=month).all()
    except Exception:
        current_salaries = []
    return render_template('salaries_pay.html', employees=employees, month=selected_month, salaries=current_salaries)


@main.route('/salaries/statements', methods=['GET'], endpoint='salaries_statements')
@login_required
def salaries_statements():
    # Accept either ?month=YYYY-MM or ?year=&month=
    month_param = (request.args.get('month') or '').strip()
    if '-' in month_param:
        try:
            y, m = month_param.split('-'); year = int(y); month = int(m)
        except Exception:
            year = datetime.utcnow().year; month = datetime.utcnow().month
    else:
        year = request.args.get('year', type=int) or datetime.utcnow().year
        month = request.args.get('month', type=int) or datetime.utcnow().month
    rows = []
    totals = {'basic': 0.0, 'allow': 0.0, 'ded': 0.0, 'prev': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0}

    # We'll build statements from each employee.hire_date up to the selected year/month (inclusive)
    try:
        # build end date
        end_year = int(year)
        end_month = int(month)

        employees = Employee.query.order_by(Employee.full_name).all()

        def month_iter(start_y, start_m, end_y, end_m):
            y, m = start_y, start_m
            while (y < end_y) or (y == end_y and m <= end_m):
                yield y, m
                m += 1
                if m > 12:
                    m = 1; y += 1

        for emp in employees:
            # skip employees without hire_date
            if not emp.hire_date:
                continue
            start_y = emp.hire_date.year
            start_m = emp.hire_date.month
            # if hire date is after selected end, skip
            if (start_y > end_year) or (start_y == end_year and start_m > end_month):
                continue

            for y, m in month_iter(start_y, start_m, end_year, end_month):
                # prefer an explicit Salary row for the period
                s = Salary.query.filter_by(employee_id=emp.id, year=y, month=m).first()
                if s:
                    basic = float(s.basic_salary or 0)
                    allow = float(s.allowances or 0)
                    ded = float(s.deductions or 0)
                    prev = float(s.previous_salary_due or 0)
                    total = max(0.0, basic + allow - ded + prev)
                    paid = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).\
                        filter(Payment.invoice_type == 'salary', Payment.invoice_id == s.id).scalar() or 0
                    paid = float(paid or 0)
                    remaining = max(0.0, total - paid)
                    status = s.status or ('paid' if remaining <= 0 else 'due')
                else:
                    # fallback to EmployeeSalaryDefault
                    usd = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first()
                    basic = float(usd.base_salary or 0) if usd else 0.0
                    allow = float(usd.allowances or 0) if usd else 0.0
                    ded = float(usd.deductions or 0) if usd else 0.0
                    prev = 0.0
                    total = max(0.0, basic + allow - ded + prev)
                    # no salary row -> cannot link payments reliably; assume none
                    paid = 0.0
                    remaining = total
                    status = 'due' if remaining > 0 else 'paid'

                rows.append({
                    'period': f"{y:04d}-{m:02d}",
                    'employee_name': emp.full_name,
                    'basic': basic,
                    'allow': allow,
                    'ded': ded,
                    'prev': prev,
                    'total': total,
                    'paid': paid,
                    'remaining': remaining,
                    'status': status
                })

                totals['basic'] += basic; totals['allow'] += allow; totals['ded'] += ded
                totals['prev'] += prev; totals['total'] += total; totals['paid'] += paid; totals['remaining'] += remaining
    except Exception:
        pass

    return render_template('salaries_statements.html', year=year, month=month, rows=rows, totals=totals)



@main.route('/reports/print/salaries', methods=['GET'], endpoint='reports_print_salaries')
@login_required
def reports_print_salaries():
    # Accept ?month=YYYY-MM or ?year=&month=
    month_param = (request.args.get('month') or '').strip()
    if '-' in month_param:
        try:
            y, m = month_param.split('-'); year = int(y); month = int(m)
        except Exception:
            year = datetime.utcnow().year; month = datetime.utcnow().month
    else:
        year = request.args.get('year', type=int) or datetime.utcnow().year
        month = request.args.get('month', type=int) or datetime.utcnow().month

    # Build current month rows (reuse logic from salaries_statements)
    rows = []
    totals = {'basic': 0.0, 'allow': 0.0, 'ded': 0.0, 'prev': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0}
    try:
        sal_list = Salary.query.filter_by(year=year, month=month).all()
        for s in sal_list:
            paid = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)). \
                filter(Payment.invoice_type == 'salary', Payment.invoice_id == s.id).scalar() or 0
            paid = float(paid or 0)
            basic = float(s.basic_salary or 0)
            allow = float(s.allowances or 0)
            ded = float(s.deductions or 0)
            prev = float(s.previous_salary_due or 0)
            total = max(0.0, basic + allow - ded + prev)
            remaining = max(0.0, total - paid)
            emp = db.session.get(Employee, s.employee_id)
            rows.append({
                'employee_name': (emp.full_name if emp else f"#{s.employee_id}"),
                'basic': basic, 'allow': allow, 'ded': ded, 'prev': prev,
                'total': total, 'paid': paid, 'remaining': remaining,
                'status': s.status or 'due'
            })
            totals['basic'] += basic; totals['allow'] += allow; totals['ded'] += ded
            totals['prev'] += prev; totals['total'] += total; totals['paid'] += paid; totals['remaining'] += remaining
    except Exception:
        pass

    # Build previous months breakdown from hire_date up to previous month
    prev_rows = []
    prev_totals = {'due': 0.0, 'paid': 0.0}
    try:
        # Helper to iterate months
        def month_iter(y0, m0, y1, m1):
            y, m = y0, m0
            count = 0
            while (y < y1) or (y == y1 and m <= m1):
                yield y, m
                m += 1
                if m > 12:
                    m = 1; y += 1
                count += 1
                if count > 240:  # safety guard: max 20 years
                    break
        # Compute previous month reference
        from calendar import monthrange
        cur_y, cur_m = year, month
        # previous month
        if cur_m == 1:
            prev_y, prev_m = cur_y - 1, 12
        else:
            prev_y, prev_m = cur_y, cur_m - 1
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
        # Preload defaults map
        try:
            from models import EmployeeSalaryDefault
            defaults = {d.employee_id: d for d in EmployeeSalaryDefault.query.all()}
        except Exception:
            defaults = {}
        for emp in employees:
            if not emp.hire_date:
                continue
            start_y = emp.hire_date.year
            start_m = emp.hire_date.month
            # Iterate months from hire to prev month
            for y, m in month_iter(start_y, start_m, prev_y, prev_m):
                s = Salary.query.filter_by(employee_id=emp.id, year=y, month=m).first()
                if s:
                    due = float(s.total_salary or 0.0)
                    paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)). \
                        filter(Payment.invoice_type == 'salary', Payment.invoice_id == s.id).scalar() or 0.0)
                else:
                    d = defaults.get(emp.id)
                    if not d:
                        continue  # no info to compute
                    base = float(d.base_salary or 0.0)
                    allow = float(d.allowances or 0.0)
                    ded = float(d.deductions or 0.0)
                    due = max(0.0, base + allow - ded)
                    paid = 0.0
                # Skip empty rows
                if (due or paid):
                    prev_rows.append({
                        'month': f"{y:04d}-{m:02d}",
                        'employee_name': emp.full_name,
                        'due': due,
                        'paid': float(paid or 0.0)
                    })
                    prev_totals['due'] += due
                    prev_totals['paid'] += float(paid or 0.0)
    except Exception:
        pass

    # Settings/header
    try:
        settings = Settings.query.first()
        company_name = settings.company_name or 'Company'
        logo_url = settings.logo_url or ''
    except Exception:
        company_name = 'Company'; logo_url = ''

    title = f"Payroll Statement — {year:04d}-{month:02d}"
    meta = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    return render_template('print/payroll.html', title=title, meta=meta,
                           company_name=company_name, logo_url=logo_url,
                           rows=rows, totals=totals,
                           prev_rows=prev_rows, prev_totals=prev_totals)



@main.route('/payments', endpoint='payments')
@login_required
def payments():
    # Build unified list of purchase and expense invoices with paid totals
    status_f = (request.args.get('status') or '').strip().lower()
    type_f = (request.args.get('type') or '').strip().lower()
    invoices = []
    PAYMENT_METHODS = ['CASH','CARD','BANK','ONLINE','MADA','VISA']

    try:
        # Purchases
        q = PurchaseInvoice.query
        for inv in q.order_by(PurchaseInvoice.created_at.desc()).limit(1000).all():
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                         .filter(Payment.invoice_id == inv.id, Payment.invoice_type == 'purchase').scalar() or 0.0)
            invoices.append({
                'id': inv.id,
                'invoice_number': getattr(inv, 'invoice_number', None) or inv.id,
                'type': 'purchase',
                'party': inv.supplier_name or 'Supplier',
                'total': total,
                'paid': paid,
                'status': (inv.status or 'unpaid'),
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
            invoices.append({
                'id': inv.id,
                'invoice_number': getattr(inv, 'invoice_number', None) or inv.id,
                'type': 'expense',
                'party': 'Expense',
                'total': total,
                'paid': paid,
                'status': (inv.status or 'paid'),
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
    # Try to load grouped layout from saved sections; otherwise simple 1..20
    settings = kv_get('table_settings', {}) or {}
    default_count = 20
    def _safe_int(value, fallback):
        try:
            v = value if value is not None else fallback
            return int(v)
        except Exception:
            return int(fallback)
    if branch_code == 'china_town':
        count = _safe_int((settings.get('china') or {}).get('count'), default_count)
    elif branch_code == 'place_india':
        count = _safe_int((settings.get('india') or {}).get('count'), default_count)
    else:
        count = default_count
    # Try to render using saved layout (sections/rows) if available
    layout = kv_get(f'layout:{branch_code}', {}) or {}
    grouped_tables = None
    if layout and isinstance(layout.get('sections'), list):
        # Build data structure the template understands
        sections = layout.get('sections') or []
        grouped = []
        for sec in sections:
            rows = []
            for row in (sec.get('rows') or []):
                row_out = []
                for t in (row or []):
                    try:
                        tn = int(str(t).strip())
                    except Exception:
                        continue
                    if tn < 1 or tn > 1000:
                        continue
                    row_out.append({
                        'number': tn,
                        'status': 'available'
                    })
                if row_out:
                    rows.append(row_out)
            grouped.append({'section': (sec.get('name') or '').strip() or 'Section', 'rows': rows})
        grouped_tables = grouped

    tables = [{'number': i, 'status': 'available'} for i in range(1, count+1)]
    return render_template('sales_tables.html', branch_code=branch_code, branch_label=branch_label, tables=tables, grouped_tables=grouped_tables)


@main.route('/table-manager/<branch_code>', endpoint='table_manager')
@login_required
def table_manager(branch_code):
    if not user_can('sales','view', branch_code):
        flash('لا تملك صلاحية الوصول لفرع المبيعات هذا', 'warning')
        return redirect(url_for('main.sales'))
    branch_label = BRANCH_LABELS.get(branch_code, branch_code)
    return render_template('table_manager.html', branch_code=branch_code, branch_label=branch_label)

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
    key = f'sections:{branch_code}'
    if not user_can('sales','view', branch_code):
        return jsonify({'success': False, 'error': 'forbidden'}), 403

    # Lazy import to avoid circulars
    try:
        from models import TableSection, TableSectionAssignment
    except Exception:
        TableSection = None
        TableSectionAssignment = None

    if request.method == 'GET':
        # Prefer DB if available; fallback to KV store
        try:
            if TableSection is not None:
                sections_q = TableSection.query.filter_by(branch_code=branch_code).order_by(TableSection.sort_order, TableSection.id).all()
                assigns_q = TableSectionAssignment.query.filter_by(branch_code=branch_code).all()
                if sections_q:
                    return jsonify({
                        'success': True,
                        'sections': [
                            {'id': s.id, 'name': s.name, 'sort_order': s.sort_order}
                            for s in sections_q
                        ],
                        'assignments': [
                            {'table_number': a.table_number, 'section_id': a.section_id}
                            for a in assigns_q
                        ]
                    })
        except Exception:
            db.session.rollback()
            # continue to KV fallback
        data = kv_get(key, {}) or {}
        return jsonify({'success': True, 'sections': data.get('sections') or [], 'assignments': data.get('assignments') or []})

    # POST: upsert both KV and DB for persistence
    try:
        payload = request.get_json(force=True) or {}
        sections = payload.get('sections') or []
        assignments = payload.get('assignments') or []

        # Normalize IDs for KV
        for idx, s in enumerate(sections, start=1):
            if not s.get('id'):
                s['id'] = idx

        # Save to KV for quick reads
        kv_set(key, {'sections': sections, 'assignments': assignments})

        # Save to DB (if models are available)
        if TableSection is not None:
            kept_ids = []
            # Upsert sections
            for idx, sd in enumerate(sections):
                sid = sd.get('id')
                name = (sd.get('name') or '').strip()
                sort_order = int(sd.get('sort_order') or idx)
                if sid:
                    sec = TableSection.query.filter_by(id=sid, branch_code=branch_code).first()
                    if sec:
                        sec.name = name
                        sec.sort_order = sort_order
                        kept_ids.append(sec.id)
                    else:
                        sec = TableSection(branch_code=branch_code, name=name, sort_order=sort_order)
                        db.session.add(sec)
                        db.session.flush()
                        kept_ids.append(sec.id)
                else:
                    existing = TableSection.query.filter_by(branch_code=branch_code, name=name).first()
                    if existing:
                        existing.sort_order = sort_order
                        kept_ids.append(existing.id)
                    else:
                        sec = TableSection(branch_code=branch_code, name=name, sort_order=sort_order)
                        db.session.add(sec)
                        db.session.flush()
                        kept_ids.append(sec.id)

            # Remove deleted sections
            if kept_ids:
                TableSection.query.filter(
                    TableSection.branch_code == branch_code,
                    ~TableSection.id.in_(kept_ids)
                ).delete(synchronize_session=False)

            # Replace assignments
            TableSectionAssignment.query.filter_by(branch_code=branch_code).delete()
            for ad in (assignments or []):
                table_number = str(ad.get('table_number') or '').strip()
                section_id = ad.get('section_id')
                if table_number and section_id:
                    db.session.add(TableSectionAssignment(
                        branch_code=branch_code,
                        table_number=table_number,
                        section_id=section_id
                    ))

            db.session.commit()

        return jsonify({'success': True})
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


@main.route('/api/table-layout/<branch_code>', methods=['GET', 'POST'], endpoint='api_table_layout')
@login_required
def api_table_layout(branch_code):
    """Persist arbitrary layout (sections -> rows -> tables) without hard DB migrations.
    Stored in AppKV under layout:<branch> and used by sales_tables() to render.
    """
    if not user_can('sales','view', branch_code):
        return jsonify({'success': False, 'error': 'forbidden'}), 403
    key = f'layout:{branch_code}'
    if request.method == 'GET':
        data = kv_get(key, {}) or {}
        return jsonify({'success': True, 'layout': data})
    try:
        payload = request.get_json(force=True) or {}
        sections = payload.get('sections')
        if not isinstance(sections, list):
            return jsonify({'success': False, 'error': 'invalid payload'}), 400
        # Normalize strings for tables and drop empties
        norm_sections = []
        for sec in sections:
            name = (sec.get('name') or '').strip()
            rows = []
            for row in (sec.get('rows') or []):
                r = [str(t).strip() for t in (row or []) if str(t or '').strip()]
                if r:
                    rows.append(r)
            norm_sections.append({'name': name or 'Section', 'rows': rows})
        kv_set(key, {'sections': norm_sections})
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

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
    invoice_number = f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
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
        # Update status
        if inv:
            if paid >= total and total > 0:
                inv.status = 'paid'
            elif paid > 0:
                inv.status = 'partial'
            else:
                inv.status = inv.status or ('unpaid' if invoice_type=='purchase' else 'paid')
        db.session.commit()
        return jsonify({'status': 'success', 'invoice_id': inv_id, 'amount': amt, 'paid': paid, 'total': total, 'new_status': getattr(inv, 'status', None)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400



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
    }
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    branch_name = BRANCH_LABELS.get(branch, branch)
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    order_no = f"ORD-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    return render_template('print/receipt.html', inv=inv_ctx, items=items_ctx,
                           settings=s, branch_name=branch_name, date_time=dt_str,
                           display_invoice_number=order_no,
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
        all_suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    except Exception:
        all_suppliers = []
    return render_template('suppliers.html', suppliers=all_suppliers)

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
PERM_SCREENS = ['dashboard','sales','purchases','inventory','expenses','salaries','financials','vat','reports','invoices','payments','customers','menu','settings','suppliers','table_settings','users','sample_data']

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
            for fld in ['company_name','tax_number','phone','address','email','currency','place_india_label','china_town_label','logo_url','default_theme','printer_type','footer_message','receipt_footer_text']:
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
                # Logo file
                logo_file = request.files.get('logo_file')
                if logo_file and getattr(logo_file, 'filename', ''):
                    ext = os.path.splitext(logo_file.filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.svg', '.gif']:
                        fname = f"logo_{int(datetime.utcnow().timestamp())}{ext}"
                        fpath = os.path.join(upload_dir, fname)
                        logo_file.save(fpath)
                        s.logo_url = f"{path_prefix}{fname}"
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
    return render_template('table_settings.html')


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
    # Read params and compute quarter date range
    try:
        y = request.args.get('year', type=int) or datetime.utcnow().year
        q = request.args.get('quarter', type=int) or 1
        q = q if q in (1, 2, 3, 4) else 1
        start_month = {1: 1, 2: 4, 3: 7, 4: 10}[q]
        end_month = {1: 3, 2: 6, 3: 9, 4: 12}[q]
        start_date = date(y, start_month, 1)
        next_month_first = date(y + (1 if end_month == 12 else 0), 1 if end_month == 12 else end_month + 1, 1)
        end_date = next_month_first - timedelta(days=1)
    except Exception:
        y = datetime.utcnow().year
        q = 1
        start_date = date(y, 1, 1)
        end_date = date(y, 3, 31)

    # Aggregate sales by branch (support both model variants)
    sales_place_india = 0.0
    sales_china_town = 0.0
    try:
        if hasattr(SalesInvoice, 'total_amount') and hasattr(SalesInvoice, 'created_at') and hasattr(SalesInvoice, 'branch_code'):
            sales_place_india = db.session.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)) \
                .filter(SalesInvoice.branch_code == 'place_india') \
                .filter(SalesInvoice.created_at.between(start_date, end_date)).scalar() or 0.0
            sales_china_town = db.session.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)) \
                .filter(SalesInvoice.branch_code == 'china_town') \
                .filter(SalesInvoice.created_at.between(start_date, end_date)).scalar() or 0.0
        elif hasattr(SalesInvoice, 'total_before_tax') and hasattr(SalesInvoice, 'date') and hasattr(SalesInvoice, 'branch'):
            sales_place_india = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
                .filter(SalesInvoice.branch == 'place_india') \
                .filter(SalesInvoice.date.between(start_date, end_date)).scalar() or 0.0
            sales_china_town = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
                .filter(SalesInvoice.branch == 'china_town') \
                .filter(SalesInvoice.date.between(start_date, end_date)).scalar() or 0.0
    except Exception:
        sales_place_india = sales_china_town = 0.0

    # Branch filter
    branch = (request.args.get('branch') or 'all').strip()
    if branch == 'place_india':
        sales_total = float(sales_place_india or 0.0)
    elif branch == 'china_town':
        sales_total = float(sales_china_town or 0.0)
    else:
        sales_total = float(sales_place_india or 0.0) + float(sales_china_town or 0.0)

    # Aggregate purchases (sum of total_price of items in period)
    purchases_total = 0.0
    try:
        q_p = db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0)) \
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id) \
            .filter(PurchaseInvoice.date.between(start_date, end_date))
        purchases_total = float(q_p.scalar() or 0.0)
    except Exception:
        purchases_total = 0.0

    # Aggregate expenses (sum invoice totals in period)
    expenses_total = 0.0
    try:
        q_e = db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_after_tax_discount), 0)) \
            .filter(ExpenseInvoice.date.between(start_date, end_date))
        expenses_total = float(q_e.scalar() or 0.0)
    except Exception:
        expenses_total = 0.0

    # VAT rate from Settings
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    vat_rate = float(getattr(s, 'vat_rate', 15) or 15) / 100.0

    output_vat = float(sales_total or 0.0) * vat_rate
    input_vat = float((purchases_total or 0.0) + (expenses_total or 0.0)) * vat_rate
    net_vat = output_vat - input_vat

    data = {
        'year': y,
        'quarter': q,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'branch': branch,
        'sales_place_india': float(sales_place_india or 0.0),
        'sales_china_town': float(sales_china_town or 0.0),
        'sales_total': float(sales_total or 0.0),
        'purchases_total': float(purchases_total or 0.0),
        'expenses_total': float(expenses_total or 0.0),
        'output_vat': float(output_vat or 0.0),
        'input_vat': float(input_vat or 0.0),
        'net_vat': float(net_vat or 0.0),
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

    # Render unified print report
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
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=data, totals=totals, totals_columns=totals_columns,
                           totals_colspan=totals_colspan, payment_totals=payment_totals)


@main.route('/reports/print/all-invoices/purchases', methods=['GET'], endpoint='reports_print_all_invoices_purchases')
@login_required
def reports_print_all_invoices_purchases():
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = request.args.get('start_date') or ''
    end_date = request.args.get('end_date') or ''
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
        'branch': 'all',
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    columns = ['Date','Invoice No.','Item','Qty','Amount','Discount','VAT','Total','Payment']
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=['Amount','Discount','VAT','Total'],
                           totals_colspan=4, payment_totals=payment_totals)


@main.route('/reports/print/all-invoices/expenses', methods=['GET'], endpoint='reports_print_all_invoices_expenses')
@login_required
def reports_print_all_invoices_expenses():
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = request.args.get('start_date') or ''
    end_date = request.args.get('end_date') or ''
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
        'branch': 'all',
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    columns = ['Date','Expense No.','Description','Qty','Amount','Tax','Discount','Line Total','Payment']
    totals_columns = ['Amount','Tax','Discount','Line Total']
    totals_colspan = len(columns) - len(totals_columns)
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=totals_columns,
                           totals_colspan=totals_colspan, payment_totals=payment_totals)
