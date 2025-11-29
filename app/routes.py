import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from forms import PurchaseInvoiceForm
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, AppKV, MenuCategory, MenuItem, SalesInvoice, SalesInvoiceItem

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

@main.route('/login', methods=['GET', 'POST'])
def login():
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
    return render_template('sales.html')

@main.route('/purchases', methods=['GET', 'POST'], endpoint='purchases')
@login_required
def purchases():
    form = PurchaseInvoiceForm()
    suppliers_list = kv_get('suppliers_list', []) or []
    materials = kv_get('raw_materials_list', []) or []
    if request.method == 'POST':
        try:
            date_s = request.form.get('date') or datetime.utcnow().date().isoformat()
            pm = request.form.get('payment_method') or 'CASH'
            supplier_name = request.form.get('supplier_name') or ''
            supplier_id = request.form.get('supplier_id') or ''
            items = []
            total_before = 0.0
            total_discount = 0.0
            total_tax = 0.0
            final_total = 0.0
            idxs = set()
            for k in request.form.keys():
                if k.startswith('items-'):
                    try:
                        p = k.split('-')[1]
                        idxs.add(int(p))
                    except Exception:
                        pass
            for i in sorted(list(idxs)):
                name = request.form.get(f'items-{i}-item_name') or ''
                unit = request.form.get(f'items-{i}-unit') or ''
                q = request.form.get(f'items-{i}-quantity') or '0'
                pr = request.form.get(f'items-{i}-price_before_tax') or '0'
                d = request.form.get(f'items-{i}-discount') or '0'
                t = request.form.get(f'items-{i}-tax_pct') or '15'
                try:
                    qf = float(q)
                except Exception:
                    qf = 0.0
                try:
                    pf = float(pr)
                except Exception:
                    pf = 0.0
                try:
                    df = max(0.0, min(100.0, float(d)))
                except Exception:
                    df = 0.0
                try:
                    tf = max(0.0, min(100.0, float(t)))
                except Exception:
                    tf = 15.0
                before = qf * pf
                disc = before * (df/100.0)
                base = max(0.0, before - disc)
                tax = base * (tf/100.0)
                line_total = base + tax
                total_before += before
                total_discount += disc
                total_tax += tax
                final_total += line_total
                items.append({
                    'item_name': name,
                    'unit': unit,
                    'quantity': qf,
                    'price_before_tax': pf,
                    'discount_pct': df,
                    'tax_pct': tf,
                    'line_total': line_total
                })
            year = datetime.utcnow().strftime('%Y')
            seq_key = f'purchase_seq:{year}'
            seq = int(kv_get(seq_key, 0) or 0) + 1
            kv_set(seq_key, seq)
            invoice_number = f'INV-PUR-{year}-{str(seq).zfill(4)}'
            rec = {
                'invoice_number': invoice_number,
                'date': date_s,
                'payment_method': pm,
                'supplier_name': supplier_name,
                'supplier_id': supplier_id,
                'totals': {
                    'total_before_tax': round(total_before, 2),
                    'total_discount': round(total_discount, 2),
                    'tax_amount': round(total_tax, 2),
                    'final_total': round(final_total, 2)
                },
                'items': items,
                'status': 'unpaid'
            }
            kv_set(f'purchase:{invoice_number}', rec)
            index = kv_get('purchases:index', []) or []
            index.append({'invoice_number': invoice_number, 'date': date_s, 'supplier_name': supplier_name, 'payment_method': pm, 'final_total': rec['totals']['final_total']})
            kv_set('purchases:index', index)
            flash('تم حفظ فاتورة الشراء بنجاح', 'success')
            return redirect(url_for('main.purchases'))
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('main.purchases'))
    return render_template('purchases.html', form=form, suppliers_list=suppliers_list, suppliers_json=json.dumps(suppliers_list), materials_json=json.dumps(materials))

@main.route('/raw-materials', endpoint='raw_materials')
@login_required
def raw_materials():
    return render_template('raw_materials.html')

@main.route('/meals', endpoint='meals')
@login_required
def meals():
    return render_template('meals.html')

@main.route('/inventory', endpoint='inventory')
@login_required
def inventory():
    return render_template('inventory.html')

@main.route('/expenses', endpoint='expenses')
@login_required
def expenses():
    return render_template('expenses.html')

@main.route('/invoices', endpoint='invoices')
@login_required
def invoices():
    return render_template('invoices.html')

@main.route('/employees', endpoint='employees')
@login_required
def employees():
    return render_template('employees.html')

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
    return render_template('sales_table_invoice.html',
                           branch_code=branch_code,
                           branch_label=branch_label,
                           table_number=table_number,
                           vat_rate=vat_rate,
                           draft_items=draft_items,
                           current_draft=current_draft,
                           categories=categories,
                           cat_map_json=cat_map_json,
                           today=today)


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
            'customer': payload.get('customer') or {}
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
        # map items to unified structure
        items = payload.get('items') or []
        # unify to {id/name/price/quantity}
        norm = []
        for it in items:
            norm.append({
                'meal_id': it.get('meal_id') or it.get('id'),
                'qty': it.get('qty') or it.get('quantity') or 1
            })
        rec['items'] = norm
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
    payment_method = payload.get('payment_method') or 'CASH'
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
    return jsonify({'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_amount, 2), 'print_url': ''})


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
    payment_method = payload.get('payment_method') or 'CASH'
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
    return jsonify({'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_amount, 2), 'print_url': ''})


@main.route('/api/invoice/confirm-print', methods=['POST'], endpoint='api_invoice_confirm_print')
@login_required
def api_invoice_confirm_print():
    # In a real system: mark invoice as printed/paid
    return jsonify({'success': True})


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




@main.route('/customers', endpoint='customers')
@login_required
def customers():
    return render_template('customers.html')

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
    # counts per category
    item_counts = {c.id: MenuItem.query.filter_by(category_id=c.id).count() for c in cats}
    return render_template('menu.html', sections=cats, current_section=current, items=items, item_counts=item_counts)


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
    name = (request.form.get('name') or '').strip()
    price = request.form.get('price', type=float) or 0.0
    if not (cat_id and name):
        flash('Missing item name or category', 'danger')
        return redirect(url_for('main.menu'))
    try:
        it = MenuItem(name=name, price=float(price or 0.0), category_id=int(cat_id))
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

@main.route('/settings', endpoint='settings')
@login_required
def settings():
    return render_template('settings.html')

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
    return render_template('vat/vat_dashboard.html')

# ---------- Financials blueprint ----------
financials = Blueprint('financials', __name__, url_prefix='/financials')

@financials.route('/income-statement', endpoint='income_statement')
@login_required
def income_statement():
    return render_template('financials/income_statement.html')

@financials.route('/balance-sheet', endpoint='balance_sheet')
@login_required
def balance_sheet():
    return render_template('financials/balance_sheet.html')

@financials.route('/trial-balance', endpoint='trial_balance')
@login_required
def trial_balance():
    return render_template('financials/trial_balance.html')
