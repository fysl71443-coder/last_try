# Phase 2 – Sales/POS blueprint. Same URLs.
from __future__ import annotations

import json
import re
import os
import base64
import mimetypes
from datetime import datetime, date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_, text

from app import db
from models import (
    SalesInvoice,
    SalesInvoiceItem,
    MenuItem,
    MenuCategory,
    Customer,
    Payment,
    Settings,
    LedgerEntry,
    JournalEntry,
    JournalLine,
    get_saudi_now,
)
from routes.common import BRANCH_LABELS, kv_get, kv_set, safe_table_number, user_can
from app.routes import (
    _set_table_status_concurrent,
    _pm_account,
    _create_receipt_journal,
    _create_sale_journal,
    CHART_OF_ACCOUNTS,
    _account,
    _platform_group,
    _acc_override,
    SHORT_TO_NUMERIC,
)
# Import warmup_db_once directly from app.routes module
try:
    from app.routes import warmup_db_once
except ImportError:
    # Fallback: define a simple version if import fails
    def warmup_db_once():
        pass

bp = Blueprint("sales", __name__)

@bp.route('/sales', endpoint='sales')
@login_required
def sales():
    # Modern flow: show branches, then tables, then table invoice
    branches = [
        {'code': 'china_town', 'label': 'CHINA TOWN', 'url': url_for('sales.sales_tables', branch_code='china_town')},
        {'code': 'place_india', 'label': 'PALACE INDIA', 'url': url_for('sales.sales_tables', branch_code='place_india')},
    ]
    # Filter branches by user permissions (allow via specific branch or global 'all')
    branches = [b for b in branches if user_can('sales', 'view', b['code'])]
    return render_template('sales_branches.html', branches=branches)





@bp.route('/sales/<branch_code>/tables', endpoint='sales_tables')
@login_required
def sales_tables(branch_code):
    if not user_can('sales','view', branch_code):
        flash('لا تملك صلاحية الوصول لفرع المبيعات هذا', 'warning')
        return redirect(url_for('sales.sales'))
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


@bp.route('/sales/china_town', endpoint='sales_china')
@login_required
def sales_china():
    return redirect(url_for('sales.sales_tables', branch_code='china_town'))



@bp.route('/sales/place_india', endpoint='sales_india')
@login_required
def sales_india():
    return redirect(url_for('sales.sales_tables', branch_code='place_india'))



@bp.route('/pos/<branch_code>', endpoint='pos_home')
@login_required
def pos_home(branch_code):
    if not user_can('sales','view', branch_code):
        flash('\u0644\u0627 \u062a\u0645\u0644\u0643 \u0635\u0644\u0627\u062d\u064a\u0629 \u0627\u0644\u0648\u0635\u0648\u0644 \u0644\u0641\u0631\u0639 \u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a \u0647\u0630\u0627', 'warning')
        return redirect(url_for('sales.sales'))

    return redirect(url_for('sales.sales_tables', branch_code=branch_code))



@bp.route('/pos/<branch_code>/table/<int:table_number>', endpoint='pos_table')
@login_required
def pos_table(branch_code, table_number):
    if not user_can('sales','view', branch_code):
        # If XHR requested HTML (POS page) but user is not allowed, redirect to login preserving next
        return redirect(url_for('main.login', next=request.path))
    branch_label = BRANCH_LABELS.get(branch_code, branch_code)
    vat_rate = 15
    # Load any existing draft for this table
    draft = kv_get(f'draft:{branch_code}:{table_number}', {}) or {}
    draft_items = json.dumps(draft.get('items') or [])
    current_draft = type('Obj', (), {'id': draft.get('draft_id')}) if draft.get('draft_id') else None
    try:
        init_cust = (draft.get('customer') or {})
        init_cust_name = (init_cust.get('name') or '').strip()
        init_cust_phone = (init_cust.get('phone') or '').strip()
    except Exception:
        init_cust_name = ''
        init_cust_phone = ''
    try:
        init_discount_pct = float((draft.get('discount_pct') or 0) or 0)
    except Exception:
        init_discount_pct = 0.0
    try:
        init_tax_pct = float((draft.get('tax_pct') or vat_rate) or vat_rate)
    except Exception:
        init_tax_pct = float(vat_rate or 15)
    init_payment_method = (draft.get('payment_method') or '').strip().upper()
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
    def _slug(s):
        try:
            import re
            s = (s or '').strip().lower()
            s = re.sub(r"[^a-z0-9]+", "-", s)
            s = re.sub(r"-+", "-", s).strip('-')
            return s or 'category'
        except Exception:
            return 'category'
    def _static_image_url(*candidates):
        try:
            import os
            for rel in candidates:
                if not rel:
                    continue
                fp = os.path.join(current_app.static_folder, rel.replace('/', os.sep))
                if os.path.exists(fp):
                    return '/static/' + rel
        except Exception:
            pass
        return None
    cat_image_map = {}
    try:
        _def_cat_img = kv_get('menu:default_category_image', None) or kv_get('menu:default_image', None) or '/static/logo.svg'
    except Exception:
        _def_cat_img = '/static/logo.svg'
    for c in cats:
        cat_map[c.name] = c.id
        cat_map[c.name.upper()] = c.id
        try:
            u = kv_get(f"menu:category_image:{c.id}", None) or kv_get(f"menu:category_image_by_name:{_slug(c.name)}", None)
        except Exception:
            u = None
        if not u:
            sslug = _slug(c.name)
            u = _static_image_url(f"images/categories/{sslug}.webp", f"images/categories/{sslug}.jpg", f"images/categories/{sslug}.png") or _def_cat_img
        cat_image_map[c.name] = u or _def_cat_img
    cat_map_json = json.dumps(cat_map)
    cat_image_map_json = json.dumps(cat_image_map)
    today = get_saudi_now().date().isoformat()
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
                           cat_image_map_json=cat_image_map_json,
                           today=today,
                           init_cust_name=init_cust_name,
                           init_cust_phone=init_cust_phone,
                           init_discount_pct=init_discount_pct,
                           init_tax_pct=init_tax_pct,
                           init_payment_method=init_payment_method,
                           settings=s)


# ---------- Lightweight APIs used by front-end JS ----------

@bp.route('/api/table-settings', methods=['GET', 'POST'], endpoint='api_table_settings')
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



@bp.route('/api/table-sections/<branch_code>', methods=['GET', 'POST'], endpoint='api_table_sections')
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



@bp.route('/api/tables/<branch_code>', methods=['GET'], endpoint='api_tables_status')
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
    # Build a quick map of DB table statuses for this branch
    try:
        from models import Table
        rows = Table.query.filter_by(branch_code=branch_code).all()
        db_status = { (str(r.table_number).strip()): (r.status or 'available') for r in (rows or []) }
        # Expand count to include highest table number present in DB
        try:
            max_db_no = 0
            for r in (rows or []):
                try:
                    n = safe_table_number(getattr(r, 'table_number', None))
                    if n > max_db_no:
                        max_db_no = n
                except Exception:
                    continue
            if max_db_no > count:
                count = max_db_no
        except Exception:
            pass
    except Exception:
        db_status = {}
    for i in range(1, count+1):
        draft = kv_get(f'draft:{branch_code}:{i}', {}) or {}
        has_draft = bool(draft.get('items') or [])
        tbl_st = (db_status.get(str(i)) or 'available').lower()
        status = 'occupied' if (has_draft or tbl_st == 'occupied') else 'available'
        items.append({'table_number': i, 'status': status})
    return jsonify(items)



@bp.route('/api/menu/<cat_id>/items', methods=['GET'], endpoint='api_menu_items')
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
    def _slug(s):
        try:
            import re
            s = (s or '').strip().lower()
            s = re.sub(r"[^a-z0-9]+", "-", s)
            s = re.sub(r"-+", "-", s).strip('-')
            return s or 'item'
        except Exception:
            return 'item'
    def _static_image_url(*candidates):
        try:
            import os
            for rel in candidates:
                if not rel:
                    continue
                fp = os.path.join(current_app.static_folder, rel.replace('/', os.sep))
                if os.path.exists(fp):
                    return '/static/' + rel
        except Exception:
            pass
        return None
    def _uploads_image_url(kind, slug):
        try:
            if not slug:
                return None
            rels = [
                f'uploads/{kind}/{slug}.webp',
                f'uploads/{kind}/{slug}.jpg',
                f'uploads/{kind}/{slug}.png',
            ]
            for r in rels:
                u = _static_image_url(r)
                if u:
                    return u
        except Exception:
            pass
        return None
    def _default_image_url():
        try:
            u = kv_get('menu:default_image', None) or kv_get('menu:default_item_image', None) or kv_get('menu:default_category_image', None)
            if isinstance(u, str) and u:
                return u
        except Exception:
            pass
        return 'https://also3odyah.com/wp-content/uploads/2024/08/Best-Asian-Restaurants-in-Riyadh-Yauatcha-1024x768-1.jpg'
    def _remote_image_for_keywords(name, kind):
        try:
            n = (name or '').lower()
            keys = {
                'category': {
                    'appetizers': 'https://images.unsplash.com/photo-1547592180-85f173990554?q=80&w=1600&auto=format&fit=crop',
                    'biryani': 'https://images.unsplash.com/photo-1604908176997-2846b8dce8e7?q=80&w=1600&auto=format&fit=crop',
                    'rice': 'https://images.unsplash.com/photo-1547592180-85f173990554?q=80&w=1600&auto=format&fit=crop',
                    'noodles': 'https://images.unsplash.com/photo-1526318472351-c75fd2f0703d?q=80&w=1600&auto=format&fit=crop',
                    'soup': 'https://images.unsplash.com/photo-1505577058444-a3dab90d4253?q=80&w=1600&auto=format&fit=crop',
                    'salad': 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?q=80&w=1600&auto=format&fit=crop',
                    'seafood': 'https://images.unsplash.com/photo-1551183053-bf91a1d81141?q=80&w=1600&auto=format&fit=crop',
                    'prawn': 'https://images.unsplash.com/photo-1611253135999-daddb98d97a2?q=80&w=1600&auto=format&fit=crop',
                    'chicken': 'https://images.unsplash.com/photo-1544025162-d76694265947?q=80&w=1600&auto=format&fit=crop',
                    'beef': 'https://images.unsplash.com/photo-1553163147-622ab57be1c7?q=80&w=1600&auto=format&fit=crop',
                    'lamb': 'https://images.unsplash.com/photo-1625944521360-4f098c2e8a04?q=80&w=1600&auto=format&fit=crop',
                    'kebab': 'https://images.unsplash.com/photo-1604908554043-3df28557f9a5?q=80&w=1600&auto=format&fit=crop',
                    'grill': 'https://images.unsplash.com/photo-1558031239-aa4ae7329230?q=80&w=1600&auto=format&fit=crop',
                    'drinks': 'https://images.unsplash.com/photo-1509228627152-72ae9ae6848d?q=80&w=1600&auto=format&fit=crop',
                    'chinese': 'https://images.unsplash.com/photo-1544510808-8b0b0f7de841?q=80&w=1600&auto=format&fit=crop',
                    'indian': 'https://images.unsplash.com/photo-1543352634-8730a9b5e570?q=80&w=1600&auto=format&fit=crop',
                },
                'item': {
                    'biryani': 'https://images.unsplash.com/photo-1604908176997-2846b8dce8e7?q=80&w=1600&auto=format&fit=crop',
                    'noodles': 'https://images.unsplash.com/photo-1526318472351-c75fd2f0703d?q=80&w=1600&auto=format&fit=crop',
                    'samosa': 'https://images.unsplash.com/photo-1625944519087-2a9c7b0f1ff4?q=80&w=1600&auto=format&fit=crop',
                    'hummus': 'https://images.unsplash.com/photo-1552332386-f8dd00dc2f85?q=80&w=1600&auto=format&fit=crop',
                    'potato': 'https://images.unsplash.com/photo-1518806118471-f66f1e488eae?q=80&w=1600&auto=format&fit=crop',
                    'naan': 'https://images.unsplash.com/photo-1601050693721-03bba7dd6e61?q=80&w=1600&auto=format&fit=crop',
                    'tempura': 'https://images.unsplash.com/photo-1562967915-6a88f1f68047?q=80&w=1600&auto=format&fit=crop',
                    'kebab': 'https://images.unsplash.com/photo-1604908554043-3df28557f9a5?q=80&w=1600&auto=format&fit=crop',
                    'prawn': 'https://images.unsplash.com/photo-1611253135999-daddb98d97a2?q=80&w=1600&auto=format&fit=crop',
                    'shrimp': 'https://images.unsplash.com/photo-1611253135999-daddb98d97a2?q=80&w=1600&auto=format&fit=crop',
                    'chicken': 'https://images.unsplash.com/photo-1544025162-d76694265947?q=80&w=1600&auto=format&fit=crop',
                    'fish': 'https://images.unsplash.com/photo-1551183053-bf91a1d81141?q=80&w=1600&auto=format&fit=crop'
                }
            }[kind]
            syn = {
                'biryani': ['برياني','بريان','biryani'],
                'noodles': ['noodles','نودلز','معكرونة','chow','mein','chopsuey'],
                'samosa': ['سمبوسة','سمبوسا','سموسا','samosa','samusa'],
                'hummus': ['حمص','homous','hummus','humus','homouse'],
                'potato': ['بطاطس','بطاطا','potato','chips','chope','chop','choap','frenchfry','french fry','fries','finger chips'],
                'naan': ['خبز نان','نان','naan','nan','garlic nan','garlic naan','plain nan','plain naan'],
                'tempura': ['تمبورا','تيمبورا','tempura'],
                'kebab': ['كباب','kebab'],
                'prawn': ['روبيان','ربيان','ribyan','prawn','prwn','prawns','fried prawns','gold.fri.prawns','gold fried prawns','prwnballs','prawn balls','prwn balls'],
                'shrimp': ['جمبري','shrimp','fried shrimp'],
                'chicken': ['دجاج','chicken','kaichai'],
                'appetizers': ['appetizers','starter','starters','مقبلات','مقبا','mixed app','mixeed app','mixed appetizer','mix app','mixeed app(l)','mixeed app(m)','platter','مقبلات مشكل'],
                'seafood': ['seafood','مأكولات بحرية'],
                'fish': ['fish','fish finger','finger fish','fishfinger','fish-finger','سمك','فيش'],
                'salad': ['سلطة','salad'],
                'soup': ['شوربة','soup']
            }
            for k, lst in syn.items():
                for t in lst:
                    if t and t in n and k in keys:
                        url = keys.get(k)
                        if url:
                            return url
            for k, url in keys.items():
                if k in n:
                    return url
        except Exception:
            pass
        return None
    def _item_image_url(m):
        return _default_image_url()
    if cat:
        items = MenuItem.query.filter_by(category_id=cat.id).order_by(MenuItem.name).all()
        return jsonify([{'id': m.id, 'name': m.name, 'price': float(m.price), 'image_url': _item_image_url(m)} for m in items])
    # KV fallback
    data = kv_get(f'menu:items:{cat_id}', None)
    if isinstance(data, list):
        return jsonify(data)
    # Demo fallback
    demo_items = [{'id': None, 'name': nm, 'price': float(pr)} for (nm, pr) in _DEF_MENU.get(cat_id, [])]


    out = []
    # Force default image for demo items as well
    for d in demo_items:
        dd = dict(d)
        dd['image_url'] = _default_image_url()
        out.append(dd)
    return jsonify(out)

# ---------- Branch Settings API used by POS ----------

@bp.route('/api/branch-settings/<branch_code>', methods=['GET'], endpoint='api_branch_settings')
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


@bp.route('/api/draft-order/<branch_code>/<int:table_number>', methods=['GET','POST'], endpoint='api_draft_create_or_update')
@login_required
def api_draft_create_or_update(branch_code, table_number):
    # Return 401 for unauthenticated XHR so the front-end can redirect cleanly
    try:
        if not getattr(current_user, 'is_authenticated', False):
            return jsonify({'success': False, 'error': 'unauthenticated'}), 401
    except Exception:
        return jsonify({'success': False, 'error': 'unauthenticated'}), 401
    if not user_can('sales','view', branch_code):
        return jsonify({'success': False, 'error': 'forbidden'}), 403

    # GET: return current draft details for prefill
    if request.method == 'GET':
        try:
            rec = kv_get(f'draft:{branch_code}:{table_number}', {}) or {}
            return jsonify({'success': True, 'draft': rec})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e), 'draft': {}}), 400

    # POST: create or update draft
    try:
        payload = _request_json()
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
        # Persist table status in DB for multi-user consistency (transactional helper)
        _set_table_status_concurrent(branch_code, str(table_number), 'available' if not items else 'occupied')
        return jsonify({'success': True, 'draft_id': draft_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


def _request_json():
    """Parse JSON body. Use get_json first; if None (e.g. sendBeacon without Content-Type), try raw body."""
    payload = request.get_json(silent=True)
    if payload is not None:
        return payload
    raw = request.get_data(as_text=True)
    if not (raw and raw.strip()):
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


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



@bp.route('/api/draft_orders/<draft_id>/update', methods=['POST'], endpoint='api_draft_update')
@login_required
def api_draft_update(draft_id):
    try:
        branch, table = _parse_draft_id(draft_id)
        if not branch:
            return jsonify({'success': False, 'error': 'invalid_draft_id'}), 400
        # Return 401 for unauthenticated XHR so the front-end can redirect cleanly
        try:
            if not getattr(current_user, 'is_authenticated', False):
                return jsonify({'success': False, 'error': 'unauthenticated'}), 401
        except Exception:
            return jsonify({'success': False, 'error': 'unauthenticated'}), 401
        payload = request.get_json(silent=True) or {}
        if not user_can('sales','view', branch):
            return jsonify({'success': False, 'error': 'forbidden'}), 403

        payload = _request_json()
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
        # Also ensure DB table status reflects occupied/available based on items
        _set_table_status_concurrent(branch, str(table), 'occupied' if rec.get('items') else 'available')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400



@bp.route('/api/draft_orders/<draft_id>/cancel', methods=['POST'], endpoint='api_draft_cancel')
@login_required
def api_draft_cancel(draft_id):
    try:
        branch, table = _parse_draft_id(draft_id)


        if not branch:
            return jsonify({'success': False, 'error': 'invalid_draft_id'}), 400
        if not user_can('sales','view', branch):
            return jsonify({'success': False, 'error': 'forbidden'}), 403

        # clear draft and mark table available in DB
        kv_set(f'draft:{branch}:{table}', {'draft_id': draft_id, 'items': []})
        _set_table_status_concurrent(branch, str(table), 'available')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400



@bp.route('/api/draft/checkout', methods=['POST'], endpoint='api_draft_checkout')


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
    discount_amount = subtotal * (discount_pct/100.0)
    taxable_amount = max(subtotal - discount_amount, 0.0)
    vat_amount = taxable_amount * (tax_pct/100.0)
    total_after = taxable_amount + vat_amount
    payment_method = (payload.get('payment_method') or '').strip().upper()
    if payment_method not in ['CASH', 'CARD', 'CREDIT']:
        return jsonify({'success': False, 'error': 'اختر طريقة الدفع (CASH أو CARD أو آجل)'}), 400
    try:
        customer_id = int(payload.get('customer_id')) if payload.get('customer_id') is not None else None
    except (TypeError, ValueError):
        customer_id = None
    customer_name = (payload.get('customer_name') or '').strip()
    customer_phone = (payload.get('customer_phone') or '').strip()

    if payment_method == 'CREDIT':
        if not customer_id:
            return jsonify({'success': False, 'error': 'يجب اختيار عميل آجل مسجل من القائمة — لا يمكن إصدار فاتورة آجلة لعميل غير مسجل'}), 400
        cust_obj = Customer.query.get(customer_id)
        if not cust_obj or getattr(cust_obj, 'customer_type', 'cash') not in ('credit', 'آجل'):
            return jsonify({'success': False, 'error': 'العميل المختار غير مسجل كعميل آجل'}), 400
        customer_name = (cust_obj.name or '').strip()
        customer_phone = (getattr(cust_obj, 'phone', None) or '').strip()
    else:
        cust_lower = customer_name.lower()
        grp_pre = _platform_group(cust_lower)
        if not customer_id and customer_name:
            name_part = (customer_name.strip() or '')[:50]
            if grp_pre == 'keeta':
                c_by_name = Customer.query.filter(Customer.active == True).filter(Customer.name.ilike('%keeta%')).first()
            elif grp_pre == 'hunger':
                c_by_name = Customer.query.filter(Customer.active == True).filter(Customer.name.ilike('%hunger%')).first()
            else:
                c_by_name = Customer.query.filter(Customer.active == True).filter(Customer.name.ilike('%' + name_part + '%')).first()
            if c_by_name:
                customer_id = int(c_by_name.id)
                customer_name = (c_by_name.name or '').strip()
                customer_phone = (getattr(c_by_name, 'phone', None) or '').strip()
        if not customer_id:
            customer_name = ''
            customer_phone = ''
        elif customer_id:
            cust_obj = Customer.query.get(customer_id)
            if cust_obj:
                customer_name = (cust_obj.name or '').strip()
                customer_phone = (getattr(cust_obj, 'phone', None) or '').strip()

    # لا خصم للعميل النقدي المسجل — discount only for credit customers
    if payment_method in ('CASH', 'CARD') and customer_id:
        cust_obj = Customer.query.get(customer_id)
        if cust_obj and getattr(cust_obj, 'customer_type', 'cash') not in ('credit', 'آجل'):
            discount_pct = 0.0
            discount_amount = subtotal * (discount_pct / 100.0)
            taxable_amount = max(subtotal - discount_amount, 0.0)
            vat_amount = taxable_amount * (tax_pct / 100.0)
            total_after = taxable_amount + vat_amount

    # Reuse preview invoice number if present to keep display number consistent
    draft_data = kv_get(f'draft:{branch}:{table}', {}) or {}
    preview_no = (draft_data.get('preview_invoice_number') or '').strip()
    invoice_number = preview_no if preview_no else f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    try:
        inv = SalesInvoice(
            invoice_number=invoice_number,
            branch=branch,
            table_number=int(table),
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            total_before_tax=round(subtotal, 2),
            tax_amount=round(vat_amount, 2),
            discount_amount=round(discount_amount, 2),
            total_after_tax_discount=round(total_after, 2),
            user_id=int(getattr(current_user, 'id', 1) or 1),
            status='issued',
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
        # Auto-mark paid for non Keeta/Hunger and create Payment record
        try:
            from models import Payment
            cust = (payload.get('customer_name') or '').strip().lower()
            grp = _platform_group(cust)
            amt = float(inv.total_after_tax_discount or 0.0)
            if grp in ('keeta', 'hunger') or payment_method == 'CREDIT':
                inv.status = 'unpaid'
                db.session.commit()
            else:
                db.session.add(Payment(
                    invoice_id=inv.id,
                    invoice_type='sales',
                    amount_paid=amt,
                    payment_method=(payment_method or 'CASH').upper(),
                    payment_date=get_saudi_now()
                ))
                inv.status = 'paid'
                db.session.commit()
        except Exception:
            pass
        try:
            _create_sale_journal(inv)
        except Exception:
            pass
        # Mark table available only after we confirm print+pay (handled in api_invoice_confirm_print)
    except Exception as e:


        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'ok': True, 'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_after, 2), 'print_url': url_for('sales.print_receipt', invoice_number=invoice_number), 'branch_code': branch, 'table_number': int(table)})


@bp.route('/api/draft/<branch_code>/<int:table_number>', methods=['GET'], endpoint='api_draft_get')
@login_required
def api_draft_get(branch_code, table_number):
    try:
        if not user_can('sales','view', branch_code):
            return jsonify({'success': False, 'error': 'forbidden'}), 403
        rec = kv_get(f'draft:{branch_code}:{table_number}', {}) or {}
        return jsonify({'success': True, 'draft': rec})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'draft': {}}), 400



@bp.route('/api/sales/checkout', methods=['POST'], endpoint='api_sales_checkout')
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
    payment_method = (payload.get('payment_method') or '').strip().upper()
    if payment_method not in ['CASH', 'CARD', 'CREDIT']:
        return jsonify({'success': False, 'error': 'اختر طريقة الدفع (CASH أو CARD أو آجل)'}), 400
    try:
        customer_id = int(payload.get('customer_id')) if payload.get('customer_id') is not None else None
    except (TypeError, ValueError):
        customer_id = None
    customer_name = (payload.get('customer_name') or '').strip()
    customer_phone = (payload.get('customer_phone') or '').strip()

    if payment_method == 'CREDIT':
        if not customer_id:
            return jsonify({'success': False, 'error': 'يجب اختيار عميل آجل مسجل من القائمة — لا يمكن إصدار فاتورة آجلة لعميل غير مسجل'}), 400
        cust_obj = Customer.query.get(customer_id)
        if not cust_obj or getattr(cust_obj, 'customer_type', 'cash') not in ('credit', 'آجل'):
            return jsonify({'success': False, 'error': 'العميل المختار غير مسجل كعميل آجل'}), 400
        customer_name = (cust_obj.name or '').strip()
        customer_phone = (getattr(cust_obj, 'phone', None) or '').strip()
    else:
        cust_lower = customer_name.lower()
        grp_checkout = _platform_group(cust_lower)
        if not customer_id and customer_name:
            name_part = (customer_name or '')[:50]
            if grp_checkout == 'keeta':
                c_by_name = Customer.query.filter(Customer.active == True).filter(Customer.name.ilike('%keeta%')).first()
            elif grp_checkout == 'hunger':
                c_by_name = Customer.query.filter(Customer.active == True).filter(Customer.name.ilike('%hunger%')).first()
            else:
                c_by_name = Customer.query.filter(Customer.active == True).filter(Customer.name.ilike('%' + name_part + '%')).first()
            if c_by_name:
                customer_id = int(c_by_name.id)
                customer_name = (c_by_name.name or '').strip()
                customer_phone = (getattr(c_by_name, 'phone', None) or '').strip()
        if not customer_id:
            customer_name = ''
            customer_phone = ''
        elif customer_id:
            cust_obj = Customer.query.get(customer_id)
            if cust_obj:
                customer_name = (cust_obj.name or '').strip()
                customer_phone = (getattr(cust_obj, 'phone', None) or '').strip()

    discount_pct = float(payload.get('discount_pct') or 0)
    if payment_method in ('CASH', 'CARD') and customer_id:
        cust_obj = Customer.query.get(customer_id)
        if cust_obj and getattr(cust_obj, 'customer_type', 'cash') not in ('credit', 'آجل'):
            discount_pct = 0.0
    tax_pct = float(payload.get('tax_pct') or 15)
    discount_amount = subtotal * (discount_pct/100.0)
    taxable_amount = max(subtotal - discount_amount, 0.0)
    vat_amount = taxable_amount * (tax_pct/100.0)
    total_after = taxable_amount + vat_amount

    invoice_number = f"INV-{int(datetime.utcnow().timestamp())}-{branch[:2]}{table}"
    inv = None
    try:
        inv = SalesInvoice(
            invoice_number=invoice_number,
            branch=branch,
            table_number=table,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            total_before_tax=round(subtotal, 2),
            tax_amount=round(vat_amount, 2),
            discount_amount=round(discount_amount, 2),
            total_after_tax_discount=round(total_after, 2),
            user_id=int(getattr(current_user, 'id', 1) or 1),
            status='issued',
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
        use_adapter = False
        adapter_success = False
        try:
            from services.accounting_adapter import is_configured, post_sales_invoice
            from services.accounting_adapter import (
                AccountingUnavailableError, FiscalYearClosedError, InvalidApiKeyError, BadRequestError,
            )
            use_adapter = is_configured()
        except Exception:
            pass

        if use_adapter:
            cust = (payload.get('customer_name') or '').strip().lower()
            grp = _platform_group(cust)
            inv_status = 'unpaid' if (grp or payment_method == 'CREDIT') else 'paid'
            date_str = (inv.date or get_saudi_now().date()).isoformat()
            items_payload = [{'product_name': it.get('name'), 'quantity': it.get('qty'), 'price': it.get('price'), 'total': float(it.get('price') or 0) * float(it.get('qty') or 1)} for it in resolved]
            try:
                r = post_sales_invoice(
                    invoice_number=invoice_number,
                    date=date_str,
                    branch=branch,
                    total_before_tax=float(inv.total_before_tax or 0),
                    discount_amount=float(inv.discount_amount or 0),
                    vat_amount=float(inv.tax_amount or 0),
                    total_after_tax=float(inv.total_after_tax_discount or 0),
                    payment_method=payment_method,
                    customer_name=inv.customer_name,
                    customer_phone=inv.customer_phone,
                    table_number=table,
                    items=items_payload,
                    status=inv_status,
                )
                inv.journal_entry_id = r.get('journal_entry_id')
                inv.status = inv_status
                if inv_status == 'paid':
                    from models import Payment
                    db.session.add(Payment(
                        invoice_id=inv.id,
                        invoice_type='sales',
                        amount_paid=float(inv.total_after_tax_discount or 0.0),
                        payment_method=(payment_method or 'CASH').upper(),
                        payment_date=get_saudi_now(),
                    ))
                db.session.commit()
                adapter_success = True
            except FiscalYearClosedError:
                db.session.rollback()
                return jsonify({'success': False, 'error': 'fiscal_year_closed', 'message': 'السنة المالية مغلقة لهذا التاريخ'}), 403
            except (InvalidApiKeyError, BadRequestError) as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 400
            except AccountingUnavailableError as e:
                try:
                    current_app.logger.warning(
                        "Accounting service unreachable, using local journal: %s", e
                    )
                except Exception:
                    pass
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 503

        if not adapter_success:
            db.session.commit()
            try:
                from models import Payment
                cust = (payload.get('customer_name') or '').strip().lower()
                grp = _platform_group(cust)
                amt = float(inv.total_after_tax_discount or 0.0)
                if grp or payment_method == 'CREDIT':
                    inv.status = 'unpaid'
                    db.session.commit()
                else:
                    db.session.add(Payment(
                        invoice_id=inv.id,
                        invoice_type='sales',
                        amount_paid=amt,
                        payment_method=(payment_method or 'CASH').upper(),
                        payment_date=get_saudi_now(),
                    ))
                    inv.status = 'paid'
                    db.session.commit()
                    cash_acc = _pm_account(payment_method)
                    try:
                        cust2 = (getattr(inv, 'customer_name', '') or '').lower()
                        grp2 = _platform_group(cust2)
                        if grp2 == 'keeta':
                            ar_code = _acc_override('AR_KEETA', SHORT_TO_NUMERIC['AR_KEETA'][0])
                        elif grp2 == 'hunger':
                            ar_code = _acc_override('AR_HUNGER', SHORT_TO_NUMERIC['AR_HUNGER'][0])
                        else:
                            ar_code = _acc_override('AR', CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141'))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                _create_sale_journal(inv)
            except Exception:
                pass
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'ok': True, 'invoice_id': invoice_number, 'payment_method': payment_method, 'total_amount': round(total_after, 2), 'print_url': url_for('sales.invoice_print', invoice_id=invoice_number), 'branch_code': branch, 'table_number': table})



@bp.route('/api/invoice/confirm-print', methods=['POST'], endpoint='api_invoice_confirm_print')
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
            grp = _platform_group(inv.customer_name or '')
            if grp in ('keeta','hunger'):
                pass
            else:
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
            try:
                key = f"pdf_path:sales:{inv.invoice_number}"
                cur = kv_get(key, {}) or {}
                if not (cur.get('saved_at')):
                    kv_set(key, {'path': cur.get('path'), 'saved_at': get_saudi_now().isoformat()})
            except Exception:
                pass
            try:
                import re
                s = re.sub(r'[^a-z]', '', (inv.customer_name or '').lower())
                is_special = s.startswith('hunger') or s.startswith('keeta') or s.startswith('keet')
                if not is_special:
                    amt = float(total_amount or float(inv.total_after_tax_discount or 0))
                    cash_acc = _pm_account(payment_method)
                    try:
                        cust = (getattr(inv, 'customer_name', '') or '').lower()
                        grp = _platform_group(cust)
                        if grp == 'keeta':
                            ar_code = _acc_override('AR_KEETA', SHORT_TO_NUMERIC['AR_KEETA'][0])
                        elif grp == 'hunger':
                            ar_code = _acc_override('AR_HUNGER', SHORT_TO_NUMERIC['AR_HUNGER'][0])
                        else:
                            ar_code = _acc_override('AR', CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141'))
                    except Exception:
                        ar_code = CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141')
                    try:
                        _create_receipt_journal(inv.date, amt, inv.invoice_number, ar_code, payment_method or 'CASH', invoice_id=inv.id)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                _archive_invoice_pdf(inv)
            except Exception as e:
                current_app.logger.error('Archive PDF failed: %s', e)

        # Clear draft to free the table and update DB table status to available
        if branch and table:
            kv_set(f'draft:{branch}:{table}', {'draft_id': f'{branch}:{table}', 'items': []})
            try:
                from models import Table
                t = Table.query.filter_by(branch_code=branch, table_number=str(table)).first()
                if t:
                    t.status = 'available'
                    t.updated_at = get_saudi_now()
                    db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'success': True})


@bp.route('/api/sales/mark-unpaid-paid', methods=['POST'], endpoint='api_sales_mark_unpaid_paid')
@login_required
def api_sales_mark_unpaid_paid():
    try:
        from models import SalesInvoice, Payment
        from sqlalchemy import func
        q = SalesInvoice.query
        # Only consider invoices not marked as paid
        q = q.filter(func.lower(SalesInvoice.status) != 'paid') if hasattr(SalesInvoice, 'status') else q
        rows = q.order_by(SalesInvoice.date.desc()).limit(5000).all()
        updated = 0
        for inv in (rows or []):
            try:
                total = float(getattr(inv, 'total_after_tax_discount', 0) or 0)
                paid_sum = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                                 .filter(Payment.invoice_type == 'sales', Payment.invoice_id == inv.id)
                                 .scalar() or 0.0)
                remaining = max(total - paid_sum, 0.0)
                if remaining <= 0:
                    inv.status = 'paid'
                    db.session.commit()
                    updated += 1
                    continue
                pm = (getattr(inv, 'payment_method', '') or 'CASH').strip().upper()
                db.session.add(Payment(
                    invoice_id=inv.id,
                    invoice_type='sales',
                    amount_paid=remaining,
                    payment_method=pm,
                    payment_date=get_saudi_now()
                ))
                inv.status = 'paid'
                db.session.commit()
                # Post payment ledger: DR Cash/Bank, CR AR
                try:
                    ar_code = CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141')
                    _create_receipt_journal(inv.date, remaining, inv.invoice_number, ar_code, pm or 'CASH', invoice_id=inv.id)
                except Exception:
                    pass
                updated += 1
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        return jsonify({'ok': True, 'updated': updated})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400



@bp.route('/api/sales/mark-platform-unpaid', methods=['GET','POST'], endpoint='api_sales_mark_platform_unpaid')

@bp.route('/api/sales/mark-platform-unpaid/', methods=['GET','POST'])
@login_required
def api_sales_mark_platform_unpaid():
    try:
        from models import SalesInvoice, Payment
        q = SalesInvoice.query
        rows = q.order_by(SalesInvoice.date.desc()).limit(3000).all()
        updated = 0
        for inv in (rows or []):
            grp = _norm_group(getattr(inv, 'customer_name', '') or '')
            if grp in ('keeta','hunger'):
                try:
                    Payment.query.filter(Payment.invoice_type=='sales', Payment.invoice_id==inv.id).delete(synchronize_session=False)
                except Exception:
                    pass
                try:
                    inv.status = 'unpaid'
                    db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                updated += 1
        return jsonify({'ok': True, 'updated': updated})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400


@bp.route('/api/sales/batch-pay', methods=['GET','POST'], endpoint='api_sales_batch_pay')

@bp.route('/api/sales/batch-pay/', methods=['GET','POST'])
@login_required
def api_sales_batch_pay():
    try:
        from models import SalesInvoice, Payment
        payload = request.get_json(silent=True) or {}
        customer = (request.form.get('customer') or payload.get('customer') or 'all').strip().lower()
        method = (request.form.get('payment_method') or payload.get('payment_method') or 'CASH').strip().upper()
        limit = int((request.form.get('limit') or payload.get('limit') or 3000))
        def _norm_group(n: str):
            s = (n or '').lower()
            if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                return 'hunger'
            if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                return 'keeta'
            return ''
        q = SalesInvoice.query
        # Consider only not-paid invoices
        try:
            q = q.filter(func.lower(SalesInvoice.status) != 'paid')
        except Exception:
            pass
        rows = q.order_by(SalesInvoice.date.desc()).limit(limit).all()
        updated = 0
        for inv in (rows or []):
            grp = _platform_group(getattr(inv, 'customer_name', '') or '')
            if customer not in ('all','') and grp != customer:
                continue
            # Compute remaining
            total = float(getattr(inv, 'total_after_tax_discount', 0.0) or 0.0)
            paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                         .filter(Payment.invoice_type == 'sales', Payment.invoice_id == inv.id)
                         .scalar() or 0.0)
            remaining = max(total - paid, 0.0)
            if remaining <= 0:
                try:
                    inv.status = 'paid'
                    db.session.commit()
                except Exception:
                    try: db.session.rollback()
                    except Exception: pass
                continue
            try:
                db.session.add(Payment(
                    invoice_id=inv.id,
                    invoice_type='sales',
                    amount_paid=remaining,
                    payment_method=method,
                    payment_date=get_saudi_now()
                ))
                inv.status = 'paid'
                db.session.commit()
                # Post payment ledger: DR Cash/Bank, CR AR (platform-specific when applicable)
                cash_acc = _pm_account(method)
                try:
                    cust = (getattr(inv, 'customer_name', '') or '').lower()
                    grp = _platform_group(cust)
                    if grp == 'keeta':
                        ar_code = _acc_override('AR_KEETA', SHORT_TO_NUMERIC['AR_KEETA'][0])
                    elif grp == 'hunger':
                        ar_code = _acc_override('AR_HUNGER', SHORT_TO_NUMERIC['AR_HUNGER'][0])
                    else:
                        ar_code = _acc_override('AR', CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141'))
                except Exception:
                    ar_code = CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141')
                try:
                    _create_receipt_journal(inv.date, remaining, inv.invoice_number, ar_code, method or 'CASH', invoice_id=inv.id)
                except Exception:
                    pass
                updated += 1
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        return jsonify({'ok': True, 'updated': updated})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400


@bp.route('/api/invoice/print-log', methods=['POST'], endpoint='api_invoice_print_log')
@login_required
def api_invoice_print_log():
    try:
        payload = request.get_json(force=True) or {}
        invoice_id = (payload.get('invoice_id') or '').strip()
        if not invoice_id:
            return jsonify({'ok': False, 'error': 'missing_invoice_id'}), 400
        key = f"print_log:{invoice_id}"
        logs = kv_get(key, []) or []
        logs.append({'ts': get_saudi_now().isoformat(), 'user_id': int(getattr(current_user, 'id', 0) or 0)})
        kv_set(key, logs)
        return jsonify({'ok': True, 'count': len(logs)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500



@bp.route('/api/sales/void-check', methods=['POST'], endpoint='api_sales_void_check')
@login_required
def api_sales_void_check():
    payload = request.get_json(force=True) or {}
    ok = (str(payload.get('password') or '').strip() == '1991')
    return jsonify({'ok': ok})








# ---- Print routes for sales receipts ----

@bp.route('/invoice/print/<invoice_id>', methods=['GET'], endpoint='invoice_print')
@login_required
def invoice_print(invoice_id):
    """
    New standalone invoice print page for issued invoices
    This is a read-only print view that opens in a new window
    """
    # Find invoice by ID or invoice number
    inv = None
    try:
        inv = SalesInvoice.query.get(int(invoice_id))
    except Exception:
        inv = SalesInvoice.query.filter_by(invoice_number=str(invoice_id)).first()
    
    if not inv:
        return 'Invoice not found', 404
    
    st = (inv.status or '').lower()
    if st not in ['issued', 'finalized', 'paid', 'unpaid', 'partial']:
        return 'Invoice not issued yet', 403
    
    items = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).all()
    
    # Prepare items context
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
        'status': inv.status.upper(),
        'total_before_tax': float(inv.total_before_tax or 0.0),
        'tax_amount': float(inv.tax_amount or 0.0),
        'discount_amount': float(inv.discount_amount or 0.0),
        'total_after_tax_discount': float(inv.total_after_tax_discount or 0.0),
        'branch': getattr(inv, 'branch', None),
        'branch_code': getattr(inv, 'branch', None),
    }
    
    try:
        s = Settings.query.first()
    except Exception:
        s = None
        
    branch_name = BRANCH_LABELS.get(getattr(inv, 'branch', None) or '', getattr(inv, 'branch', ''))
    try:
        if inv.created_at:
            base_dt = inv.created_at
            if getattr(base_dt, 'tzinfo', None):
                dt_str = base_dt.astimezone(KSA_TZ).strftime('%Y-%m-%d %H:%M:%S')
            else:
                try:
                    dt_str = base_dt.replace(tzinfo=_pytz.UTC).astimezone(KSA_TZ).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    dt_str = KSA_TZ.localize(base_dt).strftime('%Y-%m-%d %H:%M:%S')
        else:
            dt_str = get_saudi_now().strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        dt_str = get_saudi_now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Prepare embedded logo as data URL for thermal printing
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
    
    # Generate ZATCA-compliant QR
    qr_data_url = None
    try:
        from utils.qr import generate_zatca_qr_from_invoice
        b64 = generate_zatca_qr_from_invoice(inv, s, None)
        if b64:
            qr_data_url = 'data:image/png;base64,' + b64
    except Exception:
        qr_data_url = None
    
    # Render standalone print template
    return render_template('print/invoice_print.html', 
                         inv=inv_ctx, 
                         items=items_ctx,
                         settings=s, 
                         branch_name=branch_name, 
                         date_time=dt_str,
                         display_invoice_number=inv.invoice_number,
                         qr_data_url=qr_data_url,
                         logo_data_url=logo_data_url,
                         paid=(inv.status in ['paid', 'finalized']))




# ---- Customers: POS-friendly search alias and AJAX create ----



@bp.route('/api/table-layout/<branch_code>', methods=['GET', 'POST'], endpoint='api_table_layout_fixed')
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

@bp.route('/api/sales/cash_total', methods=['GET'], endpoint='api_sales_cash_total')
@login_required
def api_sales_cash_total():
    try:
        start_arg = (request.args.get('start_date') or '').strip()
        end_arg = (request.args.get('end_date') or '').strip()
        branch = (request.args.get('branch') or '').strip()
        from datetime import datetime as _dt
        today = get_saudi_now().date()
        if start_arg and end_arg:
            try:
                sd = _dt.strptime(start_arg, '%Y-%m-%d').date()
                ed = _dt.strptime(end_arg, '%Y-%m-%d').date()
            except Exception:
                sd = today.replace(day=1)
                ed = today
        else:
            sd = today.replace(day=1)
            ed = today
        from models import Payment, SalesInvoice
        q = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).\
            join(SalesInvoice, Payment.invoice_id == SalesInvoice.id).\
            filter(Payment.invoice_type == 'sales', Payment.payment_method == 'CASH')
        # Payment.payment_date may be nullable; fallback to SalesInvoice.date
        q = q.filter(or_(Payment.payment_date.between(sd, ed), SalesInvoice.date.between(sd, ed)))
        if branch in ('china_town','place_india'):
            q = q.filter(SalesInvoice.branch == branch)
        amt = float(q.scalar() or 0.0)
        return jsonify({'ok': True, 'start_date': sd.isoformat(), 'end_date': ed.isoformat(), 'branch': branch or 'all', 'amount': round(amt, 2)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/sales/pay', methods=['POST'], endpoint='api_sales_pay')
@login_required
def api_sales_pay():
    try:
        from models import SalesInvoice, Payment
        from sqlalchemy import func
        payload = request.get_json(silent=True) or {}
        invoice_id = request.form.get('invoice_id') or payload.get('invoice_id')
        amount = request.form.get('amount') or payload.get('amount')
        method = (request.form.get('payment_method') or payload.get('payment_method') or 'CASH').strip().upper()
        try:
            inv_id = int(invoice_id)
            amt = float(amount or 0)
        except Exception:
            return jsonify({'ok': False, 'error': 'invalid_parameters'}), 400
        if amt <= 0:
            return jsonify({'ok': False, 'error': 'amount_must_be_positive'}), 400
        inv = SalesInvoice.query.get(inv_id)
        if not inv:
            return jsonify({'ok': False, 'error': 'invoice_not_found'}), 404
        total = float(getattr(inv, 'total_after_tax_discount', 0.0) or 0.0)
        paid_before = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                           .filter(Payment.invoice_type == 'sales', Payment.invoice_id == inv.id)
                           .scalar() or 0.0)
        remaining = max(total - paid_before, 0.0)
        pay_amount = amt if amt < remaining else remaining
        if pay_amount <= 0:
            try:
                inv.status = 'paid'
                db.session.commit()
            except Exception:
                try: db.session.rollback()
                except Exception: pass
            return jsonify({'ok': True, 'paid': paid_before, 'remaining': 0.0, 'status': getattr(inv,'status','paid')})
        try:
            db.session.add(Payment(invoice_id=inv.id, invoice_type='sales', amount_paid=pay_amount, payment_method=method, payment_date=get_saudi_now()))
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'ok': False, 'error': 'db_error'}), 500
        paid_after = paid_before + pay_amount
        try:
            if paid_after >= total and total > 0:
                inv.status = 'paid'
            elif paid_after > 0:
                inv.status = 'partial'
            else:
                inv.status = 'unpaid'
            db.session.commit()
        except Exception:
            try: db.session.rollback()
            except Exception: pass
        try:
            ar_code = CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141')
            _create_receipt_journal(inv.date, pay_amount, inv.invoice_number, ar_code, method or 'CASH', invoice_id=inv.id)
        except Exception:
            pass
        return jsonify({'ok': True, 'invoice_id': inv.id, 'paid': paid_after, 'remaining': max(total - paid_after, 0.0), 'status': getattr(inv,'status','paid')})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# === Helpers for thermal receipt: branch name and logo from settings ===
def _receipt_branch_name_and_logo_url(branch_code, settings):
    """Return (branch_display_name, logo_url) from settings for the given branch."""
    bc = (branch_code or '').strip().lower()
    branch_name = BRANCH_LABELS.get(bc, bc or '')
    logo_url = None
    if settings:
        if ('place' in bc or 'india' in bc) and getattr(settings, 'place_india_label', None):
            branch_name = (settings.place_india_label or '').strip() or branch_name
        elif bc.startswith('china') and getattr(settings, 'china_town_label', None):
            branch_name = (settings.china_town_label or '').strip() or branch_name
        if ('place' in bc or 'india' in bc) and getattr(settings, 'place_india_logo_url', None):
            logo_url = (settings.place_india_logo_url or '').strip() or None
        elif bc.startswith('china') and getattr(settings, 'china_town_logo_url', None):
            logo_url = (settings.china_town_logo_url or '').strip() or None
        if not logo_url and getattr(settings, 'logo_url', None):
            logo_url = (settings.logo_url or '').strip() or None
    return branch_name, logo_url


def _logo_path_to_data_url(url, app):
    """Read logo file from url path (/static/... or /uploads/...) and return data URL or None."""
    if not url or not app:
        return None
    url = (url or '').strip()
    fpath = None
    if url.startswith('/static/'):
        rel = url.split('/static/', 1)[1]
        fpath = os.path.join(app.static_folder, rel)
    elif url.startswith('/uploads/'):
        upload_dir = os.getenv('UPLOAD_DIR') or os.path.join(app.static_folder, 'uploads')
        rel = url.split('/uploads/', 1)[1]
        fpath = os.path.join(upload_dir, rel)
    if not fpath or not os.path.exists(fpath):
        return None
    try:
        with open(fpath, 'rb') as f:
            b = f.read()
        mime = mimetypes.guess_type(fpath)[0] or 'image/png'
        return f'data:{mime};base64,' + base64.b64encode(b).decode('ascii')
    except Exception:
        return None


# === Print Routes ===
@bp.route('/print/receipt/<invoice_number>', methods=['GET'], endpoint='print_receipt')
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
        'branch': getattr(inv, 'branch', None),
        'branch_code': getattr(inv, 'branch', None),
    }
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    branch_code = getattr(inv, 'branch', None) or ''
    branch_name, _logo_url = _receipt_branch_name_and_logo_url(branch_code, s)
    # Use first print timestamp if available; fallback to archive saved_at or invoice.created_at
    dt_str = None
    try:
        logs = kv_get(f"print_log:{inv.invoice_number}", []) or []
    except Exception:
        logs = []
    try:
        if logs:
            from datetime import datetime as _dti
            def _p(x):
                try:
                    return _dti.fromisoformat((x or {}).get('ts') or '')
                except Exception:
                    return None
            cand = [_p(x) for x in logs]
            cand = [c for c in cand if c]
            if cand:
                dtp = min(cand)
                dt_str = dtp.strftime('%H:%M:%S %Y-%m-%d')
    except Exception:
        dt_str = None
    if not dt_str:
        try:
            meta = kv_get(f"pdf_path:sales:{inv.invoice_number}", {}) or {}
            sa = meta.get('saved_at')
            if sa:
                from datetime import datetime as _dti
                try:
                    dtp = _dti.fromisoformat(sa)
                    dt_str = dtp.strftime('%H:%M:%S %Y-%m-%d')
                except Exception:
                    dt_str = None
        except Exception:
            dt_str = None
    if not dt_str:
        try:
            from models import Payment
            dtp_row = db.session.query(Payment.payment_date).\
                filter(Payment.invoice_type == 'sales', Payment.invoice_id == inv.id).\
                order_by(Payment.payment_date.asc()).first()
            if dtp_row and dtp_row[0]:
                dt_str = dtp_row[0].strftime('%H:%M:%S %Y-%m-%d')
        except Exception:
            pass
    if not dt_str:
        try:
            if getattr(inv, 'created_at', None):
                dt_str = inv.created_at.strftime('%H:%M:%S %Y-%m-%d')
            else:
                dt_str = get_saudi_now().strftime('%H:%M:%S %Y-%m-%d')
        except Exception:
            dt_str = get_saudi_now().strftime('%H:%M:%S %Y-%m-%d')
    # Prepare embedded logo from branch-specific or global settings for thermal printing
    logo_data_url = None
    try:
        logo_url_to_use = _logo_url or (s and (getattr(s, 'logo_url', None) or '').strip()) or None
        if s and getattr(s, 'receipt_show_logo', False) and logo_url_to_use:
            logo_data_url = _logo_path_to_data_url(logo_url_to_use, current_app)
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



@bp.route('/sales/<int:invoice_id>/print', methods=['GET'], endpoint='sales_receipt_by_id')
@login_required
def print_sales_receipt_by_id(invoice_id):
    """Receipt-style print for a single sales invoice by ID (for invoices list / reports)."""
    inv = SalesInvoice.query.get_or_404(invoice_id)
    items = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).all()
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
        'table_number': getattr(inv, 'table_number', None),
        'customer_name': getattr(inv, 'customer_name', '') or '',
        'customer_phone': getattr(inv, 'customer_phone', '') or '',
        'payment_method': (inv.payment_method or 'CASH').strip().upper(),
        'status': 'PAID',
        'total_before_tax': float(inv.total_before_tax or 0.0),
        'tax_amount': float(inv.tax_amount or 0.0),
        'discount_amount': float(inv.discount_amount or 0.0),
        'total_after_tax_discount': float(inv.total_after_tax_discount or 0.0),
        'branch': getattr(inv, 'branch', None),
        'branch_code': getattr(inv, 'branch', None),
    }
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    branch_code = getattr(inv, 'branch', None) or ''
    branch_name, _logo_url = _receipt_branch_name_and_logo_url(branch_code, s)
    try:
        dt_str = (inv.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(inv, 'created_at', None) else get_saudi_now().strftime('%Y-%m-%d %H:%M:%S'))
    except Exception:
        dt_str = get_saudi_now().strftime('%Y-%m-%d %H:%M:%S')
    logo_data_url = None
    try:
        logo_url_to_use = _logo_url or (s and (getattr(s, 'logo_url', None) or '').strip()) or None
        if s and getattr(s, 'receipt_show_logo', False) and logo_url_to_use:
            logo_data_url = _logo_path_to_data_url(logo_url_to_use, current_app)
    except Exception:
        pass
    qr_data_url = None
    try:
        from utils.qr import generate_zatca_qr_from_invoice
        b64 = generate_zatca_qr_from_invoice(inv, s, None)
        if b64:
            qr_data_url = 'data:image/png;base64,' + b64
    except Exception:
        pass
    return render_template('print/receipt.html', inv=inv_ctx, items=items_ctx,
                           settings=s, branch_name=branch_name, date_time=dt_str,
                           display_invoice_number=inv.invoice_number,
                           qr_data_url=qr_data_url,
                           logo_data_url=logo_data_url,
                           paid=True)


@bp.route('/print/order-preview/<branch>/<int:table>', methods=['GET'], endpoint='print_order_preview')
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
    discount_amount = subtotal * (discount_pct/100.0)
    taxable_amount = max(subtotal - discount_amount, 0.0)
    vat_amount = taxable_amount * (tax_pct/100.0)
    total_after = taxable_amount + vat_amount

    # Resolve payment method from draft if chosen in POS
    try:
        pm_raw = (rec.get('payment_method') or '').strip()
    except Exception:
        pm_raw = ''
    inv_ctx = {
        'invoice_number': '',  # no real invoice number for preview
        'table_number': table,
        'customer_name': (rec.get('customer') or {}).get('name') or '',
        'customer_phone': (rec.get('customer') or {}).get('phone') or '',
        'payment_method': pm_raw.upper() if pm_raw else '',
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
    branch_name, _logo_url_preview = _receipt_branch_name_and_logo_url(branch, s)
    dt_str = get_saudi_now().strftime('%Y-%m-%d %H:%M:%S')
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
            get_saudi_now(),
            float(total_after),
            float(vat_amount)
        )
        if b64:
            qr_data_url = 'data:image/png;base64,' + b64
    except Exception:
        qr_data_url = None
    logo_data_url = None
    try:
        logo_url_to_use = _logo_url_preview or (s and (getattr(s, 'logo_url', None) or '').strip()) or None
        if s and getattr(s, 'receipt_show_logo', False) and logo_url_to_use:
            logo_data_url = _logo_path_to_data_url(logo_url_to_use, current_app)
    except Exception:
        pass

    return render_template('print/receipt.html', inv=inv_ctx, items=items_ctx,
                           settings=s, branch_name=branch_name, date_time=dt_str,
                           display_invoice_number=order_no,
                           qr_data_url=qr_data_url,
                           logo_data_url=logo_data_url,
                           paid=False)



@bp.route('/print/order-slip/<branch>/<int:table>', methods=['GET'], endpoint='print_order_slip')
@login_required
def print_order_slip(branch, table):
    rec = kv_get(f'draft:{branch}:{table}', {}) or {}
    raw_items = rec.get('items') or []
    items_ctx = []
    subtotal = 0.0
    for it in raw_items:
        meal_id = it.get('meal_id') or it.get('id')
        qty = float(it.get('qty') or it.get('quantity') or 1)
        name = it.get('name') or ''
        price = it.get('price') or 0.0
        if (not name) or ((not price) and meal_id):
            m = MenuItem.query.get(int(meal_id))
            if m:
                name = name or m.name
                price = price or float(m.price)
        line = float(price or 0) * qty
        subtotal += line
        items_ctx.append({'product_name': name, 'quantity': qty, 'unit_price': float(price or 0), 'discount': 0.0, 'tax': 0.0, 'line_total': line})
    tax_pct = float(rec.get('tax_pct') or 15)
    discount_pct = float(rec.get('discount_pct') or 0)
    discount_amount = subtotal * (discount_pct/100.0)
    taxable_amount = max(subtotal - discount_amount, 0.0)
    vat_amount = taxable_amount * (tax_pct/100.0)
    total_after = taxable_amount + vat_amount
    order_seq = None
    today_str = get_saudi_now().date().isoformat()
    rec_seq_date = (rec.get('order_seq_date') or '') if isinstance(rec, dict) else ''
    try:
        order_seq = rec.get('order_seq')
    except Exception:
        order_seq = None
    if not order_seq or rec_seq_date != today_str:
        key = f"order_seq:{today_str}"
        cur = kv_get(key, 1) or 1
        order_seq = int(cur)
        kv_set(key, order_seq + 1)
        rec['order_seq'] = order_seq
        rec['order_seq_date'] = today_str
        kv_set(f'draft:{branch}:{table}', rec)
    branch_name = BRANCH_LABELS.get(branch, branch)
    dt_str = get_saudi_now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        s = Settings.query.first()
    except Exception:
        s = None
    cust = rec.get('customer') or {}
    payment_method = (rec.get('payment_method') or '').strip()
    return render_template('print/order_slip.html',
                           order_number=order_seq,
                           branch_code=branch,
                           branch_name=branch_name,
                           table_number=table,
                           date_time=dt_str,
                           items=items_ctx,
                           subtotal=round(subtotal, 2),
                           discount=round(discount_amount, 2),
                           discount_pct=round(discount_pct, 2),
                           vat=round(vat_amount, 2),
                           tax_pct=round(tax_pct, 2),
                           total=round(total_after, 2),
                           customer_name=(cust.get('name') or ''),
                           customer_phone=(cust.get('phone') or ''),
                           payment_method=payment_method,
                           settings=s)

