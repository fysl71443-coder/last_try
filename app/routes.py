import json
import os
from datetime import datetime, date, timedelta
from datetime import date as _date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory, send_file, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, inspect, text, or_
from sqlalchemy.exc import IntegrityError

from app import db, csrf
from app import __init__ as app_init  # for template globals, including can()
try:
    from flask_babel import gettext as _
except Exception:
    _ = lambda s, **kwargs: (s.format(**kwargs) if kwargs else s)
ext_db = None
from app.models import AppKV, TableLayout
from models import User
from models import OrderInvoice
from models import MenuCategory, MenuItem, SalesInvoice, SalesInvoiceItem, Customer, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Settings, Meal, MealIngredient, RawMaterial, Supplier, Employee, Salary, Payment, EmployeeSalaryDefault, DepartmentRate, EmployeeHours, Account, AccountUsageMap, LedgerEntry, JournalEntry, JournalLine, JournalAudit
from models import get_saudi_now, KSA_TZ
from forms import SalesInvoiceForm, EmployeeForm, ExpenseInvoiceForm, PurchaseInvoiceForm, MealForm, RawMaterialForm

main = Blueprint('main', __name__)


@main.route('/set_language')
def set_language():
    """تبديل لغة الواجهة (ar/en) وحفظها في الجلسة."""
    lang = (request.args.get('lang') or 'ar').strip().lower()
    if lang in ('ar', 'en'):
        session['locale'] = lang
    next_url = request.args.get('next') or request.referrer or url_for('main.dashboard')
    return redirect(next_url)


# --- Employees: Detailed Payroll Report (legacy; kept for compatibility) ---
@main.route('/employees/payroll/detailed', methods=['GET'], endpoint='payroll_detailed')
@login_required
def payroll_detailed():
    return ('', 404)






# Phase 2: shared helpers from routes.common (no accounts/settings/permissions here)
from routes.common import kv_get, kv_set, BRANCH_LABELS, safe_table_number, user_can

# Safe helper: current time in Saudi Arabia timezone
try:
    import pytz as _pytz
except Exception:  # pragma: no cover
    _pytz = None
from datetime import datetime as _dt

# use get_saudi_now from models

# ---------- Table status helpers (transactional & safe for concurrency) ----------
def _set_table_status_concurrent(branch_code: str, table_number: str, status: str) -> None:
    """Set a table's status with a short transaction and row-level lock.
    Creates the row if missing. Safe for concurrent updates under Postgres.
    """
    try:
        from models import Table
        tbl_no = str(table_number)
        # Short, isolated transaction
        with db.session.begin():
            # Lock the target row if exists; otherwise create
            t = (db.session.query(Table)
                 .with_for_update(of=Table, nowait=False)
                 .filter_by(branch_code=branch_code, table_number=tbl_no)
                 .first())
            if not t:
                t = Table(branch_code=branch_code, table_number=tbl_no, status=status)
                db.session.add(t)
            else:
                t.status = status
                t.updated_at = get_saudi_now()
    except Exception:
        # Do not propagate table-status errors to main flow
        try: db.session.rollback()
        except Exception: pass

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
        try:
            db.session.rollback()
        except Exception:
            pass
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

def ensure_account_extended_columns():
    try:
        from sqlalchemy import inspect, text
        insp = inspect(db.engine)
        cols = {c['name'] for c in insp.get_columns('accounts')}
        stmts = []
        def add(col_sql):
            try:
                stmts.append(text(col_sql))
            except Exception:
                pass
        if 'name_ar' not in cols:
            add("ALTER TABLE accounts ADD COLUMN name_ar VARCHAR(200)")
        if 'name_en' not in cols:
            add("ALTER TABLE accounts ADD COLUMN name_en VARCHAR(200)")
        if 'level' not in cols:
            add("ALTER TABLE accounts ADD COLUMN level INTEGER")
        if 'parent_account_code' not in cols:
            add("ALTER TABLE accounts ADD COLUMN parent_account_code VARCHAR(20)")
        if 'allow_opening_balance' not in cols:
            add("ALTER TABLE accounts ADD COLUMN allow_opening_balance BOOLEAN DEFAULT TRUE")
        if 'vat_link_code' not in cols:
            add("ALTER TABLE accounts ADD COLUMN vat_link_code VARCHAR(20)")
        if 'pos_mapping_key' not in cols:
            add("ALTER TABLE accounts ADD COLUMN pos_mapping_key VARCHAR(50)")
        if 'inventory_link' not in cols:
            add("ALTER TABLE accounts ADD COLUMN inventory_link BOOLEAN DEFAULT FALSE")
        if 'depreciation_policy_id' not in cols:
            add("ALTER TABLE accounts ADD COLUMN depreciation_policy_id INTEGER")
        if 'notes' not in cols:
            add("ALTER TABLE accounts ADD COLUMN notes TEXT")
        if 'active' not in cols:
            add("ALTER TABLE accounts ADD COLUMN active BOOLEAN DEFAULT TRUE")
        for s in stmts:
            try:
                db.session.execute(s)
            except Exception:
                pass
        if stmts:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

def ensure_user_2fa_columns():
    try:
        from sqlalchemy import inspect, text
        insp = inspect(db.engine)
        cols = {c['name'] for c in insp.get_columns('users')}
        stmts = []
        def add(col_sql):
            try:
                stmts.append(text(col_sql))
            except Exception:
                pass
        if 'twofa_enabled' not in cols:
            add("ALTER TABLE users ADD COLUMN twofa_enabled BOOLEAN DEFAULT FALSE")
        if 'twofa_secret' not in cols:
            add("ALTER TABLE users ADD COLUMN twofa_secret VARCHAR(64)")
        for s in stmts:
            try:
                db.session.execute(s)
            except Exception:
                pass
        if stmts:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

def ensure_journal_opening_columns():
    try:
        from sqlalchemy import inspect, text
        insp = inspect(db.engine)
        cols = {c['name'] for c in insp.get_columns('journal_entries')}
        stmts = []
        def add(col_sql):
            try:
                stmts.append(text(col_sql))
            except Exception:
                pass
        if 'opening_entry' not in cols:
            add("ALTER TABLE journal_entries ADD COLUMN opening_entry BOOLEAN DEFAULT FALSE")
        if 'source_ref_type' not in cols:
            add("ALTER TABLE journal_entries ADD COLUMN source_ref_type VARCHAR(50)")
        if 'source_ref_id' not in cols:
            add("ALTER TABLE journal_entries ADD COLUMN source_ref_id VARCHAR(100)")
        for s in stmts:
            try:
                db.session.execute(s)
            except Exception:
                pass
        if stmts:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def ensure_tables():
    try:
        db.create_all()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        pass
    # Ensure new columns exist for compatibility with older DBs
    ensure_menu_sort_order_column()
    ensure_menuitem_compat_columns()
    ensure_account_extended_columns()
    ensure_journal_opening_columns()
    ensure_user_2fa_columns()


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

def _norm_name(name: str) -> str:
    try:
        import re
        s = (name or '').strip().lower()
        s = re.sub(r'[\u064B-\u065F]', '', s)
        s = re.sub(r'\s+', ' ', s)
        s = re.sub(r'[^0-9a-z\u0621-\u064A ]+', '', s)
        return s
    except Exception:
        return (name or '').strip().lower()

def _account_type_map(t: str) -> str:
    s = (t or '').strip().upper()
    if s in ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE','COGS','COST'):
        return 'COGS' if s in ('COGS','COST') else s
    return 'EXPENSE'

def _bool(v):
    s = str(v).strip().lower()
    return s in ('1','true','yes','on','y','t')

@main.route('/api/coa', methods=['GET'])
@login_required
def api_coa_get():
    try:
        ensure_account_extended_columns()
        from utils.cache_helpers import get_cached_coa
        out = get_cached_coa()
        if out is None:
            try:
                db.session.rollback()
            except Exception:
                pass
            return jsonify({'ok': False, 'error': 'Failed to load COA'}), 500
        return jsonify({'ok': True, 'accounts': out})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/coa/import', methods=['POST'])
@login_required
def api_coa_import():
    try:
        from flask_login import current_user
        if not _has_role(current_user, ['admin','accountant']):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        ensure_account_extended_columns()
        from models import Account
        file = request.files.get('file')
        csv_text = request.form.get('csv')
        if not file and not csv_text:
            return jsonify({'ok': False, 'error': 'no_csv'}), 400
        import io, csv
        if file:
            content = file.read().decode('utf-8', errors='ignore')
        else:
            content = csv_text
        reader = csv.DictReader(io.StringIO(content))
        required = ['account_code','account_name_ar','account_name_en','account_type','level','parent_account_code','allow_opening_balance','vat_link_code','pos_mapping_key','inventory_link','depreciation_policy_id','notes']
        for r in required:
            if r not in reader.fieldnames:
                return jsonify({'ok': False, 'error': f'missing_column:{r}'}), 400
        # Build existing lookup
        existing = Account.query.all()
        by_code = { (a.code or '').strip(): a for a in existing }
        norm_names = { _norm_name(getattr(a,'name','') or getattr(a,'name_ar','') or getattr(a,'name_en','') or ''): a for a in existing }
        duplicates = []
        to_create = []
        to_update = []
        from difflib import SequenceMatcher
        for row in reader:
            code = (row.get('account_code') or '').strip()
            if not code:
                duplicates.append({'row': row, 'reason': 'empty_code'})
                continue
            name_ar = (row.get('account_name_ar') or '').strip()
            name_en = (row.get('account_name_en') or '').strip()
            name = name_ar or name_en or code
            atype = _account_type_map(row.get('account_type'))
            level = int((row.get('level') or 0) or 0)
            parent_code = (row.get('parent_account_code') or '').strip() or None
            allow_open = _bool(row.get('allow_opening_balance'))
            vat_link = (row.get('vat_link_code') or '').strip() or None
            pos_key = (row.get('pos_mapping_key') or '').strip() or None
            inv_link = _bool(row.get('inventory_link'))
            dep_id_raw = (row.get('depreciation_policy_id') or '').strip()
            try:
                dep_id = int(dep_id_raw) if dep_id_raw else None
            except Exception:
                dep_id = None
            notes = (row.get('notes') or '').strip() or None
            # Duplicate detection
            nm = _norm_name(name)
            similar = None
            for ex_nm, ex in norm_names.items():
                try:
                    ratio = SequenceMatcher(None, nm, ex_nm).ratio()
                except Exception:
                    ratio = 0.0
                if ratio >= 0.85 and (by_code.get(code) is None or by_code.get(code) is not ex):
                    similar = {'existing_code': ex.code, 'existing_name': getattr(ex,'name',None), 'similarity': round(ratio, 3)}
                    break
            if similar:
                duplicates.append({'row': {'code': code, 'name': name}, 'conflict': similar, 'reason': 'similar_name'})
                continue
            rec = by_code.get(code)
            if rec:
                to_update.append({'rec': rec, 'vals': {'name': name, 'name_ar': name_ar or None, 'name_en': name_en or None, 'type': atype, 'level': level or None, 'parent_account_code': parent_code, 'allow_opening_balance': allow_open, 'vat_link_code': vat_link, 'pos_mapping_key': pos_key, 'inventory_link': inv_link, 'depreciation_policy_id': dep_id, 'notes': notes}})
            else:
                to_create.append({'code': code, 'name': name, 'name_ar': name_ar or None, 'name_en': name_en or None, 'type': atype, 'level': level or None, 'parent_account_code': parent_code, 'allow_opening_balance': allow_open, 'vat_link_code': vat_link, 'pos_mapping_key': pos_key, 'inventory_link': inv_link, 'depreciation_policy_id': dep_id, 'notes': notes})
        if duplicates and not _bool(request.form.get('force')):
            return jsonify({'ok': False, 'duplicates': duplicates, 'hint': 'Use force=1 to override similar-name check'}), 409
        created = 0
        updated = 0
        # Apply updates
        for u in to_update:
            a = u['rec']
            v = u['vals']
            a.name = v['name']
            try:
                a.name_ar = v['name_ar']
                a.name_en = v['name_en']
                a.level = v['level']
                a.parent_account_code = v['parent_account_code']
                a.allow_opening_balance = v['allow_opening_balance']
                a.vat_link_code = v['vat_link_code']
                a.pos_mapping_key = v['pos_mapping_key']
                a.inventory_link = v['inventory_link']
                a.depreciation_policy_id = v['depreciation_policy_id']
                a.notes = v['notes']
                a.type = v['type']
            except Exception:
                pass
            updated += 1
        # Create new accounts
        for c in to_create:
            a = Account(code=c['code'], name=c['name'], type=c['type'])
            try:
                a.name_ar = c['name_ar']
                a.name_en = c['name_en']
                a.level = c['level']
                a.parent_account_code = c['parent_account_code']
                a.allow_opening_balance = c['allow_opening_balance']
                a.vat_link_code = c['vat_link_code']
                a.pos_mapping_key = c['pos_mapping_key']
                a.inventory_link = c['inventory_link']
                a.depreciation_policy_id = c['depreciation_policy_id']
                a.notes = c['notes']
            except Exception:
                pass
            db.session.add(a)
            db.session.flush()
            created += 1
        db.session.commit()
        try:
            from utils.cache_helpers import invalidate_coa_cache
            invalidate_coa_cache()
        except Exception:
            pass
        return jsonify({'ok': True, 'created': created, 'updated': updated, 'duplicates_skipped': len(duplicates)})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/opening-balances/import', methods=['POST'])
@login_required
def api_opening_import():
    try:
        from flask_login import current_user
        if not _has_role(current_user, ['admin','accountant']):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        ensure_account_extended_columns(); ensure_journal_opening_columns()
        from models import Account, JournalEntry, JournalLine
        file = request.files.get('file')
        csv_text = request.form.get('csv')
        dry_run = _bool(request.form.get('dry_run'))
        rollback = _bool(request.form.get('rollback'))
        partial = _bool(request.form.get('partial'))
        import io, csv, uuid
        if not file and not csv_text:
            return jsonify({'ok': False, 'error': 'no_csv'}), 400
        if file:
            content = file.read().decode('utf-8', errors='ignore')
        else:
            content = csv_text
        reader = csv.DictReader(io.StringIO(content))
        required = ['account_code','opening_debit','opening_credit','as_of_date','description','source_ref']
        for r in required:
            if r not in reader.fieldnames:
                return jsonify({'ok': False, 'error': f'missing_column:{r}'}), 400
        rows = []
        errors = []
        total_debit = 0.0
        total_credit = 0.0
        as_of = None
        for row in reader:
            code = (row.get('account_code') or '').strip()
            try:
                debit = float(row.get('opening_debit') or 0.0)
                credit = float(row.get('opening_credit') or 0.0)
            except Exception:
                debit = 0.0; credit = 0.0
            desc = (row.get('description') or '').strip()
            src = (row.get('source_ref') or '').strip()
            ds = (row.get('as_of_date') or '').strip()
            from datetime import datetime as _dt
            try:
                dt = _dt.strptime(ds, '%Y-%m-%d').date()
            except Exception:
                errors.append({'row': row, 'error': 'invalid_date'})
                dt = None
            as_of = as_of or dt
            acc = Account.query.filter(Account.code == code).first()
            if not acc:
                errors.append({'row': row, 'error': 'account_not_found'})
                if not partial:
                    continue
            rows.append({'account': acc, 'code': code, 'debit': debit, 'credit': credit, 'desc': desc, 'dt': dt, 'src': src})
            total_debit += float(debit or 0)
            total_credit += float(credit or 0)
        if not as_of:
            return jsonify({'ok': False, 'error': 'missing_as_of'}), 400
        # Idempotency / duplicate check
        exists = JournalEntry.query.filter(JournalEntry.date == as_of).filter(getattr(JournalEntry,'opening_entry', False) == True).all()
        if exists and not rollback and not dry_run:
            return jsonify({'ok': False, 'error': 'opening_exists', 'count': len(exists), 'hint': 'Use rollback=1 to remove existing opening entries for this date'}), 409
        if rollback:
            try:
                # Delete opening entries for this date
                for je in exists:
                    try:
                        JournalLine.query.filter(JournalLine.journal_id == je.id).delete(synchronize_session=False)
                    except Exception:
                        pass
                    db.session.delete(je)
                db.session.commit()
            except Exception:
                db.session.rollback()
        # Balance check
        if round(total_debit - total_credit, 2) != 0.0:
            return jsonify({'ok': False, 'error': 'unbalanced', 'total_debit': total_debit, 'total_credit': total_credit, 'diff': round(total_debit - total_credit, 2), 'errors': errors}), 400
        if dry_run:
            return jsonify({'ok': True, 'dry_run': True, 'rows': len(rows), 'total_debit': total_debit, 'total_credit': total_credit, 'errors': errors})
        # Create single opening journal entry
        ref_id = str(uuid.uuid4())[:8]
        entry_no = f"JE-OPEN-{as_of.strftime('%Y%m%d')}-{ref_id}"
        je = JournalEntry(entry_number=entry_no, date=as_of, branch_code=None, description=f"system:opening_import:{ref_id}", status='posted', total_debit=round(total_debit,2), total_credit=round(total_credit,2), created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
        try:
            db.session.add(je); db.session.flush()
            try:
                setattr(je, 'opening_entry', True)
                setattr(je, 'source_ref_type', 'opening_import')
                setattr(je, 'source_ref_id', ref_id)
                db.session.flush()
            except Exception:
                pass
        except Exception:
            db.session.rollback(); return jsonify({'ok': False, 'error': 'je_create_failed'}), 500
        ln = 0
        for r in rows:
            if not r['account']:
                continue
            ln += 1
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=r['account'].id, debit=r['debit'], credit=r['credit'], description=(r['desc'] or 'Opening balance'), line_date=as_of))
        db.session.commit()
        return jsonify({'ok': True, 'entry_number': entry_no, 'lines': ln, 'total_debit': total_debit, 'total_credit': total_credit, 'errors': errors})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/2fa/setup', methods=['POST'])
@login_required
def api_2fa_setup():
    try:
        ensure_user_2fa_columns()
        import base64, os
        user = current_user
        raw = os.urandom(10)
        secret = base64.b32encode(raw).decode('utf-8').strip().replace('=', '')
        try:
            user.twofa_secret = secret
            db.session.commit()
        except Exception:
            db.session.rollback()
        uri = f"otpauth://totp/{'CHINA_PLACE'}:{user.username}?secret={secret}&issuer={'CHINA_PLACE'}&digits=6&period=30"
        return jsonify({'ok': True, 'secret': secret, 'uri': uri})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/2fa/enable', methods=['POST'])
@login_required
def api_2fa_enable():
    try:
        ensure_user_2fa_columns()
        import base64, hmac, hashlib, time
        code = (request.form.get('code') or request.args.get('code') or '').strip()
        user = current_user
        sec = getattr(user,'twofa_secret', None) or ''
        if not sec:
            return jsonify({'ok': False, 'error': 'no_secret'}), 400
        def _totp_check(secret, code, window=1):
            try:
                key = base64.b32decode(secret.upper())
            except Exception:
                return False
            def _hotp(k, cnt):
                msg = cnt.to_bytes(8, 'big')
                h = hmac.new(k, msg, hashlib.sha1).digest()
                o = h[-1] & 0x0F
                bin_code = ((h[o] & 0x7f) << 24) | ((h[o+1] & 0xff) << 16) | ((h[o+2] & 0xff) << 8) | (h[o+3] & 0xff)
                return bin_code % 1000000
            t = int(time.time()) // 30
            for w in range(-window, window+1):
                if f"{_hotp(key, t+w):06d}" == str(code).zfill(6):
                    return True
            return False
        if not _totp_check(sec, code, 1):
            return jsonify({'ok': False, 'error': 'invalid_code'}), 400
        try:
            user.twofa_enabled = True
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/2fa/disable', methods=['POST'])
@login_required
def api_2fa_disable():
    try:
        ensure_user_2fa_columns()
        user = current_user
        try:
            user.twofa_enabled = False
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/sync/pos', methods=['POST'])
@login_required
def api_sync_pos():
    try:
        from datetime import datetime as _dt
        start_s = (request.args.get('start') or request.form.get('start') or '').strip()
        end_s = (request.args.get('end') or request.form.get('end') or '').strip()
        from models import SalesInvoice
        start = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _dt(get_saudi_now().year, 10, 1).date()
        end = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else get_saudi_now().date()
        rows = SalesInvoice.query.filter(SalesInvoice.date.between(start, end)).all()
        from flask import current_app
        created = 0; skipped = 0
        for s in rows:
            lines = s.to_journal_entries()
            payload = {'entries': [{'date': str(s.date or get_saudi_now().date()), 'description': f"Sales {s.invoice_number}", 'branch': getattr(s,'branch',None), 'source_ref_type': 'sales', 'source_ref_id': str(int(getattr(s,'id',0) or 0)), 'lines': lines}]}
            with current_app.test_request_context():
                try:
                    from routes.journal import api_transactions_post
                    resp = api_transactions_post()
                    if hasattr(resp, 'json'):
                        j = resp.json
                        if j and j.get('ok'): created += 1
                        else: skipped += 1
                    else:
                        created += 1
                except Exception:
                    skipped += 1
        return jsonify({'ok': True, 'synced': created, 'skipped': skipped})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/sync/zatca', methods=['POST'])
@login_required
def api_sync_zatca():
    # Outgoing invoices are SalesInvoice; reuse POS sync
    return api_sync_pos()

@main.route('/api/sync/payroll', methods=['POST'])
@login_required
def api_sync_payroll():
    try:
        from datetime import datetime as _dt
        start_s = (request.args.get('start') or request.form.get('start') or '').strip()
        end_s = (request.args.get('end') or request.form.get('end') or '').strip()
        from models import Salary
        start = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _dt(get_saudi_now().year, 10, 1).date()
        end = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else get_saudi_now().date()
        rows = Salary.query.all()
        created = 0; skipped = 0
        from flask import current_app
        for s in rows:
            lines = s.to_journal_entries()
            payload = {'entries': [{'date': f"{s.year}-{int(s.month):02d}-01", 'description': f"Payroll {s.year}-{int(s.month):02d}", 'branch': None, 'source_ref_type': 'salary', 'source_ref_id': str(int(getattr(s,'id',0) or 0)), 'lines': lines}]}
            with current_app.test_request_context():
                try:
                    from routes.journal import api_transactions_post
                    resp = api_transactions_post()
                    if hasattr(resp, 'json'):
                        j = resp.json
                        if j and j.get('ok'): created += 1
                        else: skipped += 1
                    else:
                        created += 1
                except Exception:
                    skipped += 1
        return jsonify({'ok': True, 'synced': created, 'skipped': skipped})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/sync/inventory', methods=['POST'])
@login_required
def api_sync_inventory():
    try:
        # Placeholder — inventory moves not modeled; return OK
        return jsonify({'ok': True, 'synced': 0})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/jobs/daily_sync', methods=['POST'])
@login_required
def api_jobs_daily_sync():
    try:
        r1 = api_sync_pos(); r2 = api_sync_zatca(); r3 = api_sync_inventory(); r4 = api_sync_payroll()
        return jsonify({'ok': True, 'pos': getattr(r1, 'json', None), 'zatca': getattr(r2, 'json', None), 'inventory': getattr(r3, 'json', None), 'payroll': getattr(r4, 'json', None)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/jobs/monthly_reconcile', methods=['POST'])
@login_required
def api_jobs_monthly_reconcile():
    try:
        start = request.args.get('start'); end = request.args.get('end')
        with current_app.test_request_context(f"/journal/api/reconcile/vat?start={start}&end={end}"):
            from routes.journal import api_reconcile_vat
            res = api_reconcile_vat()
        return jsonify({'ok': True, 'vat': getattr(res, 'json', None)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# Warmup DB only once per process to avoid heavy create_all/seed on hot paths
_DB_WARMED_UP = False

def warmup_db_once():
    global _DB_WARMED_UP
    if _DB_WARMED_UP:
        return
    try:
        ensure_tables()
        ensure_purchaseinvoice_compat_columns()
        seed_menu_if_empty()
        seed_chart_of_accounts()
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

@main.route('/login', methods=['GET', 'POST'])
def login():
    # Ensure DB tables exist on first local run to avoid 'no such table: user'
    try:
        ensure_tables()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        pass
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = (request.form.get('password') or '').strip()
        user = None
        if username:
            try:
                user = User.query.filter(func.lower(User.username) == username.lower()).first()
            except Exception:
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
                    flash(_('تم إنشاء مستخدم المدير الافتراضي بنجاح'), 'success')
                    return redirect(url_for('main.dashboard'))
                except Exception:
                    db.session.rollback()
                    flash(_('خطأ في تهيئة المستخدم الافتراضي'), 'danger')

        if user and password and user.check_password(password):
            try:
                ensure_user_2fa_columns()
                use_2fa = bool(getattr(user,'twofa_enabled', False)) and ((getattr(user,'role','') or '').lower() in ('admin','accountant'))
            except Exception:
                use_2fa = False
            if use_2fa:
                otp = (request.form.get('otp') or '').strip()
                if not otp:
                    flash(_('أدخل رمز التحقق الثنائي 2FA'), 'warning')
                    return render_template('login.html')
                try:
                    import base64, hmac, hashlib, time
                    sec = getattr(user,'twofa_secret', None) or ''
                    if not sec:
                        flash(_('لم يتم إعداد 2FA لهذا المستخدم'), 'danger')
                        return render_template('login.html')
                    def _totp_check(secret, code, window=1):
                        try:
                            key = base64.b32decode(secret.upper())
                        except Exception:
                            return False
                        def _hotp(k, cnt):
                            msg = cnt.to_bytes(8, 'big')
                            h = hmac.new(k, msg, hashlib.sha1).digest()
                            o = h[-1] & 0x0F
                            bin_code = ((h[o] & 0x7f) << 24) | ((h[o+1] & 0xff) << 16) | ((h[o+2] & 0xff) << 8) | (h[o+3] & 0xff)
                            return bin_code % 1000000
                        t = int(time.time()) // 30
                        for w in range(-window, window+1):
                            if f"{_hotp(key, t+w):06d}" == str(code).zfill(6):
                                return True
                        return False
                    if not _totp_check(sec, otp, 1):
                        flash(_('رمز 2FA غير صحيح'), 'danger')
                        return render_template('login.html')
                except Exception:
                    flash(_('حدث خطأ في التحقق الثنائي'), 'danger')
                    return render_template('login.html')
            remember = request.form.get('remember') in ('on', '1', 'true', 'yes')
            login_user(user, remember=remember)
            return redirect(url_for('main.dashboard'))
        else:
            flash(_('خطأ في اسم المستخدم أو كلمة المرور'), 'danger')
    return render_template('login.html')

@main.route('/debug/db', methods=['GET'], endpoint='debug_db')
def debug_db():
    try:
        uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    except Exception:
        uri = None
    try:
        cnt = int(User.query.count())
    except Exception:
        cnt = -1
    return jsonify({'uri': uri, 'users_count': cnt})

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


# ---------- Main application pages (simple render-only) ----------
@main.route('/dashboard', endpoint='dashboard')
@login_required
def dashboard():
    # Hub only: no heavy queries. Dashboard = gateway via cards.
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
        flash(_('Failed to load order invoices'), 'danger')
        return render_template('order_invoices.html', orders=[], totals={'subtotal_sum':0,'discount_sum':0,'vat_sum':0,'total_sum':0}, items_summary=[])

@main.route('/orders/clear', methods=['POST'], endpoint='order_invoices_clear_all')
@login_required
def order_invoices_clear_all():
    try:
        from models import OrderInvoice
        num = db.session.query(OrderInvoice).delete(synchronize_session=False)
        db.session.commit()
        try:
            flash(_('تم حذف %(num)s من فواتير الطلبات نهائياً', num=num), 'success')
        except Exception:
            flash(_('تم حذف جميع فواتير الطلبات نهائياً'), 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error('order_invoices_clear_all error: %s', e)
        flash(_('فشل حذف فواتير الطلبات'), 'danger')
    return redirect(url_for('main.order_invoices_list'))

@main.route('/invoices', endpoint='invoices')
@login_required
def invoices():
    t = (request.args.get('type') or 'sales').strip().lower()
    if t not in ('sales','purchases','expenses','all'):
        t = 'sales'

    # Build invoices list for template to render checkboxes and actions
    invoices = []
    try:
        # Helper to compute paid sum
        def paid_sum(kind: str, ids: list):
            if not ids:
                return {}
            rows = db.session.query(
                Payment.invoice_id,
                func.coalesce(func.sum(Payment.amount_paid), 0)
            ).filter(
                Payment.invoice_type == kind,
                Payment.invoice_id.in_(ids)
            ).group_by(Payment.invoice_id).all()
            return {int(i): float(p or 0.0) for i, p in rows}

        if t in ('all', 'sales'):
            try:
                sales = SalesInvoice.query.order_by(SalesInvoice.date.desc()).limit(500).all()
            except Exception:
                sales = []
            s_ids = [int(getattr(s, 'id', 0) or 0) for s in (sales or [])]
            s_paid = paid_sum('sales', s_ids)
            for s in (sales or []):
                total = float(getattr(s, 'total_after_tax_discount', 0) or 0)
                paid = float(s_paid.get(int(getattr(s, 'id', 0) or 0), 0.0))
                remaining = max(total - paid, 0.0)
                # حساب الحالة: احترم السجل إن وجد وإلا احسب من المدفوع
                if remaining <= 0.0 and (getattr(s, 'status', '') or '').lower() == '':
                    status_calc = 'paid'
                else:
                    st = (getattr(s, 'status', '') or '').lower()
                    if st in ('paid', 'partial', 'unpaid'):
                        status_calc = st
                    else:
                        status_calc = ('paid' if remaining <= 0.0 and total > 0 else ('partial' if paid > 0 else 'unpaid'))
                invoices.append({
                    'id': int(getattr(s, 'id', 0) or 0),
                    'invoice_number': getattr(s, 'invoice_number', None) or f"S-{getattr(s, 'id', '')}",
                    'invoice_type': 'sales',
                    'customer_supplier': getattr(s, 'customer_name', None) or '-',
                    'total_amount': total,
                    'paid_amount': paid,
                    'remaining_amount': remaining,
                    'status': status_calc,
                    'due_date': None,
                })

        if t in ('all', 'purchases'):
            try:
                purchases = PurchaseInvoice.query.order_by(PurchaseInvoice.date.desc()).limit(500).all()
            except Exception:
                purchases = []
            p_ids = [int(getattr(p, 'id', 0) or 0) for p in (purchases or [])]
            p_paid = paid_sum('purchase', p_ids)
            for p in (purchases or []):
                total = float(getattr(p, 'total_after_tax_discount', 0) or 0)
                paid = float(p_paid.get(int(getattr(p, 'id', 0) or 0), 0.0))
                invoices.append({
                    'id': int(getattr(p, 'id', 0) or 0),
                    'invoice_number': getattr(p, 'invoice_number', None) or f"P-{getattr(p, 'id', '')}",
                    'invoice_type': 'purchases',
                    'customer_supplier': getattr(p, 'supplier_name', None) or '-',
                    'total_amount': total,
                    'paid_amount': paid,
                    'remaining_amount': max(total - paid, 0.0),
                    'status': (getattr(p, 'status', '') or 'unpaid').lower(),
                    'due_date': None,
                })

        if t in ('all', 'expenses'):
            try:
                expenses = ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).limit(500).all()
            except Exception:
                expenses = []
            e_ids = [int(getattr(e, 'id', 0) or 0) for e in (expenses or [])]
            e_paid = paid_sum('expense', e_ids)
            for e in (expenses or []):
                total = float(getattr(e, 'total_after_tax_discount', 0) or 0)
                paid = float(e_paid.get(int(getattr(e, 'id', 0) or 0), 0.0))
                invoices.append({
                    'id': int(getattr(e, 'id', 0) or 0),
                    'invoice_number': getattr(e, 'invoice_number', None) or f"E-{getattr(e, 'id', '')}",
                    'invoice_type': 'expenses',
                    'customer_supplier': 'Expense',
                    'total_amount': total,
                    'paid_amount': paid,
                    'remaining_amount': max(total - paid, 0.0),
                    'status': (getattr(e, 'status', '') or 'paid').lower(),
                    'due_date': None,
                })
    except Exception:
        invoices = []

    return render_template('invoices.html', current_type=t, invoices=invoices)


@main.route('/invoices/<string:kind>/<int:invoice_id>', endpoint='view_invoice')
@login_required
def view_invoice(kind, invoice_id):
    kind = (kind or '').lower()
    # Normalize: invoices list uses 'sales','purchases','expenses'; route accepts 'sales','purchase','expense'
    if kind == 'purchases':
        kind = 'purchase'
    elif kind == 'expenses':
        kind = 'expense'
    inv = None
    items = []
    title = 'Invoice'
    if kind == 'sales':
        inv = SalesInvoice.query.get_or_404(invoice_id)
        if not user_can('sales', 'view', getattr(inv, 'branch', None)):
            flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
            return redirect(url_for('main.invoices'))
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
        return redirect(url_for('main.invoices'))
    from sqlalchemy import func
    paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).
        filter_by(invoice_type=kind, invoice_id=invoice_id).scalar() or 0)
    total = float(getattr(inv, 'total_after_tax_discount', 0) or 0)
    remaining = max(total - paid, 0.0)
    # Back link tab: invoices list uses 'sales','purchases','expenses'
    back_type = 'purchases' if kind == 'purchase' else ('expenses' if kind == 'expense' else kind)
    return render_template('invoice_view.html', kind=kind, back_type=back_type, inv=inv, items=items, title=title, paid=paid, remaining=remaining)


@main.route('/invoices/delete', methods=['POST'], endpoint='invoices_delete')
@login_required
def invoices_delete():
    scope = (request.form.get('scope') or 'selected').strip().lower()
    inv_type = (request.form.get('invoice_type') or request.form.get('current_type') or 'sales').strip().lower()
    ids = [int(x) for x in request.form.getlist('invoice_ids') if str(x).isdigit()]
    deleted = 0
    # If user chose to delete selected invoices but none were selected, do not proceed with bulk delete
    if scope == 'selected' and not ids:
        try:
            flash(_('لم يتم تحديد أي فاتورة للحذف'), 'warning')
        except Exception:
            flash(_('No selected invoices to delete'), 'warning')
        return redirect(url_for('main.invoices', type=inv_type))
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
                try:
                    db.session.query(LedgerEntry).filter(LedgerEntry.description.ilike('%{}%'.format(inv.invoice_number))).delete(synchronize_session=False)
                except Exception:
                    pass
                try:
                    from models import JournalEntry, JournalLine
                    je = JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type='sales').first()
                    if je:
                        JournalLine.query.filter(JournalLine.journal_id == je.id).delete(synchronize_session=False)
                        db.session.delete(je)
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
                try:
                    db.session.query(LedgerEntry).filter(LedgerEntry.description.ilike('%{}%'.format(inv.invoice_number))).delete(synchronize_session=False)
                except Exception:
                    pass
                try:
                    from models import JournalEntry, JournalLine
                    je = JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type='purchase').first()
                    if je:
                        JournalLine.query.filter(JournalLine.journal_id == je.id).delete(synchronize_session=False)
                        db.session.delete(je)
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
                try:
                    db.session.query(LedgerEntry).filter(LedgerEntry.description.ilike('%{}%'.format(inv.invoice_number))).delete(synchronize_session=False)
                except Exception:
                    pass
                try:
                    from models import JournalEntry, JournalLine
                    je = JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type='expense').first()
                    if je:
                        JournalLine.query.filter(JournalLine.journal_id == je.id).delete(synchronize_session=False)
                        db.session.delete(je)
                except Exception:
                    pass
                db.session.delete(inv)
                deleted += 1
        db.session.commit()
        flash(_('Deleted %(n)s invoice(s)', n=deleted), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Delete failed: %(error)s', error=e), 'danger')
    return redirect(url_for('main.invoices', type=inv_type))






@main.route('/employees', methods=['GET'], endpoint='employees')
@login_required
def employees():
    """شاشة الموظفين الموحدة: إضافة، مسير رواتب، كشوفات، سلف، مستحقات غير مدفوعة."""
    from calendar import month_name
    tab = (request.args.get('tab') or 'add').strip().lower()
    year = request.args.get('year', type=int) or get_saudi_now().year
    month = request.args.get('month', type=int) or get_saudi_now().month
    pay_status = (request.args.get('status') or 'all').strip().lower()
    pay_dept = (request.args.get('dept') or '').strip()
    years = list(range(get_saudi_now().year - 2, get_saudi_now().year + 3))
    months = [{'value': i, 'label': month_name[i]} for i in range(1, 13)]
    try:
        from sqlalchemy import func as _f
        rows_d = db.session.query(_f.lower(Employee.department)).filter(Employee.department.isnot(None)).distinct().all()
        dept_options = sorted([str(r[0]) for r in rows_d if r and r[0]])
    except Exception:
        dept_options = []
    emps = Employee.query.order_by(Employee.full_name.asc()).all()
    today = get_saudi_now().date()
    start_default = today.replace(day=1)
    end_default = today
    start_date = request.args.get('start_date') or start_default.isoformat()
    end_date = request.args.get('end_date') or end_default.isoformat()
    return render_template(
        'employees.html',
        tab=tab,
        employees=emps,
        dept_options=dept_options,
        years=years,
        months=months,
        year=year,
        month=month,
        pay_status=pay_status,
        pay_dept=pay_dept,
        start_date=start_date,
        end_date=end_date,
    )


@main.route('/employees/<int:eid>/delete', methods=['POST'], endpoint='employee_delete')
@main.route('/employees/delete', methods=['POST'], endpoint='employee_delete_by_query')
@login_required
def employee_delete(eid=None):
    if not user_can('employees','delete'):
        flash(_('You do not have permission / لا تملك صلاحية الوصول'), 'danger')
        return redirect(url_for('main.dashboard'))
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
        flash(_('Employee and all related records deleted successfully'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting employee: %(error)s', error=e), 'danger')
    return redirect(url_for('main.employees'))

@main.route('/employees/create-salary', methods=['POST'], endpoint='employees_create_salary')
@login_required
def employees_create_salary():
    if not user_can('employees','add') and not user_can('salaries','add'):
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    try:
        emp_id = int(request.form.get('employee_id') or 0)
        year = int(request.form.get('year') or get_saudi_now().year)
        month = int(request.form.get('month') or get_saudi_now().month)
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
@main.route('/salaries/pay/', methods=['GET','POST'])
@login_required
def salaries_pay():
    # Create/update salary for a month and optionally record a payment
    if request.method == 'POST':
        try:
            emp_id_raw = request.form.get('employee_id')
            month_raw = (request.form.get('month') or request.form.get('pay_month') or get_saudi_now().strftime('%Y-%m'))
            month_str = (month_raw or '').strip()
            year = None
            month = None
            try:
                if '-' in month_str and month_str.count('-') == 1:
                    y, m = month_str.split('-')
                    year = int(y)
                    month = int(m)
                else:
                    from calendar import month_name
                    parts = month_str.replace('/', ' ').split()
                    if len(parts) >= 2:
                        name = parts[0].strip().lower()
                        yval = int(parts[-1])
                        idx = None
                        for i in range(1, 13):
                            if month_name[i].lower() == name:
                                idx = i
                                break
                        if idx:
                            year = yval
                            month = idx
                if not year or not month or month < 1 or month > 12:
                    raise ValueError('bad month')
            except Exception:
                if request.is_json or ('application/json' in (request.headers.get('Accept') or '').lower()):
                    return jsonify({'error': True, 'message': 'صيغة الشهر غير صحيحة. استخدم YYYY-MM مثل 2025-11'}), 400
                year = get_saudi_now().year
                month = get_saudi_now().month
            amount = float(request.form.get('paid_amount') or 0)
            method_raw = (request.form.get('payment_method') or 'cash').strip().lower()
            if method_raw in ('cash','نقدي'):
                method = 'cash'
            elif method_raw in ('bank','بنك','card','visa','بطاقة'):
                method = 'bank'
            else:
                method = 'cash'
            if not (amount > 0):
                error_msg = _('قيمة السداد مطلوبة')
                if request.is_json or ('application/json' in (request.headers.get('Accept') or '').lower()):
                    return jsonify({'error': True, 'message': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('main.payroll', year=year, month=month))

            # Validate employee id for single-payment mode
            if (emp_id_raw or '').strip().lower() != 'all':
                if not str(emp_id_raw or '').strip().isdigit():
                    error_msg = _('الموظف غير محدد أو رقم غير صالح')
                    if request.is_json or ('application/json' in (request.headers.get('Accept') or '').lower()):
                        return jsonify({'error': True, 'message': error_msg}), 400
                    flash(error_msg, 'danger')
                    return redirect(url_for('main.payroll', year=year, month=month))
                try:
                    emp_check = Employee.query.get(int(emp_id_raw))
                except Exception:
                    emp_check = None
                if not emp_check:
                    error_msg = _('الموظف غير موجود')
                    if request.is_json or ('application/json' in (request.headers.get('Accept') or '').lower()):
                        return jsonify({'error': True, 'message': error_msg}), 404
                    flash(error_msg, 'danger')
                    return redirect(url_for('main.payroll', year=year, month=month))
            basic_override = None
            allow_override = None
            ded_override   = None
            prev_override  = None

            

            # Determine employees to pay: single or all
            if (emp_id_raw or '').strip().lower() == 'all':
                dept_filter = (request.form.get('department') or '').strip().lower()
                if dept_filter:
                    from sqlalchemy import func
                    employee_ids = [int(e.id) for e in Employee.query.filter(func.lower(Employee.department) == dept_filter).all()]
                else:
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
                                hrs_row = EmployeeHours.query.filter_by(employee_id=_emp_id, year=yy, month=mm).first()
                                emp_o = Employee.query.get(_emp_id)
                                dept_name = (getattr(emp_o, 'department', '') or '').lower()
                                rate_row = DepartmentRate.query.filter(DepartmentRate.name == dept_name).first()
                                hourly_rate = float(getattr(rate_row, 'hourly_rate', 0) or 0)
                                try:
                                    from app.models import AppKV
                                    kv = AppKV.get(f"emp_settings:{int(_emp_id)}") or {}
                                    kv_type = str(kv.get('salary_type','') or '').lower()
                                    kv_rate = float(kv.get('hourly_rate') or 0.0)
                                    if kv_rate > 0:
                                        hourly_rate = kv_rate
                                    if kv_type == 'hourly':
                                        hour_based_base = float(getattr(hrs_row, 'hours', 0) or 0) * hourly_rate if hrs_row else 0.0
                                        base = float(hour_based_base or 0.0)
                                    else:
                                        base = float(getattr(d, 'base_salary', 0) or 0)
                                except Exception:
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
                                from models import JournalEntry, JournalLine
                                cash_acc = _pm_account(method)
                                pay_liab = _account(*SHORT_TO_NUMERIC['PAYROLL_LIAB'])
                                je = JournalEntry(entry_number=f"JE-SALPAY-{row.id}", date=get_saudi_now().date(), branch_code=None, description=f"Salary payment {row.year}-{row.month} EMP {row.employee_id}", status='posted', total_debit=pay_amount, total_credit=pay_amount, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), salary_id=row.id)
                                db.session.add(je); db.session.flush()
                                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=pay_liab.id, debit=pay_amount, credit=0, description='Payroll liability', line_date=get_saudi_now().date(), employee_id=row.employee_id))
                                if cash_acc:
                                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0, credit=pay_amount, description='Cash/Bank', line_date=get_saudi_now().date(), employee_id=row.employee_id))
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                            try:
                                cash_acc = _pm_account(method)
                                # Clear liability on payment: DR Payroll Liabilities, CR Cash/Bank
                                _post_ledger(get_saudi_now().date(), 'PAYROLL_LIAB', 'مستحقات رواتب الموظفين', 'liability', pay_amount, 0.0, f'PAY SAL {row.year}-{row.month} EMP {row.employee_id}')
                                if cash_acc:
                                    _post_ledger(get_saudi_now().date(), cash_acc.code, cash_acc.name, 'asset', 0.0, pay_amount, f'PAY SAL {row.year}-{row.month} EMP {row.employee_id}')
                            except Exception:
                                pass
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
                            cash_acc = _pm_account(method)
                            # Record employee advance: DR Employee Advances (asset), CR Cash/Bank
                            _post_ledger(get_saudi_now().date(), 'EMP_ADV', 'سلف للموظفين', 'asset', remaining_payment, 0.0, f'ADV EMP {adv_row.employee_id} {adv_row.year}-{adv_row.month}')
                            if cash_acc:
                                _post_ledger(get_saudi_now().date(), cash_acc.code, cash_acc.name, 'asset', 0.0, remaining_payment, f'ADV EMP {adv_row.employee_id} {adv_row.year}-{adv_row.month}')
                            try:
                                from models import JournalEntry, JournalLine
                                emp_adv_acc = _account(*SHORT_TO_NUMERIC['EMP_ADV'])
                                je2 = JournalEntry(entry_number=f"JE-ADV-{adv_row.employee_id}-{adv_row.year}{adv_row.month:02d}", date=get_saudi_now().date(), branch_code=None, description=f"Employee advance {adv_row.employee_id} {adv_row.year}-{adv_row.month}", status='posted', total_debit=remaining_payment, total_credit=remaining_payment, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), salary_id=adv_row.id)
                                db.session.add(je2); db.session.flush()
                                db.session.add(JournalLine(journal_id=je2.id, line_no=1, account_id=emp_adv_acc.id, debit=remaining_payment, credit=0, description='Employee advance', line_date=get_saudi_now().date(), employee_id=adv_row.employee_id))
                                if cash_acc:
                                    db.session.add(JournalLine(journal_id=je2.id, line_no=2, account_id=cash_acc.id, debit=0, credit=remaining_payment, description='Cash/Bank', line_date=get_saudi_now().date(), employee_id=adv_row.employee_id))
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                        except Exception:
                            pass
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
            success_msg = _('تم تسجيل السداد')
            if request.is_json or ('application/json' in (request.headers.get('Accept') or '').lower()):
                return jsonify({'success': True, 'message': success_msg, 'payment_ids': created_payment_ids})
            flash(success_msg, 'success')
        except Exception as e:
            db.session.rollback()
            error_msg = _('خطأ في حفظ الراتب/الدفع: %(error)s', error=str(e))
            if request.is_json or ('application/json' in (request.headers.get('Accept') or '').lower()):
                return jsonify({'error': True, 'message': error_msg}), 400
            flash(error_msg, 'danger')
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
    selected_month = request.args.get('month') or get_saudi_now().strftime('%Y-%m')
    selected_employee_param = request.args.get('employee', type=int)
    valid_emp_ids = {int(e.id) for e in (employees or []) if getattr(e, 'id', None)}
    selected_employee = None
    try:
        if selected_employee_param and int(selected_employee_param) in valid_emp_ids:
            selected_employee = int(selected_employee_param)
        elif employees:
            selected_employee = int(employees[0].id)
        else:
            selected_employee = None
    except Exception:
        selected_employee = (int(employees[0].id) if employees else None)
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

    # Maps for fast access and precomputed values
    employee_map = {int(e.id): e for e in (employees or []) if getattr(e, 'id', None)}
    salary_map = {int(getattr(s, 'employee_id', 0) or 0): s for s in (current_salaries or [])}
    # Selected employee's salary for this month (to prefill form with existing values)
    selected_salary = None
    try:
        if selected_employee and salary_map.get(int(selected_employee)):
            selected_salary = salary_map.get(int(selected_employee))
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

    # Precompute monetary components per employee for the selected month
    calc_map = {}
    try:
        for emp_id in valid_emp_ids:
            srow = salary_map.get(int(emp_id))
            if srow:
                base = float(getattr(srow, 'basic_salary', 0.0) or 0.0)
                allow = float(getattr(srow, 'allowances', 0.0) or 0.0)
                ded = float(getattr(srow, 'deductions', 0.0) or 0.0)
                prev = float(getattr(srow, 'previous_salary_due', 0.0) or 0.0)
                total = max(0.0, base + allow - ded + prev)
                paid = float(paid_map.get(int(getattr(srow, 'id')), 0.0) or 0.0)
                calc_map[int(emp_id)] = {
                    'basic': base,
                    'allow': allow,
                    'ded': ded,
                    'prev': prev,
                    'total': total,
                    'paid': paid,
                    'remaining': max(0.0, total - paid)
                }
            else:
                d = defaults_map.get(int(emp_id), {})
                base = float(d.get('basic_salary', 0.0) or 0.0)
                allow = float(d.get('allowances', 0.0) or 0.0)
                ded = float(d.get('deductions', 0.0) or 0.0)
                prev = float(prev_due_map.get(int(emp_id), 0.0) or 0.0)
                total = max(0.0, base + allow - ded + prev)
                calc_map[int(emp_id)] = {
                    'basic': base,
                    'allow': allow,
                    'ded': ded,
                    'prev': prev,
                    'total': total,
                    'paid': 0.0,
                    'remaining': total
                }
    except Exception:
        calc_map = {}

    return ('', 404)


@main.route('/print/salary-receipt')
@login_required
def salary_receipt():
    return ('', 404)


# Alias route to handle legacy or shortened path usage
@main.route('/pay', methods=['POST'], endpoint='pay_alias')
@login_required
def pay_alias():
    return ('', 404)


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
            year = get_saudi_now().year; month = get_saudi_now().month
    else:
        year = request.args.get('year', type=int) or get_saudi_now().year
        month = request.args.get('month', type=int) or get_saudi_now().month

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

    return ('', 404)



@main.route('/api/salaries/statements', methods=['GET'], endpoint='api_salaries_statements')
@login_required
def api_salaries_statements():
    return ('', 404)
    month_param = (request.args.get('month') or '').strip()
    status_f = (request.args.get('status') or '').strip().lower()
    emp_id_f = request.args.get('emp_id', type=int)
    dept_f = (request.args.get('dept') or '').strip()
    if '-' in month_param:
        try:
            y, m = month_param.split('-'); year = int(y); month = int(m)
        except Exception:
            year = get_saudi_now().year; month = get_saudi_now().month
    else:
        year = request.args.get('year', type=int) or get_saudi_now().year
        month = request.args.get('month', type=int) or get_saudi_now().month
    from sqlalchemy import func
    rows = []
    totals = {'basic': 0.0, 'allow': 0.0, 'ded': 0.0, 'prev': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0}
    try:
        employees_q = Employee.query.order_by(Employee.full_name.asc())
        if dept_f:
            employees_q = employees_q.filter(func.lower(Employee.department) == dept_f.lower())
        employees = employees_q.all()
        try:
            from models import EmployeeSalaryDefault
            defaults_map = {d.employee_id: d for d in EmployeeSalaryDefault.query.all()}
        except Exception:
            defaults_map = {}
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
            if emp_id_f and int(emp.id) != int(emp_id_f):
                continue
            if getattr(emp, 'hire_date', None):
                y0, m0 = int(emp.hire_date.year), int(emp.hire_date.month)
            else:
                y0, m0 = year, month
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
            total_paid_all = 0.0
            if sal_ids:
                total_paid_all = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                                       .filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_ids))
                                       .scalar() or 0.0)
            remaining_payment = total_paid_all
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
            row = {
                'employee_id': int(emp.id),
                'employee_name': emp.full_name,
                'month_label': f"{year:04d}-{month:02d}",
                'year': year,
                'month': month,
                'basic': c_base,
                'allow': c_allow,
                'ded': c_ded,
                'prev': prev_remaining,
                'total': total,
                'paid': paid_display,
                'remaining': remaining_total,
                'status': status
            }
            rows.append(row)
            totals['basic'] += c_base
            totals['allow'] += c_allow
            totals['ded'] += c_ded
            totals['prev'] += prev_remaining
            totals['total'] += total
            totals['paid'] += paid_display
            totals['remaining'] += remaining_total
    except Exception:
        pass
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
    return jsonify({'ok': True, 'year': year, 'month': month, 'rows': rows, 'totals': totals})

@main.route('/api/salaries/upsert', methods=['POST'], endpoint='api_salaries_upsert')
@login_required
def api_salaries_upsert():
    return ('', 404)
    try:
        emp_id = request.form.get('employee_id', type=int)
        month_raw = (request.form.get('month') or '').strip() or get_saudi_now().strftime('%Y-%m')
        absence_hours = float(request.form.get('absence_hours') or 0)
        overtime_hours = float(request.form.get('overtime_hours') or 0)
        bonus_amount = float(request.form.get('bonus_amount') or 0)
        deduction_amount = float(request.form.get('deduction_amount') or 0)
        if not emp_id:
            return jsonify({'ok': False, 'error': 'employee_required'}), 400
        try:
            y, m = month_raw.split('-'); year = int(y); month = int(m)
        except Exception:
            year = get_saudi_now().year; month = get_saudi_now().month
        emp = Employee.query.get(emp_id)
        if not emp:
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 404
        from models import EmployeeSalaryDefault, DepartmentRate, EmployeeHours
        d = EmployeeSalaryDefault.query.filter_by(employee_id=int(emp_id)).first()
        base = float(getattr(d, 'base_salary', 0.0) or 0.0)
        dept_name = (getattr(emp, 'department', '') or '').lower()
        rate_row = DepartmentRate.query.filter(DepartmentRate.name == dept_name).first()
        hourly_rate = float(getattr(rate_row, 'hourly_rate', 0.0) or 0.0)
        try:
            from app.models import AppKV
            kv = AppKV.get(f"emp_settings:{int(emp_id)}") or {}
            kv_type = str(kv.get('salary_type','') or '').lower()
            kv_rate = float(kv.get('hourly_rate') or 0.0)
            if kv_rate > 0:
                hourly_rate = kv_rate
            if kv_type == 'hourly':
                hrs = EmployeeHours.query.filter_by(employee_id=int(emp_id), year=year, month=month).first()
                base = float(getattr(hrs, 'hours', 0.0) or 0.0) * float(hourly_rate or 0.0)
        except Exception:
            pass
        if hourly_rate <= 0 and base > 0:
            hourly_rate = base / 240.0
        allow = max(0.0, overtime_hours * hourly_rate) + max(0.0, bonus_amount)
        ded = max(0.0, absence_hours * hourly_rate) + max(0.0, deduction_amount)
        s = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
        prev_due = float(getattr(s, 'previous_salary_due', 0.0) or 0.0) if s else 0.0
        total = max(0.0, base + allow - ded + prev_due)
        if not s:
            s = Salary(employee_id=emp_id, year=year, month=month,
                       basic_salary=base, allowances=allow, deductions=ded,
                       previous_salary_due=prev_due, total_salary=total,
                       status='due')
            db.session.add(s)
        else:
            s.basic_salary = base
            s.allowances = allow
            s.deductions = ded
            s.total_salary = total
            s.status = 'due'
        db.session.commit()
        return jsonify({'ok': True, 'salary_id': int(s.id), 'year': year, 'month': month, 'basic': base, 'allowances': allow, 'deductions': ded, 'total': total})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/salaries/<int:sid>/update', methods=['POST'], endpoint='api_salaries_update')
@login_required
def api_salaries_update(sid: int):
    return ('', 404)
    try:
        if not user_can('salaries', 'edit'):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        s = Salary.query.get_or_404(int(sid))
        basic = request.form.get('basic_salary', type=float)
        allow = request.form.get('allowances', type=float)
        ded = request.form.get('deductions', type=float)
        prev = request.form.get('previous_salary_due', type=float)
        status = (request.form.get('status') or '').strip().lower()
        if basic is not None:
            s.basic_salary = float(basic or 0.0)
        if allow is not None:
            s.allowances = float(allow or 0.0)
        if ded is not None:
            s.deductions = float(ded or 0.0)
        if prev is not None:
            s.previous_salary_due = float(prev or 0.0)
        total = max(0.0, float(s.basic_salary or 0.0) + float(s.allowances or 0.0) - float(s.deductions or 0.0) + float(s.previous_salary_due or 0.0))
        s.total_salary = total
        if status in ('paid','due','partial'):
            s.status = status
        db.session.commit()
        return jsonify({'ok': True, 'salary_id': int(s.id), 'total': float(s.total_salary or 0.0), 'status': str(s.status or 'due')})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/salaries/<int:sid>/delete', methods=['POST'], endpoint='api_salaries_delete')
@login_required
def api_salaries_delete(sid: int):
    return ('', 404)
    try:
        if not user_can('salaries', 'delete'):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        s = Salary.query.get_or_404(int(sid))
        try:
            Payment.query.filter(Payment.invoice_type == 'salary', Payment.invoice_id == int(sid)).delete(synchronize_session=False)
        except Exception:
            pass
        try:
            from models import JournalEntry
            JournalEntry.query.filter(JournalEntry.salary_id == int(sid)).delete(synchronize_session=False)
        except Exception:
            pass
        db.session.delete(s)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/payroll/seed-test', methods=['POST'], endpoint='api_payroll_seed_test')
@csrf.exempt
def api_payroll_seed_test():
    return ('', 404)
    try:
        from datetime import date as _date, timedelta as _td
        y = get_saudi_now().year
        m = get_saudi_now().month
        created = []
        for idx, cfg in enumerate([
            {'name': 'موظف تجريبي 1', 'nid': f'TST{y}A', 'dept': 'شيف', 'base': 1800.0},
            {'name': 'موظف تجريبي 2', 'nid': f'TST{y}B', 'dept': 'صالة', 'base': 1600.0},
        ]):
            try:
                emp = Employee.query.filter_by(full_name=cfg['name']).first()
            except Exception:
                emp = None
            if not emp:
                hd = (get_saudi_now().date() - _td(days=365))
                emp = Employee(full_name=cfg['name'], national_id=cfg['nid'], department=cfg['dept'], position='موظف', phone='', email='', hire_date=hd, status='active', active=True)
                db.session.add(emp); db.session.flush()
                try:
                    from models import EmployeeSalaryDefault
                    db.session.add(EmployeeSalaryDefault(employee_id=int(emp.id), base_salary=cfg['base'], allowances=0.0, deductions=0.0))
                except Exception:
                    pass
            srow = Salary.query.filter_by(employee_id=int(emp.id), year=y, month=m).first()
            if not srow:
                srow = Salary(employee_id=int(emp.id), year=y, month=m, basic_salary=cfg['base'], allowances=0.0, deductions=0.0, previous_salary_due=0.0, total_salary=cfg['base'], status='due')
                db.session.add(srow); db.session.flush()
            created.append(int(emp.id))
        db.session.commit()
        for i, emp_id in enumerate(created):
            amt_adv = 300.0 if i == 0 else 0.0
            amt_pay = 900.0 if i == 0 else 0.0
            amt_repay = 200.0 if i == 1 else 0.0
            try:
                if amt_adv > 0:
                    _post_ledger(get_saudi_now().date(), 'EMP_ADV', 'سلف للموظفين', 'asset', amt_adv, 0.0, f'ADV EMP {emp_id}')
                if amt_repay > 0:
                    _post_ledger(get_saudi_now().date(), 'EMP_ADV', 'سلف للموظفين', 'asset', 0.0, amt_repay, f'ADV REPAY {emp_id}')
            except Exception:
                pass
            try:
                srow = Salary.query.filter_by(employee_id=int(emp_id), year=y, month=m).first()
                if srow and amt_pay > 0:
                    p = Payment(invoice_id=int(srow.id), invoice_type='salary', amount_paid=amt_pay, payment_method='cash')
                    db.session.add(p); db.session.flush()
                    try:
                        from models import JournalEntry, JournalLine
                        cash_acc = _pm_account('cash')
                        pay_liab = _account(*SHORT_TO_NUMERIC['PAYROLL_LIAB'])
                        je = JournalEntry(entry_number=f"JE-SALPAY-{srow.id}", date=get_saudi_now().date(), branch_code=None, description=f"Salary payment {y}-{m} EMP {emp_id}", status='posted', total_debit=amt_pay, total_credit=amt_pay, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), salary_id=srow.id)
                        db.session.add(je); db.session.flush()
                        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=pay_liab.id, debit=amt_pay, credit=0.0, description='Payroll liability', line_date=get_saudi_now().date(), employee_id=emp_id))
                        if cash_acc:
                            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amt_pay, description='Cash/Bank', line_date=get_saudi_now().date(), employee_id=emp_id))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    try:
                        cash_acc = _pm_account('cash')
                        _post_ledger(get_saudi_now().date(), 'PAYROLL_LIAB', 'مستحقات رواتب الموظفين', 'liability', amt_pay, 0.0, f'PAY SAL {y}-{m} EMP {emp_id}')
                        if cash_acc:
                            _post_ledger(get_saudi_now().date(), cash_acc.code, cash_acc.name, 'asset', 0.0, amt_pay, f'PAY SAL {y}-{m} EMP {emp_id}')
                    except Exception:
                        pass
                    paid_sum = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type=='salary', Payment.invoice_id==srow.id).scalar() or 0.0)
                    total_due = float(srow.total_salary or 0.0)
                    if paid_sum >= total_due and total_due > 0:
                        srow.status = 'paid'
                    elif paid_sum > 0:
                        srow.status = 'partial'
                    else:
                        srow.status = 'due'
                    db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        return jsonify({'ok': True, 'employees': created})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/employees/payroll', methods=['GET'], endpoint='payroll')
@login_required
def payroll():
    year = request.args.get('year', type=int) or get_saudi_now().year
    month = request.args.get('month', type=int) or get_saudi_now().month
    status = (request.args.get('status') or 'all').strip().lower()
    dept_f = (request.args.get('dept') or '').strip().lower()
    return redirect(url_for('main.employees', tab='payroll', year=year, month=month, status=status, dept=dept_f or ''))


@main.route('/api/payroll', methods=['GET'], endpoint='api_payroll')
@login_required
def api_payroll():
    """JSON payroll data for employees hub payroll tab. مصدر الحقيقة: مسيرات الرواتب فقط — عدم وجود مسيرات = عدم عرض أي بيانات. for_new_run=1: قائمة موظفين مع الأساسي من بيانات التسجيل لملء فورم إنشاء مسير."""
    year = request.args.get('year', type=int) or get_saudi_now().year
    month = request.args.get('month', type=int) or get_saudi_now().month
    status = (request.args.get('status') or 'all').strip().lower()
    dept_f = (request.args.get('dept') or '').strip().lower()
    for_new_run = request.args.get('for_new_run', '').strip() in ('1', 'true', 'yes')
    payrolls = []
    journal_count = 0
    emp_adv_total = 0.0
    try:
        from sqlalchemy import func
        from models import EmployeeSalaryDefault
        defaults_map = {int(d.employee_id): d for d in EmployeeSalaryDefault.query.all()}
        # فورم إنشاء مسير: إرجاع كل الموظفين مع الأساسي من بيانات التسجيل (قابل للتعديل) وباقي الحقول 0
        if for_new_run:
            q_emps = Employee.query.order_by(Employee.full_name.asc())
            if dept_f:
                q_emps = q_emps.filter(func.lower(Employee.department) == dept_f)
            for emp in q_emps.all():
                d = defaults_map.get(int(emp.id))
                basic = float(getattr(d, 'base_salary', 0) or 0) if d else 0.0
                extra = absence = incentive = 0.0
                allow = float(getattr(d, 'allowances', 0) or 0) if d else 0.0
                ded = float(getattr(d, 'deductions', 0) or 0) if d else 0.0
                total_row = max(0.0, basic + extra - absence + incentive + allow - ded)
                payrolls.append({
                    'employee_id': int(emp.id),
                    'employee_name': emp.full_name,
                    'has_salary_record': False,
                    'department': getattr(emp, 'department', None) or '',
                    'basic': basic, 'extra': extra, 'absence': absence, 'incentive': incentive,
                    'allowances': allow, 'deductions': ded,
                    'prev_due': 0.0, 'total': total_row, 'paid': 0.0, 'remaining': total_row, 'status': 'due',
                })
        else:
            # مصدر الحقيقة: قيود المسير فقط — نعرض فقط موظفين لديهم سجل راتب (مسير) للشهر المحدد
            salary_rows = Salary.query.filter_by(year=year, month=month).all()
            if not salary_rows:
                # لا توجد مسيرات لهذا الشهر = لا نعرض أي بيانات (ماضي، حاضر، مستقبل)
                payrolls = []
            else:
                emp_ids = [int(s.employee_id) for s in salary_rows]
                emps_map = {int(e.id): e for e in Employee.query.filter(Employee.id.in_(emp_ids)).all()}
                for s in salary_rows:
                    emp = emps_map.get(int(s.employee_id))
                    if not emp:
                        continue
                    if dept_f and (getattr(emp, 'department', None) or '').strip().lower() != dept_f:
                        continue
                    basic = float(s.basic_salary or 0)
                    extra = float(getattr(s, 'extra', 0) or 0)
                    absence = float(getattr(s, 'absence', 0) or 0)
                    incentive = float(getattr(s, 'incentive', 0) or 0)
                    allow = float(s.allowances or 0)
                    ded = float(s.deductions or 0)
                    current_due = max(0.0, basic + extra - absence + incentive + allow - ded)
                    total_sal = float(s.total_salary or current_due)
                    sal_id = int(s.id)
                    paid_all = 0.0
                    paid_all = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                                     .filter(Payment.invoice_type == 'salary', Payment.invoice_id == sal_id).scalar() or 0.0)
                    remaining = max(0.0, total_sal - paid_all)
                    status_v = 'paid' if (total_sal > 0 and remaining <= 0.01) else ('partial' if paid_all > 0 else 'due')
                    payrolls.append({
                        'employee_id': int(emp.id),
                        'employee_name': emp.full_name,
                        'has_salary_record': True,
                        'department': getattr(emp, 'department', None) or '',
                        'basic': basic,
                        'extra': extra,
                        'absence': absence,
                        'incentive': incentive,
                        'allowances': allow,
                        'deductions': ded,
                        'prev_due': 0.0,
                        'total': total_sal,
                        'paid': paid_all,
                        'remaining': remaining,
                        'status': status_v,
                    })
                payrolls.sort(key=lambda r: (r.get('employee_name') or ''))
        if status in ('paid', 'due', 'partial'):
            payrolls = [r for r in payrolls if (r.get('status') or '').lower() == status]
    except Exception:
        payrolls = []
    try:
        from models import JournalEntry, Account
        from services.gl_truth import get_account_debit_credit_from_gl
        journal_count = int(JournalEntry.query.filter(JournalEntry.date.between(date(year, month, 1), get_saudi_now().date())).count() or 0)
        adv_code = SHORT_TO_NUMERIC.get('EMP_ADV', ('1151',))[0]
        acc = Account.query.filter(Account.code == adv_code).first()
        if acc:
            dsum, csum = get_account_debit_credit_from_gl(acc.id, get_saudi_now().date())
            emp_adv_total = max(0.0, dsum - csum)
    except Exception:
        pass
    totals = {'basic': sum(r['basic'] for r in payrolls), 'allowances': sum(r['allowances'] for r in payrolls),
              'deductions': sum(r['deductions'] for r in payrolls), 'prev_due': sum(r['prev_due'] for r in payrolls),
              'total': sum(r['total'] for r in payrolls), 'paid': sum(r['paid'] for r in payrolls),
              'remaining': sum(r['remaining'] for r in payrolls)}
    accrual_posted = False
    run_saved = False
    try:
        accrual_posted = kv_get(f'payroll_accrual_{year}_{month}') is not None
        if not accrual_posted:
            from models import JournalEntry
            je_pr = JournalEntry.query.filter_by(entry_number=f"JE-PR-{year}{month:02d}", status='posted').first()
            accrual_posted = je_pr is not None
        run_saved = Salary.query.filter_by(year=year, month=month).count() > 0
    except Exception:
        pass
    return jsonify({'ok': True, 'payrolls': payrolls, 'totals': totals, 'journal_count': journal_count,
                    'emp_adv_total': emp_adv_total, 'year': year, 'month': month, 'accrual_posted': accrual_posted, 'run_saved': run_saved})


@main.route('/employees/<int:emp_id>/pay', methods=['GET', 'POST'], endpoint='pay_salary')
@login_required
def pay_salary(emp_id):
    emp = Employee.query.get_or_404(emp_id)

    # Support provided template shape and query params (employee_id, year, month)
    selected_employee_id = request.args.get('employee_id', type=int) or int(emp.id)
    year = request.args.get('year', type=int) or get_saudi_now().year
    month = request.args.get('month', type=int) or get_saudi_now().month

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
                flash(_('Error saving salary/payment: %(error)s', error=e), 'danger')
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
    return ('', 404)


# --- Printing: Payroll summary for a month ---
@main.route('/payroll/print/<int:year>/<int:month>', methods=['GET'], endpoint='payroll_print')
def payroll_print(year: int, month: int):
    try:
        from flask_login import login_required as _lr
    except Exception:
        pass
    try:
        if not user_can('payroll','view'):
            return ('Forbidden', 403)
    except Exception:
        pass
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
    return ('', 404)


# --- Employees Settings: Hour-based payroll ---
@main.route('/employees/settings', methods=['GET', 'POST'], endpoint='employees_settings')
@login_required
def employees_settings():
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    try:
        from models import EmployeeSalaryDefault
    except Exception:
        EmployeeSalaryDefault = None

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
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first() if EmployeeSalaryDefault else None
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
        dept_rates = {dr.name: float(dr.hourly_rate or 0.0) for dr in DepartmentRate.query.all()}
        emps = Employee.query.order_by(Employee.full_name.asc()).all()
        for emp in emps:
            hours_val = request.form.get(f'hours_{emp.id}', type=float)
            allow_def = request.form.get(f'allow_default_{emp.id}', type=float)
            ded_def = request.form.get(f'ded_default_{emp.id}', type=float)
            if hours_val is None and allow_def is None and ded_def is None:
                continue
            if hours_val is not None:
                rec = EmployeeHours.query.filter_by(employee_id=emp.id, year=year, month=month).first()
                if not rec:
                    rec = EmployeeHours(employee_id=emp.id, year=year, month=month, hours=hours_val)
                    db.session.add(rec)
                else:
                    rec.hours = hours_val
            if (allow_def is not None) or (ded_def is not None):
                d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first() if EmployeeSalaryDefault else None
                if not d and EmployeeSalaryDefault:
                    d = EmployeeSalaryDefault(employee_id=emp.id, base_salary=0.0, allowances=0.0, deductions=0.0)
                    db.session.add(d); db.session.flush()
                if allow_def is not None:
                    d.allowances = float(allow_def or 0.0)
                if ded_def is not None:
                    d.deductions = float(ded_def or 0.0)
        db.session.commit()

        for emp in emps:
            hrs = EmployeeHours.query.filter_by(employee_id=emp.id, year=year, month=month).first()
            rate = dept_rates.get((emp.department or '').lower(), 0.0)
            total_basic = float(getattr(hrs, 'hours', 0.0) or 0.0) * float(rate)
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first() if EmployeeSalaryDefault else None
            abs_hours = request.form.get(f'absent_hours_{emp.id}', type=float) or 0.0
            ot_hours = request.form.get(f'overtime_hours_{emp.id}', type=float) or 0.0
            abs_ded = float(abs_hours) * float(rate)
            ot_allow = float(ot_hours) * float(rate)
            allow = float(getattr(d, 'allowances', 0.0) or 0.0) + ot_allow
            ded = float(getattr(d, 'deductions', 0.0) or 0.0) + abs_ded
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
            # Create accrual journal entry automatically if not exists and amount > 0
            try:
                if total > 0:
                    from models import JournalEntry, JournalLine
                    existing = JournalEntry.query.filter(JournalEntry.salary_id == s.id, JournalEntry.description.ilike('%Payroll accrual%')).first()
                    if not existing:
                        exp_acc = _account(*SHORT_TO_NUMERIC['SAL_EXP'])
                        liab_acc = _account(*SHORT_TO_NUMERIC['PAYROLL_LIAB'])
                        je = JournalEntry(entry_number=f"JE-SALACC-{emp.id}-{year}{month:02d}", date=get_saudi_now().date(), branch_code=None, description=f"Payroll accrual {emp.id} {year}-{month}", status='posted', total_debit=total, total_credit=total, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), salary_id=s.id)
                        db.session.add(je); db.session.flush()
                        if exp_acc:
                            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total, credit=0, description='Payroll expense', line_date=get_saudi_now().date(), employee_id=emp.id))
                        if liab_acc:
                            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=liab_acc.id, debit=0, credit=total, description='Payroll liability', line_date=get_saudi_now().date(), employee_id=emp.id))
                        try:
                            _post_ledger(get_saudi_now().date(), 'SAL_EXP', 'مصروف رواتب', 'expense', total, 0.0, f'ACCRUAL {emp.id} {year}-{month}')
                            _post_ledger(get_saudi_now().date(), 'PAYROLL_LIAB', 'رواتب مستحقة', 'liability', 0.0, total, f'ACCRUAL {emp.id} {year}-{month}')
                        except Exception:
                            pass
            except Exception:
                pass
        db.session.commit()

        flash('تم حفظ الساعات وتحديث الرواتب', 'success')
        return redirect(url_for('main.employees_settings', year=year, month=month))

    # GET: render settings
    dept_rates = DepartmentRate.query.order_by(DepartmentRate.name.asc()).all()
    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    hours = EmployeeHours.query.filter_by(year=year, month=month).all()
    hours_map = {h.employee_id: float(h.hours or 0.0) for h in hours}
    dept_rate_map = {dr.name: float(dr.hourly_rate or 0.0) for dr in dept_rates}
    defaults_map = {int(d.employee_id): d for d in (EmployeeSalaryDefault.query.all() if EmployeeSalaryDefault else [])}
    # Build status map for current month salaries
    status_map = {}
    try:
        rows = Salary.query.filter_by(year=year, month=month).all()
        ids = [int(r.id) for r in rows if getattr(r, 'id', None)]
        paid_map = {}
        if ids:
            from sqlalchemy import func as _func
            for sid, paid in db.session.query(Payment.invoice_id, _func.coalesce(_func.sum(Payment.amount_paid), 0)).\
                    filter(Payment.invoice_type=='salary', Payment.invoice_id.in_(ids)).group_by(Payment.invoice_id):
                paid_map[int(sid)] = float(paid or 0.0)
        for r in (rows or []):
            total = max(0.0, float(r.basic_salary or 0.0) + float(r.allowances or 0.0) - float(r.deductions or 0.0) + float(r.previous_salary_due or 0.0))
            paid = float(paid_map.get(int(r.id), 0.0) or 0.0)
            remaining = max(0.0, total - paid)
            st = 'paid' if (total > 0 and remaining <= 0.01) else ('partial' if paid > 0 else ('paid' if total == 0 else 'due'))
            try:
                status_map[int(r.employee_id)] = st
            except Exception:
                pass
    except Exception:
        status_map = {}
    return ('', 404)

@main.route('/salaries/save_hours', methods=['POST'], endpoint='salaries_save_hours')
@login_required
def salaries_save_hours():
    return ('', 404)
    try:
        if not user_can('employees','edit') and not user_can('salaries','edit'):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        year = request.form.get('year', type=int) or get_saudi_now().year
        month = request.form.get('month', type=int) or get_saudi_now().month
        cand = set()
        for k in request.form.keys():
            if k.startswith('hours_') or k.startswith('absent_hours_') or k.startswith('overtime_hours_') or k.startswith('allow_default_') or k.startswith('ded_default_'):
                try:
                    cand.add(int(k.split('_')[-1]))
                except Exception:
                    pass
        from models import Employee, EmployeeHours, EmployeeSalaryDefault, DepartmentRate, Salary, JournalEntry, JournalLine
        dept_rates = {}
        try:
            for dr in DepartmentRate.query.all():
                try:
                    dept_rates[(dr.name or '').strip().lower()] = float(dr.hourly_rate or 0.0)
                except Exception:
                    pass
        except Exception:
            pass
        updated = 0
        for emp_id in cand:
            emp = Employee.query.get(emp_id)
            if not emp:
                continue
            h = request.form.get(f'hours_{emp_id}', type=float) or 0.0
            ah = request.form.get(f'absent_hours_{emp_id}', type=float) or 0.0
            oh = request.form.get(f'overtime_hours_{emp_id}', type=float) or 0.0
            ad = request.form.get(f'allow_default_{emp_id}', type=float) or 0.0
            dd = request.form.get(f'ded_default_{emp_id}', type=float) or 0.0
            hrs = EmployeeHours.query.filter_by(employee_id=emp_id, year=year, month=month).first()
            if not hrs:
                hrs = EmployeeHours(employee_id=emp_id, year=year, month=month, hours=h, absent_hours=ah, overtime_hours=oh)
                db.session.add(hrs)
            else:
                hrs.hours = h; hrs.absent_hours = ah; hrs.overtime_hours = oh
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp_id).first()
            if not d:
                d = EmployeeSalaryDefault(employee_id=emp_id, base_salary=0.0, allowances=0.0, deductions=0.0)
                db.session.add(d)
            d.allowances = float(ad or 0.0)
            d.deductions = float(dd or 0.0)
            rate = float(dept_rates.get((emp.department or '').strip().lower()) or 0.0)
            try:
                from app.models import AppKV
                kv = AppKV.get(f"emp_settings:{int(emp_id)}") or {}
                rv = float(kv.get('hourly_rate') or 0.0)
                if rv > 0:
                    rate = rv
            except Exception:
                pass
            base = float(h or 0.0) * float(rate or 0.0)
            abs_ded = float(ah or 0.0) * float(rate or 0.0)
            ot_allow = float(oh or 0.0) * float(rate or 0.0)
            allow = float(ad or 0.0) + float(ot_allow or 0.0)
            ded = float(dd or 0.0) + float(abs_ded or 0.0)
            total = max(0.0, base + allow - ded)
            s = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
            if not s:
                s = Salary(employee_id=emp_id, year=year, month=month, basic_salary=base, allowances=allow, deductions=ded, previous_salary_due=0.0, total_salary=total, status='due')
                db.session.add(s)
                db.session.flush()
            else:
                s.basic_salary = base
                s.allowances = allow
                s.deductions = ded
                s.previous_salary_due = 0.0
                s.total_salary = total
                s.status = 'due'
            try:
                existing = JournalEntry.query.filter(JournalEntry.salary_id == s.id, JournalEntry.description.ilike('%Payroll accrual%')).first()
                if not existing and total > 0:
                    exp_acc = _account(*SHORT_TO_NUMERIC['SAL_EXP'])
                    liab_acc = _account(*SHORT_TO_NUMERIC['PAYROLL_LIAB'])
                    je = JournalEntry(entry_number=f"JE-SALACC-{emp_id}-{year}{month:02d}", date=get_saudi_now().date(), branch_code=None, description=f"Payroll accrual {emp_id} {year}-{month}", status='posted', total_debit=total, total_credit=total, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), salary_id=s.id)
                    db.session.add(je); db.session.flush()
                    if exp_acc:
                        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total, credit=0.0, description='Payroll expense', line_date=get_saudi_now().date(), employee_id=emp_id))
                    if liab_acc:
                        db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=liab_acc.id, debit=0.0, credit=total, description='Payroll liability', line_date=get_saudi_now().date(), employee_id=emp_id))
                    try:
                        _post_ledger(get_saudi_now().date(), 'SAL_EXP', 'مصروف رواتب', 'expense', total, 0.0, f'ACCRUAL {emp_id} {year}-{month}')
                        _post_ledger(get_saudi_now().date(), 'PAYROLL_LIAB', 'رواتب مستحقة', 'liability', 0.0, total, f'ACCRUAL {emp_id} {year}-{month}')
                    except Exception:
                        pass
            except Exception:
                pass
            updated += 1
        db.session.commit()
        return jsonify({'ok': True, 'updated': updated})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/employee/settings', methods=['GET'], endpoint='api_employee_settings_get')
@login_required
def api_employee_settings_get():
    return ('', 404)
    try:
        emp_id = request.args.get('emp_id', type=int)
        if not emp_id:
            return jsonify({'ok': False, 'error': 'employee_required'}), 400
        emp = Employee.query.get(emp_id)
        if not emp:
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 404
        s = kv_get(f"emp_settings:{int(emp_id)}", {}) or {}
        work_type = (s.get('work_type') or 'hourly')
        pay_cycle = (s.get('pay_cycle') or 'monthly')
        payment_method = (s.get('payment_method') or 'cash')
        ot_rate = float(s.get('ot_rate') or 0.0)
        allow_allowances = bool(s.get('allow_allowances', True))
        allow_bonuses = bool(s.get('allow_bonuses', True))
        show_in_reports = bool(s.get('show_in_reports', True))
        try:
            dept = (emp.department or '').strip().lower()
            dr = DepartmentRate.query.filter_by(name=dept).first()
            dept_rate = float(getattr(dr, 'hourly_rate', 0.0) or 0.0)
        except Exception:
            dept_rate = 0.0
        hourly_rate_employee = float(s.get('hourly_rate_employee') or 0.0) or dept_rate
        monthly_hours = float(s.get('monthly_hours') or (getattr(emp, 'work_hours', 0) or 0))
        status = (s.get('status') or (emp.status or 'active'))
        return jsonify({'ok': True, 'settings': {
            'work_type': work_type,
            'monthly_hours': monthly_hours,
            'hourly_rate_employee': hourly_rate_employee,
            'status': status,
            'pay_cycle': pay_cycle,
            'payment_method': payment_method,
            'ot_rate': ot_rate,
            'allow_allowances': allow_allowances,
            'allow_bonuses': allow_bonuses,
            'show_in_reports': show_in_reports,
            'dept_rate_fallback': dept_rate
        }})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/employee/settings', methods=['POST'], endpoint='api_employee_settings_save')
@login_required
@csrf.exempt
def api_employee_settings_save():
    try:
        emp_id = request.form.get('emp_id', type=int)
        if not emp_id:
            return jsonify({'ok': False, 'error': 'employee_required'}), 400
        emp = Employee.query.get(emp_id)
        if not emp:
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 404
        cur = kv_get(f"emp_settings:{int(emp_id)}", {}) or {}
        fields = ['work_type','monthly_hours','hourly_rate_employee','status','pay_cycle','payment_method','ot_rate','allow_allowances','allow_bonuses','show_in_reports']
        for f in fields:
            if f in request.form:
                val = request.form.get(f)
                if f in ('monthly_hours','hourly_rate_employee','ot_rate'):
                    try:
                        val = float(val)
                    except Exception:
                        val = 0.0
                elif f in ('allow_allowances','allow_bonuses','show_in_reports'):
                    val = True if str(val).lower() in ['1','true','yes','on'] else False
                else:
                    val = (val or '').strip()
                cur[f] = val
        if 'status' in cur:
            emp.status = cur['status'] or (emp.status or 'active')
        if 'monthly_hours' in cur:
            try:
                emp.work_hours = float(cur['monthly_hours'] or 0.0)
            except Exception:
                pass
        db.session.commit()
        kv_set(f"emp_settings:{int(emp_id)}", cur)
        return jsonify({'ok': True, 'settings': cur})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

# --- Department Rates API ---
@main.route('/api/dept-rates', methods=['GET'], endpoint='api_dept_rates_get')
@login_required
def api_dept_rates_get():
    try:
        rows = DepartmentRate.query.order_by(DepartmentRate.name.asc()).all()
        data = []
        for r in rows:
            name = (r.name or '').strip().lower()
            mh_raw = kv_get(f"dept_hours:{name}", None)
            mh = 0.0
            try:
                if isinstance(mh_raw, dict):
                    mh = float(mh_raw.get('monthly_hours') or 0.0)
                elif mh_raw is None:
                    mh = 0.0
                else:
                    mh = float(mh_raw or 0.0)
            except Exception:
                mh = 0.0
            data.append({'name': r.name, 'hourly_rate': float(r.hourly_rate or 0.0), 'monthly_hours': mh})
        return jsonify({'ok': True, 'rows': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/dept-rates', methods=['POST'], endpoint='api_dept_rates_set')
@login_required
@csrf.exempt
def api_dept_rates_set():
    try:
        name = (request.form.get('name') or '').strip().lower()
        rate = request.form.get('hourly_rate', type=float) or 0.0
        monthly_hours = request.form.get('monthly_hours', type=float)
        mode = (request.form.get('mode') or '').strip().lower()
        month_param = (request.form.get('month') or '').strip()
        apply_future = True if str(request.form.get('apply_future', 'false')).lower() in ['1','true','yes','on'] else False
        if '-' in month_param:
            try:
                y, m = month_param.split('-'); year = int(y); month = int(m)
            except Exception:
                year = get_saudi_now().year; month = get_saudi_now().month
        else:
            year = request.form.get('year', type=int) or get_saudi_now().year
            month = request.form.get('month', type=int) or get_saudi_now().month

        if not name:
            return jsonify({'ok': False, 'error': 'dept_name_required'}), 400

        if mode == 'delete':
            row = DepartmentRate.query.filter_by(name=name).first()
            if row:
                db.session.delete(row)
                db.session.commit()
            return jsonify({'ok': True, 'deleted': True})
        else:
            row = DepartmentRate.query.filter_by(name=name).first()
            if row:
                row.hourly_rate = rate
            else:
                row = DepartmentRate(name=name, hourly_rate=rate)
                db.session.add(row)
            db.session.commit()
            if monthly_hours is not None:
                try:
                    kv_set(f"dept_hours:{name}", float(monthly_hours or 0.0))
                except Exception:
                    pass

        # Recalculate salaries for the selected period, only for unpaid ones
        emps = Employee.query.filter(func.lower(Employee.department) == name).all()
        for emp in emps:
            try:
                hrs = EmployeeHours.query.filter_by(employee_id=emp.id, year=year, month=month).first()
                total_basic = float(getattr(hrs, 'hours', 0.0) or 0.0) * float(rate)
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
                    if str(getattr(s, 'status', 'due')).lower() != 'paid':
                        s.basic_salary = total_basic
                        s.allowances = allow
                        s.deductions = ded
                        s.previous_salary_due = prev_due
                        s.total_salary = total
            except Exception:
                pass
        db.session.commit()

        # Optionally apply to next period (future)
        if apply_future:
            yy, mm = year, month + 1
            if mm > 12:
                mm = 1; yy += 1
            for emp in emps:
                try:
                    hrs = EmployeeHours.query.filter_by(employee_id=emp.id, year=yy, month=mm).first()
                    total_basic = float(getattr(hrs, 'hours', 0.0) or 0.0) * float(rate)
                    d = EmployeeSalaryDefault.query.filter_by(employee_id=emp.id).first()
                    allow = float(getattr(d, 'allowances', 0.0) or 0.0)
                    ded = float(getattr(d, 'deductions', 0.0) or 0.0)
                    prev_due = 0.0
                    total = max(0.0, total_basic + allow - ded + prev_due)
                    s = Salary.query.filter_by(employee_id=emp.id, year=yy, month=mm).first()
                    if not s:
                        s = Salary(employee_id=emp.id, year=yy, month=mm,
                                   basic_salary=total_basic, allowances=allow,
                                   deductions=ded, previous_salary_due=prev_due,
                                   total_salary=total, status='due')
                        db.session.add(s)
                    else:
                        if str(getattr(s, 'status', 'due')).lower() != 'paid':
                            s.basic_salary = total_basic
                            s.allowances = allow
                            s.deductions = ded
                            s.previous_salary_due = prev_due
                            s.total_salary = total
                except Exception:
                    pass
            db.session.commit()

        return jsonify({'ok': True, 'name': name, 'hourly_rate': rate, 'year': year, 'month': month, 'apply_future': apply_future})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/dept-reassign', methods=['POST'], endpoint='api_dept_reassign')
@login_required
@csrf.exempt
def api_dept_reassign():
    try:
        from_dept = (request.form.get('from_dept') or '').strip().lower()
        to_dept = (request.form.get('to_dept') or '').strip().lower()
        if not from_dept or not to_dept:
            return jsonify({'ok': False, 'error': 'invalid_dept'}), 400
        emps = Employee.query.filter(func.lower(Employee.department) == from_dept).all()
        for emp in emps:
            emp.department = to_dept
        db.session.commit()
        return jsonify({'ok': True, 'reassigned': len(emps)})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/employee/note', methods=['POST'], endpoint='api_employee_note')
@login_required
@csrf.exempt
def api_employee_note():
    try:
        emp_id = request.form.get('emp_id', type=int)
        note = (request.form.get('note') or '').strip()
        if not emp_id:
            return jsonify({'ok': False, 'error': 'employee_required'}), 400
        kv_set(f"emp_note:{int(emp_id)}", {'note': note})
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# --- Employee monthly hours API ---
@main.route('/api/employee-hours', methods=['GET'], endpoint='api_employee_hours_get')
@login_required
def api_employee_hours_get():
    try:
        month_param = (request.args.get('month') or '').strip()
        if '-' in month_param:
            try:
                y, m = month_param.split('-'); year = int(y); month = int(m)
            except Exception:
                year = get_saudi_now().year; month = get_saudi_now().month
        else:
            year = request.args.get('year', type=int) or get_saudi_now().year
            month = request.args.get('month', type=int) or get_saudi_now().month
        rows = EmployeeHours.query.filter_by(year=year, month=month).all()
        data = [{'employee_id': r.employee_id, 'hours': float(r.hours or 0.0)} for r in rows]
        return jsonify({'ok': True, 'year': year, 'month': month, 'rows': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# --- Printing: Bulk salary receipt for selected employees (current period) ---
@main.route('/salary/receipt', methods=['POST'], endpoint='salary_receipt_bulk')
@login_required
@csrf.exempt
def salary_receipt_bulk():
    return ('', 404)

@main.route('/admin/reclassify-keeta-hunger', methods=['POST'], endpoint='admin_reclassify_keeta_hunger')
@login_required
def admin_reclassify_keeta_hunger():
    start_date = (request.form.get('start_date') or '2025-10-01').strip()
    end_date = (request.form.get('end_date') or get_saudi_now().date().isoformat()).strip()
    changed = 0
    removed = 0
    try:
        import re
        from sqlalchemy import or_
        sd_dt = datetime.fromisoformat(start_date)
        ed_dt = datetime.fromisoformat(end_date)
        def norm(n: str):
            s = re.sub(r'[^a-z]', '', (n or '').lower())
            if s.startswith('hunger'):
                return 'hunger'
            if s.startswith('keeta') or s.startswith('keet'):
                return 'keeta'
            return ''
        q = SalesInvoice.query
        try:
            q = q.filter(or_(SalesInvoice.created_at.between(sd_dt, ed_dt), SalesInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        for inv in q.order_by(SalesInvoice.created_at.desc()).limit(5000).all():
            g = norm(inv.customer_name or '')
            if g not in ('keeta','hunger'):
                continue
            for p in db.session.query(Payment).filter(Payment.invoice_type=='sales', Payment.invoice_id==inv.id).all():
                try:
                    db.session.delete(p)
                    removed += 1
                except Exception:
                    pass
            inv.status = 'unpaid'
            changed += 1
        db.session.commit()
        return jsonify({'ok': True, 'changed': changed, 'removed': removed})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

# ---------- POS/Tables: basic navigation ----------
@main.route('/salaries/accrual', methods=['POST'], endpoint='salaries_accrual')
@login_required
def salaries_accrual():
    return ('', 404)
    if not user_can('salaries','add'):
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    try:
        emp_id_raw = (request.form.get('employee_id') or '').strip().lower()
        month_str = (request.form.get('month') or get_saudi_now().strftime('%Y-%m')).strip()
        y, m = month_str.split('-'); year = int(y); month = int(m)
        if emp_id_raw == 'all':
            employee_ids = [int(e.id) for e in Employee.query.all()]
        else:
            employee_ids = [int(emp_id_raw)] if emp_id_raw else []
        created = 0
        for _emp_id in employee_ids:
            s = Salary.query.filter_by(employee_id=_emp_id, year=year, month=month).first()
            if not s:
                try:
                    from models import EmployeeSalaryDefault
                    d = EmployeeSalaryDefault.query.filter_by(employee_id=_emp_id).first()
                    base = float(getattr(d, 'base_salary', 0) or 0)
                    allow = float(getattr(d, 'allowances', 0) or 0)
                    ded = float(getattr(d, 'deductions', 0) or 0)
                except Exception:
                    base = allow = ded = 0.0
                total = max(0.0, base + allow - ded)
                s = Salary(employee_id=_emp_id, year=year, month=month, basic_salary=base, allowances=allow, deductions=ded, previous_salary_due=0.0, total_salary=total, status='due')
                db.session.add(s)
                db.session.flush()
            amount = float(s.total_salary or 0.0)
            if amount <= 0:
                continue
            try:
                from models import JournalEntry, JournalLine
                exp_acc = _account(*SHORT_TO_NUMERIC['SAL_EXP'])
                liab_acc = _account(*SHORT_TO_NUMERIC['PAYROLL_LIAB'])
                je = JournalEntry(entry_number=f"JE-SALACC-{_emp_id}-{year}{month:02d}", date=get_saudi_now().date(), branch_code=None, description=f"Payroll accrual {_emp_id} {year}-{month}", status='posted', total_debit=amount, total_credit=amount, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), salary_id=s.id)
                db.session.add(je); db.session.flush()
                if exp_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=amount, credit=0, description='Payroll expense', line_date=get_saudi_now().date(), employee_id=_emp_id))
                if liab_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=liab_acc.id, debit=0, credit=amount, description='Payroll liability', line_date=get_saudi_now().date(), employee_id=_emp_id))
                db.session.commit()
                try:
                    _post_ledger(get_saudi_now().date(), 'SAL_EXP', 'مصروف رواتب', 'expense', amount, 0.0, f'ACCRUAL {_emp_id} {year}-{month}')
                    _post_ledger(get_saudi_now().date(), 'PAYROLL_LIAB', 'رواتب مستحقة', 'liability', 0.0, amount, f'ACCRUAL {_emp_id} {year}-{month}')
                except Exception:
                    pass
                created += 1
            except Exception:
                db.session.rollback()
        return jsonify({'ok': True, 'count': created})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400


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
    # meal_ids already in current section (for bulk-add UI: disable already-added)
    existing_meal_ids_in_section = set()
    if current:
        for it in items:
            if getattr(it, 'meal_id', None) is not None:
                existing_meal_ids_in_section.add(int(it.meal_id))
    return render_template('menu.html', sections=cats, current_section=current, items=items, item_counts=item_counts, meals=meals, existing_meal_ids_in_section=existing_meal_ids_in_section)


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
        # Avoid UNIQUE (category_id, meal_id): skip if already linked
        if meal_id:
            existing = MenuItem.query.filter_by(category_id=int(cat_id), meal_id=int(meal_id)).first()
            if existing:
                flash(_('الصنف مضاف مسبقاً لهذا القسم / Item already in this section'), 'info')
                return redirect(url_for('main.menu', cat_id=cat_id))
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
            flash(_('Missing item name'), 'danger')
            return redirect(url_for('main.menu', cat_id=cat_id))
        it = MenuItem(name=final_name, price=final_price, category_id=int(cat_id), meal_id=(meal.id if meal else None))
        db.session.add(it)
        db.session.commit()
        flash(_('تمت إضافة الصنف / Item added'), 'success')
        return redirect(url_for('main.menu', cat_id=cat_id))
    except Exception as e:
        db.session.rollback()
        flash(_('Error creating item: %(error)s', error=e), 'danger')
        return redirect(url_for('main.menu', cat_id=cat_id))


@main.route('/menu/items/bulk-add', methods=['POST'], endpoint='menu_items_bulk_add')
@login_required
def menu_items_bulk_add():
    """Add multiple meals to the selected section. Skips (category_id, meal_id) duplicates."""
    warmup_db_once()
    cat_id = request.form.get('section_id', type=int)
    meal_ids = request.form.getlist('meal_ids[]') or request.form.getlist('meal_ids')
    if not cat_id:
        flash(_('Missing section'), 'danger')
        return redirect(url_for('main.menu'))
    if not meal_ids:
        flash(_('لم تحدد أي أصناف / No meals selected'), 'warning')
        return redirect(url_for('main.menu', cat_id=cat_id))
    added = 0
    skipped = 0
    try:
        for mid in meal_ids:
            try:
                meal_id = int(mid)
            except (TypeError, ValueError):
                continue
            existing = MenuItem.query.filter_by(category_id=cat_id, meal_id=meal_id).first()
            if existing:
                skipped += 1
                continue
            meal = db.session.get(Meal, meal_id)
            if not meal:
                continue
            name = f"{meal.name} / {meal.name_ar}" if getattr(meal, 'name_ar', None) else (meal.name or '')
            price = float(meal.selling_price or 0.0)
            it = MenuItem(name=(name or '')[:150], price=price, category_id=cat_id, meal_id=meal_id)
            db.session.add(it)
            added += 1
        db.session.commit()
        if skipped:
            flash(_('تمت إضافة %(added)s صنف، وتخطي %(skipped)s (مضاف مسبقاً) / Added %(added)s, skipped %(skipped)s (already in section)', added=added, skipped=skipped), 'success')
        else:
            flash(_('تمت إضافة %(added)s صنف للقسم / Added %(added)s item(s)', added=added), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error: %(error)s', error=e), 'danger')
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
            flash(_('Item not found'), 'warning')
            return redirect(url_for('main.menu'))
        if name:
            it.name = name
        if price is not None:
            it.price = float(price)
        db.session.commit()
        return redirect(url_for('main.menu', cat_id=it.category_id))
    except Exception:
        db.session.rollback()
        flash(_('Error updating item'), 'danger')
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
            flash(_('Item deleted'), 'info')
            return redirect(url_for('main.menu', cat_id=cat_id))
    except Exception:
        db.session.rollback()
        flash(_('Error deleting item'), 'danger')
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
        email = (data.get('email') or '').strip() or None
        if email and User.query.filter_by(email=email).first():
            return jsonify({'ok': False, 'error': 'email_taken'}), 400
        role = (data.get('role') or 'user').strip() or 'user'
        u = User(username=username, email=email, role=role)
        u.set_password(password)
        if hasattr(u, 'active'):
            u.active = bool(active)
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
        # Update email if provided
        if 'email' in data:
            em = (data.get('email') or '').strip() or None
            if em and User.query.filter(User.email == em, User.id != uid).first():
                return jsonify({'ok': False, 'error': 'email_taken'}), 400
            u.email = em
        # Update role if provided
        if 'role' in data:
            r = (data.get('role') or 'user').strip() or 'user'
            if hasattr(u, 'role'):
                u.role = r
        # Optional: allow password change
        pw = (data.get('password') or '').strip()
        if pw:
            u.set_password(pw)
        # Active status: persist in AppKV and sync to model if column exists
        if 'active' in data:
            active_val = bool(data.get('active'))
            try:
                kv_set(f"user_active:{u.id}", {'active': active_val})
            except Exception:
                pass
            if hasattr(u, 'active'):
                u.active = active_val
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
PERM_SCREENS = ['dashboard','sales','purchases','inventory','expenses','employees','salaries','financials','vat','reports','invoices','payments','customers','menu','settings','suppliers','table_settings','users','sample_data','archive','journal']

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
            try:
                u = User.query.get(int(uid))
            except Exception:
                u = None
            if u and ((getattr(u, 'username','') == 'admin') or (getattr(u,'id',None) == 1) or (getattr(u,'role','') == 'admin')):
                for it in items:
                    if it.get('screen_key') == 'archive':
                        it['view'] = True
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
                db.session.add(s)

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

            try:
                acc_map = kv_get('acc_map', {}) or {}
                def _set_acc(key_alias, form_key):
                    val = (form_data.get(form_key) or '').strip()
                    if val:
                        acc_map[key_alias] = val
                _set_acc('AR_KEETA', 'acc_ar_keeta')
                _set_acc('AR_HUNGER', 'acc_ar_hunger')
                _set_acc('AR', 'acc_ar_default')
                _set_acc('REV_KEETA', 'acc_rev_keeta')
                _set_acc('REV_HUNGER', 'acc_rev_hunger')
                _set_acc('REV_CT', 'acc_rev_ct')
                _set_acc('REV_PI', 'acc_rev_pi')
                kv_set('acc_map', acc_map)
            except Exception:
                pass

            try:
                platforms = kv_get('platforms_map', []) or []
                pk = (form_data.get('platform_key') or '').strip().lower()
                if pk:
                    kws_raw = (form_data.get('platform_keywords') or '').strip()
                    keywords = [x.strip().lower() for x in kws_raw.split(',') if x.strip()]
                    entry = {
                        'key': pk,
                        'keywords': keywords,
                        'ar_code': (form_data.get('platform_ar_code') or '').strip(),
                        'rev_code': (form_data.get('platform_rev_code') or '').strip(),
                        'auto_unpaid': True
                    }
                    idx = None
                    for i, e in enumerate(platforms):
                        if (e.get('key') or '').strip().lower() == pk:
                            idx = i; break
                    if idx is not None:
                        # merge update
                        prev = platforms[idx]
                        prev.update({k: v for k, v in entry.items() if v})
                        platforms[idx] = prev
                    else:
                        platforms.append(entry)
                    kv_set('platforms_map', platforms)
            except Exception:
                pass

            db.session.commit()
            try:
                from utils.cache_helpers import invalidate_settings_cache
                invalidate_settings_cache()
            except Exception:
                pass
            flash(_('Settings saved'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Could not save settings: %(error)s', error=str(e)), 'danger')
        return redirect(url_for('main.settings'))
    return render_template('settings.html', s=s or Settings())

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
        flash(_('Branch not found'), 'error')
        return redirect(url_for('main.table_settings'))
    
    branch_label = branch_labels[branch_code]
    return render_template('table_manager.html', branch_code=branch_code, branch_label=branch_label)

@csrf.exempt
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

 

# ---------- VAT blueprint ----------
vat = Blueprint('vat', __name__, url_prefix='/vat')

@vat.route('/', endpoint='vat_dashboard')
@login_required
def vat_dashboard():
    # Period handling (quarterly default; supports monthly as well)
    period = (request.args.get('period') or 'quarterly').strip().lower()
    branch = (request.args.get('branch') or 'all').strip()

    try:
        y = request.args.get('year', type=int) or get_saudi_now().year
    except Exception:
        y = get_saudi_now().year

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
                today = get_saudi_now().date()
                start_date = date(today.year, today.month, 1)
                nm_y = today.year + (1 if today.month == 12 else 0)
                nm_m = 1 if today.month == 12 else today.month + 1
                end_date = date(nm_y, nm_m, 1) - timedelta(days=1)
        except Exception:
            today = get_saudi_now().date()
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

        # Optional split of zero-tax sales into exempt vs exports using keyword mapping (AppKV)
        try:
            m = kv_get('vat_category_map', {}) or {}
            exempt_kw = [str(x).strip().lower() for x in (m.get('exempt_keywords') or []) if str(x).strip()]
            export_kw = [str(x).strip().lower() for x in (m.get('exports_keywords') or []) if str(x).strip()]
            zero_kw = [str(x).strip().lower() for x in (m.get('zero_keywords') or []) if str(x).strip()]
            q_items = (
                db.session.query(SalesInvoiceItem, SalesInvoice)
                .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
                .filter(SalesInvoice.date.between(start_date, end_date))
            )
            if hasattr(SalesInvoice, 'branch') and branch in ('place_india','china_town'):
                q_items = q_items.filter(SalesInvoice.branch == branch)
            for it, inv_row in q_items.all():
                name = (getattr(it, 'product_name', '') or '').strip().lower()
                qty = float(getattr(it, 'quantity', 0) or 0)
                price = float(getattr(it, 'price_before_tax', 0) or 0)
                disc = float(getattr(it, 'discount', 0) or 0)
                tax = float(getattr(it, 'tax', 0) or 0)
                base = max(0.0, (price * qty) - disc)
                if tax > 0:
                    sales_standard_base += base
                    sales_standard_vat += tax
                    sales_standard_total += (base + tax)
                else:
                    cat = 'zero'
                    if name and export_kw and any(kw in name for kw in export_kw):
                        cat = 'exports'
                    elif name and exempt_kw and any(kw in name for kw in exempt_kw):
                        cat = 'exempt'
                    elif name and zero_kw and any(kw in name for kw in zero_kw):
                        cat = 'zero'
                    if cat == 'exports':
                        sales_exports_base += base
                        sales_exports_vat += 0.0
                        sales_exports_total += base
                    elif cat == 'exempt':
                        sales_exempt_base += base
                        sales_exempt_vat += 0.0
                        sales_exempt_total += base
                    else:
                        sales_zero_base += base
                        sales_zero_vat += 0.0
                        sales_zero_total += base
        except Exception:
            pass

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
    # Include deductible expenses VAT in input VAT
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
        # Expenses breakdown (explicit rows)
        'expenses_deductible_base': float(e_ded_base or 0.0),
        'expenses_deductible_vat': float(e_ded_vat or 0.0),
        'expenses_non_deductible_base': float(e_nd_base or 0.0),
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

    try:
        output_vat = float(db.session.query(func.coalesce(func.sum(SalesInvoice.tax_amount), 0))
            .filter(SalesInvoice.date.between(start_date, end_date))
            .scalar() or 0.0)
    except Exception:
        output_vat = float(sales_total or 0) * vat_rate
    try:
        input_vat = float(db.session.query(func.coalesce(func.sum(PurchaseInvoiceItem.tax), 0))
            .join(PurchaseInvoice, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id)
            .filter(PurchaseInvoice.date.between(start_date, end_date))
            .scalar() or 0.0) + float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.tax_amount), 0))
            .filter(ExpenseInvoice.date.between(start_date, end_date))
            .scalar() or 0.0)
    except Exception:
        input_vat = float((purchases_total or 0) + (expenses_total or 0)) * vat_rate
    net_vat = output_vat - input_vat

    # CSV export
    fmt = (request.args.get('format') or '').strip().lower()
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Metric', 'Amount'])
            writer.writerow(['Sales (Net Base)', float(sales_total or 0.0)])
            writer.writerow(['Purchases', float(purchases_total or 0.0)])
            writer.writerow(['Expenses', float(expenses_total or 0.0)])
            writer.writerow(['Output VAT', float(output_vat or 0.0)])
            writer.writerow(['Input VAT', float(input_vat or 0.0)])
            writer.writerow(['Net VAT', float(net_vat or 0.0)])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': f'attachment; filename="vat_q{quarter}_{year}.csv"'})
        except Exception:
            pass

    # إقرار ضريبي رسمي للطباعة (مواصفات قريبة من نموذج الهيئة)
    company_name = (getattr(s, 'company_name', None) or 'Company').strip() if s else 'Company'
    tax_number = (getattr(s, 'tax_number', None) or '').strip() if s else ''
    address = (getattr(s, 'address', None) or '').strip() if s else ''
    currency = (getattr(s, 'currency', None) or 'SAR').strip() if s else 'SAR'
    period_label = f"الربع {quarter} سنة {year}"
    return render_template(
        'vat/vat_declaration_print.html',
        settings=s,
        company_name=company_name,
        tax_number=tax_number,
        address=address,
        currency=currency,
        generated_at=get_saudi_now().strftime('%d-%m-%Y %H:%M'),
        start_date=start_date.strftime('%d-%m-%Y') if hasattr(start_date, 'strftime') else start_date,
        end_date=end_date.strftime('%d-%m-%Y') if hasattr(end_date, 'strftime') else end_date,
        period_label=period_label,
        branch=branch or 'all',
        vat_rate=vat_rate,
        sales_total=float(sales_total or 0.0),
        purchases_total=float(purchases_total or 0.0),
        expenses_total=float(expenses_total or 0.0),
        output_vat=float(output_vat or 0.0),
        input_vat=float(input_vat or 0.0),
        net_vat=float(net_vat or 0.0),
    )

# ---------- Financials blueprint ----------
financials = Blueprint('financials', __name__, url_prefix='/financials')

@financials.route('/income-statement', endpoint='income_statement')
@login_required
def income_statement():
    period = (request.args.get('period') or 'today').strip()
    today = get_saudi_now().date()
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

    vat_out = vat_in = rev_pi = rev_ct = 0.0
    try:
        from models import JournalLine, JournalEntry
        _base_cred_minus_deb = db.session.query(Account.code, func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0).label('amt')).join(
            JournalLine, JournalLine.account_id == Account.id
        ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(
            JournalLine.line_date >= start_date, JournalLine.line_date <= end_date, JournalEntry.status == 'posted'
        ).group_by(Account.id, Account.code)
        _by_code_cred = {r.code: float(r.amt or 0) for r in _base_cred_minus_deb.all() if getattr(r, 'code', None)}
        _base_deb_minus_cred = db.session.query(Account.id, Account.code, func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0).label('amt')).join(
            JournalLine, JournalLine.account_id == Account.id
        ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(
            JournalLine.line_date >= start_date, JournalLine.line_date <= end_date, JournalEntry.status == 'posted'
        ).group_by(Account.id, Account.code)
        _by_code_deb = {r.code: float(r.amt or 0) for r in _base_deb_minus_cred.all() if getattr(r, 'code', None)}
        vat_out = _by_code_cred.get('2141', 0.0)
        vat_in = _by_code_deb.get('1170', 0.0)
        rev_pi = _by_code_cred.get('4112', 0.0)
        rev_ct = _by_code_cred.get('4111', 0.0)
    except Exception:
        pass

    pl_types = ['REVENUE','OTHER_INCOME','EXPENSE','OTHER_EXPENSE','COGS','TAX']
    type_totals = {}
    for t in pl_types:
        try:
            from models import JournalLine, JournalEntry
            q = db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0) if t in ['REVENUE','OTHER_INCOME'] else func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).join(
                JournalEntry, JournalLine.journal_id == JournalEntry.id
            ).join(Account, JournalLine.account_id == Account.id).filter(
                Account.type == t,
                JournalLine.line_date >= start_date,
                JournalLine.line_date <= end_date,
                JournalEntry.status == 'posted'
            ).scalar() or 0.0
            type_totals[t] = float(q)
        except Exception:
            type_totals[t] = 0.0


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
        'zakat': 0.0,
        'income_tax': 0.0,
        'net_profit_after_tax': float(net_profit_after_tax or 0.0),
        'vat_out': float(vat_out or 0.0),
        'vat_in': float(vat_in or 0.0),
        'revenue_by_branch': {'Place India': float(rev_pi or 0.0), 'China Town': float(rev_ct or 0.0)},
        'type_totals': type_totals,
    }
    return render_template('financials/income_statement.html', data=data)


@financials.route('/print/income_statement', methods=['GET'], endpoint='print_income_statement')
@login_required
def print_income_statement():
    # Period params
    period = (request.args.get('period') or 'today').strip()
    today = get_saudi_now().date()
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
                           generated_at=get_saudi_now().strftime('%Y-%m-%d %H:%M'),
                           start_date=start_date.isoformat(), end_date=end_date.isoformat(),
                           payment_method=None, branch=branch or 'all',
                           columns=columns, data=rows, totals=totals, totals_columns=['Amount'],
                           totals_colspan=1, payment_totals=None)



@financials.route('/balance-sheet', endpoint='balance_sheet')
@login_required
def balance_sheet():
    d_str = (request.args.get('date') or get_saudi_now().date().isoformat())
    try:
        asof = datetime.strptime(d_str, '%Y-%m-%d').date()
    except Exception:
        asof = get_saudi_now().date()

    from models import JournalLine, JournalEntry
    from sqlalchemy import or_, and_
    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted'))) \
     .group_by(Account.id) \
     .order_by(Account.type.asc(), Account.code.asc()).all()

    ca_codes = {'1111','1112','1121','1122','1123','1131','1132','1141','1142','1151','1152','1161','1162','1170'}
    cl_codes = {'2111','2121','2122','2131','2132','2133','2141','2142','2151','2152','2153'}
    current_assets = 0.0
    noncurrent_assets = 0.0
    current_liabilities = 0.0
    noncurrent_liabilities = 0.0
    asset_rows_detail = []
    liability_rows_detail = []
    equity_rows_detail = []
    for r in rows:
        if r.type == 'ASSET':
            bal = float(r.debit or 0) - float(r.credit or 0)
            if (r.code or '') in ca_codes:
                current_assets += bal
            else:
                noncurrent_assets += bal
            asset_rows_detail.append({'code': r.code, 'name': r.name, 'balance': bal, 'class': 'Current' if (r.code or '') in ca_codes else 'Non-current'})
        elif r.type == 'LIABILITY':
            bal = float(r.credit or 0) - float(r.debit or 0)
            if (r.code or '') in cl_codes:
                current_liabilities += bal
            else:
                noncurrent_liabilities += bal
            liability_rows_detail.append({'code': r.code, 'name': r.name, 'balance': bal, 'class': 'Current' if (r.code or '') in cl_codes else 'Non-current'})
        elif r.type == 'EQUITY':
            bal = float(r.credit or 0) - float(r.debit or 0)
            equity_rows_detail.append({'code': r.code, 'name': r.name, 'balance': bal})
    assets = current_assets + noncurrent_assets
    liabilities = current_liabilities + noncurrent_liabilities
    equity = assets - liabilities
    type_totals = {}
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        d = float(r.debit or 0)
        c = float(r.credit or 0)
        if t not in type_totals:
            type_totals[t] = {'debit': 0.0, 'credit': 0.0}
        type_totals[t]['debit'] += d
        type_totals[t]['credit'] += c
    data = {
        'date': asof,
        'assets': assets, 'liabilities': liabilities, 'equity': equity,
        'current_assets': current_assets, 'noncurrent_assets': noncurrent_assets,
        'current_liabilities': current_liabilities, 'noncurrent_liabilities': noncurrent_liabilities,
        'asset_rows_detail': asset_rows_detail,
        'liability_rows_detail': liability_rows_detail,
        'equity_rows_detail': equity_rows_detail,
        'type_totals': type_totals
    }
    return render_template('financials/balance_sheet.html', data=data)

@financials.route('/trial-balance', endpoint='trial_balance')
@login_required
def trial_balance():
    d_str = (request.args.get('date') or get_saudi_now().date().isoformat())
    try:
        asof = datetime.strptime(d_str, '%Y-%m-%d').date()
    except Exception:
        asof = get_saudi_now().date()
    from models import JournalLine, JournalEntry
    from sqlalchemy import or_, and_
    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted'))) \
     .group_by(Account.id) \
     .order_by(Account.type.asc(), Account.code.asc()).all()
    if not rows:
        rows = []
    total_debit = float(sum([float(getattr(r, 'debit', 0) or 0) for r in rows]))
    total_credit = float(sum([float(getattr(r, 'credit', 0) or 0) for r in rows]))
    type_totals = {}
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        d = float(getattr(r, 'debit', 0) or 0)
        c = float(getattr(r, 'credit', 0) or 0)
        if t not in type_totals:
            type_totals[t] = {'debit': 0.0, 'credit': 0.0}
        type_totals[t]['debit'] += d
        type_totals[t]['credit'] += c
    data = {
        'date': asof,
        'rows': rows,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'type_totals': type_totals,
    }
    return render_template('financials/trial_balance.html', data=data)


@financials.route('/ledger/backfill', methods=['GET', 'POST'], endpoint='ledger_backfill')
@login_required
def ledger_backfill():
    sd = request.args.get('start_date')
    ed = request.args.get('end_date')
    scope = (request.args.get('scope') or 'all').strip().lower()
    today = get_saudi_now().date()
    try:
        start_date = datetime.strptime(sd, '%Y-%m-%d').date() if sd else date(today.year, 1, 1)
        end_date = datetime.strptime(ed, '%Y-%m-%d').date() if ed else date(today.year, 12, 31)
    except Exception:
        start_date = date(today.year, 1, 1)
        end_date = date(today.year, 12, 31)

    def get_or_create(code, name, type_):
        acc = Account.query.filter_by(code=code).first()
        if not acc:
            acc = Account(code=code, name=name, type=type_)
            db.session.add(acc)
            db.session.flush()
        return acc

    def pm_code(pm):
        p = (pm or 'CASH').strip().upper()
        if p in ('CASH',):
            return '1111'
        if p in ('BANK','CARD','VISA','MASTERCARD','MADA','ONLINE','TRANSFER'):
            return '1121'
        return '1141'

    created = {'sales': 0, 'purchase': 0, 'expense': 0}

    if scope in ('all','sales'):
        try:
            for inv in SalesInvoice.query.filter(SalesInvoice.date.between(start_date, end_date)).all():
                desc_key = f"Sales {inv.invoice_number}"
                exists = db.session.query(LedgerEntry.id).filter(LedgerEntry.description == desc_key).first()
                if exists:
                    continue
                gross = float(inv.total_after_tax_discount or 0.0)
                base = max(0.0, float(inv.total_before_tax or 0.0) - float(inv.discount_amount or 0.0))
                vat = float(inv.tax_amount or 0.0)
                cash_code = pm_code(inv.payment_method)
                cash_acc = get_or_create(cash_code, 'صندوق رئيسي' if cash_code=='1111' else ('بنك' if cash_code=='1121' else 'عملاء'), 'ASSET')
                rev_code = '4111'
                rev_name = 'مبيعات CHINA TOWN'
                rev_acc = get_or_create(rev_code, rev_name, 'REVENUE')
                vat_out_acc = get_or_create('2141', 'ضريبة القيمة المضافة – مستحقة', 'LIABILITY')
                db.session.add(LedgerEntry(date=inv.date, account_id=cash_acc.id, debit=gross, credit=0, description=desc_key))
                if base > 0:
                    db.session.add(LedgerEntry(date=inv.date, account_id=rev_acc.id, debit=0, credit=base, description=desc_key))
                if vat > 0:
                    db.session.add(LedgerEntry(date=inv.date, account_id=vat_out_acc.id, debit=0, credit=vat, description=f"VAT Output {inv.invoice_number}"))
                created['sales'] += 1
            db.session.commit()
        except Exception:
            db.session.rollback()

    if scope in ('all','purchase'):
        try:
            for inv in PurchaseInvoice.query.filter(PurchaseInvoice.date.between(start_date, end_date)).all():
                desc_key = f"Purchase {inv.invoice_number}"
                exists = db.session.query(LedgerEntry.id).filter(LedgerEntry.description == desc_key).first()
                if exists:
                    continue
                base = float(inv.total_before_tax or 0.0)
                vat = float(inv.tax_amount or 0.0)
                gross = float(inv.total_after_tax_discount or 0.0)
                inv_acc = get_or_create('1161', 'مخزون بضائع', 'ASSET')
                vat_in_acc = get_or_create('1170', 'ضريبة القيمة المضافة – مدخلات', 'ASSET')
                ap_acc = get_or_create('2111', 'موردون', 'LIABILITY')
                db.session.add(LedgerEntry(date=inv.date, account_id=inv_acc.id, debit=base, credit=0, description=desc_key))
                if vat > 0:
                    db.session.add(LedgerEntry(date=inv.date, account_id=vat_in_acc.id, debit=vat, credit=0, description=f"VAT Input {inv.invoice_number}"))
                db.session.add(LedgerEntry(date=inv.date, account_id=ap_acc.id, credit=gross, debit=0, description=f"AP for {inv.invoice_number}"))
                created['purchase'] += 1
            db.session.commit()
        except Exception:
            db.session.rollback()

    if scope in ('all','expense'):
        try:
            for inv in ExpenseInvoice.query.filter(ExpenseInvoice.date.between(start_date, end_date)).all():
                desc_key = f"Expense {inv.invoice_number}"
                exists = db.session.query(LedgerEntry.id).filter(LedgerEntry.description == desc_key).first()
                if exists:
                    continue
                base = max(0.0, float(inv.total_before_tax or 0.0) - float(inv.discount_amount or 0.0))
                vat = float(inv.tax_amount or 0.0)
                gross = float(inv.total_after_tax_discount or 0.0)
                exp_acc = get_or_create('5470', 'مصروفات متنوعة إدارية', 'EXPENSE')
                vat_in_acc = get_or_create('1170', 'ضريبة القيمة المضافة – مدخلات', 'ASSET')
                ap_acc = get_or_create('2111', 'موردون', 'LIABILITY')
                if base > 0:
                    db.session.add(LedgerEntry(date=inv.date, account_id=exp_acc.id, debit=base, credit=0, description=desc_key))
                if vat > 0:
                    db.session.add(LedgerEntry(date=inv.date, account_id=vat_in_acc.id, debit=vat, credit=0, description=f"VAT Input {inv.invoice_number}"))
                db.session.add(LedgerEntry(date=inv.date, account_id=ap_acc.id, credit=gross, debit=0, description=f"AP for {inv.invoice_number}"))
                created['expense'] += 1
            db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({'status': 'ok', 'created': created, 'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(), 'scope': scope})


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
                           generated_at=get_saudi_now().strftime('%Y-%m-%d %H:%M'),
                           start_date=d, end_date=d,
                           payment_method=None, branch='all',
                           columns=columns, data=data_rows, totals=totals, totals_columns=['Amount'],
                           totals_colspan=1, payment_totals=None)

@financials.route('/trial-balance/print', endpoint='print_trial_balance')
@login_required
def print_trial_balance():
    d_str = (request.args.get('date') or get_saudi_now().date().isoformat())
    try:
        asof = datetime.strptime(d_str, '%Y-%m-%d').date()
    except Exception:
        asof = get_saudi_now().date()
    from models import JournalLine, JournalEntry
    from sqlalchemy import or_, and_
    rows_q = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted'))) \
     .group_by(Account.id) \
     .order_by(Account.code.asc()).all()
    rows = []
    if rows_q:
        try:
            from data.coa_new_tree import get_account_display_name
        except Exception:
            get_account_display_name = lambda code, name: name or code
        for r in rows_q:
            rows.append({'Code': r.code, 'Account': get_account_display_name(r.code, r.name), 'Debit': float(r.debit or 0.0), 'Credit': float(r.credit or 0.0)})
    total_debit = float(sum([float(r.get('Debit') or 0.0) for r in rows]))
    total_credit = float(sum([float(r.get('Credit') or 0.0) for r in rows]))
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    columns = ['Code', 'Account', 'Debit', 'Credit']
    totals = {'Debit': total_debit, 'Credit': total_credit}
    return render_template('print_report.html', report_title=f"Trial Balance — {asof}", settings=settings,
                           generated_at=get_saudi_now().strftime('%Y-%m-%d %H:%M'),
                           start_date=asof, end_date=asof,
                           payment_method=None, branch='all',
                           columns=columns, data=rows, totals=totals, totals_columns=['Debit','Credit'],
                           totals_colspan=2, payment_totals=None)


# --------- Minimal report APIs to avoid 404s and support UI tables/prints ---------
@main.route('/api/all-invoices', methods=['GET'], endpoint='api_all_invoices')
@login_required
def api_all_invoices():
    try:
        payment_method = (request.args.get('payment_method') or 'all').strip().lower()
        branch_f = (request.args.get('branch') or 'all').strip().lower()
        start_date = (request.args.get('start_date') or '').strip()
        end_date = (request.args.get('end_date') or '').strip()
        type_f = (request.args.get('type') or 'all').strip().lower()
        if type_f not in ('sales', 'purchases', 'expenses', 'all'):
            type_f = 'all'
        try:
            per_page = min(int(request.args.get('per_page') or request.args.get('limit') or 50), 500)
        except (TypeError, ValueError):
            per_page = 50
        try:
            page = max(1, int(request.args.get('page') or 1))
        except (TypeError, ValueError):
            page = 1
        offset = (page - 1) * per_page
        limit = per_page
        rows = []
        branch_totals = {}
        overall = {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0}

        # Join sales invoices with items for itemized view
        from models import SalesInvoice, SalesInvoiceItem, PurchaseInvoice, PurchaseInvoiceItem

        # معالجة فواتير المبيعات (فقط عند type=sales أو all)
        if type_f in ('sales', 'all'):
            q_sales = db.session.query(SalesInvoice, SalesInvoiceItem).join(SalesInvoiceItem, SalesInvoiceItem.invoice_id == SalesInvoice.id)
            if payment_method and payment_method != 'all':
                q_sales = q_sales.filter(func.lower(SalesInvoice.payment_method) == payment_method)
            if branch_f and branch_f != 'all':
                q_sales = q_sales.filter(func.lower(SalesInvoice.branch) == branch_f)
            if start_date:
                try:
                    if hasattr(SalesInvoice, 'created_at'):
                        q_sales = q_sales.filter(func.date(SalesInvoice.created_at) >= start_date)
                    elif hasattr(SalesInvoice, 'date'):
                        q_sales = q_sales.filter(SalesInvoice.date >= start_date)
                except Exception:
                    pass
            if end_date:
                try:
                    if hasattr(SalesInvoice, 'created_at'):
                        q_sales = q_sales.filter(func.date(SalesInvoice.created_at) <= end_date)
                    elif hasattr(SalesInvoice, 'date'):
                        q_sales = q_sales.filter(SalesInvoice.date <= end_date)
                except Exception:
                    pass
            if hasattr(SalesInvoice, 'created_at'):
                q_sales = q_sales.order_by(SalesInvoice.created_at.desc())
            elif hasattr(SalesInvoice, 'date'):
                q_sales = q_sales.order_by(SalesInvoice.date.desc())
            total_sales = q_sales.count()
            results_sales = q_sales.limit(limit).offset(offset).all()
        else:
            total_sales = 0
            results_sales = []

        # معالجة فواتير المشتريات (فقط عند type=purchases أو all)
        if type_f in ('purchases', 'all'):
            q_purchases = db.session.query(PurchaseInvoice, PurchaseInvoiceItem).join(PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id)
            if payment_method and payment_method != 'all':
                q_purchases = q_purchases.filter(func.lower(PurchaseInvoice.payment_method) == payment_method)
            if branch_f and branch_f != 'all':
                q_purchases = q_purchases.filter(func.lower(PurchaseInvoice.branch) == branch_f)
            if start_date:
                try:
                    if hasattr(PurchaseInvoice, 'created_at'):
                        q_purchases = q_purchases.filter(func.date(PurchaseInvoice.created_at) >= start_date)
                    elif hasattr(PurchaseInvoice, 'date'):
                        q_purchases = q_purchases.filter(PurchaseInvoice.date >= start_date)
                except Exception:
                    pass
            if end_date:
                try:
                    if hasattr(PurchaseInvoice, 'created_at'):
                        q_purchases = q_purchases.filter(func.date(PurchaseInvoice.created_at) <= end_date)
                    elif hasattr(PurchaseInvoice, 'date'):
                        q_purchases = q_purchases.filter(PurchaseInvoice.date <= end_date)
                except Exception:
                    pass
            if hasattr(PurchaseInvoice, 'created_at'):
                q_purchases = q_purchases.order_by(PurchaseInvoice.created_at.desc())
            elif hasattr(PurchaseInvoice, 'date'):
                q_purchases = q_purchases.order_by(PurchaseInvoice.date.desc())
            total_purchases = q_purchases.count()
            results_purchases = q_purchases.limit(limit).offset(offset).all()
        else:
            total_purchases = 0
            results_purchases = []
        
        # معالجة فواتير المبيعات
        # Aggregate invoice base for proportional head discount/VAT allocation
        inv_base = {}
        for inv, it in results_sales:
            line_base = float(getattr(it, 'price_before_tax', 0.0) or 0.0) * float(getattr(it, 'quantity', 0.0) or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results_sales:
            branch = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
            if getattr(inv, 'created_at', None):
                date_s = inv.created_at.date().isoformat()
            elif getattr(inv, 'date', None):
                date_s = inv.date.isoformat()
            else:
                date_s = ''
            amount = float((getattr(it, 'price_before_tax', 0.0) or 0.0) * (getattr(it, 'quantity', 0.0) or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat  = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat  = inv_vat  * (amount / base_total)
            else:
                disc = float(getattr(it, 'discount', 0.0) or 0.0)
                vat  = float(getattr(it, 'tax', 0.0) or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            total = base_after_disc + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'branch': branch,
                'date': date_s,
                'invoice_number': inv.invoice_number + ' (بيع)',
                'item_name': getattr(it, 'product_name', '') or '',
                'quantity': float(getattr(it, 'quantity', 0.0) or 0.0),
                'price': amount,
                'discount': round(disc, 2),
                'vat': round(vat, 2),
                'total': round(total, 2),
                'payment_method': pm,
                'type': 'sale'
            })
            bt = branch_totals.setdefault(branch, {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0})
            bt['amount'] += amount; bt['discount'] += disc; bt['vat'] += vat; bt['total'] += total
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += total

        # معالجة فواتير المشتريات
        # Aggregate invoice base for proportional head discount/VAT allocation
        inv_base_purchases = {}
        for inv, it in results_purchases:
            line_base = float(getattr(it, 'price_before_tax', 0.0) or 0.0) * float(getattr(it, 'quantity', 0.0) or 0.0)
            inv_base_purchases[inv.id] = inv_base_purchases.get(inv.id, 0.0) + line_base

        for inv, it in results_purchases:
            branch = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
            if getattr(inv, 'created_at', None):
                date_s = inv.created_at.date().isoformat()
            elif getattr(inv, 'date', None):
                date_s = inv.date.isoformat()
            else:
                date_s = ''
            amount = float((getattr(it, 'price_before_tax', 0.0) or 0.0) * (getattr(it, 'quantity', 0.0) or 0.0))
            base_total = float(inv_base_purchases.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat  = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat  = inv_vat  * (amount / base_total)
            else:
                disc = float(getattr(it, 'discount', 0.0) or 0.0)
                vat  = float(getattr(it, 'tax', 0.0) or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            total = base_after_disc + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'branch': branch,
                'date': date_s,
                'invoice_number': inv.invoice_number + ' (شراء)',
                'item_name': getattr(it, 'raw_material_name', '') or '',
                'quantity': float(getattr(it, 'quantity', 0.0) or 0.0),
                'price': amount,
                'discount': round(disc, 2),
                'vat': round(vat, 2),
                'total': round(total, 2),
                'payment_method': pm,
                'type': 'purchase'
            })
            bt = branch_totals.setdefault(branch, {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0})
            bt['amount'] += amount; bt['discount'] += disc; bt['vat'] += vat; bt['total'] += total
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += total

        pages_sales = max(1, (total_sales + per_page - 1) // per_page) if type_f in ('sales', 'all') else 1
        pages_purchases = max(1, (total_purchases + per_page - 1) // per_page) if type_f in ('purchases', 'all') else 1
        pages = max(pages_sales, pages_purchases) if type_f == 'all' else (pages_sales if type_f == 'sales' else pages_purchases)
        has_more = (len(results_sales) == limit or len(results_purchases) == limit)
        return jsonify({
            'invoices': rows,
            'branch_totals': branch_totals,
            'overall_totals': overall,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'offset': offset,
                'total_sales': total_sales,
                'total_purchases': total_purchases,
                'has_more': has_more,
                'pages': pages,
            }
        })
    except Exception as e:
        try:
            current_app.logger.exception(f"/api/all-invoices failed: {e}")
        except Exception:
            pass
        return jsonify({'invoices': [], 'branch_totals': {}, 'overall_totals': {'amount':0,'discount':0,'vat':0,'total':0}, 'note': 'stub', 'error': str(e)}), 200


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


@main.route('/api/vat/categories-map', methods=['GET','POST'], endpoint='api_vat_categories_map')
@login_required
def api_vat_categories_map():
    try:
        default_map = {
            'zero_keywords': [],
            'exempt_keywords': [],
            'exports_keywords': []
        }
        if request.method == 'GET':
            m = kv_get('vat_category_map', default_map) or default_map
            return jsonify({'ok': True, 'map': m})
        data = request.get_json(silent=True) or {}
        out = {
            'zero_keywords': [str(x).strip() for x in (data.get('zero_keywords') or []) if str(x).strip()],
            'exempt_keywords': [str(x).strip() for x in (data.get('exempt_keywords') or []) if str(x).strip()],
            'exports_keywords': [str(x).strip() for x in (data.get('exports_keywords') or []) if str(x).strip()],
        }
        kv_set('vat_category_map', out)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
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


def _archive_invoice_pdf(inv):
    import os, io
    try:
        dt = getattr(inv, 'created_at', None) or get_saudi_now()
    except Exception:
        dt = get_saudi_now()
    year = dt.year; month = dt.month; day = dt.day
    quarter_num = ((month - 1) // 3) + 1
    quarter = f"Q{quarter_num}"
    base_dir = os.getenv('ARCHIVE_DIR') or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Archive')
    rel_dir = os.path.join(str(year), quarter, f"{month:02d}", f"{day:02d}")
    out_dir = os.path.join(base_dir, rel_dir)
    os.makedirs(out_dir, exist_ok=True)
    fname = f"INV-{inv.invoice_number}.pdf"
    fpath = os.path.join(out_dir, fname)
    # Render receipt HTML
    try:
        items = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).all()
        items_ctx = []
        for it in items:
            line = float(getattr(it, 'price_before_tax', 0) or 0) * float(getattr(it, 'quantity', 0) or 0)
            items_ctx.append({'product_name': getattr(it, 'product_name', '') or '', 'quantity': float(getattr(it, 'quantity', 0) or 0), 'total_price': line})
        s = None
        try:
            s = Settings.query.first()
        except Exception:
            s = None
        dt_str = get_saudi_now().strftime('%Y-%m-%d %H:%M:%S')
        html = render_template('print/receipt.html', inv={
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
        }, items=items_ctx, settings=s, branch_name=BRANCH_LABELS.get(getattr(inv,'branch',None) or '', getattr(inv,'branch','')), date_time=dt_str, display_invoice_number=inv.invoice_number)
    except Exception:
        html = '<html><body><h3>Receipt</h3><p>Render failed.</p></body></html>'
    # Convert to PDF
    pdf_bytes = None
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html, base_url=current_app.root_path).write_pdf()
    except Exception:
        try:
            import pdfkit
            pdf_bytes = pdfkit.from_string(html, False)
        except Exception:
            pdf_bytes = None
    if pdf_bytes:
        with open(fpath, 'wb') as f:
            f.write(pdf_bytes)
    else:
        # Fallback: save HTML for now
        fpath = fpath[:-4] + '.html'
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(html)
    try:
        kv_set(f"pdf_path:sales:{inv.invoice_number}", {'path': fpath, 'saved_at': get_saudi_now().isoformat()})
    except Exception:
        pass

@main.route('/api/archive/list', methods=['GET'], endpoint='api_archive_list')
def api_archive_list():
    try:
        year = request.args.get('year', type=int)
        quarter = (request.args.get('quarter') or '').strip().upper() or None
        month = request.args.get('month', type=int)
        day = request.args.get('day', type=int)
        branch = (request.args.get('branch') or '').strip()
        last4 = (request.args.get('last4') or '').strip()
        page = request.args.get('page', type=int) or 1
        page_size = request.args.get('page_size', type=int) or 100
        if page_size > 500:
            page_size = 500
        if page_size < 1:
            page_size = 100
        if (not year) and (month or day or quarter):
            year = get_saudi_now().year
        start_date = None
        end_date = None
        if year and (not quarter and not month and not day):
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
        if year and quarter and (not month and not day):
            qmap = {'Q1': (1, 3), 'Q2': (4, 6), 'Q3': (7, 9), 'Q4': (10, 12)}
            rng = qmap.get(quarter)
            if rng:
                start_date = datetime(year, rng[0], 1)
                if rng[1] == 12:
                    end_date = datetime(year, 12, 31, 23, 59, 59)
                else:
                    end_date = datetime(year, rng[1] + 1, 1) - timedelta(seconds=1)
        if year and month and (not day):
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year, 12, 31, 23, 59, 59)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        if year and month and day:
            start_date = datetime(year, month, day)
            end_date = start_date + timedelta(days=1) - timedelta(seconds=1)

        q = db.session.query(
            SalesInvoice.invoice_number,
            SalesInvoice.created_at,
            SalesInvoice.date,
            SalesInvoice.payment_method,
            SalesInvoice.total_after_tax_discount,
            SalesInvoice.branch
        ).filter((SalesInvoice.status == 'paid'))
        if branch:
            q = q.filter(SalesInvoice.branch == branch)
        if start_date and end_date:
            q = q.filter(SalesInvoice.date.between(start_date.date(), end_date.date()))
        if last4:
            try:
                if len(last4) <= 8:
                    q = q.filter(SalesInvoice.invoice_number.like(f"%{last4}"))
            except Exception:
                pass
        q = q.order_by(SalesInvoice.date.desc(), SalesInvoice.created_at.desc())
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
        keys = [f"pdf_path:sales:{r[0]}" for r in rows]
        meta_rows = AppKV.query.filter(AppKV.k.in_(keys)).all() if keys else []
        log_keys = [f"print_log:{r[0]}" for r in rows]
        log_rows = AppKV.query.filter(AppKV.k.in_(log_keys)).all() if log_keys else []
        meta_map = {}
        for kv in meta_rows:
            try:
                meta_map[kv.k] = json.loads(kv.v) if kv.v else {}
            except Exception:
                meta_map[kv.k] = {}
        logs_map = {}
        for kv in log_rows:
            try:
                logs_map[kv.k] = json.loads(kv.v) if kv.v else []
            except Exception:
                logs_map[kv.k] = []
        out = []
        for r in rows:
            inv_no, created_at, date_f, pm, total_amt, branch_code = r
            # Use saved print timestamp if available
            meta = meta_map.get(f"pdf_path:sales:{inv_no}", {}) or {}
            logs = logs_map.get(f"print_log:{inv_no}", []) or []
            dt_print = None
            try:
                if logs:
                    try:
                        from datetime import datetime as _dti
                        def _p(x):
                            try:
                                return _dti.fromisoformat((x or {}).get('ts') or '')
                            except Exception:
                                return None
                        cand = [_p(x) for x in logs]
                        cand = [c for c in cand if c]
                        if cand:
                            dt_print = min(cand)
                    except Exception:
                        dt_print = None
                if (dt_print is None):
                    sa = meta.get('saved_at')
                    if sa:
                        try:
                            from datetime import datetime as _dti
                            dt_print = _dti.fromisoformat(sa)
                        except Exception:
                            dt_print = None
            except Exception:
                dt_print = None
            if dt_print is not None:
                dt_date = dt_print.date()
                tstr = dt_print.strftime('%H:%M:%S')
            else:
                try:
                    from models import SalesInvoice as SI, Payment
                    sid = db.session.query(SI.id).filter(SI.invoice_number == inv_no).scalar()
                    dtp_row = None
                    if sid:
                        dtp_row = db.session.query(Payment.payment_date).\
                            filter(Payment.invoice_type == 'sales', Payment.invoice_id == sid).\
                            order_by(Payment.payment_date.asc()).first()
                    if dtp_row and dtp_row[0]:
                        dt_date = dtp_row[0].date()
                        tstr = dtp_row[0].strftime('%H:%M:%S')
                    else:
                        raise Exception('no_payment_date')
                except Exception:
                    dt_date = (date_f or (created_at and created_at.date()) or get_saudi_now().date())
                    try:
                        tstr = created_at.strftime('%H:%M:%S') if created_at else '00:00:00'
                    except Exception:
                        tstr = '00:00:00'
            m = int(dt_date.month)
            qn = ((m - 1) // 3) + 1
            out.append({
                'invoice_number': inv_no,
                'date': dt_date.strftime('%Y-%m-%d'),
                'time': tstr,
                'payment_method': pm,
                'total_amount': float(total_amt or 0.0),
                'branch': branch_code,
                'quarter': f"Q{qn}",
                'pdf_path': meta.get('path')
            })
        if quarter in ('Q1','Q2','Q3','Q4'):
            out = [x for x in out if x['quarter'] == quarter]
        return jsonify({'ok': True, 'items': out, 'page': page, 'page_size': page_size})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/archive/open/<invoice_number>', methods=['GET'], endpoint='archive_open')
@login_required
def archive_open(invoice_number):
    try:
        meta = kv_get(f"pdf_path:sales:{invoice_number}", {}) or {}
        p = meta.get('path')
        if not p or (not os.path.exists(p)):
            return 'File not found', 404
        return send_file(p, as_attachment=False)
    except Exception as e:
        return f'Error: {e}', 500

@main.route('/archive', methods=['GET'], endpoint='archive')
@login_required
def archive_page():
    try:
        return render_template('archive.html', now=get_saudi_now(), branches=BRANCH_LABELS)
    except Exception as e:
        return f'Error loading archive: {e}', 500

@main.route('/archive/download', methods=['GET'], endpoint='archive_download')
@login_required
def archive_download():
    try:
        import io, zipfile, csv
        year = request.args.get('year', type=int)
        quarter = (request.args.get('quarter') or '').strip().upper() or None
        month = request.args.get('month', type=int)
        day = request.args.get('day', type=int)
        branch = (request.args.get('branch') or '').strip()
        fmt = (request.args.get('fmt') or '').strip().lower() or 'zip'
        if (not year) and (month or day or quarter):
            year = get_saudi_now().year
        start_date = None
        end_date = None
        if year and (not quarter and not month and not day):
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
        if year and quarter and (not month and not day):
            qmap = {'Q1': (1, 3), 'Q2': (4, 6), 'Q3': (7, 9), 'Q4': (10, 12)}
            rng = qmap.get(quarter)
            if rng:
                start_date = datetime(year, rng[0], 1)
                if rng[1] == 12:
                    end_date = datetime(year, 12, 31, 23, 59, 59)
                else:
                    end_date = datetime(year, rng[1] + 1, 1) - timedelta(seconds=1)
        if year and month and (not day):
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year, 12, 31, 23, 59, 59)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        if year and month and day:
            start_date = datetime(year, month, day)
            end_date = start_date + timedelta(days=1) - timedelta(seconds=1)
        # فقط الفواتير المرتبطة بقيود (مصدر الحقيقة) — لا مجرد PDF مخزن
        with_journal = db.session.query(JournalEntry.invoice_id).filter(
            JournalEntry.invoice_type == 'sales',
            JournalEntry.invoice_id.isnot(None)
        ).distinct()
        q = db.session.query(
            SalesInvoice.invoice_number,
            SalesInvoice.created_at,
            SalesInvoice.date,
            SalesInvoice.payment_method,
            SalesInvoice.total_after_tax_discount,
            SalesInvoice.branch
        ).filter((SalesInvoice.status == 'paid'), SalesInvoice.id.in_(with_journal))
        if branch:
            q = q.filter(SalesInvoice.branch == branch)
        if start_date and end_date:
            q = q.filter(SalesInvoice.date.between(start_date.date(), end_date.date()))
        rows = q.order_by(SalesInvoice.date.desc(), SalesInvoice.created_at.desc()).limit(2000).all()
        items = []
        keys = [f"pdf_path:sales:{r[0]}" for r in rows]
        meta_rows = AppKV.query.filter(AppKV.k.in_(keys)).all() if keys else []
        log_keys = [f"print_log:{r[0]}" for r in rows]
        log_rows = AppKV.query.filter(AppKV.k.in_(log_keys)).all() if log_keys else []
        meta_map = {}
        for kv in meta_rows:
            try:
                meta_map[kv.k] = json.loads(kv.v) if kv.v else {}
            except Exception:
                meta_map[kv.k] = {}
        logs_map = {}
        for kv in log_rows:
            try:
                logs_map[kv.k] = json.loads(kv.v) if kv.v else []
            except Exception:
                logs_map[kv.k] = []
        for r in rows:
            inv_no, created_at, date_f, pm, total_amt, branch_code = r
            meta = meta_map.get(f"pdf_path:sales:{inv_no}", {}) or {}
            logs = logs_map.get(f"print_log:{inv_no}", []) or []
            dt_print = None
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
                        dt_print = min(cand)
                if (dt_print is None):
                    sa = meta.get('saved_at')
                    if sa:
                        from datetime import datetime as _dti
                        try:
                            dt_print = _dti.fromisoformat(sa)
                        except Exception:
                            dt_print = None
            except Exception:
                dt_print = None
            if dt_print is None:
                try:
                    from models import SalesInvoice as SI, Payment
                    sid = db.session.query(SI.id).filter(SI.invoice_number == inv_no).scalar()
                    dtp_row = None
                    if sid:
                        dtp_row = db.session.query(Payment.payment_date).\
                            filter(Payment.invoice_type == 'sales', Payment.invoice_id == sid).\
                            order_by(Payment.payment_date.asc()).first()
                    if dtp_row and dtp_row[0]:
                        dt_date = dtp_row[0].date()
                    else:
                        dt_date = (date_f or (created_at and created_at.date()) or get_saudi_now().date())
                except Exception:
                    dt_date = (date_f or (created_at and created_at.date()) or get_saudi_now().date())
            else:
                dt_date = dt_print.date()
            m = int(dt_date.month)
            qn = ((m - 1) // 3) + 1
            if quarter in ('Q1','Q2','Q3','Q4') and f"Q{qn}" != quarter:
                continue
            p = meta.get('path')
            items.append({
                'invoice_number': inv_no,
                'date': dt_date.strftime('%Y-%m-%d'),
                'payment_method': pm,
                'total_amount': float(total_amt or 0.0),
                'branch': branch_code,
                'quarter': f"Q{qn}",
                'pdf_path': p if (p and os.path.exists(p)) else None
            })
        ts = get_saudi_now().strftime('%Y%m%d-%H%M%S')
        if fmt == 'csv':
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(['invoice_number','date','payment_method','total_amount','branch','quarter','pdf_path'])
            for it in items:
                w.writerow([it['invoice_number'], it['date'], it['payment_method'] or '', f"{it['total_amount']:.2f}", it['branch'] or '', it['quarter'], it['pdf_path'] or ''])
            data = out.getvalue().encode('utf-8')
            buf = io.BytesIO(data)
            return send_file(buf, mimetype='text/csv', as_attachment=True, download_name=f"invoices-{ts}.csv")
        else:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                manifest = io.StringIO()
                w = csv.writer(manifest)
                w.writerow(['invoice_number','date','payment_method','total_amount','branch','quarter','pdf_path'])
                for it in items:
                    w.writerow([it['invoice_number'], it['date'], it['payment_method'] or '', f"{it['total_amount']:.2f}", it['branch'] or '', it['quarter'], it['pdf_path'] or ''])
                z.writestr('manifest.csv', manifest.getvalue())
                for it in items:
                    if it['pdf_path']:
                        name = f"{it['invoice_number']}.pdf"
                        try:
                            z.write(it['pdf_path'], arcname=name)
                        except Exception:
                            pass
            buf.seek(0)
            return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=f"invoices-{ts}.zip")
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
def _account(code, name, kind):
    try:
        a = Account.query.filter(func.lower(Account.code) == code.lower()).first()
        if not a:
            a = Account(code=code.upper(), name=name, type=kind)
            db.session.add(a)
            db.session.flush()
        return a
    except Exception:
        return None

def _pm_account(pm):
    """حساب الدفع: يُحدد من إعدادات الحسابات (account_usage_map) إن وُجد، وإلا من SHORT_TO_NUMERIC."""
    p = (pm or 'CASH').strip().upper()
    usage_group = 'Cash' if p == 'CASH' else 'Bank'
    try:
        acc = (
            db.session.query(Account)
            .join(AccountUsageMap, AccountUsageMap.account_id == Account.id)
            .filter(
                AccountUsageMap.module == 'Payments',
                AccountUsageMap.action == 'PayExpense',
                AccountUsageMap.usage_group == usage_group,
                AccountUsageMap.active == True,
            )
            .order_by(AccountUsageMap.is_default.desc())
            .first()
        )
        if acc:
            return acc
    except Exception:
        pass
    try:
        from app.routes import SHORT_TO_NUMERIC as _short
    except Exception:
        _short = {}
    if p == 'CASH':
        tgt = _short.get('CASH') or ('1111','صندوق رئيسي','ASSET')
    else:
        tgt = _short.get('BANK') or ('1121','بنك الراجحي','ASSET')
    return _account(tgt[0], tgt[1], tgt[2])

def _acc_override(name: str, default_code: str) -> str:
    try:
        m = kv_get('acc_map', {}) or {}
        code = (m.get(name) or '').strip()
        if code:
            return code
    except Exception:
        pass
    return default_code

def _platform_group(name: str) -> str:
    try:
        s = (name or '').strip().lower()
        # Configured platforms from settings (AppKV)
        platforms = kv_get('platforms_map', []) or []
        for p in platforms:
            key = (p.get('key') or '').strip().lower()
            kws = p.get('keywords') or []
            for kw in kws:
                k = (kw or '').strip().lower()
                if k and (k in s):
                    return key
        # Built-in fallback for known platforms
        if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
            return 'hunger'
        if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
            return 'keeta'
        return ''
    except Exception:
        return ''

def _create_sale_journal(inv):
    """قيد المبيعات: عميل نقدي = صندوق/بنك، عميل آجل أو منصة (keeta/hunger) = ذمم مدينة. الخصم يظهر في حساب 5540 خصم ممنوح للعملاء."""
    try:
        from models import JournalEntry, JournalLine, Customer
        subtotal = float(inv.total_before_tax or 0.0)
        discount_amt = float(inv.discount_amount or 0.0)
        base_amt = max(0.0, subtotal - discount_amt)
        tax_amt = float(inv.tax_amount or 0.0)
        total_inc_tax = round(base_amt + tax_amt, 2)
        cust = (getattr(inv, 'customer_name', '') or '').strip().lower()
        grp = _platform_group(cust)
        is_credit_customer = False
        cust_obj = None
        if getattr(inv, 'customer_id', None):
            cust_obj = Customer.query.get(inv.customer_id)
            if cust_obj:
                is_credit_customer = bool(getattr(cust_obj, 'is_credit', False))
        use_ar = is_credit_customer or (grp in ('keeta', 'hunger'))
        if grp == 'keeta':
            rev_code = _acc_override('REV_KEETA', SHORT_TO_NUMERIC.get('REV_KEETA', ('4111',))[0])
        elif grp == 'hunger':
            rev_code = _acc_override('REV_HUNGER', SHORT_TO_NUMERIC.get('REV_HUNGER', ('4111',))[0])
        elif is_credit_customer or use_ar:
            rev_code = '4112'
        else:
            if (getattr(inv, 'branch', '') or '') == 'place_india':
                rev_code = _acc_override('REV_PI', SHORT_TO_NUMERIC.get('REV_PI', ('4111',))[0])
            elif (getattr(inv, 'branch', '') or '') == 'china_town':
                rev_code = _acc_override('REV_CT', SHORT_TO_NUMERIC.get('REV_CT', ('4111',))[0])
            else:
                rev_code = _acc_override('REV_CT', SHORT_TO_NUMERIC.get('REV_CT', ('4111',))[0])
        vat_out_code = SHORT_TO_NUMERIC.get('VAT_OUT', ('2141',))[0] if isinstance(SHORT_TO_NUMERIC.get('VAT_OUT'), tuple) else '2141'
        total_debit_credit = round(total_inc_tax + discount_amt, 2)
        je = JournalEntry(entry_number=f"JE-SAL-{inv.invoice_number}", date=(getattr(inv,'date',None) or get_saudi_now().date()), branch_code=getattr(inv,'branch',None), description=f"Sales {inv.invoice_number}", status='posted', total_debit=total_debit_credit, total_credit=total_debit_credit, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=inv.id, invoice_type='sales')
        db.session.add(je); db.session.flush()
        ln = 1
        if use_ar:
            if grp == 'keeta':
                ar_code = _acc_override('AR_KEETA', (SHORT_TO_NUMERIC.get('AR_KEETA') or ('1141',))[0] if isinstance(SHORT_TO_NUMERIC.get('AR_KEETA'), (list, tuple)) else (SHORT_TO_NUMERIC.get('AR_KEETA') or '1141'))
            elif grp == 'hunger':
                ar_code = _acc_override('AR_HUNGER', (SHORT_TO_NUMERIC.get('AR_HUNGER') or ('1141',))[0] if isinstance(SHORT_TO_NUMERIC.get('AR_HUNGER'), (list, tuple)) else (SHORT_TO_NUMERIC.get('AR_HUNGER') or '1141'))
            else:
                ar_code = _acc_override('AR', CHART_OF_ACCOUNTS.get('1141', {'code':'1141'}).get('code','1141'))
            ar_acc = _account(ar_code, CHART_OF_ACCOUNTS.get(ar_code, {'name':'عملاء','type':'ASSET'}).get('name','عملاء'), CHART_OF_ACCOUNTS.get(ar_code, {'name':'عملاء','type':'ASSET'}).get('type','ASSET'))
            if ar_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=ar_acc.id, debit=total_inc_tax, credit=0.0, description=f"AR {inv.invoice_number}", line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
                ln += 1
        else:
            ca = _pm_account(getattr(inv,'payment_method','CASH'))
            if ca:
                db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=ca.id, debit=total_inc_tax, credit=0.0, description=f"Receipt {inv.invoice_number}", line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
                ln += 1
        if discount_amt > 0:
            disc_code = (SHORT_TO_NUMERIC.get('DISC_GRANTED') or ('5540',))[0] if isinstance(SHORT_TO_NUMERIC.get('DISC_GRANTED'), (list, tuple)) else (SHORT_TO_NUMERIC.get('DISC_GRANTED') or '5540')
            disc_acc = _account(disc_code, CHART_OF_ACCOUNTS.get(disc_code, {'name':'خصم ممنوح للعملاء','type':'EXPENSE'}).get('name','خصم ممنوح للعملاء'), 'EXPENSE')
            if disc_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=disc_acc.id, debit=round(discount_amt, 2), credit=0.0, description=f"خصم فاتورة {inv.invoice_number}", line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
                ln += 1
        rev_acc = _account(rev_code, CHART_OF_ACCOUNTS.get(rev_code, {'name':'مبيعات CHINA TOWN','type':'REVENUE'}).get('name','مبيعات CHINA TOWN'), 'REVENUE')
        vat_acc = _account(vat_out_code, CHART_OF_ACCOUNTS.get(vat_out_code, {'name':'ضريبة القيمة المضافة – مستحقة','type':'LIABILITY'}).get('name','ضريبة القيمة المضافة – مستحقة'), 'LIABILITY')
        if rev_acc and subtotal > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=rev_acc.id, debit=0.0, credit=round(subtotal, 2), description=f"Revenue {inv.invoice_number}", line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
            ln += 1
        if vat_acc and tax_amt > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=vat_acc.id, debit=0.0, credit=round(tax_amt, 2), description=f"VAT Output {inv.invoice_number}", line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
        inv.journal_entry_id = je.id
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        raise

def _create_purchase_journal(inv):
    """إنشاء قيد المشتريات: إذا الفاتورة مدفوعة فوراً (نقداً/بنك) قيد واحد من حـ مخزون/مصروف إلى حـ الصندوق/البنك. وإلا ذمة مورد (2111). يستخدم إجماليات الفاتورة أو من الأصناف إن كان الرأس صفراً."""
    try:
        from models import JournalEntry, JournalLine
        total_before, tax_amt, total_inc_tax = inv.get_effective_totals()
        status = (getattr(inv, 'status', None) or '').strip().lower()
        pm = (getattr(inv, 'payment_method', None) or '').strip().upper()
        paid_at_creation = (status == 'paid' and pm in ('CASH', 'BANK'))
        exp_acc = _account('1161', CHART_OF_ACCOUNTS.get('1161', {'name':'مخزون بضائع','type':'ASSET'}).get('name','مخزون بضائع'), CHART_OF_ACCOUNTS.get('1161', {'name':'مخزون بضائع','type':'ASSET'}).get('type','ASSET'))
        vat_in_acc = _account('1170', CHART_OF_ACCOUNTS.get('1170', {'name':'ضريبة القيمة المضافة – مدخلات','type':'ASSET'}).get('name','ضريبة القيمة المضافة – مدخلات'), CHART_OF_ACCOUNTS.get('1170', {'name':'ضريبة القيمة المضافة – مدخلات','type':'ASSET'}).get('type','ASSET'))
        credit_acc = _pm_account(pm) if paid_at_creation else _account('2111', CHART_OF_ACCOUNTS.get('2111', {'name':'موردون','type':'LIABILITY'}).get('name','موردون'), CHART_OF_ACCOUNTS.get('2111', {'name':'موردون','type':'LIABILITY'}).get('type','LIABILITY'))
        je = JournalEntry(entry_number=f"JE-PUR-{inv.invoice_number}", date=(getattr(inv,'date',None) or get_saudi_now().date()), branch_code=None, description=f"Purchase {inv.invoice_number}", status='posted', total_debit=total_inc_tax, total_credit=total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=inv.id, invoice_type='purchase')
        db.session.add(je); db.session.flush()
        ln = 1
        if exp_acc and total_before > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=exp_acc.id, debit=total_before, credit=0.0, description="Purchase", line_date=(getattr(inv,'date',None) or get_saudi_now().date()))); ln += 1
        if vat_in_acc and tax_amt > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=vat_in_acc.id, debit=tax_amt, credit=0.0, description="VAT Input", line_date=(getattr(inv,'date',None) or get_saudi_now().date()))); ln += 1
        if credit_acc:
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=credit_acc.id, debit=0.0, credit=total_inc_tax, description="صندوق/بنك" if paid_at_creation else "Accounts Payable", line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        raise

def _create_expense_journal(inv):
    """إنشاء قيد المصروف: إذا الفاتورة مدفوعة فوراً (نقداً/بنك) قيد واحد من حـ مصروف إلى حـ الصندوق/البنك. وإلا ذمة مورد (2111).
    للهدر والتالف (payment_method=INTERNAL): قيد من حـ تكلفة الهدر والتالف (5160) إلى حـ المخزون (1160) — لا نقد، لا مورد، لا ضريبة."""
    try:
        from models import JournalEntry, JournalLine
        total_before = float(inv.total_before_tax or 0.0)
        tax_amt = float(inv.tax_amount or 0.0)
        total_inc_tax = round(total_before + tax_amt, 2)
        status = (getattr(inv, 'status', None) or '').strip().lower()
        pm = (getattr(inv, 'payment_method', None) or '').strip().upper()
        is_waste = (pm == 'INTERNAL')
        if is_waste:
            total_inc_tax = round(total_before, 2)
            tax_amt = 0.0
        paid_at_creation = (status == 'paid' and pm in ('CASH', 'BANK'))
        vat_in_acc = _account('1170', CHART_OF_ACCOUNTS.get('1170', {'name':'ضريبة القيمة المضافة – مدخلات','type':'ASSET'}).get('name','VAT مدخلات'), 'ASSET')
        credit_acc = None
        if is_waste:
            inv_info = CHART_OF_ACCOUNTS.get('1160', {'name': 'المخزون', 'type': 'ASSET'})
            credit_acc = _account('1160', inv_info.get('name', 'المخزون'), 'ASSET')
        elif paid_at_creation:
            credit_acc = _pm_account(pm)
        if not credit_acc and not is_waste:
            liability_code = (getattr(inv, 'liability_account_code', None) or '').strip() or '2111'
            ap_info = CHART_OF_ACCOUNTS.get(liability_code, {'name': 'ذمم دائنة', 'type': 'LIABILITY'})
            credit_acc = _account(liability_code, ap_info.get('name', 'ذمم دائنة'), 'LIABILITY')
        je = JournalEntry(entry_number=f"JE-EXP-{inv.invoice_number}", date=(getattr(inv,'date',None) or get_saudi_now().date()), branch_code=None, description=f"Expense {inv.invoice_number}" + (" (هدر/تالف)" if is_waste else ""), status='posted', total_debit=total_inc_tax, total_credit=total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=inv.id, invoice_type='expense')
        db.session.add(je); db.session.flush()
        ln = 1
        acc_totals = {}
        items = getattr(inv, 'items', []) or []
        for it in items:
            amt = float((it.quantity or 0) * (it.price_before_tax or 0) - (it.discount or 0))
            if amt <= 0:
                continue
            code = (getattr(it, 'account_code', '') or '').strip()
            if not code:
                sel = _expense_account_for(getattr(it, 'description', '') or '')
                code = (sel[0] if sel else '5410')
            if is_waste:
                code = '5160'
            if code not in acc_totals:
                acc_totals[code] = 0.0
            acc_totals[code] += amt
        if not acc_totals and total_before > 0:
            acc_totals['5160' if is_waste else '5410'] = total_before
        for code, amt in acc_totals.items():
            if amt <= 0:
                continue
            sel = _expense_account_by_code(code) if code else None
            if not sel:
                sel = _expense_account_for('')
            exp_code, exp_name, exp_type = sel
            acc_type = exp_type if exp_type in ('EXPENSE', 'COGS') else 'EXPENSE'
            exp_acc = _account(exp_code, CHART_OF_ACCOUNTS.get(exp_code, {'name': exp_name}).get('name', exp_name), acc_type)
            if exp_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=exp_acc.id, debit=round(amt, 2), credit=0.0, description="تكلفة الهدر والتالف" if is_waste else "Expense", line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
                ln += 1
        if not is_waste and vat_in_acc and tax_amt > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=vat_in_acc.id, debit=tax_amt, credit=0.0, description="VAT Input", line_date=(getattr(inv,'date',None) or get_saudi_now().date()))); ln += 1
        if credit_acc:
            desc_credit = "المخزون" if is_waste else ("صندوق/بنك" if paid_at_creation else "موردون/ذمم دائنة")
            db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=credit_acc.id, debit=0.0, credit=total_inc_tax, description=desc_credit, line_date=(getattr(inv,'date',None) or get_saudi_now().date())))
        try:
            from services.gl_truth import sync_ledger_from_journal
            sync_ledger_from_journal(je)
        except Exception:
            pass
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        raise

def _create_receipt_journal(date_val, amount, inv_num, ar_code, payment_method, invoice_id=None):
    """قيد تحصيل من عميل: مدين صندوق/بنك، دائن ذمم مدينة."""
    try:
        from models import JournalEntry, JournalLine
        amt = float(amount or 0)
        if amt <= 0:
            return
        ca = _pm_account(payment_method)
        ar_acc = _account(ar_code, CHART_OF_ACCOUNTS.get(ar_code, {'name':'عملاء','type':'ASSET'}).get('name','عملاء'), 'ASSET')
        if not ca or not ar_acc:
            return
        base_en = f"JE-REC-{inv_num}"
        en = base_en
        suffix = 1
        while JournalEntry.query.filter_by(entry_number=en).first():
            en = f"{base_en}-{suffix}"
            suffix += 1
        je = JournalEntry(entry_number=en, date=date_val, branch_code=None, description=f"Receipt {inv_num}", status='posted', total_debit=amt, total_credit=amt, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=invoice_id, invoice_type='sales_payment')
        db.session.add(je); db.session.flush()
        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ca.id, debit=amt, credit=0.0, description=f"Receipt {inv_num}", line_date=date_val))
        db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ar_acc.id, debit=0.0, credit=amt, description=f"Clear AR {inv_num}", line_date=date_val))
        try:
            from services.gl_truth import sync_ledger_from_journal
            sync_ledger_from_journal(je)
        except Exception:
            pass
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass

def _create_supplier_payment_journal(date_val, amount, inv_num, payment_method, bank_fee=0):
    """قيد دفعة لمورد: مدين موردون، دائن صندوق/بنك. يُنشئ أيضاً قيد رسوم بنكية إن وُجدت."""
    try:
        from models import JournalEntry, JournalLine
        amt = float(amount or 0)
        if amt <= 0:
            return
        ca = _pm_account(payment_method)
        ap_acc = _account('2111', CHART_OF_ACCOUNTS.get('2111', {'name':'موردون','type':'LIABILITY'}).get('name','موردون'), 'LIABILITY')
        if not ca or not ap_acc:
            return
        base_en = f"JE-PAY-PUR-{inv_num}"
        en = base_en
        suffix = 1
        while JournalEntry.query.filter_by(entry_number=en).first():
            en = f"{base_en}-{suffix}"
            suffix += 1
        je = JournalEntry(entry_number=en, date=date_val, branch_code=None, description=f"Payment Purchase {inv_num}", status='posted', total_debit=amt, total_credit=amt, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
        db.session.add(je); db.session.flush()
        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ap_acc.id, debit=amt, credit=0.0, description=f"Pay AP {inv_num}", line_date=date_val))
        db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ca.id, debit=0.0, credit=amt, description=f"Payment {inv_num}", line_date=date_val))
        try:
            from services.gl_truth import sync_ledger_from_journal
            sync_ledger_from_journal(je)
        except Exception:
            pass
        db.session.commit()
        fee = float(bank_fee or 0)
        if fee > 0 and ca:
            fee_acc = _account('5610', CHART_OF_ACCOUNTS.get('5610', {'name':'مصروفات بنكية','type':'EXPENSE'}).get('name','مصروفات بنكية'), 'EXPENSE')
            if fee_acc:
                fee_en = f"JE-BANKFEE-{inv_num}"
                fee_suffix = 1
                while JournalEntry.query.filter_by(entry_number=fee_en).first():
                    fee_en = f"JE-BANKFEE-{inv_num}-{fee_suffix}"
                    fee_suffix += 1
                fee_je = JournalEntry(entry_number=fee_en, date=date_val, branch_code=None, description=f"Bank Fee {inv_num}", status='posted', total_debit=fee, total_credit=fee, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
                db.session.add(fee_je); db.session.flush()
                db.session.add(JournalLine(journal_id=fee_je.id, line_no=1, account_id=fee_acc.id, debit=fee, credit=0.0, description=f"Bank Fee {inv_num}", line_date=date_val))
                db.session.add(JournalLine(journal_id=fee_je.id, line_no=2, account_id=ca.id, debit=0.0, credit=fee, description=f"Bank Fee {inv_num}", line_date=date_val))
                try:
                    from services.gl_truth import sync_ledger_from_journal
                    sync_ledger_from_journal(fee_je)
                except Exception:
                    pass
                db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass

def _create_supplier_direct_payment_journal(date_val, amount, ref_text, payment_method):
    """قيد دفعة مباشرة لمورد (بدون فاتورة): مدين موردون، دائن صندوق/بنك."""
    try:
        from models import JournalEntry, JournalLine
        amt = float(amount or 0)
        if amt <= 0:
            return
        ca = _pm_account(payment_method)
        ap_acc = _account('2111', CHART_OF_ACCOUNTS.get('2111', {'name':'موردون','type':'LIABILITY'}).get('name','موردون'), 'LIABILITY')
        if not ca or not ap_acc:
            return
        safe_ref = (ref_text or 'SUP')[:30].replace(' ', '_')
        base_en = f"JE-PAY-SUP-{safe_ref}"
        en = base_en
        suffix = 1
        while JournalEntry.query.filter_by(entry_number=en).first():
            en = f"{base_en}-{suffix}"
            suffix += 1
        je = JournalEntry(entry_number=en, date=date_val, branch_code=None, description=ref_text[:255] if ref_text else 'Supplier payment', status='posted', total_debit=amt, total_credit=amt, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
        db.session.add(je); db.session.flush()
        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ap_acc.id, debit=amt, credit=0.0, description=ref_text[:500] if ref_text else 'Pay AP', line_date=date_val))
        db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ca.id, debit=0.0, credit=amt, description='Payment', line_date=date_val))
        try:
            from services.gl_truth import sync_ledger_from_journal
            sync_ledger_from_journal(je)
        except Exception:
            pass
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass

def _create_expense_payment_journal(date_val, amount, inv_num, payment_method, liability_account_code=None):
    """قيد دفعة مصروف: مدين موردون (أو ذمم دائنة منصة)، دائن صندوق/بنك."""
    try:
        from models import JournalEntry, JournalLine
        amt = float(amount or 0)
        if amt <= 0:
            return
        ca = _pm_account(payment_method)
        ap_code = (liability_account_code or '').strip() or '2111'
        ap_info = CHART_OF_ACCOUNTS.get(ap_code, {'name': 'ذمم دائنة', 'type': 'LIABILITY'})
        ap_acc = _account(ap_code, ap_info.get('name', 'موردون'), 'LIABILITY')
        if not ca or not ap_acc:
            return
        base_en = f"JE-PAY-EXP-{inv_num}"
        en = base_en
        suffix = 1
        while JournalEntry.query.filter_by(entry_number=en).first():
            en = f"{base_en}-{suffix}"
            suffix += 1
        je = JournalEntry(entry_number=en, date=date_val, branch_code=None, description=f"Payment Expense {inv_num}", status='posted', total_debit=amt, total_credit=amt, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=None, invoice_type='expense_payment')
        db.session.add(je); db.session.flush()
        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ap_acc.id, debit=amt, credit=0.0, description=f"Pay AP {inv_num}", line_date=date_val))
        db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ca.id, debit=0.0, credit=amt, description=f"Payment {inv_num}", line_date=date_val))
        try:
            from services.gl_truth import sync_ledger_from_journal
            sync_ledger_from_journal(je)
        except Exception:
            pass
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass

def _post_ledger(date_val, acc_code, acc_name, acc_type, debit_amt, credit_amt, ref_text):
    """Deprecated: لا يُنشئ قيداً – استخدم دوال القيود المخصصة. موجود للتوافق فقط."""
    pass

def _expense_account_by_code(code):
    """تُرجع حساب مصروف من الشجرة الجديدة بناءً على الكود."""
    c = (code or '').strip()
    # إذا كان الكود رقمي (من الشجرة الجديدة)، استخدمه مباشرة
    if c.isdigit() and len(c) == 4:
        if c in CHART_OF_ACCOUNTS:
            info = CHART_OF_ACCOUNTS[c]
            atype = info.get('type')
            if atype in ('EXPENSE', 'COGS'):
                return (c, info.get('name', c), atype)
    # خريطة الاختصارات القديمة إلى الحسابات الجديدة (من get_short_to_numeric)
    old_to_new_map = {
        'RENT': '5270',      # مصروف إيجار
        'MAINT': '5240',     # مصروف صيانة
        'UTIL': '5210',      # مصروف كهرباء
        'LOG': '5260',       # مصروف نقل وتوصيل
        'MKT': '5510',       # دعاية وإعلان
        'TEL': '5230',       # مصروف اتصالات وإنترنت
        'STAT': '5420',      # قرطاسية ومكتبية
        'CLEAN': '5250',     # مصروف نظافة
        'GOV': '5410',       # مصروفات حكومية ورسوم
        'EXP': '5470',       # مصروفات متنوعة إدارية
    }
    if c in old_to_new_map:
        new_code = old_to_new_map[c]
        if new_code in CHART_OF_ACCOUNTS:
            info = CHART_OF_ACCOUNTS[new_code]
            return (new_code, info.get('name', new_code), 'EXPENSE')
    # افتراضي: مصروفات متنوعة إدارية
    default_code = '5470'
    if default_code in CHART_OF_ACCOUNTS:
        info = CHART_OF_ACCOUNTS[default_code]
        return (default_code, info.get('name', default_code), 'EXPENSE')
    return (default_code, 'مصروفات متنوعة إدارية', 'EXPENSE')

def _expense_account_for(desc):
    """تُرجع حساب مصروف من الشجرة الجديدة بناءً على الوصف."""
    s = (desc or '').strip().lower()
    # خريطة الكلمات المفتاحية إلى الحسابات الجديدة
    mapping = [
        (('rent','ايجار','إيجار'), '5270'),  # مصروف إيجار
        (('maintenance','صيانة'), '5240'),    # مصروف صيانة
        (('electric','كهرب','كهرباء'), '5210'),  # مصروف كهرباء
        (('water','ماء'), '5220'),            # مصروف ماء
        (('utilities','فاتورة'), '5210'),     # مصروف كهرباء
        (('delivery','نقل','شحن','logistics','لوجست'), '5260'),  # مصروف نقل وتوصيل
        (('marketing','تسويق','اعلان','إعلان','دعاية'), '5510'),  # دعاية وإعلان
        (('internet','انترنت','شبكة','اتصالات','هاتف','phone','telecom'), '5230'),  # اتصالات وإنترنت
        (('stationery','قرطاس','قرطاسية','مطبوعات'), '5420'),  # قرطاسية ومكتبية
        (('clean','نظافة'), '5250'),          # مصروف نظافة
        (('government','حكوم','حكومي','gosi','قوى','muqeem'), '5410'),  # مصروفات حكومية ورسوم
        (('salary','راتب','رواتب','wages','أجور'), '5310'),  # رواتب وأجور
        (('allowance','بدل','بدلات'), '5320'),  # بدلات
        (('bank','بنك','banking','عمولة'), '5610'),  # مصروفات بنكية
        (('fine','غرامة','غرامات'), '5460'),  # غرامات ومخالفات
    ]
    for kws, code in mapping:
        for kw in kws:
            if kw in s:
                if code in CHART_OF_ACCOUNTS:
                    info = CHART_OF_ACCOUNTS[code]
                    return (code, info.get('name', code), 'EXPENSE')
    # افتراضي: مصروفات متنوعة إدارية
    default_code = '5470'
    if default_code in CHART_OF_ACCOUNTS:
        info = CHART_OF_ACCOUNTS[default_code]
        return (default_code, info.get('name', default_code), 'EXPENSE')
    return (default_code, 'مصروفات متنوعة إدارية', 'EXPENSE')

# ---- شجرة الحسابات المعتمدة (من data.coa_new_tree) ----
def _coa_build():
    try:
        from data.coa_new_tree import build_coa_dict, get_short_to_numeric
        coa = build_coa_dict()
        short = get_short_to_numeric(coa)
        return coa, short
    except Exception:
        return {}, {}

_CHART, _SHORT = _coa_build()
CHART_OF_ACCOUNTS = _CHART
SHORT_TO_NUMERIC = _SHORT

def refresh_chart_from_db():
    """تحديث CHART_OF_ACCOUNTS من قاعدة البيانات - فقط الحسابات من الشجرة الجديدة."""
    try:
        from models import Account
        from data.coa_new_tree import build_coa_dict
        # الحصول على الحسابات الجديدة فقط
        new_coa = build_coa_dict()
        new_codes = set(new_coa.keys())
        
        # تحديث CHART_OF_ACCOUNTS من قاعدة البيانات للحسابات الجديدة فقط
        for a in Account.query.filter(Account.code.in_(new_codes)).order_by(Account.code.asc()).all():
            code = str(a.code or '').strip()
            if code in CHART_OF_ACCOUNTS:
                # تحديث البيانات من DB
                CHART_OF_ACCOUNTS[code]['name'] = (getattr(a, 'name', '') or CHART_OF_ACCOUNTS[code].get('name', ''))
                CHART_OF_ACCOUNTS[code]['type'] = (getattr(a, 'type', '') or CHART_OF_ACCOUNTS[code].get('type', 'EXPENSE')).strip().upper()
    except Exception:
        try:
            from extensions import db as _db
            if _db:
                _db.session.rollback()
        except Exception:
            pass

def _resolve_account(code: str, name: str, kind: str):
    c = (code or '').strip().upper()
    if c in SHORT_TO_NUMERIC:
        cc, nn, tt = SHORT_TO_NUMERIC[c]
        return cc, nn, tt
    # If numeric code already
    if c in CHART_OF_ACCOUNTS:
        return c, CHART_OF_ACCOUNTS[c]['name'], CHART_OF_ACCOUNTS[c]['type']
    return c, name, (kind or '').strip().upper()

def seed_chart_of_accounts():
    """زرع شجرة الحسابات الجديدة فقط في قاعدة البيانات."""
    try:
        from data.coa_new_tree import build_coa_dict
        # استخدام الشجرة الجديدة فقط
        new_coa = build_coa_dict()
        for cc, info in new_coa.items():
            _account(cc, info.get('name', ''), info.get('type', 'EXPENSE'))
        db.session.commit()
    except Exception:
        db.session.rollback()
@main.route('/financial', methods=['GET'], endpoint='financial_dashboard')
@login_required
def financial_dashboard():
    warmup_db_once()
    sd = (request.args.get('start_date') or '').strip()
    ed = (request.args.get('end_date') or '').strip()
    br = (request.args.get('branch') or 'all').strip()
    try:
        if sd:
            start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
        else:
            today = get_saudi_now().date()
            start_dt = date(today.year, today.month, 1)
        end_dt = datetime.strptime(ed, '%Y-%m-%d').date() if ed else get_saudi_now().date()
    except Exception:
        today = get_saudi_now().date()
        start_dt = date(today.year, today.month, 1)
        end_dt = today

    def branch_filter(q, model):
        try:
            if br in ('place_india','china_town') and hasattr(model, 'branch'):
                return q.filter(model.branch == br)
            return q
        except Exception:
            return q

    sales_q = db.session.query(
        func.coalesce(func.sum(SalesInvoice.total_before_tax), 0).label('amount'),
        func.coalesce(func.sum(SalesInvoice.discount_amount), 0).label('discount'),
        func.coalesce(func.sum(SalesInvoice.tax_amount), 0).label('vat'),
        func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0).label('total')
    ).filter(SalesInvoice.date.between(start_dt, end_dt))
    sales_q = branch_filter(sales_q, SalesInvoice)
    sales_row = sales_q.first()
    sales_summary = {
        'amount': float(sales_row.amount or 0),
        'discount': float(sales_row.discount or 0),
        'vat_out': float(sales_row.vat or 0),
        'net_sales': float(sales_row.total or 0),
    }

    pm_rows = db.session.query(SalesInvoice.payment_method, func.count('*'), func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0))
    pm_rows = pm_rows.filter(SalesInvoice.date.between(start_dt, end_dt))
    pm_rows = branch_filter(pm_rows, SalesInvoice)
    pm_rows = pm_rows.group_by(SalesInvoice.payment_method).all()
    by_payment_sales = [{'method': (r[0] or 'unknown'), 'count': int(r[1] or 0), 'total': float(r[2] or 0)} for r in pm_rows]

    purch_q = db.session.query(
        func.coalesce(func.sum(PurchaseInvoice.total_before_tax), 0),
        func.coalesce(func.sum(PurchaseInvoice.tax_amount), 0),
        func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0)
    ).filter(PurchaseInvoice.date.between(start_dt, end_dt))
    purch_row = purch_q.first()
    purchases_summary = {
        'amount': float(purch_row[0] or 0),
        'vat_in': float(purch_row[1] or 0),
        'total': float(purch_row[2] or 0),
        'no_vat_amount': float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax - PurchaseInvoice.discount_amount), 0))
            .filter(PurchaseInvoice.date.between(start_dt, end_dt), func.coalesce(PurchaseInvoice.tax_amount, 0) == 0).scalar() or 0)
    }

    exp_rows = db.session.query(
        ExpenseInvoiceItem.description,
        func.coalesce(func.sum((ExpenseInvoiceItem.price_before_tax * ExpenseInvoiceItem.quantity) - ExpenseInvoiceItem.discount), 0).label('amount')
    ).join(ExpenseInvoice, ExpenseInvoiceItem.invoice_id == ExpenseInvoice.id)
    exp_rows = exp_rows.filter(ExpenseInvoice.date.between(start_dt, end_dt)).group_by(ExpenseInvoiceItem.description).all()
    expenses_total = float(sum([float(r[1] or 0) for r in exp_rows]) or 0)
    expenses_summary = {
        'total': expenses_total,
        'items': [{'label': r[0], 'amount': float(r[1] or 0)} for r in exp_rows]
    }

    vat_summary = {
        'vat_out': float(sales_summary['vat_out']),
        'vat_in': float(purchases_summary['vat_in']),
        'net_vat_due': float(sales_summary['vat_out']) - float(purchases_summary['vat_in'])
    }

    try:
        ap_total = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
            .filter(PurchaseInvoice.date.between(start_dt, end_dt)).scalar() or 0)
        ap_paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
            .filter(Payment.invoice_type == 'purchase').filter(Payment.created_at.between(start_dt, end_dt)).scalar() or 0)
        liabilities_summary = {
            'suppliers_due': max(0.0, ap_total - ap_paid),
            'prev_owner': 0.0,
            'other_dues': 0.0,
        }
    except Exception:
        liabilities_summary = {'suppliers_due': 0.0, 'prev_owner': 0.0, 'other_dues': 0.0}

    try:
        gross_profit = float(sales_summary['net_sales']) - float(purchases_summary['no_vat_amount'])
        net_profit = gross_profit - float(expenses_total)
    except Exception:
        gross_profit = 0.0
        net_profit = 0.0

    return render_template('financial_dashboard.html',
        start_date=start_dt, end_date=end_dt, branch=br,
        sales_summary=sales_summary, by_payment_sales=by_payment_sales,
        purchases_summary=purchases_summary,
        expenses_summary=expenses_summary,
        vat_summary=vat_summary,
        liabilities_summary=liabilities_summary,
        gross_profit=gross_profit, net_profit=net_profit)
@main.route('/financial/print', methods=['GET'], endpoint='financial_print')
@login_required
def financial_print():
    warmup_db_once()
    args = request.args.to_dict()
    with current_app.test_request_context(query_string=args):
        return financial_dashboard()

@main.route('/api/kpi/dashboard', methods=['GET'])
def api_kpi_dashboard():
    try:
        from models import SalesInvoice, Account, JournalLine
        today = get_saudi_now().date()
        start_dt = today.replace(day=1)
        end_dt = today
        try:
            sd = (request.args.get('start') or '').strip()
            ed = (request.args.get('end') or '').strip()
            if sd:
                start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            if ed:
                end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        except Exception:
            pass
        orders_count = int(SalesInvoice.query.filter(SalesInvoice.date.between(start_dt, end_dt)).count() or 0)
        from sqlalchemy import func
        total_sales = float(db.session.query(func.coalesce(func.sum(SalesInvoice.total_after_tax_discount), 0)).filter(SalesInvoice.date.between(start_dt, end_dt)).scalar() or 0)
        avg_order_value = (total_sales / orders_count) if orders_count > 0 else 0.0
        rev_amt = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
                        .join(Account, JournalLine.account_id == Account.id)
                        .filter(Account.type == 'REVENUE')
                        .filter(JournalLine.line_date.between(start_dt, end_dt)).scalar() or 0)
        cogs_amt = float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
                         .join(Account, JournalLine.account_id == Account.id)
                         .filter(Account.type == 'COGS')
                         .filter(JournalLine.line_date.between(start_dt, end_dt)).scalar() or 0)
        exp_amt = float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
                        .join(Account, JournalLine.account_id == Account.id)
                        .filter(Account.type == 'EXPENSE')
                        .filter(JournalLine.line_date.between(start_dt, end_dt)).scalar() or 0)
        total_earnings = rev_amt - cogs_amt - exp_amt
        from flask import jsonify
        return jsonify({'ok': True, 'period': {'start': str(start_dt), 'end': str(end_dt)}, 'orders_count': orders_count, 'avg_order_value': avg_order_value, 'total_earnings': total_earnings})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/kpi/branches_daily', methods=['GET'])
def api_kpi_branches_daily():
    try:
        from models import SalesInvoice
        today = get_saudi_now().date()
        start_dt = today
        end_dt = today
        try:
            sd = (request.args.get('start') or '').strip()
            ed = (request.args.get('end') or '').strip()
            if sd:
                start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            if ed:
                end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        except Exception:
            pass
        from sqlalchemy import func
        branches = {}
        q = SalesInvoice.query.filter(SalesInvoice.date.between(start_dt, end_dt))
        for inv in q.all():
            br = (getattr(inv, 'branch', '') or '').strip().lower() or 'default'
            arr = branches.get(br) or {'sales': 0.0, 'invoices': 0}
            arr['sales'] += float(inv.total_after_tax_discount or 0.0)
            arr['invoices'] += 1
            branches[br] = arr
        return jsonify({'ok': True, 'start': str(start_dt), 'end': str(end_dt), 'branches': branches})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/kpi/payments_breakdown', methods=['GET'])
def api_kpi_payments_breakdown():
    try:
        from models import SalesInvoice
        today = get_saudi_now().date()
        start_dt = today
        end_dt = today
        try:
            sd = (request.args.get('start') or '').strip()
            ed = (request.args.get('end') or '').strip()
            if sd:
                start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            if ed:
                end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        except Exception:
            pass
        breakdown = {}
        q = SalesInvoice.query.filter(SalesInvoice.date.between(start_dt, end_dt))
        for inv in q.all():
            pm = (getattr(inv, 'payment_method', '') or 'UNKNOWN').strip().upper()
            cur = breakdown.get(pm) or {'count': 0, 'amount': 0.0}
            cur['count'] += 1
            cur['amount'] += float(inv.total_after_tax_discount or 0.0)
            breakdown[pm] = cur
        return jsonify({'ok': True, 'start': str(start_dt), 'end': str(end_dt), 'breakdown': breakdown})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/kpi/purchases_daily', methods=['GET'])
def api_kpi_purchases_daily():
    try:
        from models import PurchaseInvoice
        today = get_saudi_now().date()
        start_dt = today
        end_dt = today
        try:
            sd = (request.args.get('start') or '').strip()
            ed = (request.args.get('end') or '').strip()
            if sd:
                start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            if ed:
                end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        except Exception:
            pass
        total = 0.0
        count = 0
        for inv in PurchaseInvoice.query.filter(PurchaseInvoice.date.between(start_dt, end_dt)).all():
            total += float(inv.total_after_tax_discount or 0.0)
            count += 1
        return jsonify({'ok': True, 'start': str(start_dt), 'end': str(end_dt), 'total': total, 'count': count})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/kpi/expenses_daily', methods=['GET'])
def api_kpi_expenses_daily():
    try:
        from models import ExpenseInvoice
        today = get_saudi_now().date()
        start_dt = today
        end_dt = today
        try:
            sd = (request.args.get('start') or '').strip()
            ed = (request.args.get('end') or '').strip()
            if sd:
                start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            if ed:
                end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        except Exception:
            pass
        total = 0.0
        count = 0
        for inv in ExpenseInvoice.query.filter(ExpenseInvoice.date.between(start_dt, end_dt)).all():
            total += float(inv.total_after_tax_discount or 0.0)
            count += 1
        return jsonify({'ok': True, 'start': str(start_dt), 'end': str(end_dt), 'total': total, 'count': count})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/kpi/inventory_snapshot', methods=['GET'])
def api_kpi_inventory_snapshot():
    try:
        from models import Account, JournalLine
        from sqlalchemy import func
        codes = ['1161', '1162']
        out = {}
        for code in codes:
            acc = Account.query.filter(Account.code == code).first()
            if not acc:
                out[code] = 0.0
                continue
            bal_q = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).filter(JournalLine.account_id == acc.id)
            out[code] = float(bal_q.scalar() or 0)
        return jsonify({'ok': True, 'accounts': out})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/kpi/dashboard_full', methods=['GET'])
def api_kpi_dashboard_full():
    try:
        from models import SalesInvoice, SalesInvoiceItem
        from sqlalchemy import func
        today = get_saudi_now().date()
        start_dt = today
        end_dt = today
        try:
            sd = (request.args.get('start') or '').strip()
            ed = (request.args.get('end') or '').strip()
            if sd:
                start_dt = datetime.strptime(sd, '%Y-%m-%d').date()
            if ed:
                end_dt = datetime.strptime(ed, '%Y-%m-%d').date()
        except Exception:
            pass
        q = SalesInvoice.query.filter(SalesInvoice.date.between(start_dt, end_dt))
        invoices = q.all()
        branches = {}
        payment_cash = 0.0
        payment_bank = 0.0
        for inv in invoices:
            br = (getattr(inv, 'branch', '') or 'default').strip().lower()
            cur = branches.get(br) or {'sales': 0.0, 'invoices': 0}
            cur['sales'] += float(getattr(inv, 'total_after_tax_discount', 0.0) or 0.0)
            cur['invoices'] += 1
            branches[br] = cur
            pm = (getattr(inv, 'payment_method', '') or '').strip().lower()
            amt = float(getattr(inv, 'total_after_tax_discount', 0.0) or 0.0)
            if pm == 'cash':
                payment_cash += amt
            elif pm in ('bank','card'):
                payment_bank += amt
        invoices_count = len(invoices)
        items_sold = 0
        ids = [int(getattr(inv,'id',0) or 0) for inv in invoices if getattr(inv,'id',None)]
        if ids:
            try:
                items_sold = int(db.session.query(func.coalesce(func.sum(SalesInvoiceItem.quantity), 0)).filter(SalesInvoiceItem.invoice_id.in_(ids)).scalar() or 0)
            except Exception:
                items_sold = 0
        return jsonify({'ok': True, 'branches': branches, 'payment_cash': payment_cash, 'payment_bank': payment_bank, 'invoices_count': invoices_count, 'items_sold': items_sold})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/advances', methods=['GET'], endpoint='advances_page')
@login_required
def advances_page():
    warmup_db_once()
    try:
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        employees = []
    return ('', 404)

@main.route('/api/advances/list', methods=['GET'], endpoint='api_advances_list')
@login_required
def api_advances_list():
    try:
        from datetime import date as _date
        from datetime import datetime as _dt
        from models import JournalLine, JournalEntry, Employee
        emp_id = request.args.get('employee_id', type=int)
        dept_f = (request.args.get('dept') or '').strip()
        if dept_f:
            low = dept_f.lower()
            if low in ('kitchen','chef'):
                dept_f = 'شيف'
            elif low in ('hall','floor','wait'):
                dept_f = 'الصالة'
            elif low in ('admin','management'):
                dept_f = 'إداري'
        month_param = (request.args.get('month') or '').strip()
        start_date = (request.args.get('start') or '').strip()
        end_date = (request.args.get('end') or '').strip()

        q = db.session.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        adv_code = SHORT_TO_NUMERIC['EMP_ADV'][0]
        acc = _account(adv_code, CHART_OF_ACCOUNTS[adv_code]['name'], CHART_OF_ACCOUNTS[adv_code]['type'])
        if acc:
            q = q.filter(JournalLine.account_id == acc.id)

        # AND logic: apply all provided filters
        if emp_id:
            q = q.filter(JournalLine.employee_id == emp_id)
        if dept_f:
            try:
                emp_ids = [int(e.id) for e in Employee.query.filter(func.lower(Employee.department) == dept_f.lower()).all()]
                if emp_ids:
                    q = q.filter(JournalLine.employee_id.in_(emp_ids))
                else:
                    q = q.filter(JournalLine.employee_id == -1)
            except Exception:
                pass
        # Date range: month or explicit start/end
        if month_param and '-' in month_param:
            try:
                y, m = month_param.split('-'); y = int(y); m = int(m)
                start_dt = _date(y, m, 1)
                end_dt = _date(y + (1 if m == 12 else 0), 1 if m == 12 else (m + 1), 1)
                q = q.filter(JournalEntry.date >= start_dt, JournalEntry.date < end_dt)
            except Exception:
                pass
        else:
            sd_dt = None; ed_dt = None
            try:
                sd_dt = _dt.fromisoformat(start_date).date() if start_date else None
            except Exception:
                sd_dt = None
            try:
                ed_dt = _dt.fromisoformat(end_date).date() if end_date else None
            except Exception:
                ed_dt = None
            if sd_dt and ed_dt:
                q = q.filter(JournalEntry.date.between(sd_dt, ed_dt))
            elif sd_dt and not ed_dt:
                q = q.filter(JournalEntry.date >= sd_dt)
            elif ed_dt and not sd_dt:
                q = q.filter(JournalEntry.date <= ed_dt)

        rows = q.order_by(JournalEntry.date.desc(), JournalLine.line_no.asc()).all()
        data_map = {}
        for jl, je in rows:
            k = int(getattr(jl, 'employee_id', 0) or 0)
            if k not in data_map:
                data_map[k] = {
                    'employee_id': k,
                    'employee_name': '',
                    'branch': getattr(je, 'branch_code', '') or '',
                    'department': '',
                    'granted': 0.0,
                    'paid': 0.0,
                    'remaining': 0.0,
                    'last_date': str(getattr(je, 'date', get_saudi_now().date()))
                }
            data_map[k]['granted'] += float(getattr(jl, 'debit', 0) or 0)
            data_map[k]['paid'] += float(getattr(jl, 'credit', 0) or 0)
            data_map[k]['remaining'] = max(0.0, data_map[k]['granted'] - data_map[k]['paid'])
            data_map[k]['last_date'] = str(getattr(je, 'date', get_saudi_now().date()))
        # Attach names and departments
        try:
            emps = {int(e.id): e for e in Employee.query.all()}
            for k, v in data_map.items():
                e = emps.get(k)
                v['employee_name'] = (getattr(e, 'full_name', '') or '') if e else ''
                v['department'] = (getattr(e, 'department', '') or '') if e else ''
        except Exception:
            pass
        # Filter to only current active employees and exclude orphan keys (e.g., employee_id=0)
        active_ids = set()
        try:
            active_ids = {int(e.id) for e in Employee.query.filter_by(active=True).all()}
        except Exception:
            active_ids = set(int(k) for k in (emps.keys() if 'emps' in locals() else []))
        data = [v for (k, v) in data_map.items() if int(k or 0) in active_ids]
        totals = {
            'granted': float(sum([d['granted'] for d in data]) or 0),
            'paid': float(sum([d['paid'] for d in data]) or 0),
            'remaining': float(sum([d['remaining'] for d in data]) or 0),
        }
        return jsonify({'ok': True, 'rows': data, 'totals': totals})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/advances/metrics', methods=['GET'], endpoint='api_advances_metrics')
@login_required
def api_advances_metrics():
    try:
        from models import JournalLine, JournalEntry, Employee
        adv_code = SHORT_TO_NUMERIC['EMP_ADV'][0]
        acc = _account(adv_code, CHART_OF_ACCOUNTS[adv_code]['name'], CHART_OF_ACCOUNTS[adv_code]['type'])
        if not acc:
            return jsonify({'ok': True, 'total': 0.0, 'unpaid': 0.0, 'last_date': None, 'series': []})
        rows = db.session.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalLine.account_id == acc.id).order_by(JournalEntry.date.asc(), JournalLine.line_no.asc()).all()
        total_debit = float(sum([float(getattr(jl, 'debit', 0) or 0) for jl, _ in rows]) or 0)
        total_credit = float(sum([float(getattr(jl, 'credit', 0) or 0) for jl, _ in rows]) or 0)
        last_date = None
        for _, je in rows:
            last_date = str(getattr(je, 'date', get_saudi_now().date()))
        series_map = {}
        emp_depts = {}
        try:
            for e in Employee.query.all():
                emp_depts[int(e.id)] = (e.department or '').strip()
        except Exception:
            pass
        for jl, je in rows:
            d = getattr(je, 'date', get_saudi_now().date())
            y = int(getattr(d, 'year', get_saudi_now().year))
            m = int(getattr(d, 'month', get_saudi_now().month))
            dept = (emp_depts.get(int(getattr(jl, 'employee_id', 0) or 0)) or '')
            key = (y, m, dept)
            if key not in series_map:
                series_map[key] = {'year': y, 'month': m, 'department': dept, 'granted': 0.0, 'repaid': 0.0}
            series_map[key]['granted'] += float(getattr(jl, 'debit', 0) or 0)
            series_map[key]['repaid'] += float(getattr(jl, 'credit', 0) or 0)
        series = list(series_map.values())
        series.sort(key=lambda r: (r['year'], r['month']))
        return jsonify({'ok': True, 'total': total_debit, 'unpaid': max(0.0, total_debit - total_credit), 'last_date': last_date, 'series': series})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/advances/pay', methods=['POST'], endpoint='api_advances_pay')
@login_required
def api_advances_pay():
    try:
        emp_id = request.form.get('employee_id', type=int)
        amount = request.form.get('amount', type=float) or 0.0
        method = (request.form.get('method') or 'cash').strip().lower()
        date_s = (request.form.get('date') or get_saudi_now().strftime('%Y-%m-%d'))
        from datetime import datetime as _dt
        dval = _dt.strptime(date_s, '%Y-%m-%d').date()
        if not emp_id or amount <= 0:
            return jsonify({'ok': False, 'error': 'invalid'}), 400
        try:
            from models import JournalEntry, JournalLine
            cash_acc = _pm_account(method)
            emp_adv_acc = _account(*SHORT_TO_NUMERIC['EMP_ADV'])
            base_en = f"JE-ADVPAY-{emp_id}-{dval.strftime('%Y%m%d')}"
            en = base_en
            suffix = 1
            while JournalEntry.query.filter_by(entry_number=en).first():
                en = f"{base_en}-{suffix}"
                suffix += 1
            je = JournalEntry(entry_number=en, date=dval, branch_code=None, description=f"Advance repayment {emp_id}", status='posted', total_debit=amount, total_credit=amount, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
            db.session.add(je); db.session.flush()
            if cash_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=cash_acc.id, debit=amount, credit=0.0, description='Advance repayment cash/bank', line_date=dval, employee_id=emp_id))
            if emp_adv_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=emp_adv_acc.id, debit=0.0, credit=amount, description='Advance repayment', line_date=dval, employee_id=emp_id))
            db.session.commit()
        except Exception:
            db.session.rollback(); return jsonify({'ok': False, 'error': 'post_failed'}), 400
        try:
            if method in ('bank','card','visa','mastercard'):
                _post_ledger(dval, 'BANK', 'Bank', 'asset', amount, 0.0, f'ADV REPAY {emp_id}')
            else:
                _post_ledger(dval, 'CASH', 'Cash', 'asset', amount, 0.0, f'ADV REPAY {emp_id}')
            _post_ledger(dval, 'EMP_ADV', 'سلف للموظفين', 'asset', 0.0, amount, f'ADV REPAY {emp_id}')
        except Exception:
            pass
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/employees', methods=['GET'], endpoint='api_employees')
@login_required
def api_employees():
    try:
        rows = Employee.query.order_by(Employee.full_name.asc()).all()
        data = []
        for e in rows:
            data.append({
                'id': int(getattr(e,'id',0) or 0),
                'name': getattr(e,'full_name','') or '',
                'department': getattr(e,'department','') or '',
                'position': getattr(e,'position','') or '',
                'branch_code': getattr(e,'branch_code','') or '',
                'status': getattr(e,'status','') or '',
                'basic': float(getattr(getattr(e,'employee_salary_default',None),'base_salary',0) or 0),
                'last_salary': 0.0,
                'advance': 0.0,
            })
        return jsonify({'ok': True, 'employees': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

def _ensure_salary_records_from_hire_date(emp_id, base_salary, allowances=0.0, deductions=0.0, hire_date=None):
    """إنشاء مسيرات رواتب من تاريخ التعيين حتى الشهر الحالي — مصدر حقيقة موحد لقسم المسيرات والسداد."""
    if not hire_date:
        return 0
    from models import Salary
    now = get_saudi_now()
    cur_y, cur_m = int(now.year), int(now.month)
    sy, sm = int(hire_date.year), int(hire_date.month)
    if (sy > cur_y) or (sy == cur_y and sm > cur_m):
        return 0
    base = float(base_salary or 0)
    allow = float(allowances or 0)
    ded = float(deductions or 0)
    created = 0
    yy, mm = sy, sm
    guard = 0
    while (yy < cur_y) or (yy == cur_y and mm <= cur_m):
        if Salary.query.filter_by(employee_id=emp_id, year=yy, month=mm).first():
            mm += 1
            if mm > 12:
                mm = 1
                yy += 1
            guard += 1
            if guard > 240:
                break
            continue
        total = max(0.0, base + allow - ded)
        sal = Salary(employee_id=emp_id, year=yy, month=mm, basic_salary=base, allowances=allow,
                     deductions=ded, previous_salary_due=0.0, total_salary=total, status='due')
        db.session.add(sal)
        created += 1
        mm += 1
        if mm > 12:
            mm = 1
            yy += 1
        guard += 1
        if guard > 240:
            break
    return created

@main.route('/api/employees', methods=['POST'], endpoint='api_employees_create')
@login_required
def api_employees_create():
    try:
        if not user_can('employees','add'):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        from models import Employee, EmployeeSalaryDefault
        full_name = (request.form.get('full_name') or '').strip()
        national_id = (request.form.get('national_id') or '').strip()
        department = (request.form.get('department') or '').strip()
        position = (request.form.get('position') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        email = (request.form.get('email') or '').strip()
        hire_date = (request.form.get('hire_date') or '').strip()
        branch_code = (request.form.get('branch_code') or '').strip()
        base_salary = request.form.get('base_salary', type=float) or 0.0
        salary_type = (request.form.get('salary_type') or 'fixed').strip().lower()
        hourly_rate = request.form.get('hourly_rate', type=float)
        if not full_name or not national_id:
            return jsonify({'ok': False, 'error': 'missing_fields'}), 400
        from datetime import datetime as _dt
        hd = None
        try:
            hd = _dt.strptime(hire_date, '%Y-%m-%d').date() if hire_date else None
        except Exception:
            hd = None
        emp = Employee(full_name=full_name, national_id=national_id, department=department, position=position, phone=phone, email=email, hire_date=hd, status='active', active=True)
        try:
            db.session.add(emp)
            db.session.flush()
            db.session.add(EmployeeSalaryDefault(employee_id=int(emp.id), base_salary=base_salary, allowances=0.0, deductions=0.0))
            db.session.flush()
            _ensure_salary_records_from_hire_date(int(emp.id), base_salary, 0.0, 0.0, hd)
            db.session.commit()
            try:
                from app.models import AppKV
                settings = {'salary_type': ('hourly' if salary_type=='hourly' else 'fixed')}
                if hourly_rate is not None:
                    settings['hourly_rate'] = float(hourly_rate or 0.0)
                AppKV.set(f"emp_settings:{int(emp.id)}", settings)
            except Exception:
                pass
            return jsonify({'ok': True, 'id': int(emp.id)})
        except Exception as e:
            db.session.rollback(); return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/employees/<int:eid>', methods=['PUT'], endpoint='api_employees_update')
@login_required
def api_employees_update(eid: int):
    try:
        if not user_can('employees','edit'):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        from models import Employee, EmployeeSalaryDefault
        emp = Employee.query.get_or_404(int(eid))
        full_name = (request.form.get('full_name') or '').strip() or emp.full_name
        department = (request.form.get('department') or '').strip() or (emp.department or '')
        position = (request.form.get('position') or '').strip() or (emp.position or '')
        branch_code = (request.form.get('branch_code') or '').strip() or ''
        base_salary = request.form.get('base_salary', type=float)
        salary_type = (request.form.get('salary_type') or '').strip().lower()
        hourly_rate = request.form.get('hourly_rate', type=float)
        emp.full_name = full_name
        emp.department = department
        emp.position = position
        try:
            emp.branch_code = branch_code
        except Exception:
            pass
        db.session.flush()
        try:
            d = EmployeeSalaryDefault.query.filter_by(employee_id=int(emp.id)).first()
            if not d:
                d = EmployeeSalaryDefault(employee_id=int(emp.id), base_salary=0.0, allowances=0.0, deductions=0.0)
                db.session.add(d)
            if base_salary is not None:
                d.base_salary = float(base_salary or 0.0)
        except Exception:
            pass
        try:
            from app.models import AppKV
            cur = AppKV.get(f"emp_settings:{int(emp.id)}") or {}
            if salary_type in ('fixed','hourly'):
                cur['salary_type'] = salary_type
            if hourly_rate is not None:
                cur['hourly_rate'] = float(hourly_rate or 0.0)
            if cur:
                AppKV.set(f"emp_settings:{int(emp.id)}", cur)
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback(); return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/employees/<int:eid>', methods=['DELETE'], endpoint='api_employees_delete')
@login_required
def api_employees_delete(eid: int):
    return ('', 404)
    try:
        if not user_can('employees','delete'):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        from models import Employee, Salary, Payment, EmployeeSalaryDefault, EmployeeHours, JournalLine, JournalEntry, LedgerEntry
        emp = Employee.query.get_or_404(int(eid))
        sal_rows = Salary.query.filter_by(employee_id=int(eid)).all()
        sal_ids = [s.id for s in sal_rows]
        if sal_ids:
            try:
                Payment.query.filter(Payment.invoice_type=='salary', Payment.invoice_id.in_(sal_ids)).delete(synchronize_session=False)
            except Exception:
                pass
            Salary.query.filter(Salary.id.in_(sal_ids)).delete(synchronize_session=False)
        # Remove employee hours records
        try:
            EmployeeHours.query.filter_by(employee_id=int(eid)).delete(synchronize_session=False)
        except Exception:
            pass
        try:
            EmployeeSalaryDefault.query.filter_by(employee_id=int(eid)).delete(synchronize_session=False)
        except Exception:
            pass
        # Remove journal lines linked to this employee
        jline_ids = []
        jentry_ids = set()
        try:
            rows = JournalLine.query.filter(JournalLine.employee_id == int(eid)).all()
            for jl in rows:
                try:
                    jline_ids.append(int(jl.id))
                except Exception:
                    pass
                try:
                    jentry_ids.add(int(getattr(jl, 'journal_id', 0) or 0))
                except Exception:
                    pass
            if jline_ids:
                JournalLine.query.filter(JournalLine.id.in_(jline_ids)).delete(synchronize_session=False)
        except Exception:
            pass
        # Remove journal entries tied to the employee's salaries (accruals, payments, advances)
        try:
            if sal_ids:
                JournalEntry.query.filter(JournalEntry.salary_id.in_(sal_ids)).delete(synchronize_session=False)
        except Exception:
            pass
        # Clean up orphan journal entries (no remaining lines)
        try:
            if jentry_ids:
                for jid in list(jentry_ids):
                    try:
                        cnt = JournalLine.query.filter(JournalLine.journal_id == int(jid)).count()
                        if int(cnt or 0) == 0:
                            je = JournalEntry.query.get(int(jid))
                            if je:
                                db.session.delete(je)
                    except Exception:
                        continue
        except Exception:
            pass
        # Remove ledger entries created for salary payments or advances for this employee
        try:
            # Match descriptions used when posting:
            # - 'PAY SAL ... EMP <eid>' (salary payment)
            # - 'ADV EMP <eid>' (advance grant)
            # - 'ADV REPAY <eid>' (advance repayment)
            like_emp = f"% EMP {int(eid)}%"
            like_adv = f"%ADV EMP {int(eid)}%"
            like_adv_repay = f"%ADV REPAY {int(eid)}%"
            LedgerEntry.query.filter(
                or_(
                    LedgerEntry.description.like(like_emp),
                    LedgerEntry.description.like(like_adv),
                    LedgerEntry.description.like(like_adv_repay)
                )
            ).delete(synchronize_session=False)
        except Exception:
            pass
        db.session.delete(emp)
        # Remove KV settings/notes for this employee
        try:
            from app.models import AppKV
            AppKV.query.filter(AppKV.k.in_([f"emp_settings:{int(eid)}", f"emp_note:{int(eid)}"]))\
                .delete(synchronize_session=False)
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback(); return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/employees/<int:eid>', methods=['GET'], endpoint='api_employees_get')
@login_required
def api_employees_get(eid: int):
    return ('', 404)
    try:
        from models import Employee, EmployeeSalaryDefault
        emp = Employee.query.get(int(eid))
        if not emp:
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 404
        d = EmployeeSalaryDefault.query.filter_by(employee_id=int(emp.id)).first()
        data = {
            'id': int(getattr(emp,'id',0) or 0),
            'full_name': getattr(emp,'full_name','') or '',
            'department': getattr(emp,'department','') or '',
            'position': getattr(emp,'position','') or '',
            'branch_code': getattr(emp,'branch_code','') or '',
            'status': getattr(emp,'status','') or '',
            'basic': float(getattr(d,'base_salary',0) or 0) if d else 0.0,
            'email': getattr(emp,'email','') or '',
            'phone': getattr(emp,'phone','') or ''
        }
        return jsonify({'ok': True, 'employee': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/maintenance/cleanup-dummy', methods=['POST'], endpoint='api_cleanup_dummy')
@login_required
def api_cleanup_dummy():
    try:
        # Remove journal lines whose employee_id no longer exists
        from models import Employee, JournalLine, JournalEntry, LedgerEntry
        existing_ids = {int(e.id) for e in Employee.query.all()}
        rem_lines = 0
        try:
            rows = JournalLine.query.all()
            for jl in rows:
                try:
                    eid = int(getattr(jl, 'employee_id', 0) or 0)
                except Exception:
                    eid = 0
                if eid and eid not in existing_ids:
                    db.session.delete(jl); rem_lines += 1
            db.session.flush()
        except Exception:
            pass
        # Remove orphan journal entries (no remaining lines)
        rem_entries = 0
        try:
            jrows = JournalEntry.query.all()
            for je in jrows:
                try:
                    cnt = JournalLine.query.filter(JournalLine.journal_id == int(je.id)).count()
                    if int(cnt or 0) == 0:
                        db.session.delete(je); rem_entries += 1
                except Exception:
                    continue
        except Exception:
            pass
        # Remove ledger entries for advances/payments referencing non-active employees via description patterns
        rem_ledgers = 0
        try:
            active_ids = {int(e.id) for e in Employee.query.filter_by(active=True).all()}
            lrows = LedgerEntry.query.all()
            for le in lrows:
                desc = str(getattr(le, 'description', '') or '')
                # Try to extract employee id from patterns
                cand = None
                for tag in (' EMP ', 'ADV EMP ', 'ADV REPAY '):
                    if tag in desc:
                        try:
                            tail = desc.split(tag)[-1].strip()
                            cand = int(''.join([ch for ch in tail if ch.isdigit()]))
                        except Exception:
                            cand = None
                        break
                if cand and cand not in active_ids:
                    db.session.delete(le); rem_ledgers += 1
        except Exception:
            pass
        # Optionally remove known dummy employees by name if present
        removed_emps = 0
        try:
            dummies = Employee.query.filter(Employee.full_name.in_(['RIDOY','SAIFUL ISLAM'])).all()
            for emp in dummies:
                db.session.delete(emp); removed_emps += 1
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True, 'removed': {'journal_lines': rem_lines, 'journal_entries': rem_entries, 'ledger_entries': rem_ledgers, 'employees': removed_emps}})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/payroll-templates', methods=['GET'], endpoint='api_payroll_templates')
@login_required
def api_payroll_templates():
    try:
        tpl = {
            'template_id': 'default',
            'components': ["basic","extra","day_off","bonus","ot","others","vac_eid","deduct"]
        }
        return jsonify({'ok': True, 'templates': [tpl]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/payroll-run', methods=['POST'], endpoint='api_payroll_run')
@login_required
def api_payroll_run():
    """حفظ المسير مع إنشاء قيد استحقاق (مدين: مصروف رواتب، دائن: رواتب مستحقة). rows = [{ employee_id, selected, salary }]."""
    try:
        import json as _json
        month = request.form.get('month') or request.form.get('pay_month') or get_saudi_now().strftime('%Y-%m')
        y, m = month.split('-'); year = int(y); mon = int(m)
        employees_json = request.form.get('rows') or '[]'
        rows = _json.loads(employees_json) if isinstance(employees_json, str) else (employees_json or [])
        selected_ids = set()
        details = []
        for r in rows:
            sel = r.get('selected') in (True, 1, '1', 'true', 'yes')
            if not sel:
                continue
            eid = r.get('employee_id') or r.get('id')
            try:
                eid = int(eid)
            except (TypeError, ValueError):
                continue
            basic = float(r.get('basic') or 0)
            extra = float(r.get('extra') or 0)
            absence = float(r.get('absence') or 0)
            incentive = float(r.get('incentive') or 0)
            allow = float(r.get('allowances') or 0)
            ded = float(r.get('deductions') or 0)
            sal = float(r.get('salary') or r.get('total') or 0)
            if sal == 0 and (basic or extra or allow or incentive or absence or ded):
                sal = basic + extra - absence + incentive + allow - ded
            selected_ids.add(eid)
            details.append({'employee_id': eid, 'basic': basic, 'extra': extra, 'absence': absence, 'incentive': incentive, 'allowances': allow, 'deductions': ded, 'salary': round(max(0, sal), 2)})
        if not selected_ids:
            return jsonify({'ok': False, 'error': 'select_at_least_one'}), 400
        for d in details:
            eid = int(d['employee_id'])
            basic = round(float(d.get('basic') or 0), 2)
            extra = round(float(d.get('extra') or 0), 2)
            absence = round(float(d.get('absence') or 0), 2)
            incentive = round(float(d.get('incentive') or 0), 2)
            allow = round(float(d.get('allowances') or 0), 2)
            ded = round(float(d.get('deductions') or 0), 2)
            sal = round(float(d.get('salary') or 0), 2)
            if sal <= 0:
                sal = max(0, basic + extra - absence + incentive + allow - ded)
            s = Salary.query.filter_by(employee_id=eid, year=year, month=mon).first()
            if not s:
                s = Salary(employee_id=eid, year=year, month=mon, basic_salary=basic, extra=extra, absence=absence, incentive=incentive, allowances=allow, deductions=ded, previous_salary_due=0.0, total_salary=sal, status='due')
                db.session.add(s)
            else:
                s.basic_salary = basic
                s.extra = extra
                s.absence = absence
                s.incentive = incentive
                s.allowances = allow
                s.deductions = ded
                s.previous_salary_due = 0.0
                s.total_salary = sal
            db.session.flush()
        all_per = Salary.query.filter_by(year=year, month=mon).all()
        for s in all_per:
            if (s.employee_id or 0) in selected_ids:
                continue
            paid = db.session.query(Payment).filter(Payment.invoice_type == 'salary', Payment.invoice_id == s.id).first()
            if not paid:
                db.session.delete(s)
        ok_acc, acc_data, acc_entry = _create_payroll_accrual_je(year, mon)
        if not ok_acc and acc_data != 'already_posted':
            try:
                db.session.rollback()
            except Exception:
                pass
            return jsonify({'ok': False, 'error': acc_data or 'accrual_failed'}), 400
        db.session.commit()
        out = {'ok': True, 'month': {'year': year, 'month': mon}, 'details': details}
        if acc_entry:
            out['entry_number'] = acc_entry
        return jsonify(out)
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400


@main.route('/api/payroll/ensure-records', methods=['POST'], endpoint='api_payroll_ensure_records')
@login_required
def api_payroll_ensure_records():
    """إنشاء مسيرات رواتب ناقصة للموظفين من تاريخ التعيين حتى الشهر الحالي، ثم إنشاء قيد استحقاق (JE-PR) لكل شهر له مسيرات لضمان صحة المحاسبة."""
    try:
        from models import Employee, EmployeeSalaryDefault
        defaults = {int(d.employee_id): d for d in (EmployeeSalaryDefault.query.all() or [])}
        total_created = 0
        for emp in Employee.query.all():
            hire_date = getattr(emp, 'hire_date', None)
            if not hire_date:
                continue
            d = defaults.get(int(emp.id))
            base = float(getattr(d, 'base_salary', 0) or 0) if d else 0.0
            allow = float(getattr(d, 'allowances', 0) or 0) if d else 0.0
            ded = float(getattr(d, 'deductions', 0) or 0) if d else 0.0
            n = _ensure_salary_records_from_hire_date(int(emp.id), base, allow, ded, hire_date)
            total_created += n
        db.session.commit()
        # إنشاء قيد استحقاق (مدين: مصروف رواتب، دائن: رواتب مستحقة) لكل شهر له مسيرات ولا يملك قيداً بعد
        months_with_salary = db.session.query(Salary.year, Salary.month).distinct().all()
        accruals_created = 0
        for (y, m) in months_with_salary:
            ok, _, _ = _create_payroll_accrual_je(y, m)
            if ok:
                accruals_created += 1
        db.session.commit()
        msg = f'تم إنشاء {total_created} مسير رواتب'
        if accruals_created:
            msg += f' و{accruals_created} قيد استحقاق'
        return jsonify({'ok': True, 'created': total_created, 'accruals_created': accruals_created, 'message': msg})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


def _create_payroll_accrual_je(year, month):
    """إنشاء قيد استحقاق رواتب (مدين: مصروف رواتب، دائن: رواتب مستحقة) لشهر معيّن.
    يُرجع: (True, total, entry_number) عند النجاح، أو (False, error_code, None) عند الخطأ، أو (False, 'already_posted', None) إذا كان القيد موجوداً."""
    y, m = int(year), int(month)
    kv_key = f'payroll_accrual_{y}_{m}'
    if kv_get(kv_key) is not None:
        return (False, 'already_posted', None)
    if JournalEntry.query.filter_by(entry_number=f"JE-PR-{y}{m:02d}", status='posted').first():
        return (False, 'already_posted', None)
    total = float(db.session.query(func.coalesce(func.sum(Salary.total_salary), 0)).filter(Salary.year == y, Salary.month == m).scalar() or 0)
    total = round(total, 2)
    if total <= 0:
        return (False, 'no_salaries_or_zero_total', None)
    exp_code = SHORT_TO_NUMERIC.get('SAL_EXP', ('5310',))[0]
    liab_code = SHORT_TO_NUMERIC.get('PAYROLL_LIAB', ('2121',))[0]
    je = JournalEntry(entry_number=f"JE-PR-{y}{m:02d}", date=get_saudi_now().date(), branch_code=None, description=f"مسير رواتب {y}-{m:02d}", status='posted', total_debit=total, total_credit=total, created_by=getattr(current_user, 'id', None), posted_by=getattr(current_user, 'id', None))
    db.session.add(je)
    db.session.flush()
    exp_acc = _account(exp_code, CHART_OF_ACCOUNTS.get(exp_code, {}).get('name', 'مصروف رواتب'), CHART_OF_ACCOUNTS.get(exp_code, {}).get('type', 'EXPENSE'))
    liab_acc = _account(liab_code, CHART_OF_ACCOUNTS.get(liab_code, {}).get('name', 'رواتب مستحقة'), CHART_OF_ACCOUNTS.get(liab_code, {}).get('type', 'LIABILITY'))
    if exp_acc:
        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total, credit=0.0, description=f"مسير رواتب {y}-{m:02d}", line_date=get_saudi_now().date()))
    if liab_acc:
        db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=liab_acc.id, debit=0.0, credit=total, description=f"مسير رواتب {y}-{m:02d}", line_date=get_saudi_now().date()))
    kv_set(kv_key, int(je.id))
    return (True, total, je.entry_number)


@main.route('/api/payroll-post', methods=['POST'], endpoint='api_payroll_post')
@login_required
def api_payroll_post():
    """ترحيل المسير: إنشاء قيد استحقاق (مصروف رواتب / رواتب مستحقة) لفترة الشهر. يقبل form أو JSON مع year, month (اختياريان: يُستخدم الشهر الحالي)."""
    try:
        payload = request.get_json(silent=True) or {}
        year = request.form.get('year') or request.args.get('year') or payload.get('year')
        month = request.form.get('month') or request.args.get('month') or payload.get('month')
        if year is None or year == '' or month is None or month == '':
            y, m = get_saudi_now().year, get_saudi_now().month
        else:
            try:
                y = int(year)
                m = int(month)
            except (TypeError, ValueError):
                return jsonify({'ok': False, 'error': 'invalid_year_month'}), 400
        if not (1 <= m <= 12):
            return jsonify({'ok': False, 'error': 'invalid_month'}), 400
        ok, data, entry_number = _create_payroll_accrual_je(y, m)
        if not ok:
            if data == 'already_posted':
                return jsonify({'ok': True, 'already_posted': True, 'message': 'مسير مرحّل مسبقاً'})
            return jsonify({'ok': False, 'error': data or 'unknown'}), 400
        db.session.commit()
        return jsonify({'ok': True, 'entry_number': entry_number, 'total': data})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@main.route('/api/employee-unpaid-months', methods=['GET'], endpoint='api_employee_unpaid_months')
@login_required
def api_employee_unpaid_months():
    """قائمة أشهر المسيرات غير المدفوعة (أو المدفوعة جزئياً) لموظف معين — لاستخدامها في السداد الفردي.
    فلترة: من/إلى (شهر واحد = من==إلى، عدة أشهر = من..إلى)."""
    try:
        emp_id = request.args.get('employee_id', type=int)
        if not emp_id:
            return jsonify({'ok': False, 'error': 'employee_id_required'}), 400
        if not Employee.query.get(emp_id):
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 404
        from_year = request.args.get('from_year', type=int)
        from_month = request.args.get('from_month', type=int)
        to_year = request.args.get('to_year', type=int)
        to_month = request.args.get('to_month', type=int)
        rows = Salary.query.filter_by(employee_id=emp_id).order_by(Salary.year.desc(), Salary.month.desc()).all()
        out = []
        def _month_key(y, m):
            return int(y or 0) * 12 + int(m or 1)

        for s in rows:
            paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                .filter(Payment.invoice_type == 'salary', Payment.invoice_id == s.id).scalar() or 0)
            total = float(s.total_salary or 0)
            remaining = max(0.0, total - paid)
            if remaining < 1e-6:
                continue
            y, m = int(s.year or 0), int(s.month or 1)
            if from_year is not None and from_month is not None:
                if _month_key(y, m) < _month_key(from_year, from_month):
                    continue
            if to_year is not None and to_month is not None:
                if _month_key(y, m) > _month_key(to_year, to_month):
                    continue
            out.append({
                'year': int(s.year or 0),
                'month': int(s.month or 0),
                'label': f'{s.year}-{s.month:02d}',
                'label_ar': f'{int(s.month):02d}/{s.year}',
                'total': round(total, 2),
                'paid': round(paid, 2),
                'remaining': round(remaining, 2),
                'salary_id': int(s.id),
            })
        return jsonify({'ok': True, 'months': out})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@main.route('/api/employee-pay-months', methods=['POST'], endpoint='api_employee_pay_months')
@login_required
def api_employee_pay_months():
    """سداد فردي لعدة أشهر لموظف واحد: دفع المتبقي بالكامل لكل شهر محدد (شهر = مسير)."""
    try:
        data = request.get_json(force=True, silent=True) or request.form
        emp_id = data.get('employee_id')
        try:
            emp_id = int(emp_id)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'employee_id_required'}), 400
        months = data.get('months') or []
        if not isinstance(months, list) or not months:
            return jsonify({'ok': False, 'error': 'months_required'}), 400
        method = (data.get('payment_method') or 'cash').strip().lower()
        date_s = (data.get('date') or get_saudi_now().strftime('%Y-%m-%d')).strip()
        try:
            pay_dt = _dt.strptime(date_s, '%Y-%m-%d').date()
        except Exception:
            pay_dt = get_saudi_now().date()
        emp = Employee.query.get(emp_id)
        if not emp:
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 404
        pay_liab = _account(*SHORT_TO_NUMERIC.get('PAYROLL_LIAB', ('2121', 'رواتب مستحقة', 'LIABILITY')))
        cash_acc = _pm_account(method)
        created = 0
        for m in months:
            y, mo = m.get('year'), m.get('month')
            try:
                y, mo = int(y), int(mo)
            except (TypeError, ValueError):
                continue
            row = Salary.query.filter_by(employee_id=emp_id, year=y, month=mo).first()
            if not row:
                continue
            paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                .filter(Payment.invoice_type == 'salary', Payment.invoice_id == row.id).scalar() or 0)
            total = float(row.total_salary or 0)
            remaining = max(0.0, total - paid)
            if remaining < 1e-6:
                continue
            p = Payment(invoice_id=row.id, invoice_type='salary', amount_paid=round(remaining, 2), payment_date=pay_dt, payment_method=method)
            db.session.add(p)
            db.session.flush()
            je = JournalEntry(entry_number=f"JE-SALPAY-{row.id}", date=pay_dt, branch_code=None, description=f"Salary payment {y}-{mo:02d} EMP {emp_id}", status='posted', total_debit=round(remaining, 2), total_credit=round(remaining, 2), created_by=getattr(current_user, 'id', None), posted_by=getattr(current_user, 'id', None), salary_id=row.id)
            db.session.add(je)
            db.session.flush()
            if pay_liab:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=pay_liab.id, debit=round(remaining, 2), credit=0.0, description=f'سداد راتب {y}-{mo:02d}', line_date=pay_dt, employee_id=emp_id))
            if cash_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=round(remaining, 2), description='صندوق/بنك', line_date=pay_dt, employee_id=emp_id))
            row.status = 'paid'
            created += 1
        db.session.commit()
        return jsonify({'ok': True, 'paid_months': created})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400


@main.route('/api/advances', methods=['POST'], endpoint='api_advances')
@login_required
def api_advances():
    try:
        emp_id = request.form.get('employee_id', type=int)
        amount = request.form.get('amount', type=float) or 0.0
        method = (request.form.get('method') or 'cash').strip().lower()
        date_s = (request.form.get('date') or get_saudi_now().strftime('%Y-%m-%d'))
        from datetime import datetime as _dt
        dval = _dt.strptime(date_s, '%Y-%m-%d').date()
        if not emp_id or amount <= 0:
            return jsonify({'ok': False, 'error': 'invalid'}), 400
        try:
            from models import JournalEntry, JournalLine
            cash_acc = _pm_account(method)
            emp_adv_acc = _account(*SHORT_TO_NUMERIC['EMP_ADV'])
            je = JournalEntry(entry_number=f"JE-ADV-{emp_id}-{int(amount)}", date=dval, branch_code=None, description=f"Employee advance {emp_id}", status='posted', total_debit=amount, total_credit=amount, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
            db.session.add(je); db.session.flush()
            if emp_adv_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=emp_adv_acc.id, debit=amount, credit=0.0, description='Employee advance', line_date=dval, employee_id=emp_id))
            if cash_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amount, description='Cash/Bank', line_date=dval, employee_id=emp_id))
            db.session.commit()
        except Exception:
            db.session.rollback(); return jsonify({'ok': False, 'error': 'post_failed'}), 400
        try:
            _post_ledger(dval, 'EMP_ADV', 'سلف للموظفين', 'asset', amount, 0.0, f'ADV EMP {emp_id}')
            if method in ('bank','card','visa','mastercard'):
                _post_ledger(dval, 'BANK', 'Bank', 'asset', 0.0, amount, f'ADV EMP {emp_id}')
            else:
                _post_ledger(dval, 'CASH', 'Cash', 'asset', 0.0, amount, f'ADV EMP {emp_id}')
        except Exception:
            pass
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/employee-ledger', methods=['GET'], endpoint='api_employee_ledger')
@login_required
def api_employee_ledger():
    try:
        emp_id = request.args.get('emp_id', type=int)
        if not emp_id:
            return jsonify({'ok': False, 'error': 'emp_id_required'}), 400
        from models import JournalLine, JournalEntry
        rows = db.session.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalLine.employee_id == emp_id).order_by(JournalEntry.date.asc(), JournalLine.line_no.asc()).all()
        data = []
        for jl, je in rows:
            data.append({
                'date': str(getattr(je,'date',get_saudi_now().date())),
                'entry': getattr(je,'entry_number',''),
                'desc': getattr(jl,'description',''),
                'debit': float(getattr(jl,'debit',0) or 0),
                'credit': float(getattr(jl,'credit',0) or 0)
            })
        return jsonify({'ok': True, 'rows': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/payroll-import', methods=['POST'], endpoint='api_payroll_import')
@login_required
def api_payroll_import():
    return ('', 404)
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'ok': False, 'error': 'no_file'}), 400
        import csv, io
        content = file.read().decode('utf-8', errors='ignore')
        reader = csv.DictReader(io.StringIO(content))
        count = 0
        for row in reader:
            emp_id = int(row.get('employee_id') or 0)
            month = int(row.get('month') or get_saudi_now().month)
            year = int(row.get('year') or get_saudi_now().year)
            def to_f(x):
                try:
                    return float(x or 0)
                except Exception:
                    return 0.0
            b = to_f(row.get('basic'))
            ex = to_f(row.get('extra'))
            doff = to_f(row.get('day_off'))
            bon = to_f(row.get('bonus'))
            otv = to_f(row.get('ot'))
            oth = to_f(row.get('others'))
            ve = to_f(row.get('vac_eid'))
            ded = to_f(row.get('deduct'))
            total = to_f(row.get('total')) or round(b + ex + bon + otv + oth + ve - doff - ded, 2)
            s = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
            if not s:
                s = Salary(employee_id=emp_id, year=year, month=month, basic_salary=b, allowances=ex+bon+otv+oth+ve, deductions=doff+ded, previous_salary_due=0.0, total_salary=total, status='due')
                db.session.add(s)
            else:
                s.basic_salary = b
                s.allowances = ex+bon+otv+oth+ve
                s.deductions = doff+ded
                s.previous_salary_due = 0.0
                s.total_salary = total
            count += 1
        db.session.commit()
        return jsonify({'ok': True, 'imported': count})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/payroll/previous', methods=['GET'], endpoint='payroll_previous_page')
@login_required
def payroll_previous_page():
    warmup_db_once()
    try:
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        employees = []
    return ('', 404)

@main.route('/api/payroll/history', methods=['GET'], endpoint='api_payroll_history')
@login_required
def api_payroll_history():
    return ('', 404)
    try:
        rows = db.session.query(Salary.year, Salary.month, func.sum(func.coalesce(Salary.total_salary, 0))).group_by(Salary.year, Salary.month).order_by(Salary.year.desc(), Salary.month.desc()).all()
        total = float(sum([float(r[2] or 0) for r in rows]) or 0)
        last = rows[0] if rows else None
        months_count = len(rows)
        last_label = None
        if last:
            last_label = f"{last[1]:02d}/{last[0]}"
        series = [{'year': int(r[0]), 'month': int(r[1]), 'total': float(r[2] or 0)} for r in reversed(rows)]
        return jsonify({'ok': True, 'total': total, 'last_month': last_label, 'months': months_count, 'series': series})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/payroll/history/list', methods=['GET'], endpoint='api_payroll_history_list')
@login_required
def api_payroll_history_list():
    return ('', 404)
    try:
        month = (request.args.get('month') or '').strip()
        dept = (request.args.get('department') or '').strip().lower()
        status = (request.args.get('status') or '').strip().lower()
        pay_method = (request.args.get('payment_method') or '').strip().upper()
        if month:
            y, m = month.split('-')
            y = int(y); m = int(m)
            q = Salary.query.filter_by(year=y, month=m)
        else:
            q = Salary.query
        rows = q.all()
        data = []
        for s in rows:
            try:
                e = Employee.query.get(int(s.employee_id))
            except Exception:
                e = None
            dep = (getattr(e, 'department', '') or '')
            if dept and dept not in dep.lower():
                continue
            st = (getattr(s, 'status', '') or '').strip().lower()
            if status and status not in st:
                continue
            pm_display = ''
            receipt_url = ''
            try:
                from flask import url_for
                pay_rows = Payment.query.filter(Payment.invoice_type=='salary', Payment.invoice_id==int(s.id)).order_by(Payment.payment_date.asc()).all()
                pids = []
                last_method = None
                for p in (pay_rows or []):
                    try:
                        pids.append(str(int(p.id)))
                        last_method = (getattr(p,'payment_method','') or '').strip().upper()
                    except Exception:
                        continue
                if pids:
                    receipt_url = url_for('main.salary_receipt') + '?pids=' + ','.join(pids)
                pm_display = last_method or ''
            except Exception:
                pm_display = ''
                receipt_url = ''
            if pay_method:
                def _norm(m):
                    m = (m or '').upper()
                    return 'BANK' if m in ('BANK','TRANSFER') else ('CASH' if m=='CASH' else m)
                if _norm(pm_display) != _norm(pay_method):
                    continue
            data.append({
                'employee_id': int(getattr(s, 'employee_id', 0) or 0),
                'employee_name': getattr(e, 'full_name', '') if e else '',
                'month_label': f"{int(getattr(s,'month',0)):02d}/{int(getattr(s,'year',0))}",
                'basic': float(getattr(s, 'basic_salary', 0) or 0),
                'ot': 0.0,
                'bonus': 0.0,
                'total': float(getattr(s, 'total_salary', 0) or 0),
                'status': getattr(s, 'status', '') or 'due',
                'payment_method': pm_display,
                'receipt_url': receipt_url,
            })
        return jsonify({'ok': True, 'rows': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/ledger', methods=['GET'], endpoint='ledger_page')
@login_required
def ledger_page():
    warmup_db_once()
    try:
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
    except Exception:
        employees = []
    return render_template('ledger.html', employees=employees)

@main.route('/chart-of-accounts', methods=['GET'], endpoint='chart_of_accounts')
@login_required
def chart_of_accounts():
    return render_template('chart.html')

def _gen_code_for_type(acc_type: str) -> str:
    try:
        import re
        t = (acc_type or '').strip().upper()
        ranges = {
            'ASSET': (1000, 1999),
            'LIABILITY': (2000, 2999),
            'EQUITY': (3000, 3999),
            'REVENUE': (4000, 4999),
            'EXPENSE': (5000, 5999),
            'TAX': (6000, 6999),
            'COGS': (5000, 5999)
        }
        base, end = ranges.get(t, (7000, 7999))
        seq_key = f"chart_code_seq:{t}"
        last = kv_get(seq_key, None)
        if isinstance(last, int):
            cand = min(last + 10, end)
        else:
            codes = []
            for k in CHART_OF_ACCOUNTS.keys():
                try:
                    x = int(re.sub(r'[^0-9]', '', str(k)))
                except Exception:
                    x = 0
                if x >= base and x <= end:
                    codes.append(x)
            extra = kv_get('chart_accounts', []) or []
            for e in extra:
                try:
                    x = int(re.sub(r'[^0-9]', '', str(e.get('code'))))
                except Exception:
                    x = 0
                if x >= base and x <= end:
                    codes.append(x)
            cand = max(codes) + 10 if codes else base
        if cand > end:
            cand = end
        kv_set(seq_key, cand)
        return str(cand)
    except Exception:
        return str(int(datetime.utcnow().timestamp()) % 10000)

@main.route('/api/chart/list', methods=['GET'], endpoint='api_chart_list')
@login_required
def api_chart_list():
    try:
        overrides = kv_get('chart_overrides', {}) or {}
        extra = kv_get('chart_accounts', []) or []
        out = []
        coa = CHART_OF_ACCOUNTS
        if not coa:
            try:
                from data.coa_new_tree import build_coa_dict
                coa = build_coa_dict()
            except Exception as e:
                try:
                    current_app.logger.warning("api_chart_list: coa_new_tree fallback failed: %s", e)
                except Exception:
                    pass
        for code, info in (coa or {}).items():
            # استخدام parent_account_code من الشجرة الجديدة إن وُجد، وإلا استخدام parent_guess كاحتياطي
            parent_code = info.get('parent_account_code') or ''
            if not parent_code and code not in ('1000','2000','3000','4000','5000','0006'):
                t = (info.get('type') or '').upper()
                parent_code = {'ASSET':'1000','LIABILITY':'2000','EQUITY':'3000','REVENUE':'4000','EXPENSE':'5000','TAX':'0006','COGS':'5000'}.get(t,'')
            out.append({
                'code': code,
                'name': info.get('name'),
                'type': info.get('type'),
                'enabled': bool((overrides.get(code) or {}).get('enabled', True)),
                'parent': parent_code,
                'balance': 0.0,
                'notes': '',
                'system': True,
            })
        for e in extra:
            out.append({
                'code': e.get('code'),
                'name': e.get('name'),
                'type': e.get('type'),
                'enabled': bool(e.get('enabled', True)),
                'parent': e.get('parent') or '',
                'balance': float(e.get('balance') or 0.0),
                'notes': e.get('notes') or '',
                'system': False,
            })
        try:
            from models import Account
            rows = Account.query.all()
            known = {x['code'] for x in out}
            for a in rows:
                c = (a.code or '').strip()
                if not c or c in known:
                    continue
                out.append({
                    'code': c,
                    'name': a.name,
                    'type': (a.type or 'EXPENSE'),
                    'enabled': True,
                    'parent': ({'ASSET':'1000','LIABILITY':'2000','EQUITY':'3000','REVENUE':'4000','EXPENSE':'5000','TAX':'0006','COGS':'5000'}).get((a.type or '').upper(), ''),
                    'balance': 0.0,
                    'notes': '',
                    'system': False,
                })
        except Exception:
            pass
        return jsonify({'ok': True, 'items': out})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/chart/balances', methods=['GET'], endpoint='api_chart_balances')
@login_required
def api_chart_balances():
    try:
        from models import JournalLine, Account, JournalEntry
        start_arg = (request.args.get('start_date') or '').strip()
        end_arg = (request.args.get('end_date') or '').strip()
        branch = (request.args.get('branch') or '').strip()
        q = db.session.query(Account.code.label('code'), func.coalesce(func.sum(JournalLine.debit), 0.0).label('debit_total'), func.coalesce(func.sum(JournalLine.credit), 0.0).label('credit_total')).join(Account, JournalLine.account_id == Account.id).join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        if start_arg and end_arg:
            try:
                from datetime import datetime as _dt
                sd = _dt.strptime(start_arg, '%Y-%m-%d').date()
                ed = _dt.strptime(end_arg, '%Y-%m-%d').date()
                q = q.filter(JournalLine.line_date.between(sd, ed))
            except Exception:
                pass
        if branch in ('china_town','place_india'):
            q = q.filter(JournalEntry.branch_code == branch)
        rows = q.group_by(Account.code).all()
        items = []
        for code, d, c in rows:
            dd = float(d or 0.0); cc = float(c or 0.0)
            items.append({'code': code, 'debit_total': dd, 'credit_total': cc, 'net': round(dd - cc, 2)})
        return jsonify({'ok': True, 'items': items})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/chart/opening_balance', methods=['POST'], endpoint='api_chart_opening_balance')
@login_required
@csrf.exempt
def api_chart_opening_balance():
    try:
        data = request.get_json(force=True) or {}
        code = (data.get('code') or '').strip()
        side = (data.get('side') or 'debit').strip().lower()
        amount = float(data.get('amount') or 0.0)
        date_str = (data.get('date') or '').strip()
        note = (data.get('note') or '').strip()
        if not code or amount <= 0:
            return jsonify({'ok': False, 'error': 'invalid_input'}), 400
        # Resolve date
        try:
            if date_str:
                from datetime import datetime as _dt
                je_date = _dt.strptime(date_str, '%Y-%m-%d').date()
            else:
                today = get_saudi_now().date()
                je_date = today.replace(month=1, day=1)
        except Exception:
            je_date = get_saudi_now().date()
        from models import Account, JournalEntry, JournalLine
        # Ensure main account exists
        acc = Account.query.filter(Account.code == code).first()
        if not acc:
            info = CHART_OF_ACCOUNTS.get(code, {'name': 'Account', 'type': 'EXPENSE'})
            acc = Account(code=code, name=info.get('name'), type=info.get('type'))
            db.session.add(acc); db.session.flush()
        # Ensure offset account (Owners’ Equity) exists
        off_code = '3110'
        off = Account.query.filter(Account.code == off_code).first()
        if not off:
            info = CHART_OF_ACCOUNTS.get(off_code, {'name':'حقوق الملكية','type':'EQUITY'})
            off = Account(code=off_code, name=info.get('name'), type=info.get('type'))
            db.session.add(off); db.session.flush()
        # Create journal entry
        entry_no = f"JE-OPEN-{code}-{int(get_saudi_now().timestamp())}"
        je = JournalEntry(entry_number=entry_no, date=je_date, branch_code=None, description=f"Opening Balance {code}", status='posted', total_debit=amount, total_credit=amount, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
        db.session.add(je); db.session.flush()
        # Lines
        if side == 'debit':
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=acc.id, debit=amount, credit=0.0, description=note or f"Opening {code}", line_date=je_date))
            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=off.id, debit=0.0, credit=amount, description=note or f"Opening offset", line_date=je_date))
        else:
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=acc.id, debit=0.0, credit=amount, description=note or f"Opening {code}", line_date=je_date))
            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=off.id, debit=amount, credit=0.0, description=note or f"Opening offset", line_date=je_date))
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/vat/net', methods=['GET'], endpoint='api_vat_net')
@login_required
def api_vat_net():
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
        from models import JournalLine, Account, JournalEntry
        q_out = db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0)).\
            join(Account, JournalLine.account_id == Account.id).\
            join(JournalEntry, JournalLine.journal_id == JournalEntry.id).\
            filter(Account.code == '2141', JournalLine.line_date.between(sd, ed))
        q_in = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).\
            join(Account, JournalLine.account_id == Account.id).\
            join(JournalEntry, JournalLine.journal_id == JournalEntry.id).\
            filter(Account.code == '1100', JournalLine.line_date.between(sd, ed))
        if branch in ('china_town','place_india'):
            q_out = q_out.filter(JournalEntry.branch_code == branch)
            q_in = q_in.filter(JournalEntry.branch_code == branch)
        vat_out = float(q_out.scalar() or 0.0)
        vat_in = float(q_in.scalar() or 0.0)
        net = round(vat_out - vat_in, 2)
        return jsonify({'ok': True, 'start_date': sd.isoformat(), 'end_date': ed.isoformat(), 'branch': branch or 'all', 'out': vat_out, 'in': vat_in, 'net': net})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/expenses/proof', methods=['POST'], endpoint='api_expense_proof')
@login_required
@csrf.exempt
def api_expense_proof():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = request.form.to_dict() if request.form else {}
    try:
        scenario = (data.get('scenario') or '').strip().lower()
        amount = float(data.get('amount') or 0.0)
        if amount <= 0:
            return jsonify({'ok': False, 'error': 'invalid_amount'}), 400
        date_str = (data.get('date') or '').strip()
        branch_raw = (data.get('branch') or '').strip().lower()
        branch = branch_raw if branch_raw in ('china_town','place_india') else None
        pm = (data.get('payment_method') or 'cash').strip().lower()
        note = (data.get('note') or '').strip()
        apply_vat = bool(str(data.get('apply_vat') or '').lower() in ('1','true','yes','on'))
        bank_fee = float(data.get('bank_fee') or 0.0)
        from models import ExpenseInvoice, ExpenseInvoiceItem, JournalEntry, JournalLine
        try:
            from datetime import datetime as _dt
            inv_date = _dt.strptime(date_str, '%Y-%m-%d').date() if date_str else get_saudi_now().date()
        except Exception:
            inv_date = get_saudi_now().date()
        purchase_category = (data.get('purchase_category') or '').strip()
        purchase_item = (data.get('purchase_item') or '').strip()
        desc = {
            'salaries': 'Salaries Payment / سداد رواتب',
            'vat': 'VAT Settlement / سداد ضريبة القيمة المضافة',
            'purchase_no_vat': 'Operating Purchases (No VAT) / مشتريات تشغيل بدون ضريبة',
            'maintenance': 'Maintenance & Services / صيانة وخدمات',
            'prepaid_rent': 'Prepaid Rent / إيجار مقدم',
            'cash_deposit': 'Bank Cash Deposit / إيداع نقدي بالبنك',
        }.get(scenario, 'Expense / مصروف')
        if scenario == 'purchase_no_vat':
            extra = []
            if purchase_category:
                extra.append(purchase_category)
            if purchase_item:
                extra.append(purchase_item)
            if extra:
                desc = f"{desc} — " + "; ".join(extra)

        def acc(code, name, typ):
            return _account(code, name, typ)
        cash_acc = _pm_account(pm)

        # عمليات قيد فقط (لا فاتورة): سداد رواتب، سداد VAT، إيداع نقدي
        ops_je_only = scenario in ('salaries', 'vat', 'cash_deposit')
        if ops_je_only:
            ts = int(get_saudi_now().timestamp())
            total = round(amount + (bank_fee if scenario == 'cash_deposit' else 0.0), 2)
            je = JournalEntry(
                entry_number=f"JE-OPS-{ts}",
                date=inv_date,
                branch_code=branch,
                description=desc,
                status='posted',
                total_debit=total,
                total_credit=total,
                created_by=getattr(current_user, 'id', None),
                posted_by=getattr(current_user, 'id', None),
            )
            db.session.add(je)
            db.session.flush()
            if scenario == 'salaries':
                a = acc('5310', CHART_OF_ACCOUNTS.get('5310', {}).get('name', 'رواتب وأجور'), 'EXPENSE')
                if a:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=a.id, debit=amount, credit=0.0, description=desc, line_date=inv_date))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amount, description=desc, line_date=inv_date))
            elif scenario == 'vat':
                a = acc('2141', CHART_OF_ACCOUNTS.get('2141', {'name': 'ضريبة القيمة المضافة – مستحقة', 'type': 'LIABILITY'}).get('name', 'ضريبة القيمة المضافة – مستحقة'), 'LIABILITY')
                if a:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=a.id, debit=amount, credit=0.0, description=desc, line_date=inv_date))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amount, description=desc, line_date=inv_date))
            else:
                assert scenario == 'cash_deposit'
                b = acc('1121', CHART_OF_ACCOUNTS.get('1121', {}).get('name', 'بنك'), 'ASSET')
                c = acc('1111', CHART_OF_ACCOUNTS.get('1111', {}).get('name', 'صندوق رئيسي'), 'ASSET')
                ln = 1
                if b:
                    db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=b.id, debit=amount, credit=0.0, description=desc, line_date=inv_date))
                    ln += 1
                if c:
                    db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=c.id, debit=0.0, credit=amount, description=desc, line_date=inv_date))
                    ln += 1
                if bank_fee > 0 and b:
                    f = acc('5610', CHART_OF_ACCOUNTS.get('5610', {}).get('name', 'مصروفات بنكية'), 'EXPENSE')
                    if f:
                        db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=f.id, debit=bank_fee, credit=0.0, description=desc, line_date=inv_date))
                        ln += 1
                    db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=b.id, debit=0.0, credit=bank_fee, description=desc, line_date=inv_date))
            db.session.commit()
            return jsonify({'ok': True, 'journal_only': True, 'entry_number': je.entry_number})

        # مصروفات (فاتورة + قيد): مشتريات تشغيل، صيانة، إيجار مقدم، وغيرها
        tax_amt = round(amount * 0.15, 2) if (apply_vat and scenario in ('maintenance', 'services', 'service', 'prepaid_rent', 'rent')) else 0.0
        total_final = round(amount + tax_amt, 2)
        inv_no = f"EXP-{int(get_saudi_now().timestamp())}"
        inv = ExpenseInvoice(
            invoice_number=inv_no,
            date=inv_date,
            payment_method=pm.upper(),
            total_before_tax=amount,
            tax_amount=tax_amt,
            discount_amount=0.0,
            total_after_tax_discount=total_final,
            status='paid',
            user_id=getattr(current_user, 'id', None),
        )
        db.session.add(inv)
        db.session.flush()
        item = ExpenseInvoiceItem(
            invoice_id=inv.id,
            description=desc,
            quantity=1,
            price_before_tax=amount,
            tax=tax_amt,
            discount=0.0,
            total_price=total_final,
        )
        db.session.add(item)
        db.session.flush()
        je = JournalEntry(
            entry_number=f"JE-EXP-{inv_no}",
            date=inv_date,
            branch_code=branch,
            description=desc,
            status='posted',
            total_debit=total_final,
            total_credit=total_final,
            created_by=getattr(current_user, 'id', None),
            posted_by=getattr(current_user, 'id', None),
        )
        db.session.add(je)
        db.session.flush()
        if scenario == 'purchase_no_vat':
            a = acc('1161', CHART_OF_ACCOUNTS.get('1161', {}).get('name', 'مخزون بضائع'), 'ASSET')
            if a:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=a.id, debit=amount, credit=0.0, description=desc, line_date=inv_date))
            if pm == 'creditor':
                ar = acc('2111', CHART_OF_ACCOUNTS.get('2111', {}).get('name', 'موردون'), 'LIABILITY')
                if ar:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ar.id, debit=0.0, credit=amount, description=desc, line_date=inv_date))
            else:
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amount, description=desc, line_date=inv_date))
        elif scenario == 'maintenance':
            ln = 1
            a = acc('5240', CHART_OF_ACCOUNTS.get('5240', {}).get('name', 'مصروف صيانة'), 'EXPENSE')
            if a:
                db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=a.id, debit=amount, credit=0.0, description=desc, line_date=inv_date))
                ln += 1
            if apply_vat:
                v = acc('1170', CHART_OF_ACCOUNTS.get('1170', {}).get('name', 'ضريبة القيمة المضافة – مدخلات'), 'ASSET')
                if v and tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=v.id, debit=tax_amt, credit=0.0, description=desc, line_date=inv_date))
                    ln += 1
            if pm == 'creditor':
                ar = acc('2111', CHART_OF_ACCOUNTS.get('2111', {}).get('name', 'موردون'), 'LIABILITY')
                if ar:
                    db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=ar.id, debit=0.0, credit=total_final, description=desc, line_date=inv_date))
            else:
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=ln, account_id=cash_acc.id, debit=0.0, credit=total_final, description=desc, line_date=inv_date))
        elif scenario == 'prepaid_rent':
            a = acc('1142', CHART_OF_ACCOUNTS.get('1142', {}).get('name', 'ذمم مدينة أخرى'), 'ASSET')
            if a:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=a.id, debit=amount, credit=0.0, description=desc, line_date=inv_date))
            if cash_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amount, description=desc, line_date=inv_date))
        else:
            a = acc('5410', CHART_OF_ACCOUNTS.get('5410', {}).get('name', 'مصروفات حكومية ورسوم'), 'EXPENSE')
            if a:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=a.id, debit=amount, credit=0.0, description=desc, line_date=inv_date))
            if cash_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amount, description=desc, line_date=inv_date))
        db.session.commit()
        return jsonify({'ok': True, 'invoice_number': inv_no})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/chart/toggle/<code>', methods=['POST'], endpoint='api_chart_toggle')
@login_required
@csrf.exempt
def api_chart_toggle(code):
    try:
        overrides = kv_get('chart_overrides', {}) or {}
        cur = overrides.get(code) or {}
        cur['enabled'] = not bool(cur.get('enabled', True))
        overrides[code] = cur
        kv_set('chart_overrides', overrides)
        return jsonify({'ok': True, 'enabled': cur['enabled']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/chart/add', methods=['POST'], endpoint='api_chart_add')
@login_required
@csrf.exempt
def api_chart_add():
    try:
        data = request.get_json(force=True) or {}
        name = (data.get('name') or '').strip()
        acc_type = (data.get('type') or '').strip().upper()
        role = (data.get('role') or '').strip().lower()
        enabled = bool(data.get('enabled', True))
        parent = (data.get('parent_code') or '').strip()
        opening_balance = float(data.get('opening_balance') or 0.0)
        notes = (data.get('notes') or '').strip()
        if not name or not acc_type:
            return jsonify({'ok': False, 'error': 'missing_fields'}), 400
        code = _gen_code_for_type(acc_type)
        cur = kv_get('chart_accounts', []) or []
        cur.append({'code': code, 'name': name, 'type': acc_type, 'enabled': enabled, 'parent': parent, 'balance': opening_balance, 'notes': notes})
        kv_set('chart_accounts', cur)
        if role in ('platform_ar','platform_revenue'):
            pk = (data.get('platform_key') or '').strip().lower()
            if pk:
                platforms = kv_get('platforms_map', []) or []
                kws_raw = (data.get('platform_keywords') or '').strip()
                keywords = [x.strip().lower() for x in kws_raw.split(',') if x.strip()]
                entry = {'key': pk, 'keywords': keywords, 'auto_unpaid': True}
                if role == 'platform_ar':
                    entry['ar_code'] = code
                else:
                    entry['rev_code'] = code
                idx = None
                for i, e in enumerate(platforms):
                    if (e.get('key') or '').strip().lower() == pk:
                        idx = i; break
                if idx is not None:
                    prev = platforms[idx]
                    prev.update(entry)
                    if keywords:
                        prev['keywords'] = keywords
                    platforms[idx] = prev
                else:
                    platforms.append(entry)
                kv_set('platforms_map', platforms)
        elif role in ('branch_rev_ct','branch_rev_pi','default_ar'):
            acc_map = kv_get('acc_map', {}) or {}
            if role == 'branch_rev_ct':
                acc_map['REV_CT'] = code
            elif role == 'branch_rev_pi':
                acc_map['REV_PI'] = code
            elif role == 'default_ar':
                acc_map['AR'] = code
            kv_set('acc_map', acc_map)
        return jsonify({'ok': True, 'code': code})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/chart/refresh', methods=['POST'], endpoint='api_chart_refresh')
@login_required
@csrf.exempt
def api_chart_refresh():
    try:
        overrides = kv_get('chart_overrides', {}) or {}
        cur = kv_get('chart_accounts', []) or []
        try:
            from models import Account
            rows = Account.query.all()
        except Exception:
            rows = []
        existing_codes = set([str(x.get('code')) for x in cur if x.get('code')])
        default_codes = set(list(CHART_OF_ACCOUNTS.keys()))
        added = 0
        for a in rows:
            c = (a.code or '').strip()
            if not c or c in existing_codes or c in default_codes:
                continue
            cur.append({'code': c, 'name': a.name, 'type': (a.type or 'EXPENSE'), 'enabled': bool((overrides.get(c) or {}).get('enabled', True))})
            existing_codes.add(c)
            added += 1
        kv_set('chart_accounts', cur)
        return jsonify({'ok': True, 'added': added, 'total': len(cur)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/chart/merge_rules', methods=['GET'], endpoint='api_chart_merge_rules')
@login_required
def api_chart_merge_rules():
    try:
        rules = kv_get('chart_name_merge', []) or []
        return jsonify({'ok': True, 'items': rules})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/chart/add_merge_rule', methods=['POST'], endpoint='api_chart_add_merge_rule')
@login_required
@csrf.exempt
def api_chart_add_merge_rule():
    try:
        data = request.get_json(force=True) or {}
        target_code = (data.get('target_code') or '').strip()
        patterns_raw = (data.get('patterns') or '').strip()
        acc_type = (data.get('type') or '').strip().upper() if data.get('type') else None
        if not target_code or not patterns_raw:
            return jsonify({'ok': False, 'error': 'missing_fields'}), 400
        patterns = [x.strip() for x in patterns_raw.split(',') if x.strip()]
        rules = kv_get('chart_name_merge', []) or []
        rules.append({'target_code': target_code, 'patterns': patterns, 'type': acc_type})
        kv_set('chart_name_merge', rules)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/ledger/metrics', methods=['GET'], endpoint='api_ledger_metrics')
@login_required
def api_ledger_metrics():
    try:
        month = (request.args.get('month') or '').strip()
        start_dt = None; end_dt = None
        if month:
            y, m = month.split('-'); y = int(y); m = int(m)
            start_dt = date(y, m, 1)
            if m == 12:
                end_dt = date(y+1, 1, 1)
            else:
                end_dt = date(y, m+1, 1)
        from models import JournalLine, JournalEntry
        q = db.session.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        if start_dt and end_dt:
            q = q.filter(JournalEntry.date >= start_dt, JournalEntry.date < end_dt)
        rows = q.all()
        total_adv = float(sum([float(getattr(jl, 'debit', 0) or 0) for jl, _ in rows]) or 0)
        total_ded = float(sum([float(getattr(jl, 'credit', 0) or 0) for jl, _ in rows]) or 0)
        count_entries = len(rows)
        ser = {}
        for jl, je in rows:
            d = getattr(je, 'date', get_saudi_now().date())
            y = int(getattr(d, 'year', get_saudi_now().year))
            m = int(getattr(d, 'month', get_saudi_now().month))
            k = (y, m)
            if k not in ser:
                ser[k] = {'year': y, 'month': m, 'debit_total': 0.0, 'credit_total': 0.0, 'entries_count': 0}
            ser[k]['debit_total'] += float(getattr(jl, 'debit', 0) or 0)
            ser[k]['credit_total'] += float(getattr(jl, 'credit', 0) or 0)
            ser[k]['entries_count'] += 1
        series = list(ser.values())
        series.sort(key=lambda r: (r['year'], r['month']))
        return jsonify({'ok': True, 'deductions_total': total_ded, 'advances_outstanding': total_adv, 'entries_count': count_entries, 'series': series})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/ledger/list', methods=['GET'], endpoint='api_ledger_list')
@login_required
def api_ledger_list():
    try:
        emp_id = request.args.get('emp_id', type=int)
        month = (request.args.get('month') or '').strip()
        acc_type = (request.args.get('type') or '').strip().lower()
        dept = (request.args.get('dept') or '').strip().lower()
        start_dt = None; end_dt = None
        if month:
            y, m = month.split('-'); y = int(y); m = int(m)
            start_dt = date(y, m, 1)
            if m == 12:
                end_dt = date(y+1, 1, 1)
            else:
                end_dt = date(y, m+1, 1)
        from models import JournalLine, JournalEntry
        q = db.session.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        if emp_id:
            q = q.filter(JournalLine.employee_id == emp_id)
        if start_dt and end_dt:
            q = q.filter(JournalEntry.date >= start_dt, JournalEntry.date < end_dt)
        rows = q.order_by(JournalEntry.date.asc(), JournalLine.line_no.asc()).all()
        data = []
        for jl, je in rows:
            item = {
                'employee_id': int(getattr(jl, 'employee_id', 0) or 0),
                'employee_name': '',
                'employee_department': '',
                'date': str(getattr(je, 'date', get_saudi_now().date())),
                'desc': getattr(jl, 'description', '') or '',
                'debit': float(getattr(jl, 'debit', 0) or 0),
                'credit': float(getattr(jl, 'credit', 0) or 0)
            }
            dsc = (item['desc'] or '').lower()
            typ = 'advance' if ('advance' in dsc or 'سلفة' in item['desc']) else ('deduction' if ('deduct' in dsc or 'خصم' in item['desc']) else 'other')
            bal = float(item['debit']) - float(item['credit'])
            st = 'paid' if item['debit']>0 and item['credit']==0 else ('partial' if item['debit']>0 and item['credit']>0 else ('due' if item['credit']>0 and item['debit']==0 else 'posted'))
            item['type'] = typ
            item['balance'] = bal
            item['status'] = st
            data.append(item)
        try:
            emps = {int(e.id): (e.full_name, (e.department or '').strip().lower()) for e in Employee.query.all()}
            for d in data:
                val = emps.get(d['employee_id'])
                if val:
                    d['employee_name'] = val[0]
                    d['employee_department'] = val[1]
        except Exception:
            pass
        if dept and dept not in ('all',):
            data = [d for d in data if (d.get('employee_department','') or '') == dept]
        if acc_type:
            if acc_type == 'advance':
                data = [d for d in data if d.get('type') == 'advance']
            elif acc_type == 'deduction':
                data = [d for d in data if d.get('type') == 'deduction']
        # Fallback aggregation when no journal rows exist for the employee/month
        if (not data) and emp_id:
            try:
                from models import Salary, Payment
                agg = []
                if start_dt and end_dt:
                    y = int(start_dt.year); m = int(start_dt.month)
                    srows = Salary.query.filter_by(employee_id=int(emp_id), year=y, month=m).all()
                else:
                    srows = Salary.query.filter_by(employee_id=int(emp_id)).order_by(Salary.year.desc(), Salary.month.desc()).limit(12).all()
                sal_ids = [int(getattr(s,'id',0) or 0) for s in srows]
                for s in srows:
                    dt = date(int(getattr(s,'year', get_saudi_now().year)), int(getattr(s,'month', get_saudi_now().month)), 1)
                    tot = float(getattr(s,'total_salary',0) or 0)
                    if tot>0:
                        agg.append({'employee_id': int(emp_id), 'employee_name': emps.get(int(emp_id), ('', ''))[0] if 'emps' in locals() else '', 'employee_department': emps.get(int(emp_id), ('',''))[1] if 'emps' in locals() else '', 'date': str(dt), 'desc': 'مرتب مستحق', 'type': 'salary', 'debit': 0.0, 'credit': tot, 'balance': -tot, 'status': 'due'})
                if sal_ids:
                    pays = db.session.query(Payment).filter(Payment.invoice_type=='salary', Payment.invoice_id.in_(sal_ids)).order_by(Payment.payment_date.asc()).all()
                    for p in pays:
                        amt = float(getattr(p,'amount_paid',0) or 0)
                        dval = getattr(p,'payment_date', get_saudi_now())
                        agg.append({'employee_id': int(emp_id), 'employee_name': emps.get(int(emp_id), ('', ''))[0] if 'emps' in locals() else '', 'employee_department': emps.get(int(emp_id), ('',''))[1] if 'emps' in locals() else '', 'date': str(dval.date() if hasattr(dval,'date') else dval), 'desc': 'سداد راتب', 'type': 'payment', 'debit': amt, 'credit': 0.0, 'balance': amt, 'status': 'paid'})
                # Compute running month balances
                agg.sort(key=lambda r: r['date'])
                data = agg
                if acc_type:
                    if acc_type == 'advance':
                        data = [d for d in data if d.get('type') == 'advance']
                    elif acc_type == 'deduction':
                        data = [d for d in data if d.get('type') == 'deduction']
            except Exception:
                pass
        return jsonify({'ok': True, 'rows': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@main.route('/api/ledger/create', methods=['POST'], endpoint='api_ledger_create')
@login_required
def api_ledger_create():
    try:
        from datetime import datetime as _dt
        from models import JournalEntry, JournalLine
        emp_id = request.form.get('employee_id', type=int)
        amount = request.form.get('amount', type=float) or 0.0
        date_s = (request.form.get('date') or get_saudi_now().strftime('%Y-%m-%d'))
        typ = (request.form.get('type') or '').strip().lower()
        method = (request.form.get('method') or 'cash').strip().lower()
        desc = (request.form.get('description') or '').strip() or f'{typ} entry'
        if not emp_id or amount <= 0 or typ not in ('advance','deduction'):
            return jsonify({'ok': False, 'error': 'invalid'}), 400
        dval = _dt.strptime(date_s, '%Y-%m-%d').date()
        cash_acc = _pm_account(method)
        if typ == 'advance':
            emp_adv_acc = _account(*SHORT_TO_NUMERIC['EMP_ADV'])
            je = JournalEntry(entry_number=f"JE-LED-ADV-{emp_id}-{int(amount)}", date=dval, branch_code=None, description=desc, status='posted', total_debit=amount, total_credit=amount, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
            db.session.add(je); db.session.flush()
            if emp_adv_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=emp_adv_acc.id, debit=amount, credit=0.0, description='Employee advance', line_date=dval, employee_id=emp_id))
            if cash_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cash_acc.id, debit=0.0, credit=amount, description='Cash/Bank', line_date=dval, employee_id=emp_id))
        elif typ == 'deduction':
            ded_acc = _account(SHORT_TO_NUMERIC['SAL_DED'][0], CHART_OF_ACCOUNTS.get('5310', {'name':'رواتب وأجور','type':'EXPENSE'}).get('name','رواتب وأجور'), CHART_OF_ACCOUNTS.get('5310', {'name':'رواتب وأجور','type':'EXPENSE'}).get('type','EXPENSE'))
            je = JournalEntry(entry_number=f"JE-LED-DED-{emp_id}-{int(amount)}", date=dval, branch_code=None, description=desc, status='posted', total_debit=amount, total_credit=amount, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
            db.session.add(je); db.session.flush()
            if cash_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=cash_acc.id, debit=amount, credit=0.0, description='Cash/Bank', line_date=dval, employee_id=emp_id))
            if ded_acc:
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ded_acc.id, debit=0.0, credit=amount, description='Salary deduction', line_date=dval, employee_id=emp_id))
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback(); return jsonify({'ok': False, 'error': str(e)}), 400

@main.route('/api/ledger/delete/<int:jeid>', methods=['DELETE'], endpoint='api_ledger_delete')
@login_required
def api_ledger_delete(jeid: int):
    try:
        from models import JournalEntry
        from routes.journal import delete_journal_entry_and_linked_invoice
        je = JournalEntry.query.get_or_404(int(jeid))
        delete_journal_entry_and_linked_invoice(je)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback(); return jsonify({'ok': False, 'error': str(e)}), 400


@main.route('/api/employee/settings2', methods=['GET', 'POST'], endpoint='api_employee_settings2')
@login_required
def api_employee_settings():
    try:
        emp_id = request.args.get('emp_id', type=int) or request.form.get('emp_id', type=int)
        if not emp_id:
            return jsonify({'ok': False, 'error': 'emp_id required'}), 400
        from models import Employee
        emp = Employee.query.get(int(emp_id))
        if not emp:
            return jsonify({'ok': False, 'error': 'employee not found'}), 404
        try:
            from app.models import AppKV
        except Exception:
            AppKV = None
        if request.method == 'GET':
            kv = {}
            if AppKV:
                try:
                    kv = AppKV.get(f"emp_settings:{int(emp.id)}") or {}
                except Exception:
                    kv = {}
            # Compose settings response
            settings = {
                'work_type': (kv.get('salary_type') or 'fixed'),
                'monthly_hours': float(kv.get('monthly_hours') or 0.0),
                'hourly_rate_employee': float(kv.get('hourly_rate') or 0.0),
                'status': (emp.status or 'active'),
                'payment_method': (kv.get('payment_method') or 'cash'),
                'ot_rate': float(kv.get('ot_rate') or 0.0),
                'allow_allowances': bool(kv.get('allow_allowances') or False),
                'allow_bonuses': bool(kv.get('allow_bonuses') or False),
                'show_in_reports': bool(kv.get('show_in_reports') or True),
            }
            return jsonify({'ok': True, 'settings': settings})
        # POST save
        status = (request.form.get('status') or '').strip().lower()
        work_type = (request.form.get('work_type') or '').strip().lower()
        monthly_hours = request.form.get('monthly_hours', type=float)
        hourly_rate = request.form.get('hourly_rate_employee', type=float)
        payment_method = (request.form.get('payment_method') or '').strip().lower()
        ot_rate = request.form.get('ot_rate', type=float)
        allow_allowances = bool(request.form.get('allow_allowances'))
        allow_bonuses = bool(request.form.get('allow_bonuses'))
        show_in_reports = bool(request.form.get('show_in_reports', True))
        # Update employee basic fields
        if status in ('active','inactive'):
            emp.status = status
            emp.active = (status == 'active')
        try:
            db.session.flush()
        except Exception:
            pass
        # Persist KV settings
        if AppKV:
            try:
                cur = AppKV.get(f"emp_settings:{int(emp.id)}") or {}
                if work_type in ('fixed','hourly'):
                    cur['salary_type'] = work_type
                if monthly_hours is not None:
                    cur['monthly_hours'] = float(monthly_hours or 0.0)
                if hourly_rate is not None:
                    cur['hourly_rate'] = float(hourly_rate or 0.0)
                if payment_method:
                    cur['payment_method'] = payment_method
                if ot_rate is not None:
                    cur['ot_rate'] = float(ot_rate or 0.0)
                cur['allow_allowances'] = bool(allow_allowances)
                cur['allow_bonuses'] = bool(allow_bonuses)
                cur['show_in_reports'] = bool(show_in_reports)
                AppKV.set(f"emp_settings:{int(emp.id)}", cur)
            except Exception:
                pass
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'ok': False, 'error': 'save_failed'}), 500
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
def _has_role(user, roles):
    try:
        # Admins and authenticated users allowed in development
        if getattr(user,'username','') == 'admin' or getattr(user,'id',None) == 1:
            return True
        if getattr(user,'is_authenticated', False):
            return True
        return (getattr(user,'role','') or '').lower() in {r.lower() for r in roles}
    except Exception:
        return False
