import json
import os
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func

from app import db, csrf
from app.models import User, AppKV, MenuCategory, MenuItem, SalesInvoice, SalesInvoiceItem, Customer
from models import PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Settings, Meal
from forms import SalesInvoiceForm, EmployeeForm, ExpenseInvoiceForm

main = Blueprint('main', __name__)

# --- Simple helpers / constants ---
BRANCH_LABELS = {
    'place_india': 'Place India',
    'china_town': 'China Town',
}

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

def ensure_tables():
    try:
        db.create_all()
    except Exception:
        pass


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
    return render_template('sales_branches.html', branches=branches)

@main.route('/purchases', endpoint='purchases')
@login_required
def purchases():
    return render_template('purchases.html')

@main.route('/raw-materials', endpoint='raw_materials')
@login_required
def raw_materials():
    return render_template('raw_materials.html')

@main.route('/meals', endpoint='meals')
@login_required
def meals():
    return render_template('meals.html')

# -------- Meals import (Excel/CSV): Name, Name (Arabic), Selling Price --------
@main.route('/meals/import', methods=['POST'], endpoint='meals_import')
@login_required
def meals_import():
    import os, csv
    from io import TextIOWrapper
    file = request.files.get('file')
    if not file or not file.filename:
        flash('لم يتم اختيار ملف', 'warning')
        return redirect(url_for('main.meals'))

    ext = os.path.splitext(file.filename)[1].lower()

    def ensure_category(name='Meals'):
        cat = MenuCategory.query.filter_by(name=name).first()
        if not cat:
            cat = MenuCategory(name=name, sort_order=0)
            db.session.add(cat)
            db.session.commit()
        return cat

    def upsert_item(name_en, name_ar, price_val):
        # دمج الاسم العربي للعرض فقط
        display_name = (name_en or '').strip()
        if name_ar:
            display_name = f"{display_name} / {str(name_ar).strip()}" if display_name else str(name_ar).strip()
        try:
            price = float(str(price_val).replace(',', '').strip()) if price_val is not None else 0.0
        except Exception:
            price = 0.0
        cat = ensure_category('Meals')
        item = MenuItem(name=display_name or 'Unnamed', price=price, category_id=cat.id)
        db.session.add(item)
        return item

    imported, errors = 0, 0

    if ext == '.csv':
        try:
            stream = TextIOWrapper(file.stream, encoding='utf-8')
            reader = csv.DictReader(stream)
            # تطبيع أسماء الأعمدة
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
                    upsert_item(name, name_ar, price)
                    imported += 1
                except Exception:
                    errors += 1
            db.session.commit()
            flash(f'تم استيراد {imported} عنصر بنجاح' + (f'، أخطاء: {errors}' if errors else ''), 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'فشل استيراد CSV: {e}', 'danger')
        return redirect(url_for('main.meals'))

    elif ext in ('.xlsx', '.xls'):
        try:
            try:
                import openpyxl  # يتطلب تثبيت openpyxl
            except Exception:
                flash('لا يمكن قراءة ملفات Excel بدون تثبيت openpyxl. يمكنك رفع CSV بدلاً من ذلك أو اسمح لي بتثبيت openpyxl.', 'warning')
                return redirect(url_for('main.meals'))
            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active
            # اقرأ العناوين من الصف الأول
            headers = []
            for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True)):
                headers.append((cell or '').strip().lower())
            # اصنع خريطة اسم -> فهرس
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
                    upsert_item(name, name_ar, price)
                    imported += 1
                except Exception:
                    errors += 1
            db.session.commit()
            flash(f'تم استيراد {imported} عنصر من Excel' + (f'، أخطاء: {errors}' if errors else ''), 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'فشل استيراد Excel: {e}', 'danger')
        return redirect(url_for('main.meals'))

    else:
        flash('صيغة الملف غير مدعومة. الرجاء رفع ملف CSV أو Excel (.xlsx/.xls).', 'warning')
        return redirect(url_for('main.meals'))

@main.route('/inventory', endpoint='inventory')
@login_required
def inventory():
    return render_template('inventory.html')

@main.route('/expenses', methods=['GET', 'POST'], endpoint='expenses')
@login_required
def expenses():
    form = ExpenseInvoiceForm()
    try:
        form.date.data = datetime.utcnow().date()
    except Exception:
        pass
    if request.method == 'POST':
        # Best-effort create using external ExpenseInvoice model if available
        try:
            e = ExpenseInvoice()
            # Populate common fields if present
            for fld, getter in [
                ('date', lambda: request.form.get('date') or request.json.get('date') if request.is_json else request.form.get('date')),
                ('description', lambda: request.form.get('description') or request.json.get('description') if request.is_json else request.form.get('description')),
                ('amount', lambda: request.form.get('amount') or request.json.get('amount') if request.is_json else request.form.get('amount')),
                ('payment_method', lambda: request.form.get('payment_method') or request.json.get('payment_method') if request.is_json else request.form.get('payment_method')),
                ('notes', lambda: request.form.get('notes') or request.json.get('notes') if request.is_json else request.form.get('notes')),
            ]:
                if hasattr(e, fld):
                    val = getter() if getter else None
                    setattr(e, fld, val)
            db.session.add(e)
            db.session.commit()
            flash('Expense saved', 'success')
        except Exception as ex:
            db.session.rollback()
            flash('Could not save expense (placeholder handler)', 'warning')
        return redirect(url_for('main.expenses'))
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
                    SalesInvoiceItem.query.filter_by(invoice_id=inv.id).delete()
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
                    PurchaseInvoiceItem.query.filter_by(invoice_id=inv.id).delete()
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
                    ExpenseInvoiceItem.query.filter_by(invoice_id=inv.id).delete()
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

@main.route('/employees', endpoint='employees')
@login_required
def employees():
    form = EmployeeForm()
    employees = []  # Placeholder list until Employee model is integrated
    return render_template('employees.html', form=form, employees=employees)

@main.route('/payments', endpoint='payments')
@login_required
def payments():
    return render_template('payments.html')

@main.route('/reports', endpoint='reports')
@login_required
def reports():
    return render_template('reports.html')

# ---------- POS/Tables: basic navigation ----------
@main.route('/sales/<branch_code>/tables', endpoint='sales_tables')
@login_required
def sales_tables(branch_code):
    branch_label = BRANCH_LABELS.get(branch_code, branch_code)
    # Try to load grouped layout from saved sections; otherwise simple 1..20
    settings = kv_get('table_settings', {}) or {}
    default_count = 20
    if branch_code == 'china_town':
        count = int((settings.get('china') or {}).get('count', default_count))
    elif branch_code == 'place_india':
        count = int((settings.get('india') or {}).get('count', default_count))
    else:
        count = default_count
    tables = [{'number': i, 'status': 'available'} for i in range(1, count+1)]
    return render_template('sales_tables.html', branch_code=branch_code, branch_label=branch_label, tables=tables, grouped_tables=None)

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
    return redirect(url_for('main.sales_tables', branch_code=branch_code))


@main.route('/pos/<branch_code>/table/<int:table_number>', endpoint='pos_table')
@login_required
def pos_table(branch_code, table_number):
    branch_label = BRANCH_LABELS.get(branch_code, branch_code)
    vat_rate = 15
    # Load any existing draft for this table
    draft = kv_get(f'draft:{branch_code}:{table_number}', {}) or {}
    draft_items = json.dumps(draft.get('items') or [])
    current_draft = type('Obj', (), {'id': draft.get('draft_id')}) if draft.get('draft_id') else None
    # Ensure DB tables exist and seed demo menu on first run
    ensure_tables(); seed_menu_if_empty()
    # Load categories from DB for UI and provide a name->id map
    cats = MenuCategory.query.order_by(MenuCategory.sort_order, MenuCategory.name).all()
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
    if request.method == 'GET':
        data = kv_get(key, {}) or {}
        return jsonify({'success': True, 'sections': data.get('sections') or [], 'assignments': data.get('assignments') or []})
    try:
        payload = request.get_json(force=True) or {}
        # Normalize and assign IDs to new sections if missing
        sections = payload.get('sections') or []
        # Generate simple incremental IDs based on position
        for idx, s in enumerate(sections, start=1):
            if not s.get('id'):
                s['id'] = idx
        store = {'sections': sections, 'assignments': payload.get('assignments') or []}
        kv_set(key, store)
        return jsonify({'success': True, 'sections': sections})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@main.route('/api/tables/<branch_code>', methods=['GET'], endpoint='api_tables_status')
@login_required
def api_tables_status(branch_code):
    # Read drafts to mark occupied tables
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
    # Prefer DB; fallback to KV/demo
    ensure_tables(); seed_menu_if_empty()
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
    ensure_tables()
    draft = kv_get(f'draft:{branch}:{table}', {}) or {}
    items = draft.get('items') or []
    total_amount = 0.0
    for it in items:
        qty = float(it.get('qty') or it.get('quantity') or 1)
        price = float(it.get('price') or it.get('unit') or 0.0)
        if price <= 0 and it.get('meal_id'):
            m = MenuItem.query.get(int(it.get('meal_id')))
            if m: price = float(m.price)
        total_amount += qty * (price or 0.0)
    discount_pct = float(payload.get('discount_pct') or 0)
    tax_pct = float(payload.get('tax_pct') or 15)
    total_amount = total_amount * (1 + tax_pct/100.0) * (1 - discount_pct/100.0)
    payment_method = (payload.get('payment_method') or '').strip().upper()
    if payment_method not in ['CASH','CARD']:
        return jsonify({'success': False, 'error': 'اختر طريقة الدفع (CASH أو CARD)'}), 400
    invoice_number = f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    try:
        inv = SalesInvoice(
            invoice_number=invoice_number,
            branch_code=branch,
            table_number=int(table),
            customer_name=(payload.get('customer_name') or '').strip(),
            customer_phone=(payload.get('customer_phone') or '').strip(),
            payment_method=payment_method,
            discount_pct=discount_pct,
            tax_pct=tax_pct,
            total_amount=round(total_amount, 2),
        )
        db.session.add(inv)
        db.session.flush()
        for it in items:
            qty = float(it.get('qty') or it.get('quantity') or 1)
            price = float(it.get('price') or it.get('unit') or 0.0)
            if price <= 0 and it.get('meal_id'):
                m = MenuItem.query.get(int(it.get('meal_id')))
                if m: price = float(m.price)
            db.session.add(SalesInvoiceItem(
                invoice_id=inv.id,
                meal_id=(it.get('meal_id') or it.get('id')),
                name=(it.get('name') or ''),
                unit_price=price or 0.0,
                qty=qty,
            ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_amount, 2), 'print_url': url_for('main.print_receipt', invoice_number=invoice_number), 'branch_code': branch, 'table_number': int(table)})


@main.route('/api/sales/checkout', methods=['POST'], endpoint='api_sales_checkout')
@login_required
def api_sales_checkout():
    payload = request.get_json(force=True) or {}
    ensure_tables()
    branch = (payload.get('branch_code') or '').strip() or 'unknown'
    table = int(payload.get('table_number') or 0)
    items = payload.get('items') or []
    # get prices from DB when missing
    total_amount = 0.0
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
        total_amount += qty * (price or 0.0)
        resolved.append({'meal_id': it.get('meal_id'), 'name': name, 'price': price or 0.0, 'qty': qty})
    discount_pct = float(payload.get('discount_pct') or 0)
    tax_pct = float(payload.get('tax_pct') or 15)
    total_amount = total_amount * (1 + tax_pct/100.0) * (1 - discount_pct/100.0)
    payment_method = (payload.get('payment_method') or '').strip().upper()
    if payment_method not in ['CASH','CARD']:
        return jsonify({'success': False, 'error': '\u0627\u062e\u062a\u0631 \u0637\u0631\u064a\u0642\u0629 \u0627\u0644\u062f\u0641\u0639 (CASH \u0623\u0648 CARD)'}), 400
    invoice_number = f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    try:
        inv = SalesInvoice(
            invoice_number=invoice_number,
            branch_code=branch,
            table_number=table,
            customer_name=(payload.get('customer_name') or '').strip(),
            customer_phone=(payload.get('customer_phone') or '').strip(),
            payment_method=payment_method,
            discount_pct=discount_pct,
            tax_pct=tax_pct,
            total_amount=round(total_amount, 2),
        )
        db.session.add(inv)
        db.session.flush()
        for it in resolved:
            db.session.add(SalesInvoiceItem(
                invoice_id=inv.id,
                meal_id=it.get('meal_id'),
                name=it.get('name'),
                unit_price=float(it.get('price') or 0.0),
                qty=float(it.get('qty') or 1),
            ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_amount, 2), 'print_url': url_for('main.print_receipt', invoice_number=invoice_number), 'branch_code': branch, 'table_number': table})


@main.route('/api/invoice/confirm-print', methods=['POST'], endpoint='api_invoice_confirm_print')
@login_required
def api_invoice_confirm_print():
    # Mark invoice printed/paid and free the table by clearing draft
    try:
        payload = request.get_json(force=True) or {}
        branch = (payload.get('branch_code') or '').strip()
        table = int(payload.get('table_number') or 0)
        if branch and table:
            kv_set(f'draft:{branch}:{table}', {'draft_id': f'{branch}:{table}', 'items': []})
        return jsonify({'success': True})
    except Exception as e:
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
    invoice_id = request.form.get('invoice_id') or (request.get_json(silent=True) or {}).get('invoice_id')
    amount = request.form.get('amount') or (request.get_json(silent=True) or {}).get('amount')
    payment_method = request.form.get('payment_method') or (request.get_json(silent=True) or {}).get('payment_method')
    # For now just return success; integrate with real ledger later
    return jsonify({'status': 'success', 'invoice_id': invoice_id, 'amount': amount, 'payment_method': payment_method})



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
    # compute totals
    subtotal = 0.0
    items_ctx = []
    for it in items:
        line = float(it.unit_price or 0) * float(it.qty or 0)
        subtotal += line
        items_ctx.append({
            'product_name': it.name or '',
            'quantity': float(it.qty or 0),
            'total_price': line,
        })
    tax_pct = float(inv.tax_pct or 15)
    discount_pct = float(inv.discount_pct or 0)
    vat_amount = subtotal * (tax_pct/100.0)
    discount_amount = (subtotal + vat_amount) * (discount_pct/100.0)
    total_after = subtotal + vat_amount - discount_amount

    inv_ctx = {
        'invoice_number': inv.invoice_number,
        'table_number': inv.table_number,
        'customer_name': inv.customer_name,
        'customer_phone': inv.customer_phone,
        'payment_method': inv.payment_method,
        'status': 'PAID',
        'total_before_tax': round(subtotal, 2),
        'tax_amount': round(vat_amount, 2),
        'discount_amount': round(discount_amount, 2),
        'total_after_tax_discount': round(total_after, 2),
    }
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    branch_name = BRANCH_LABELS.get(inv.branch_code, inv.branch_code)
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('print/receipt.html', inv=inv_ctx, items=items_ctx,
                           settings=s, branch_name=branch_name, date_time=dt_str,
                           display_invoice_number=inv.invoice_number,
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

@main.route('/suppliers', endpoint='suppliers')
@login_required
def suppliers():
    return render_template('suppliers.html')

@main.route('/menu', methods=['GET'], endpoint='menu')
@login_required
def menu():
    ensure_tables(); seed_menu_if_empty()
    cats = MenuCategory.query.order_by(MenuCategory.sort_order, MenuCategory.name).all()
    current = None
    cat_id = request.args.get('cat_id', type=int)
    if cat_id:
        try:
            current = db.session.get(MenuCategory, int(cat_id))
        except Exception:
            current = None
    if not current and cats:
        current = cats[0]
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
    ensure_tables()
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
    ensure_tables()
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
    ensure_tables()
    cat_id = request.form.get('section_id', type=int)
    meal_id = request.form.get('meal_id', type=int)
    name = (request.form.get('name') or '').strip()
    price = request.form.get('price', type=float)
    if not cat_id:
        flash('Missing category', 'danger')
        return redirect(url_for('main.menu'))
    try:
        # If a meal is selected, use its name (EN/AR) and selling price by default
        if meal_id:
            meal = db.session.get(Meal, int(meal_id))
        else:
            meal = None
        if meal:
            disp_name = f"{meal.name} / {meal.name_ar}" if getattr(meal, 'name_ar', None) else (meal.name or name)
            final_name = (name or '').strip() or disp_name
            final_price = float(price) if price is not None else float(meal.selling_price or 0.0)
        else:
            # Fallback to manual
            final_name = name
            final_price = float(price or 0.0)
        if not final_name:
            flash('Missing item name', 'danger')
            return redirect(url_for('main.menu', cat_id=cat_id))
        it = MenuItem(name=final_name, price=final_price, category_id=int(cat_id))
        db.session.add(it)
        db.session.commit()
        return redirect(url_for('main.menu', cat_id=cat_id))
    except Exception:
        db.session.rollback()
        flash('Error creating item', 'danger')
        return redirect(url_for('main.menu', cat_id=cat_id))


@main.route('/menu/item/<int:item_id>/update', methods=['POST'], endpoint='menu_item_update')
@login_required
def menu_item_update(item_id):
    ensure_tables()
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
    ensure_tables()
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

@main.route('/settings', methods=['GET', 'POST'], endpoint='settings')
@login_required
def settings():
    # Pass Settings instance to template to avoid 's' undefined
    s = None
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    if request.method == 'POST':
        try:
            if not s:
                s = Settings()
                db.session.add(s)
            # Safely set only attributes that exist on Settings model
            form_data = request.form if request.form else (request.get_json(silent=True) or {})
            for fld in [
                'company_name','tax_number','phone','address','vat_rate',
                'receipt_show_logo','receipt_paper_width','receipt_font_size','receipt_logo_height','receipt_extra_bottom_mm',
                'logo_url','currency','currency_image','footer_message','receipt_footer_text'
            ]:
                if hasattr(s, fld) and fld in form_data:
                    val = form_data.get(fld)
                    # Coerce booleans/numerics if needed
                    if fld in ['receipt_show_logo']:
                        val = True if str(val).lower() in ['1','true','yes','on'] else False
                    elif fld in ['vat_rate','receipt_paper_width','receipt_font_size','receipt_logo_height','receipt_extra_bottom_mm']:
                        try: val = float(val)
                        except Exception: pass
                    setattr(s, fld, val)
            # Map currency_image_url -> currency_image
            cur_url = (form_data.get('currency_image_url') or '').strip() if hasattr(s, 'currency_image') else ''
            if cur_url:
                s.currency_image = cur_url
            # Handle file uploads (logo, currency PNG)
            try:
                upload_dir = os.path.join(current_app.static_folder, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                # Logo file
                logo_file = request.files.get('logo_file')
                if logo_file and getattr(logo_file, 'filename', ''):
                    ext = os.path.splitext(logo_file.filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.svg', '.gif']:
                        fname = f"logo_{int(datetime.utcnow().timestamp())}{ext}"
                        fpath = os.path.join(upload_dir, fname)
                        logo_file.save(fpath)
                        s.logo_url = f"/static/uploads/{fname}"
                # Currency PNG
                cur_file = request.files.get('currency_file')
                if cur_file and getattr(cur_file, 'filename', ''):
                    ext = os.path.splitext(cur_file.filename)[1].lower()
                    if ext == '.png':
                        fname = f"currency_{int(datetime.utcnow().timestamp())}{ext}"
                        fpath = os.path.join(upload_dir, fname)
                        cur_file.save(fpath)
                        if hasattr(s, 'currency_image'):
                            s.currency_image = f"/static/uploads/{fname}"
            except Exception:
                pass
            db.session.commit()
            flash('Settings saved', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Could not save settings (placeholder handler)', 'warning')
        return redirect(url_for('main.settings'))
    return render_template('settings.html', s=s)

@main.route('/table-settings', endpoint='table_settings')
@login_required
def table_settings():
    return render_template('table_settings.html')

@main.route('/users', endpoint='users')
@login_required
def users():
    return render_template('users.html')

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

    data = {
        'year': y,
        'quarter': q,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'sales_place_india': 0.0,
        'sales_china_town': 0.0,
        'sales_total': 0.0,
        'purchases_total': 0.0,
        'expenses_total': 0.0,
        'output_vat': 0.0,
        'input_vat': 0.0,
        'net_vat': 0.0,
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

    sales_total = float(sales_place_india or 0) + float(sales_china_town or 0)

    # For now, avoid cross-DB model usage; default to 0 if models are not available in this context
    purchases_total = 0
    expenses_total = 0

    s = None
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    vat_rate = float(getattr(s, 'vat_rate', 15) or 15)/100.0

    output_vat = float(sales_total or 0) * vat_rate
    input_vat = float((purchases_total or 0) + (expenses_total or 0)) * vat_rate
    net_vat = output_vat - input_vat

    company_name = getattr(s, 'company_name', '') if s else ''
    tax_number = getattr(s, 'tax_number', '') if s else ''
    place_lbl = getattr(s, 'place_india_label', 'Place India') if s else 'Place India'
    china_lbl = getattr(s, 'china_town_label', 'China Town') if s else 'China Town'
    currency = getattr(s, 'currency', 'SAR') if s else 'SAR'

    return render_template('vat/vat_print_fallback.html',
                           year=year, quarter=quarter,
                           start_date=start_date, end_date=end_date,
                           sales_place_india=float(sales_place_india or 0),
                           sales_china_town=float(sales_china_town or 0),
                           sales_total=float(sales_total or 0),
                           purchases_total=float(purchases_total or 0),
                           expenses_total=float(expenses_total or 0),
                           output_vat=output_vat, input_vat=input_vat, net_vat=net_vat,
                           vat_rate=vat_rate,
                           company_name=company_name, tax_number=tax_number,
                           place_lbl=place_lbl, china_lbl=china_lbl, currency=currency)

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

    data = {
        'period': period,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'revenue': 0.0,
        'cogs': 0.0,
        'gross_profit': 0.0,
        'operating_expenses': 0.0,
        'operating_profit': 0.0,
        'other_income': 0.0,
        'other_expenses': 0.0,
        'net_profit_before_tax': 0.0,
        'tax': 0.0,
        'net_profit_after_tax': 0.0,
    }
    return render_template('financials/income_statement.html', data=data)

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
    data = {
        'date': d,
        'assets': 0.0,
        'liabilities': 0.0,
        'equity': 0.0,
    }
    return render_template('financials/balance_sheet.html', data=data)

@financials.route('/trial-balance/print', endpoint='print_trial_balance')
@login_required
def print_trial_balance():
    d = (request.args.get('date') or date.today().isoformat())
    data = {
        'date': d,
        'rows': [],
        'total_debit': 0.0,
        'total_credit': 0.0,
    }
    return render_template('financials/trial_balance.html', data=data)


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
        q = q.order_by(SalesInvoice.created_at.desc()).limit(1000)

        for inv, it in q.all():
            branch = inv.branch_code
            date_s = (inv.created_at.date().isoformat() if getattr(inv, 'created_at', None) else '')
            amount = float((it.unit_price or 0.0) * (it.qty or 0.0))
            disc = float(((inv.discount_pct or 0.0) / 100.0) * amount) if hasattr(inv, 'discount_pct') else 0.0
            base = max(amount - disc, 0.0)
            vat = float(((inv.tax_pct or 0.0) / 100.0) * base) if hasattr(inv, 'tax_pct') else 0.0
            total = base + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'branch': branch,
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.name,
                'quantity': float(it.qty or 0.0),
                'price': float(it.unit_price or 0.0),
                'amount': amount,
                'discount': disc,
                'vat': vat,
                'total': total,
                'payment_method': pm,
            })
            bt = branch_totals.setdefault(branch, {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0})
            bt['amount'] += amount; bt['discount'] += disc; bt['vat'] += vat; bt['total'] += total
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += total

        return jsonify({'invoices': rows, 'branch_totals': branch_totals, 'overall_totals': overall})
    except Exception as e:
        # Return empty but 200 to avoid UI breaking
        return jsonify({'invoices': [], 'branch_totals': {}, 'overall_totals': {'amount':0,'discount':0,'vat':0,'total':0}, 'note': 'stub'}), 200


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
        q = q.order_by(PurchaseInvoice.created_at.desc()).limit(1000)
        for inv, it in q.all():
            date_s = (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            disc = float(it.discount or 0.0)
            base = max(amount - disc, 0.0)
            vat = float(it.tax or 0.0)
            total = float(it.total_price or (base + vat))
            rows.append({
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.raw_material_name,
                'quantity': float(it.quantity or 0.0),
                'price': float(it.price_before_tax or 0.0),
                'amount': amount,
                'discount': disc,
                'vat': vat,
                'total': total,
                'payment_method': (inv.payment_method or '').upper(),
            })
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += total
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
            rows.append({
                'date': (exp.date.strftime('%Y-%m-%d') if getattr(exp, 'date', None) else ''),
                'expense_number': exp.invoice_number,
                'item': '',
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
        q = q.order_by(SalesInvoice.created_at.desc()).limit(1000)
        for inv, it in q.all():
            branch = inv.branch_code
            date_s = (inv.created_at.date().isoformat() if getattr(inv, 'created_at', None) else '')
            amount = float((it.unit_price or 0.0) * (it.qty or 0.0))
            disc = float(((inv.discount_pct or 0.0) / 100.0) * amount) if hasattr(inv, 'discount_pct') else 0.0
            base = max(amount - disc, 0.0)
            vat = float(((inv.tax_pct or 0.0) / 100.0) * base) if hasattr(inv, 'tax_pct') else 0.0
            total = base + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'branch': branch,
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.name,
                'quantity': float(it.qty or 0.0),
                'amount': amount,
                'discount': disc,
                'vat': vat,
                'total': total,
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
        'branch': 'all',
        'start_date': request.args.get('start_date') or '',
        'end_date': request.args.get('end_date') or '',
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    return render_template('reports_print_sales.html', rows=rows, branch_totals=branch_totals, overall=overall, settings=settings, meta=meta, payment_totals=payment_totals)


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
        q = q.order_by(PurchaseInvoice.created_at.desc()).limit(2000)
        for inv, it in q.all():
            d = (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            disc = float(it.discount or 0.0)
            base = max(amount - disc, 0.0)
            vat = float(it.tax or 0.0)
            total = float(it.total_price or (base + vat))
            pm = (inv.payment_method or '').upper()
            rows.append({
                'Date': d,
                'Invoice No.': inv.invoice_number,
                'Item': it.raw_material_name,
                'Qty': float(it.quantity or 0.0),
                'Amount': amount,
                'Discount': disc,
                'VAT': vat,
                'Total': total,
                'Payment': pm,
            })
            totals['Amount'] += amount; totals['Discount'] += disc; totals['VAT'] += vat; totals['Total'] += total
            payment_totals[pm] = payment_totals.get(pm, 0.0) + total
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
            amt = float(exp.total_after_tax_discount or 0.0)
            pm = (exp.payment_method or '').upper()
            rows.append({
                'Date': d,
                'Expense No.': exp.invoice_number,
                'Description': getattr(exp, 'description', '') or '',
                'Amount': amt,
                'Payment': pm,
            })
            totals['Amount'] += amt
            payment_totals[pm] = payment_totals.get(pm, 0.0) + amt
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
    columns = ['Date','Expense No.','Description','Amount','Payment']
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=['Amount'],
                           totals_colspan=3, payment_totals=payment_totals)
