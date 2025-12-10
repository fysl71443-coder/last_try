from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from models import get_saudi_now
from sqlalchemy import func
from extensions import db
from sqlalchemy.exc import IntegrityError
from models import Account, JournalEntry, JournalLine, SalesInvoice, PurchaseInvoice, ExpenseInvoice, Salary, Payment, LedgerEntry

bp = Blueprint('financials', __name__, url_prefix='/financials')

# CSRF exempt helper (for JSON APIs)
try:
    from app import csrf
except Exception:
    class _CSRF:
        def exempt(self, f):
            return f
    csrf = _CSRF()


def _normalize_short_aliases():
    try:
        from app.routes import SHORT_TO_NUMERIC
    except Exception:
        SHORT_TO_NUMERIC = {}
    try:
        shorts = ['CASH','BANK','AR','AP','VAT_IN','VAT_OUT','VAT_SETTLE','COGS']
        for sc in shorts:
            try:
                src = Account.query.filter(func.lower(Account.code) == sc.lower()).first()
            except Exception:
                src = None
            if not src:
                continue
            tgt_meta = SHORT_TO_NUMERIC.get(sc)
            if not tgt_meta:
                continue
            tgt_code = tgt_meta[0]
            tgt = Account.query.filter(Account.code == tgt_code).first()
            if not tgt:
                tgt = Account(code=tgt_code, name=tgt_meta[1], type=tgt_meta[2])
                db.session.add(tgt); db.session.flush()
            JournalLine.query.filter(JournalLine.account_id == src.id).update({JournalLine.account_id: tgt.id})
            LedgerEntry.query.filter(LedgerEntry.account_id == src.id).update({LedgerEntry.account_id: tgt.id})
            db.session.flush()
            try:
                db.session.delete(src)
            except Exception:
                pass
        num_map = {
            '6100': '2024',
            '6300': '6000',
            '1.1.4.2': '1030',
            '2.1.2.1': '2130',
            '2120': '2050',
            '1010': '1011',
            '1040': '1011',
            '1110': '1012',
            '1050': '1013',
            '1120': '1014',
            '1100': '6200',
            '2060': '6300',
            '5005': '5000',
            '4100': '4011',
            '4110': '4012',
            '4120': '4013',
            '4130': '4014',
            '5160': '5060',
            '5170': '5070',
            '5180': '5080',
            '5190': '5090',
            '5200': '5100',
            '5310': '5010',
            '4030': '5090',
            '4040': '5090',
            '4020': '4013',
            '4023': '4013',
            '2030': '2130'
        }
        for old_code, new_code in num_map.items():
            old = Account.query.filter(Account.code == old_code).first()
            new = Account.query.filter(Account.code == new_code).first()
            if old and new:
                JournalLine.query.filter(JournalLine.account_id == old.id).update({JournalLine.account_id: new.id})
                LedgerEntry.query.filter(LedgerEntry.account_id == old.id).update({LedgerEntry.account_id: new.id})
                db.session.flush()
                try:
                    db.session.delete(old)
                except Exception:
                    pass
        # Name-based merges configured by user
        try:
            from app.routes import kv_get
            rules = kv_get('chart_name_merge', []) or []
            for r in rules:
                tgt_code = (r.get('target_code') or '').strip()
                pats = [p for p in (r.get('patterns') or []) if p]
                ty = (r.get('type') or '').strip().upper() if r.get('type') else None
                if not tgt_code or not pats:
                    continue
                target = Account.query.filter(Account.code == tgt_code).first()
                if not target:
                    # create placeholder under provided type or EXPENSE
                    target = Account(code=tgt_code, name='Merged Account', type=(ty or 'EXPENSE'))
                    db.session.add(target); db.session.flush()
                q = Account.query
                if ty:
                    q = q.filter(Account.type == ty)
                f = None
                for p in pats:
                    cond = Account.name.ilike(f"%{p}%")
                    f = cond if f is None else (f | cond)
                if f is None:
                    continue
                cand = q.filter(f).all()
                for acc in cand:
                    if acc.id == target.id:
                        continue
                    JournalLine.query.filter(JournalLine.account_id == acc.id).update({JournalLine.account_id: target.id})
                    LedgerEntry.query.filter(LedgerEntry.account_id == acc.id).update({LedgerEntry.account_id: target.id})
                    db.session.flush()
                    try:
                        db.session.delete(acc)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            target_salaries_payable = Account.query.filter(Account.code == '2130').first()
            if not target_salaries_payable:
                target_salaries_payable = Account(code='2130', name='الرواتب المستحقة', type='LIABILITY')
                db.session.add(target_salaries_payable); db.session.flush()
            sal_names = ['%رواتب مستحقة%','%الرواتب المستحقة%','%salaries payable%','%payroll payable%']
            q = Account.query
            f = None
            for p in sal_names:
                cond = Account.name.ilike(p)
                f = cond if f is None else (f | cond)
            cand = q.filter(f).all()
            for acc in cand:
                if acc.code == '2130':
                    continue
                JournalLine.query.filter(JournalLine.account_id == acc.id).update({JournalLine.account_id: target_salaries_payable.id})
                LedgerEntry.query.filter(LedgerEntry.account_id == acc.id).update({LedgerEntry.account_id: target_salaries_payable.id})
                db.session.flush()
                try:
                    db.session.delete(acc)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            target_comm = Account.query.filter(Account.code == '5090').first()
            if not target_comm:
                target_comm = Account(code='5090', name='عمولات بنكية', type='EXPENSE')
                db.session.add(target_comm); db.session.flush()
            # Merge accounts named as bank fees/commissions into 5090
            syn_names = ['%عمولات بنكية%', '%مصاريف بنكية%', '%مصروفات بنكية%', '%عمولات بنكية مستلمة%']
            cand = Account.query.filter(
                (Account.name.ilike(syn_names[0])) | (Account.name.ilike(syn_names[1])) | (Account.name.ilike(syn_names[2])) | (Account.name.ilike(syn_names[3]))
            ).all()
            for acc in cand:
                if acc.code == '5090':
                    continue
                JournalLine.query.filter(JournalLine.account_id == acc.id).update({JournalLine.account_id: target_comm.id})
                LedgerEntry.query.filter(LedgerEntry.account_id == acc.id).update({LedgerEntry.account_id: target_comm.id})
                db.session.flush()
                try:
                    db.session.delete(acc)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            target_keeta = Account.query.filter(Account.code == '4013').first()
            if not target_keeta:
                target_keeta = Account(code='4013', name='Keeta Online', type='REVENUE')
                db.session.add(target_keeta); db.session.flush()
            keeta_names = ['%keeta%','%كيتا%','%مبيعات keeta%']
            q = Account.query.filter(Account.type.in_(['REVENUE','OTHER_INCOME']))
            f = None
            for p in keeta_names:
                cond = Account.name.ilike(p)
                f = cond if f is None else (f | cond)
            cand = q.filter(f).all()
            for acc in cand:
                if acc.code == '4013':
                    continue
                JournalLine.query.filter(JournalLine.account_id == acc.id).update({JournalLine.account_id: target_keeta.id})
                LedgerEntry.query.filter(LedgerEntry.account_id == acc.id).update({LedgerEntry.account_id: target_keeta.id})
                db.session.flush()
                try:
                    db.session.delete(acc)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            import re
            def _norm(n):
                s = (n or '').strip().lower()
                s = re.sub(r'[\u064B-\u065F]', '', s)
                s = re.sub(r'\s+', ' ', s)
                s = re.sub(r'[^0-9a-z\u0621-\u064A ]+', '', s)
                return s
            def _num_code(c):
                m = re.sub(r'[^0-9]', '', (c or ''))
                try:
                    return int(m) if m else 0
                except Exception:
                    return 0
            accs = Account.query.all()
            groups = {}
            for a in accs:
                t = (getattr(a, 'type', '') or '').strip().upper()
                nm = _norm(getattr(a, 'name', '') or '')
                if not nm or not t:
                    continue
                k = f"{t}:{nm}"
                arr = groups.get(k) or []
                arr.append(a)
                groups[k] = arr
            try:
                from app.routes import CHART_OF_ACCOUNTS
            except Exception:
                CHART_OF_ACCOUNTS = {}
            for k, arr in groups.items():
                if len(arr) < 2:
                    continue
                pref = None
                for a in arr:
                    if (CHART_OF_ACCOUNTS or {}).get(a.code):
                        pref = a
                        break
                if pref is None:
                    pref = sorted(arr, key=lambda x: _num_code(x.code))[0]
                target = Account.query.filter(Account.id == pref.id).first()
                for acc in arr:
                    if acc.id == target.id:
                        continue
                    JournalLine.query.filter(JournalLine.account_id == acc.id).update({JournalLine.account_id: target.id})
                    LedgerEntry.query.filter(LedgerEntry.account_id == acc.id).update({LedgerEntry.account_id: target.id})
                    db.session.flush()
                    try:
                        db.session.delete(acc)
                    except Exception:
                        pass
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
def period_range(kind: str):
    today = get_saudi_now().date()
    if kind == 'today':
        return today, today
    if kind == 'this_week':
        return today - timedelta(days=today.weekday()), today
    if kind == 'this_month':
        return today.replace(day=1), today
    if kind == 'this_year':
        return today.replace(month=1, day=1), today
    return today.replace(day=1), today


@bp.route('/income_statement')
def income_statement():
    try:
        fn = globals().get('_normalize_short_aliases')
        if fn:
            fn()
    except Exception:
        pass
    period = request.args.get('period', 'custom')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    branch = (request.args.get('branch') or 'all').strip()
    start_date, end_date = period_range(period)
    try:
        if (period or '') == 'custom':
            if start_arg and end_arg:
                start_date = datetime.strptime(start_arg, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_arg, '%Y-%m-%d').date()
            else:
                start_date = datetime(2025,10,1).date()
                end_date = get_saudi_now().date()
    except Exception:
        pass

    try:
        from app.routes import CHART_OF_ACCOUNTS
        keys = list((CHART_OF_ACCOUNTS or {}).keys())
        try:
            existing = {str(code) for (code,) in db.session.query(Account.code).filter(Account.code.in_(keys)).all()}
        except Exception:
            existing = set()
        for code, meta in (CHART_OF_ACCOUNTS or {}).items():
            if str(code) not in existing:
                try:
                    db.session.add(Account(code=code, name=meta.get('name',''), type=meta.get('type','EXPENSE')))
                    db.session.flush()
                except IntegrityError:
                    db.session.rollback()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    # Helper to sum by account type
    def sum_type(acc_type):
        return float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .filter(Account.type == acc_type)
            .filter(JournalLine.line_date.between(start_date, end_date))
            .scalar() or 0)

    # For P&L, revenue accounts are usually credit-nature => use (credit - debit)
    def sum_revenue():
        return float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .filter(Account.type.in_(['REVENUE', 'OTHER_INCOME']))
            .filter(JournalLine.line_date.between(start_date, end_date))
            .scalar() or 0)

    def sum_expense(types):
        return float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .filter(Account.type.in_(types))
            .filter(JournalLine.line_date.between(start_date, end_date))
            .scalar() or 0)

    def sum_cogs():
        q = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)) \
            .join(Account, JournalLine.account_id == Account.id) \
            .filter(JournalLine.line_date.between(start_date, end_date)) \
            .filter(
                (Account.type == 'COGS') |
                (func.lower(Account.code) == 'cogs') |
                (Account.name.ilike('%COGS%')) |
                (Account.name.ilike('%تكلفة%')) |
                (Account.name.ilike('%تكلفة المبيعات%'))
            )
        return float(q.scalar() or 0)

    def inv_balance(code: str, end_dt):
        q = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)) \
            .join(Account, JournalLine.account_id == Account.id) \
            .filter(Account.code == code) \
            .filter(JournalLine.line_date <= end_dt)
        return float(q.scalar() or 0)

    try:
        opening_dt = (start_date - timedelta(days=1))
        inv_codes = ['1210','1025','1070']
        opening_inv = sum(inv_balance(c, opening_dt) for c in inv_codes)
        closing_inv = sum(inv_balance(c, end_date) for c in inv_codes)
    except Exception:
        opening_inv = 0.0
        closing_inv = 0.0

    try:
        purch_q = db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax - PurchaseInvoice.discount_amount), 0)) \
            .filter(PurchaseInvoice.date.between(start_date, end_date))
        if branch in ('china_town','place_india'):
            purch_q = purch_q.filter(PurchaseInvoice.branch == branch)
        purchases_amt = float(purch_q.scalar() or 0)
    except Exception:
        purchases_amt = 0.0

    try:
        waste_q = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)) \
            .join(Account, JournalLine.account_id == Account.id) \
            .filter(Account.code == '1080') \
            .filter(JournalLine.line_date.between(start_date, end_date))
        waste_amt = float(waste_q.scalar() or 0)
    except Exception:
        waste_amt = 0.0

    revenue = sum_revenue()
    cogs_journal = sum_cogs()
    cogs_computed = max(0.0, opening_inv + purchases_amt - closing_inv) + max(0.0, waste_amt)
    cogs = cogs_computed if cogs_computed > 0 else cogs_journal
    operating_expenses = sum_expense(['EXPENSE'])
    other_income = 0.0
    other_expenses = sum_expense(['OTHER_EXPENSE'])
    base_tax_q = db.session.query(func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0)) \
        .join(Account, LedgerEntry.account_id == Account.id) \
        .filter(Account.type == 'TAX') \
        .filter(LedgerEntry.date.between(start_date, end_date))
    vat_tax = float(db.session.query(func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0)) \
        .join(Account, LedgerEntry.account_id == Account.id) \
        .filter(Account.type == 'TAX') \
        .filter(Account.code.in_(['6010','6020'])) \
        .filter(LedgerEntry.date.between(start_date, end_date)).scalar() or 0)
    zakat = 0.0
    tax_total_all = 0.0
    income_tax = 0.0
    tax = 0.0

    

    gross_profit = revenue - cogs
    operating_profit = gross_profit - operating_expenses
    net_profit_before_tax = operating_profit + other_income - other_expenses
    net_profit_after_tax = net_profit_before_tax - tax

    vat_out = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '2024')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    vat_in = float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '6200')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    # Fallback to invoice aggregates if journals missing
    if (vat_out == 0.0) or (vat_in == 0.0):
        try:
            q_sales = db.session.query(func.coalesce(func.sum(SalesInvoice.tax_amount), 0)).filter(SalesInvoice.date.between(start_date, end_date))
            q_purch = db.session.query(func.coalesce(func.sum(PurchaseInvoice.tax_amount), 0)).filter(PurchaseInvoice.date.between(start_date, end_date))
            if branch in ('china_town','place_india'):
                q_sales = q_sales.filter(SalesInvoice.branch == branch)
                q_purch = q_purch.filter(PurchaseInvoice.branch == branch)
            vat_out_fallback = float(q_sales.scalar() or 0)
            vat_in_fallback = float(q_purch.scalar() or 0)
            vat_out = vat_out if vat_out != 0.0 else vat_out_fallback
            vat_in = vat_in if vat_in != 0.0 else vat_in_fallback
        except Exception:
            pass
    vat_net = float(vat_out - vat_in)
    tax = max(vat_net, 0.0)
    net_profit_after_tax = net_profit_before_tax - tax
    rev_ct = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4011')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    rev_pi = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4012')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    rev_keeta = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4013')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    rev_hunger = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4014')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    sales_discount = float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4140')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    pl_types = ['REVENUE','OTHER_INCOME','EXPENSE','OTHER_EXPENSE','COGS','TAX']
    type_totals = {}
    for t in pl_types:
        if t in ['REVENUE','OTHER_INCOME']:
            amt = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
                .join(Account, JournalLine.account_id == Account.id)
                .filter(Account.type == t)
                .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
        else:
            amt = float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
                .join(Account, JournalLine.account_id == Account.id)
                .filter(Account.type == t)
                .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
        type_totals[t] = amt
    data = {
        'period': period, 'start_date': start_date, 'end_date': end_date,
        'revenue': revenue, 'cogs': cogs, 'gross_profit': gross_profit,
        'operating_expenses': operating_expenses, 'operating_profit': operating_profit,
        'other_income': other_income, 'other_expenses': other_expenses,
        'net_profit_before_tax': net_profit_before_tax, 'tax': tax,
        'zakat': zakat, 'income_tax': income_tax,
        'net_profit_after_tax': net_profit_after_tax,
        'vat_out': vat_out, 'vat_in': vat_in, 'vat_net': vat_net,
        'revenue_by_branch': {'China Town': rev_ct, 'Place India': rev_pi, 'Keeta Online': rev_keeta, 'Hunger Online': rev_hunger},
        'type_totals': type_totals,
        'branch': branch
    }
    data['cogs_breakdown'] = {
        'opening': opening_inv,
        'purchases': purchases_amt,
        'closing': closing_inv,
        'waste': waste_amt,
        'computed': cogs_computed,
        'journal': cogs_journal,
        'used': 'computed' if cogs == cogs_computed else 'journal'
    }
    # Branch-level sales & discounts from SalesInvoice for accurate channel totals
    try:
        q_si = db.session.query(SalesInvoice).filter(SalesInvoice.date.between(start_date, end_date))
        if branch in ('china_town','place_india'):
            q_si = q_si.filter(SalesInvoice.branch == branch)
        rows = q_si.all()
        def channel(name: str):
            s = (name or '').lower()
            if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                return 'hunger'
            if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                return 'keeta'
            return 'offline'
        branch_totals = {}
        branch_channels = {}
        for inv in rows:
            br = (getattr(inv, 'branch', '') or '').strip() or 'unknown'
            ch = channel(getattr(inv,'customer_name','') or '')
            bt = branch_totals.setdefault(br, {'gross':0.0,'discount':0.0,'vat':0.0,'net':0.0})
            bt['gross'] += float(inv.total_before_tax or 0)
            bt['discount'] += float(inv.discount_amount or 0)
            bt['vat'] += float(inv.tax_amount or 0)
            bt['net'] += float(inv.total_after_tax_discount or 0)
            bc = branch_channels.setdefault(br, {})
            row = bc.setdefault(ch, {'gross':0.0,'discount':0.0,'vat':0.0,'net':0.0,'count':0})
            row['gross'] += float(inv.total_before_tax or 0)
            row['discount'] += float(inv.discount_amount or 0)
            row['vat'] += float(inv.tax_amount or 0)
            row['net'] += float(inv.total_after_tax_discount or 0)
            row['count'] += 1
        data['branch_totals'] = branch_totals
        data['branch_channels'] = branch_channels
    except Exception:
        data['branch_totals'] = {}
        data['branch_channels'] = {}
    return render_template('financials/income_statement.html', data=data)

@bp.route('/accounts/normalize', methods=['POST','GET'])
def normalize_accounts():
    # Merge short-code accounts (CASH/BANK/AR/AP) into numeric codes and move postings
    moved = []
    errors = []
    from app.routes import SHORT_TO_NUMERIC
    try:
        for short_code in ['CASH','BANK','AR','AP','VAT_IN','VAT_OUT','VAT_SETTLE']:
            try:
                # find short account by code
                src = Account.query.filter(func.lower(Account.code) == short_code.lower()).first()
            except Exception:
                src = None
            if not src:
                continue
            # resolve target numeric code
            tgt_meta = SHORT_TO_NUMERIC.get(short_code)
            if not tgt_meta:
                continue
            tgt_code = tgt_meta[0]
            tgt = Account.query.filter(Account.code == tgt_code).first()
            if not tgt:
                tgt = Account(code=tgt_code, name=tgt_meta[1], type=tgt_meta[2])
                db.session.add(tgt); db.session.flush()
            try:
                # move journal lines
                JournalLine.query.filter(JournalLine.account_id == src.id).update({JournalLine.account_id: tgt.id})
                # move ledger entries
                LedgerEntry.query.filter(LedgerEntry.account_id == src.id).update({LedgerEntry.account_id: tgt.id})
                db.session.flush()
                moved.append(short_code)
                # delete src
                db.session.delete(src)
            except Exception as e:
                errors.append(f"{short_code}:{str(e)}")
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        errors.append(str(e))
    return render_template('financials/accounts.html', data={'moved': moved, 'errors': errors})

@bp.route('/balance_sheet')
def balance_sheet():
    try:
        fn = globals().get('_normalize_short_aliases')
        if fn:
            fn()
    except Exception:
        pass
    _normalize_short_aliases()
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today

    try:
        from app.routes import CHART_OF_ACCOUNTS
        keys = list((CHART_OF_ACCOUNTS or {}).keys())
        try:
            existing = {str(code) for (code,) in db.session.query(Account.code).filter(Account.code.in_(keys)).all()}
        except Exception:
            existing = set()
        for code, meta in (CHART_OF_ACCOUNTS or {}).items():
            if str(code) not in existing:
                try:
                    db.session.add(Account(code=code, name=meta.get('name',''), type=meta.get('type','EXPENSE')))
                    db.session.flush()
                except IntegrityError:
                    db.session.rollback()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .filter((JournalLine.line_date <= asof) | (JournalLine.id.is_(None))) \
     .group_by(Account.id) \
     .order_by(Account.type.asc(), Account.code.asc()).all()
    ca_codes = {
        '1011','1012','1013','1014',
        '1020','1021','1022','1130','1140',
        '1210','1070','1025','1040','1041','1042',
        '6200',
        '1030'
    }
    cl_codes = {
        '2010','2110','2130',
        '2023','2024'
    }
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
    return render_template('financials/balance_sheet.html', data={
        'date': asof,
        'assets': assets, 'liabilities': liabilities, 'equity': equity,
        'current_assets': current_assets, 'noncurrent_assets': noncurrent_assets,
        'current_liabilities': current_liabilities, 'noncurrent_liabilities': noncurrent_liabilities,
        'asset_rows_detail': asset_rows_detail,
        'liability_rows_detail': liability_rows_detail,
        'equity_rows_detail': equity_rows_detail,
        'type_totals': type_totals
    })


@bp.route('/trial_balance')
def trial_balance():
    try:
        fn = globals().get('_normalize_short_aliases')
        if fn:
            fn()
    except Exception:
        pass
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today

    try:
        from app.routes import CHART_OF_ACCOUNTS
        for code, meta in (CHART_OF_ACCOUNTS or {}).items():
            if not Account.query.filter_by(code=code).first():
                db.session.add(Account(code=code, name=meta.get('name',''), type=meta.get('type','EXPENSE')))
        db.session.commit()
    except Exception:
        pass

    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .filter((JournalLine.line_date <= asof) | (JournalLine.id.is_(None))) \
     .group_by(Account.id) \
     .order_by(Account.type.asc(), Account.code.asc()).all()

    hide_codes = {'AR','AP','CASH','BANK','VAT_IN','VAT_OUT','VAT_SETTLE','COGS','1000','2000','3000','4000','5000','6000'}
    rows = [r for r in rows if (r.code not in hide_codes) and not (float(r.debit or 0) == 0.0 and float(r.credit or 0) == 0.0 and (r.code in {'1010','1020'}))]

    total_debit = float(sum([float(r.debit or 0) for r in rows]))
    total_credit = float(sum([float(r.credit or 0) for r in rows]))
    type_totals = {}
    grouped = {}
    order = ['ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE','COGS','TAX']
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        d = float(r.debit or 0); c = float(r.credit or 0)
        if t not in type_totals:
            type_totals[t] = {'debit': 0.0, 'credit': 0.0}
        if t not in grouped:
            grouped[t] = []
        type_totals[t]['debit'] += d
        type_totals[t]['credit'] += c
        grouped[t].append({'code': r.code, 'name': r.name, 'debit': d, 'credit': c})

    return render_template('financials/trial_balance.html', data={
        'date': asof, 'rows': rows, 'total_debit': total_debit, 'total_credit': total_credit,
        'type_totals': type_totals,
        'grouped': grouped,
        'order': order
    })



@bp.route('/print/trial_balance')
def print_trial_balance():
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today

    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).join(JournalLine, JournalLine.account_id == Account.id) \
     .filter(JournalLine.line_date <= asof) \
     .group_by(Account.id) \
     .order_by(Account.code.asc()).all()

    columns = ["Code", "Account", "Debit", "Credit"]
    data = []
    total_debit = 0.0
    total_credit = 0.0
    for r in rows:
        d = float(r.debit or 0)
        c = float(r.credit or 0)
        total_debit += d
        total_credit += c
        data.append({
            "Code": r.code,
            "Account": r.name,
            "Debit": d,
            "Credit": c
        })
    totals = {"Debit": total_debit, "Credit": total_credit}

    from datetime import datetime as _dt
    return render_template(
        'print_report.html',
        report_title="Trial Balance",
        columns=columns,
        data=data,
        totals=totals,
        totals_columns=["Debit", "Credit"],
        totals_colspan=2,
        start_date=asof,
        end_date=asof,
        generated_at=_dt.now().strftime('%Y-%m-%d %H:%M')
    )


@bp.route('/print/income_statement')
def print_income_statement():
    period = request.args.get('period', 'this_month')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    start_date, end_date = period_range(period)
    if period == 'custom' and start_arg and end_arg:
        try:
            start_date = datetime.strptime(start_arg, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_arg, '%Y-%m-%d').date()
        except Exception:
            pass

    # Reuse the same aggregation logic as view
    def sum_revenue():
        return float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .filter(Account.type.in_(['REVENUE', 'OTHER_INCOME']))
            .filter(JournalLine.line_date.between(start_date, end_date))
            .scalar() or 0)

    def sum_expense(types):
        return float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .filter(Account.type.in_(types))
            .filter(JournalLine.line_date.between(start_date, end_date))
            .scalar() or 0)

    revenue = sum_revenue()
    cogs = sum_expense(['COGS'])
    operating_expenses = sum_expense(['EXPENSE'])
    other_income = 0.0
    other_expenses = sum_expense(['OTHER_EXPENSE'])
    tax = sum_expense(['TAX'])

    if revenue == 0 and cogs == 0 and operating_expenses == 0 and other_income == 0 and other_expenses == 0 and tax == 0:
        revenue = float(db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0))
            .filter(SalesInvoice.date.between(start_date, end_date)).scalar() or 0)
        cogs = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax), 0))
            .filter(PurchaseInvoice.date.between(start_date, end_date)).scalar() or 0)
        operating_expenses = float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0))
            .filter(ExpenseInvoice.date.between(start_date, end_date)).scalar() or 0)
        tax = 0.0

    gross_profit = revenue - cogs
    operating_profit = gross_profit - operating_expenses
    net_profit_before_tax = operating_profit + other_income - other_expenses
    net_profit_after_tax = net_profit_before_tax - tax

    columns = ["Line", "Amount"]
    lines = [
        ("Revenue", revenue),
        ("COGS", cogs),
        ("Gross Profit", gross_profit),
        ("Operating Expenses", operating_expenses),
        ("Operating Profit", operating_profit),
        ("Other Income", other_income),
        ("Other Expenses", other_expenses),
        ("Net Profit Before Tax", net_profit_before_tax),
        ("Tax", tax),
        ("Net Profit After Tax", net_profit_after_tax),
    ]
    data = [{"Line": k, "Amount": float(v or 0)} for k, v in lines]

    from datetime import datetime as _dt
    return render_template(
        'print_report.html',
        report_title="Income Statement",
        columns=columns,
        data=data,
        totals={"Amount": float(net_profit_after_tax or 0)},
        totals_columns=["Amount"],
        totals_colspan=1,
        start_date=start_date,
        end_date=end_date,
        generated_at=_dt.now().strftime('%Y-%m-%d %H:%M')
    )

@bp.route('/export/trial_balance')
def export_trial_balance():
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today
    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .filter((JournalLine.line_date <= asof) | (JournalLine.id.is_(None))) \
     .group_by(Account.id) \
     .order_by(Account.code.asc()).all()
    import csv
    from io import StringIO
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(['Code','Account','Debit','Credit'])
    td = 0.0; tc = 0.0
    for r in rows:
        d = float(r.debit or 0); c = float(r.credit or 0);
        td += d; tc += c
        w.writerow([r.code, r.name, f"{d:.2f}", f"{c:.2f}"])
    w.writerow(['TOTAL','','{:.2f}'.format(td), '{:.2f}'.format(tc)])
    from flask import Response
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=trial_balance_{asof}.csv'})

@bp.route('/export/income_statement')
def export_income_statement():
    period = request.args.get('period', 'this_month')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    start_date, end_date = period_range(period)
    if period == 'custom' and start_arg and end_arg:
        try:
            start_date = datetime.strptime(start_arg, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_arg, '%Y-%m-%d').date()
        except Exception:
            pass
    def sum_revenue():
        return float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .filter(Account.type.in_(['REVENUE', 'OTHER_INCOME']))
            .filter(JournalLine.line_date.between(start_date, end_date))
            .scalar() or 0)
    def sum_expense(types):
        return float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .filter(Account.type.in_(types))
            .filter(JournalLine.line_date.between(start_date, end_date))
            .scalar() or 0)
    revenue = sum_revenue(); cogs = sum_expense(['COGS']); operating_expenses = sum_expense(['EXPENSE']); other_income = 0.0; other_expenses = sum_expense(['OTHER_EXPENSE']); tax = sum_expense(['TAX'])
    gross_profit = revenue - cogs
    operating_profit = gross_profit - operating_expenses
    net_profit_before_tax = operating_profit + other_income - other_expenses
    net_profit_after_tax = net_profit_before_tax - tax
    import csv
    from io import StringIO
    buf = StringIO(); w = csv.writer(buf)
    w.writerow(['Line','Amount'])
    w.writerow(['Revenue', f"{revenue:.2f}"]); w.writerow(['COGS', f"{cogs:.2f}"]); w.writerow(['Gross Profit', f"{gross_profit:.2f}"]); w.writerow(['Operating Expenses', f"{operating_expenses:.2f}"]); w.writerow(['Operating Profit', f"{operating_profit:.2f}"]); w.writerow(['Net Profit Before Tax', f"{net_profit_before_tax:.2f}"]); w.writerow(['Tax', f"{tax:.2f}"]); w.writerow(['Net Profit After Tax', f"{net_profit_after_tax:.2f}"])
    from flask import Response
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=income_statement_{start_date}_{end_date}.csv'})


@bp.route('/print/balance_sheet')
def print_balance_sheet():
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today

    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        Account.type.label('type'),
        func.coalesce(func.sum(LedgerEntry.debit), 0).label('debit'),
        func.coalesce(func.sum(LedgerEntry.credit), 0).label('credit'),
    ).join(LedgerEntry, LedgerEntry.account_id == Account.id) \
     .filter(LedgerEntry.date <= asof) \
     .group_by(Account.id) \
     .all()

    ca_codes = {'1000','1010','1011','1012','1013','1014','1020','1021','1022','1025','1030','1130','1140'}
    cl_codes = {'2000','2020','2010','2023','2024'}
    current_assets = 0.0
    noncurrent_assets = 0.0
    current_liabilities = 0.0
    noncurrent_liabilities = 0.0
    for r in rows:
        if r.type == 'ASSET':
            bal = float(r.debit or 0) - float(r.credit or 0)
            if (r.code or '') in ca_codes:
                current_assets += bal
            else:
                noncurrent_assets += bal
        elif r.type == 'LIABILITY':
            bal = float(r.credit or 0) - float(r.debit or 0)
            if (r.code or '') in cl_codes:
                current_liabilities += bal
            else:
                noncurrent_liabilities += bal

    assets = current_assets + noncurrent_assets
    liabilities = current_liabilities + noncurrent_liabilities
    equity = assets - liabilities

    columns = ["Section", "Current", "Non-current", "Total"]
    data = [
        {"Section": "Assets", "Current": current_assets, "Non-current": noncurrent_assets, "Total": assets},
        {"Section": "Liabilities", "Current": current_liabilities, "Non-current": noncurrent_liabilities, "Total": liabilities},
        {"Section": "Equity", "Current": 0.0, "Non-current": 0.0, "Total": equity},
    ]

    from datetime import datetime as _dt
    return render_template(
        'print_report.html',
        report_title="Balance Sheet",
        columns=columns,
        data=data,
        totals=None,
        totals_columns=None,
        totals_colspan=1,
        start_date=asof,
        end_date=asof,
        generated_at=_dt.now().strftime('%Y-%m-%d %H:%M')
    )
@bp.route('/accounts')
def accounts():
    period = request.args.get('period', 'custom')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    today = get_saudi_now().date()
    try:
        start_date = datetime.strptime(start_arg, '%Y-%m-%d').date() if start_arg else datetime(2025,10,1).date()
        end_date = datetime.strptime(end_arg, '%Y-%m-%d').date() if end_arg else today
    except Exception:
        start_date = datetime(2025,10,1).date()
        end_date = today

    rows = db.session.query(
        Account.id.label('id'), Account.code.label('code'), Account.name.label('name'), Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit')
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .filter((JournalLine.line_date.between(start_date, end_date)) | (JournalLine.id.is_(None))) \
     .group_by(Account.id) \
     .order_by(Account.code.asc()).all()

    return render_template('financials/accounts.html', rows=rows, start_date=start_date, end_date=end_date)

@bp.route('/account_statement')
def account_statement():
    code = request.args.get('code')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    today = get_saudi_now().date()
    try:
        start_date = datetime.strptime(start_arg, '%Y-%m-%d').date() if start_arg else datetime(2025,10,1).date()
        end_date = datetime.strptime(end_arg, '%Y-%m-%d').date() if end_arg else today
    except Exception:
        start_date = datetime(2025,10,1).date()
        end_date = today

    acc = Account.query.filter_by(code=code).first()
    if not acc:
        return render_template('financials/account_statement.html', acc=None, entries=[], start_date=start_date, end_date=end_date, opening_balance=0.0)

    entries = db.session.query(JournalLine, JournalEntry.entry_number, JournalEntry.description) \
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
        .filter(JournalLine.account_id == acc.id) \
        .filter(JournalLine.line_date.between(start_date, end_date)) \
        .order_by(JournalLine.line_date.asc(), JournalLine.id.asc()).all()

    opening_debit = float(db.session.query(func.coalesce(func.sum(JournalLine.debit), 0))
        .filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date < start_date).scalar() or 0)
    opening_credit = float(db.session.query(func.coalesce(func.sum(JournalLine.credit), 0))
        .filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date < start_date).scalar() or 0)
    opening_balance = opening_debit - opening_credit if acc.type != 'LIABILITY' else opening_credit - opening_debit

    return render_template('financials/account_statement.html', acc=acc, entries=entries,
                           start_date=start_date, end_date=end_date, opening_balance=opening_balance)
@bp.route('/backfill_journals', methods=['GET','POST'])
def backfill_journals():
    if request.method == 'GET':
        today = get_saudi_now().date()
        return render_template('financials/backfill.html', start_date=datetime(2025,10,1).date(), end_date=today)
    start_arg = request.form.get('start_date')
    end_arg = request.form.get('end_date')
    try:
        start_date = datetime.strptime(start_arg, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_arg, '%Y-%m-%d').date()
    except Exception:
        start_date = datetime(2025,10,1).date()
        end_date = get_saudi_now().date()
    created = 0
    from models import Account
    try:
        from app.routes import SHORT_TO_NUMERIC, CHART_OF_ACCOUNTS
    except Exception:
        SHORT_TO_NUMERIC = {'CASH': ('1110', '', ''), 'BANK': ('1120', '', ''), 'REV_CT': ('4100', '', ''), 'REV_PI': ('4110', '', '')}
        CHART_OF_ACCOUNTS = {}
    def acc_by_code(code):
        a = Account.query.filter_by(code=code).first()
        if not a:
            meta = CHART_OF_ACCOUNTS.get(code, {'name':'','type':'EXPENSE'})
            a = Account(code=code, name=meta.get('name',''), type=meta.get('type','EXPENSE'))
            db.session.add(a); db.session.flush()
        return a
    sales = SalesInvoice.query.filter(SalesInvoice.date.between(start_date, end_date)).all()
    for inv in sales:
        exists = JournalEntry.query.filter(JournalEntry.description.ilike(f"%{inv.invoice_number}%")).first()
        if exists:
            continue
        rev_code = SHORT_TO_NUMERIC['REV_PI'][0] if (inv.branch or '')=='place_india' else SHORT_TO_NUMERIC.get('REV_CT', ('4100',))[0]
        cash_code = SHORT_TO_NUMERIC['BANK'][0] if (inv.payment_method or '').upper() in ('BANK','TRANSFER') else SHORT_TO_NUMERIC['CASH'][0]
        vat_out_code = '2024'
        total_before = float(inv.total_before_tax or 0)
        discount_amt = float(inv.discount_amount or 0)
        tax_amt = float(inv.tax_amount or 0)
        net_rev = max(0.0, total_before - discount_amt)
        total_inc_tax = round(net_rev + tax_amt, 2)
        cash_acc = acc_by_code(cash_code)
        rev_acc = acc_by_code(rev_code)
        vat_out_acc = acc_by_code(vat_out_code)
        je = JournalEntry(entry_number=f"JE-{inv.date.strftime('%Y%m')}-{inv.id:04d}", date=inv.date, branch_code=inv.branch, description=f"Sales {inv.invoice_number}", status='posted', total_debit=total_inc_tax, total_credit=total_inc_tax)
        db.session.add(je); db.session.flush()
        db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=cash_acc.id, debit=total_inc_tax, credit=0, description=f"Receipt {inv.invoice_number}", line_date=inv.date))
        if net_rev > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=rev_acc.id, debit=0, credit=net_rev, description=f"Revenue {inv.invoice_number}", line_date=inv.date))
        if tax_amt > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=vat_out_acc.id, debit=0, credit=tax_amt, description=f"VAT Output {inv.invoice_number}", line_date=inv.date))
        db.session.commit(); created += 1
    purchases = PurchaseInvoice.query.filter(PurchaseInvoice.date.between(start_date, end_date)).all()
    for inv in purchases:
        exists = JournalEntry.query.filter(JournalEntry.description.ilike(f"%{inv.invoice_number}%")).first()
        if exists:
            continue
        exp_acc = acc_by_code('1210')
        vat_in_acc = acc_by_code('6200')
        ap_acc = acc_by_code('2110')
        total_before = float(inv.total_before_tax or 0)
        tax_amt = float(inv.tax_amount or 0)
        total_inc_tax = round(total_before + tax_amt, 2)
        je = JournalEntry(entry_number=f"JE-PUR-{inv.invoice_number}", date=inv.date, branch_code=None, description=f"Purchase {inv.invoice_number}", status='posted', total_debit=total_inc_tax, total_credit=total_inc_tax)
        db.session.add(je); db.session.flush()
        if total_before > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description=f"Purchase", line_date=inv.date))
        if tax_amt > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description=f"VAT Input", line_date=inv.date))
        db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description=f"Accounts Payable", line_date=inv.date))
        db.session.commit(); created += 1
    expenses = ExpenseInvoice.query.filter(ExpenseInvoice.date.between(start_date, end_date)).all()
    for inv in expenses:
        exists = JournalEntry.query.filter(JournalEntry.description.ilike(f"%{inv.invoice_number}%")).first()
        if exists:
            continue
        vat_in_acc = acc_by_code('6200')
        ap_acc = acc_by_code('2110')
        total_before = float(inv.total_before_tax or 0)
        tax_amt = float(inv.tax_amount or 0)
        total_inc_tax = round(total_before + tax_amt, 2)
        je = JournalEntry(entry_number=f"JE-EXP-{inv.invoice_number}", date=inv.date, branch_code=None, description=f"Expense {inv.invoice_number}", status='posted', total_debit=total_inc_tax, total_credit=total_inc_tax)
        db.session.add(je); db.session.flush()
        if total_before > 0:
            exp_acc = acc_by_code('5100')
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description=f"Expense", line_date=inv.date))
        if tax_amt > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description=f"VAT Input", line_date=inv.date))
        db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description=f"Accounts Payable", line_date=inv.date))
        db.session.commit(); created += 1
    return render_template('financials/backfill_result.html', created=created, start_date=start_date, end_date=end_date)
@bp.route('/cash_flow')
def cash_flow():
    from datetime import datetime
    period = request.args.get('period', 'custom')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    start_date, end_date = period_range(period)
    try:
        if (period or '') == 'custom':
            if start_arg and end_arg:
                start_date = datetime.strptime(start_arg, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_arg, '%Y-%m-%d').date()
            else:
                start_date = datetime(2025,10,1).date(); end_date = get_saudi_now().date()
    except Exception:
        pass
    rows = db.session.query(JournalLine).join(Account, JournalLine.account_id == Account.id).filter(Account.code.in_(['1011','1012','1013','1014'])).filter(JournalLine.line_date.between(start_date, end_date)).all()
    inflow = float(sum([float(r.debit or 0) for r in rows]))
    outflow = float(sum([float(r.credit or 0) for r in rows]))
    net = round(inflow - outflow, 2)
    data = {'title': 'Cash Flow', 'start_date': start_date, 'end_date': end_date, 'inflow': inflow, 'outflow': outflow, 'net': net, 'rows': [{'code': r.account.code, 'name': r.account.name, 'debit': float(r.debit or 0), 'credit': float(r.credit or 0), 'date': r.line_date} for r in rows]}
    return render_template('financials/cash_flow.html', data=data)

@bp.route('/accounts_hub')
def accounts_hub():
    return render_template('financials/accounts_hub.html')

@bp.route('/operations')
def operations():
    return render_template('financials/operations.html')

@bp.route('/api/trial_balance_json')
def api_trial_balance_json():
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today
    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        getattr(Account, 'name_ar', Account.name).label('name_ar'),
        getattr(Account, 'name_en', Account.name).label('name_en'),
        Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit')
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .filter((JournalLine.line_date <= asof) | (JournalLine.id.is_(None))) \
     .group_by(Account.id) \
     .order_by(Account.type.asc(), Account.code.asc()).all()
    total_debit = float(sum([float(r.debit or 0) for r in rows]))
    total_credit = float(sum([float(r.credit or 0) for r in rows]))
    grouped = {}
    order = ['ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE','COGS','TAX']
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        d = float(r.debit or 0); c = float(r.credit or 0)
        arr = grouped.get(t) or []
        arr.append({
            'code': r.code,
            'name': r.name,
            'name_ar': getattr(r, 'name_ar', None),
            'name_en': getattr(r, 'name_en', None),
            'debit': d,
            'credit': c,
            'balance': (d-c) if t!='LIABILITY' and t!='EQUITY' else (c-d)
        })
        grouped[t] = arr
    from flask import jsonify
    return jsonify({'ok': True, 'date': str(asof), 'total_debit': total_debit, 'total_credit': total_credit, 'grouped': grouped, 'order': order})

@bp.route('/api/account_ledger_json')
def api_account_ledger_json():
    code = (request.args.get('code') or '').strip()
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    today = get_saudi_now().date()
    try:
        start_date = datetime.strptime(start_arg, '%Y-%m-%d').date() if start_arg else datetime(2025,10,1).date()
        end_date = datetime.strptime(end_arg, '%Y-%m-%d').date() if end_arg else today
    except Exception:
        start_date = datetime(2025,10,1).date()
        end_date = today
    acc = Account.query.filter_by(code=code).first()
    if not acc:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'account_not_found'}), 404
    q = db.session.query(JournalLine, JournalEntry.entry_number) \
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
        .filter(JournalLine.account_id == acc.id) \
        .filter(JournalLine.line_date.between(start_date, end_date)) \
        .order_by(JournalLine.line_date.asc(), JournalLine.id.asc())
    rows = []
    bal = 0.0
    opening_debit = float(db.session.query(func.coalesce(func.sum(JournalLine.debit), 0)).filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date < start_date).scalar() or 0)
    opening_credit = float(db.session.query(func.coalesce(func.sum(JournalLine.credit), 0)).filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date < start_date).scalar() or 0)
    opening_balance = opening_debit - opening_credit if acc.type != 'LIABILITY' else opening_credit - opening_debit
    bal = opening_balance
    for ln, entry_no in q.all():
        d = float(getattr(ln,'debit',0) or 0); c = float(getattr(ln,'credit',0) or 0)
        if acc.type in ('LIABILITY','EQUITY'):
            bal += (c - d)
        else:
            bal += (d - c)
        rows.append({'date': str(getattr(ln,'line_date',None) or ''), 'entry_number': entry_no, 'description': getattr(ln,'description',''), 'debit': d, 'credit': c, 'balance': bal})
    from flask import jsonify
    return jsonify({'ok': True, 'account': {'code': acc.code, 'name': acc.name, 'name_ar': getattr(acc, 'name_ar', acc.name), 'name_en': getattr(acc, 'name_en', acc.name), 'type': acc.type}, 'start_date': str(start_date), 'end_date': str(end_date), 'opening_balance': opening_balance, 'final_balance': bal, 'lines': rows})

@bp.route('/api/accounts/list')
def api_accounts_list():
    rows = Account.query.order_by(Account.code.asc()).all()
    out = []
    for a in rows:
        out.append({'code': a.code, 'name': a.name, 'name_ar': getattr(a,'name_ar', a.name), 'name_en': getattr(a,'name_en', a.name), 'type': a.type, 'active': bool(getattr(a,'active', True))})
    from flask import jsonify
    return jsonify({'ok': True, 'accounts': out})

@bp.route('/api/list_suppliers')
def api_list_suppliers():
    try:
        from models import Supplier
        rows = db.session.query(Supplier).filter(getattr(Supplier, 'active', True) == True).order_by(getattr(Supplier, 'name', 'name').asc()).all()
        out = [{'id': int(getattr(s,'id',0) or 0), 'name': getattr(s,'name','') } for s in rows]
        from flask import jsonify
        return jsonify({'ok': True, 'suppliers': out})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/list_customers')
def api_list_customers():
    try:
        from models import Customer
        rows = db.session.query(Customer).filter(getattr(Customer, 'active', True) == True).order_by(getattr(Customer, 'name', 'name').asc()).all()
        # Ensure platform customers are present
        names = [getattr(c,'name','') for c in rows]
        if not any('keeta' in (n or '').lower() for n in names):
            rows.insert(0, type('Obj', (), {'id': 0, 'name': 'Keeta'})())
        if not any('hunger' in (n or '').lower() for n in names):
            rows.insert(1, type('Obj', (), {'id': 0, 'name': 'HungerStation'})())
        out = [{'id': int(getattr(c,'id',0) or 0), 'name': getattr(c,'name','') } for c in rows]
        from flask import jsonify
        return jsonify({'ok': True, 'customers': out})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/accounts/bilingualize', methods=['POST'])
@csrf.exempt
def api_accounts_bilingualize():
    try:
        import re
        from flask import jsonify
        # Comprehensive bilingual mapping for major accounts
        BMAP = {
            '1011': ('صندوق رئيسي', 'Main Cash'),
            '1012': ('صندوق نقاط البيع', 'POS Cash Drawer'),
            '1013': ('البنك – حساب رئيسي', 'Bank Main'),
            '1014': ('البنك – حساب إضافي', 'Bank Additional'),
            '1020': ('المدينون', 'Accounts Receivable'),
            '1021': ('عملاء المطعم', 'Restaurant Customers'),
            '1022': ('العملاء الإلكترونيين', 'Online Customers'),
            '1031': ('مواد غذائية', 'Food Supplies'),
            '1032': ('مشروبات', 'Beverages'),
            '1033': ('مستلزمات أخرى', 'Other Supplies'),
            '1034': ('مواد وأدوات تشغيل', 'Operating Supplies'),
            '1040': ('مصروفات مدفوعة مسبقاً', 'Prepaid Expenses'),
            '1041': ('إيجار مدفوع مقدماً', 'Prepaid Rent'),
            '1042': ('تأمين مدفوع مقدماً', 'Prepaid Insurance'),
            '1051': ('معدات وتجهيزات المطعم', 'Equipment'),
            '1052': ('أثاث وديكور', 'Furniture'),
            '1053': ('أجهزة كمبيوتر وبرمجيات', 'Computers & Software'),
            '1054': ('قيمة شراء من المالك السابق', 'Previous Owner Purchase'),
            '1080': ('هدر مواد – مراقب', 'Material Waste'),
            '2010': ('الموردون', 'Accounts Payable'),
            '2021': ('الرواتب المستحقة', 'Accrued Salaries'),
            '2023': ('ضريبة القيمة المضافة المستحقة', 'VAT Payable'),
            '2024': ('ضريبة المخرجات', 'Output VAT'),
            '3000': ('حقوق الملكية', 'Equity'),
            '4011': ('الصين تاون', 'China Town'),
            '4012': ('بليس إنديا', 'Place India'),
            '4013': ('كيـتا عبر الإنترنت', 'Keeta Online'),
            '4014': ('هنقرستيشن عبر الإنترنت', 'HungerStation Online'),
            '5000': ('تكلفة المواد الغذائية المباشرة', 'Food Direct Cost'),
            '5010': ('رواتب وأجور الموظفين', 'Salaries & Wages'),
            '5020': ('كهرباء وماء وصيانة', 'Utilities & Maintenance'),
            '5030': ('إيجار', 'Rent'),
            '5040': ('ديزل', 'Diesel'),
            '5050': ('إنترنت', 'Internet'),
            '5060': ('مصروفات مكتبية', 'Office Supplies'),
            '5070': ('مواد تنظيف', 'Cleaning Supplies'),
            '5080': ('غسيل ملابس', 'Laundry'),
            '5090': ('عمولات بنكية', 'Bank Fees'),
            '5100': ('رسوم حكومية', 'Government Fees'),
            '5110': ('تسويق', 'Marketing'),
            '5120': ('مصروفات أخرى', 'Other Expenses'),
            '5150': ('صيانة عامة', 'General Maintenance'),
            '6200': ('ضريبة المدخلات', 'Input VAT'),
            '6300': ('تسوية ضريبة القيمة المضافة', 'VAT Settlement'),
        }
        def split_lang(n):
            s = (n or '').strip()
            if ' / ' in s:
                p = s.split(' / ', 1)
                return p[0].strip(), p[1].strip()
            m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", s)
            if m:
                return (m.group(1) or '').strip(), (m.group(2) or '').strip()
            return None, None
        def is_ar(s):
            return bool(re.search(r"[\u0621-\u064A]", (s or '')))
        updated = 0
        rows = Account.query.all()
        for a in rows:
            code = (a.code or '').strip()
            nm = (a.name or '').strip()
            ar = (getattr(a, 'name_ar', None) or '').strip()
            en = (getattr(a, 'name_en', None) or '').strip()
            if ar and en:
                continue
            # Prefer explicit bilingual map
            if code in BMAP:
                sar, sen = BMAP[code]
            else:
                sar, sen = split_lang(nm)
                if not sar and not sen:
                    if is_ar(nm):
                        sar = nm; sen = ''
                    else:
                        sen = nm; sar = ''
            sar = sar or ar or nm
            sen = sen or en or nm
            try:
                a.name_ar = sar
                a.name_en = sen
            except Exception:
                pass
            updated += 1
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({'ok': True, 'updated': updated})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/accounts/add', methods=['POST'])
def api_accounts_add():
    try:
        from flask_login import current_user
        from app.routes import _has_role
        if not _has_role(current_user, ['admin','accountant']):
            from flask import jsonify
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
    except Exception:
        pass
    code = (request.form.get('code') or request.json.get('code') if request.is_json else None) or ''
    name = (request.form.get('name') or request.json.get('name') if request.is_json else None) or ''
    atype = (request.form.get('type') or request.json.get('type') if request.is_json else None) or 'EXPENSE'
    code = code.strip(); name = name.strip(); atype = atype.strip().upper()
    if not code or not name:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'missing_fields'}), 400
    a = Account.query.filter(Account.code == code).first()
    if a:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'exists'}), 409
    a = Account(code=code, name=name, type=atype)
    db.session.add(a); db.session.commit()
    from flask import jsonify
    return jsonify({'ok': True})

@bp.route('/api/accounts/update', methods=['POST'])
def api_accounts_update():
    try:
        from flask_login import current_user
        from app.routes import _has_role
        if not _has_role(current_user, ['admin','accountant']):
            from flask import jsonify
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
    except Exception:
        pass
    code = (request.form.get('code') or request.json.get('code') if request.is_json else None) or ''
    name = (request.form.get('name') or request.json.get('name') if request.is_json else None) or ''
    atype = (request.form.get('type') or request.json.get('type') if request.is_json else None)
    a = Account.query.filter(Account.code == code.strip()).first()
    if not a:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    if name:
        a.name = name.strip()
    if atype:
        a.type = atype.strip().upper()
    db.session.commit()
    from flask import jsonify
    return jsonify({'ok': True})

@bp.route('/api/accounts/toggle_active', methods=['POST'])
def api_accounts_toggle_active():
    try:
        from flask_login import current_user
        from app.routes import _has_role
        if not _has_role(current_user, ['admin','accountant']):
            from flask import jsonify
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
    except Exception:
        pass
    code = (request.form.get('code') or request.json.get('code') if request.is_json else None) or ''
    a = Account.query.filter(Account.code == code.strip()).first()
    if not a:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    cur = bool(getattr(a,'active', True))
    try:
        setattr(a, 'active', not cur)
        db.session.commit()
    except Exception:
        db.session.rollback()
    from flask import jsonify
    return jsonify({'ok': True, 'active': bool(getattr(a,'active', True))})

@bp.route('/api/accounts/cleanup_duplicates', methods=['POST'])
@csrf.exempt
def api_accounts_cleanup_duplicates():
    try:
        from flask import jsonify
        dry = (request.args.get('dry_run') or request.form.get('dry_run') or '').strip().lower() in ('1','true','yes','on')
        q = Account.query.filter(Account.name.ilike('%مكرر%')).all()
        cleaned = []
        skipped = []
        errors = []
        import re
        def _norm(n: str) -> str:
            s = (n or '').strip().lower()
            s = s.replace('مكرر', '')
            s = re.sub(r'[\u064B-\u065F]', '', s)
            s = re.sub(r'\s+', ' ', s)
            s = re.sub(r'[^0-9a-z\u0621-\u064A ]+', '', s)
            return s.strip()
        all_accounts = Account.query.all()
        by_norm = {}
        for a in all_accounts:
            key = _norm(getattr(a,'name','') or '')
            by_norm.setdefault(key, []).append(a)
        code_map = {
            '5160':'5060','5170':'5070','5180':'5080','5190':'5090','5200':'5100','5310':'5010',
            '4020':'4013','4023':'4013','4030':'5090','4040':'5090',
            '1022':'1020','1220':'1080','1090':'1040','4010':'4011','2130':'2021'
        }
        for dup in q:
            base_key = _norm(getattr(dup,'name','') or '')
            cands = [a for a in (by_norm.get(base_key) or []) if a.id != dup.id]
            target = None
            # Prefer explicit code mapping when available
            try:
                tgt_code = code_map.get((dup.code or '').strip())
                if tgt_code:
                    target = Account.query.filter(Account.code == tgt_code).first() or target
            except Exception:
                pass
            # Prefer same type candidate
            for a in cands:
                if (getattr(a,'type','') or '') == (getattr(dup,'type','') or ''):
                    target = a; break
            # Fallback to first candidate
            if not target and cands:
                target = cands[0]
            if not target:
                skipped.append({'code': dup.code, 'name': dup.name, 'reason': 'no_target'})
                continue
            try:
                if not dry:
                    JournalLine.query.filter(JournalLine.account_id == dup.id).update({JournalLine.account_id: target.id})
                    LedgerEntry.query.filter(LedgerEntry.account_id == dup.id).update({LedgerEntry.account_id: target.id})
                    db.session.flush()
                    try:
                        db.session.delete(dup)
                    except Exception:
                        pass
                    db.session.commit()
                cleaned.append({'from': {'code': dup.code, 'name': dup.name}, 'to': {'code': target.code, 'name': target.name}})
            except Exception as e:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                errors.append({'code': dup.code, 'name': dup.name, 'error': str(e)})

        # Force cleanup by codes as well (even if name does not include "مكرر")
        for old_code, new_code in code_map.items():
            try:
                old = Account.query.filter(Account.code == old_code).first()
                if not old:
                    continue
                target = Account.query.filter(Account.code == new_code).first()
                if not target:
                    # create target if missing
                    try:
                        from app.routes import CHART_OF_ACCOUNTS
                    except Exception:
                        CHART_OF_ACCOUNTS = {}
                    meta = CHART_OF_ACCOUNTS.get(new_code, {'name': new_code, 'type': 'EXPENSE'})
                    target = Account(code=new_code, name=meta.get('name', new_code), type=meta.get('type','EXPENSE'))
                    db.session.add(target); db.session.flush()
                if not dry:
                    JournalLine.query.filter(JournalLine.account_id == old.id).update({JournalLine.account_id: target.id})
                    LedgerEntry.query.filter(LedgerEntry.account_id == old.id).update({LedgerEntry.account_id: target.id})
                    db.session.flush()
                    try:
                        db.session.delete(old)
                    except Exception:
                        pass
                    db.session.commit()
                cleaned.append({'from': {'code': old_code, 'name': getattr(old,'name','')}, 'to': {'code': new_code, 'name': getattr(target,'name','')}})
            except Exception as e:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                errors.append({'code': old_code, 'name': getattr(old,'name','') if 'old' in locals() and old else '', 'error': str(e)})
        return jsonify({'ok': True, 'dry_run': dry, 'duplicates_found': len(q), 'cleaned': cleaned, 'skipped': skipped, 'errors': errors})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/accounts/delete', methods=['POST'])
@csrf.exempt
def api_accounts_delete():
    try:
        from flask import jsonify
        code = (request.json.get('code') if request.is_json else request.form.get('code')) or ''
        target_code = (request.json.get('target_code') if request.is_json else request.form.get('target_code')) or ''
        code = code.strip(); target_code = (target_code or '').strip()
        if not code:
            return jsonify({'ok': False, 'error': 'missing_code'}), 400
        acc = Account.query.filter(Account.code == code).first()
        if not acc:
            return jsonify({'ok': True, 'deleted': False, 'message': 'not_found'})
        if target_code:
            tgt = Account.query.filter(Account.code == target_code).first()
            if not tgt:
                tgt = Account(code=target_code, name=target_code, type='EXPENSE')
                db.session.add(tgt); db.session.flush()
            JournalLine.query.filter(JournalLine.account_id == acc.id).update({JournalLine.account_id: tgt.id})
            LedgerEntry.query.filter(LedgerEntry.account_id == acc.id).update({LedgerEntry.account_id: tgt.id})
            db.session.flush()
        lines_cnt = db.session.query(func.count(JournalLine.id)).filter(JournalLine.account_id == acc.id).scalar() or 0
        led_cnt = db.session.query(func.count(LedgerEntry.id)).filter(LedgerEntry.account_id == acc.id).scalar() or 0
        if int(lines_cnt or 0) > 0 or int(led_cnt or 0) > 0:
            return jsonify({'ok': False, 'error': 'has_postings', 'lines': int(lines_cnt or 0), 'ledgers': int(led_cnt or 0)})
        db.session.delete(acc)
        db.session.commit()
        return jsonify({'ok': True, 'deleted': True})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/accounts/purge', methods=['POST'])
@csrf.exempt
def api_accounts_purge():
    try:
        from flask import jsonify
        jl_count = int(db.session.query(func.count(JournalLine.id)).scalar() or 0)
        le_count = int(db.session.query(func.count(LedgerEntry.id)).scalar() or 0)
        je_count = int(db.session.query(func.count(JournalEntry.id)).scalar() or 0)
        ac_count = int(db.session.query(func.count(Account.id)).scalar() or 0)
        db.session.query(JournalLine).delete()
        db.session.query(LedgerEntry).delete()
        db.session.query(JournalEntry).delete()
        db.session.query(Account).delete()
        db.session.commit()
        return jsonify({'ok': True, 'deleted': {'journal_lines': jl_count, 'ledger_entries': le_count, 'journal_entries': je_count, 'accounts': ac_count}})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/accounts/seed_official', methods=['POST'])
@csrf.exempt
def api_accounts_seed_official():
    try:
        from flask import jsonify
        chart = {
            'ASSET': {
                '1000': ('الأصول', 'Assets'),
                '1010': ('النقدية', 'Cash'),
                '1011': ('صندوق رئيسي', 'Main Cash'),
                '1012': ('درج كاش نقاط البيع', 'POS Cash Drawer'),
                '1013': ('بنك – حساب رئيسي', 'Bank – Main Account'),
                '1014': ('بنك – حساب إضافي', 'Bank – Additional Account'),
                '1020': ('المدينون', 'Accounts Receivable'),
                '1021': ('عملاء المطعم', 'Restaurant Customers'),
                '1022': ('العملاء الإلكترونيون', 'Online Customers'),
                '1025': ('مخزون – مستلزمات أخرى', 'Inventory – Other Supplies'),
                '1030': ('سلف الموظفين المستحقة', 'Employee Advances Receivable'),
                '1031': ('مواد غذائية', 'Food Supplies'),
                '1032': ('مشروبات', 'Beverages'),
                '1033': ('مستلزمات أخرى', 'Other Supplies'),
                '1034': ('أدوات تشغيل', 'Operating Supplies'),
                '1040': ('مصروفات مدفوعة مقدماً', 'Prepaid Expenses'),
                '1041': ('إيجار مدفوع مقدماً', 'Prepaid Rent'),
                '1042': ('تأمين مدفوع مقدماً', 'Prepaid Insurance'),
                '1051': ('معدات وتجهيزات المطعم', 'Equipment'),
                '1052': ('أثاث وديكور', 'Furniture & Decoration'),
                '1053': ('أجهزة كمبيوتر وبرمجيات', 'Computers & Software'),
                '1054': ('قيمة شراء من المالك السابق', 'Previous Owner Purchase Value'),
                '1060': ('أصول ثابتة', 'Fixed Assets'),
                '1070': ('مخزون مواد غذائية', 'Food Inventory'),
                '1080': ('هدر مواد – مراقب', 'Wastage – Supervisor'),
                '1100': ('ضريبة مدخلات (قديم)', 'Input VAT (Legacy)'),
                '1130': ('حسابات التحصيل – Keeta', 'Receivables – Keeta'),
                '1140': ('حسابات التحصيل – HungerStation', 'Receivables – HungerStation'),
                '1210': ('مواد وأدوات تشغيل', 'Operating Materials & Tools'),
                '1310': ('إيجار مدفوع مقدماً', 'Prepaid Rent (احتفظ بالأول فقط)'),
                '1320': ('تأمين مدفوع مقدماً', 'Prepaid Insurance (احتفظ بالأول فقط)'),
                '1510': ('معدات وتجهيزات', 'Equipment (حُذفت النسخة المكررة)'),
                '1520': ('أثاث وديكور', 'Furniture (حُذفت النسخة المكررة)'),
                '1530': ('كمبيوتر وبرمجيات', 'Software & Computers (حُذفت النسخة المكررة)'),
                '1540': ('قيمة شراء المطعم من المالك السابق', 'Restaurant Purchase Value'),
            },
            'LIABILITY': {
                '2000': ('الالتزامات العامة', 'General Liabilities'),
                '2010': ('الموردون', 'Suppliers'),
                '2020': ('التزامات أخرى', 'Other Liabilities'),
                '2023': ('ضريبة القيمة المضافة المستحقة', 'VAT Payable'),
                '2024': ('ضريبة المخرجات', 'Output VAT'),
                '2030': ('الرواتب المستحقة', 'Salaries Payable'),
                '2040': ('سلف الموظفين المستحقة', 'Employee Advance Payable'),
                '2050': ('ضريبة مخرجات', 'Output VAT (مكرر – تم دمجه)'),
                '2060': ('ضريبة المخرجات', 'Output VAT (احتفظ بالأعلى)'),
                '2110': ('الموردون – عام', 'Suppliers – General'),
                '2120': ('ضريبة القيمة المضافة مستحقة', 'VAT Payable'),
                '2130': ('رواتب مستحقة', 'Salaries Payable'),
                '2200': ('التزامات طويلة الأجل', 'Long-Term Liabilities'),
            },
            'EQUITY': {
                '3000': ('حقوق الملكية', 'Equity'),
                '3010': ('رأس المال عند التأسيس', 'Initial Capital'),
                '3020': ('المسحوبات الشخصية', 'Owner Withdrawals'),
                '3030': ('صافي الربح/الخسارة', 'Net Profit or Loss'),
                '3100': ('رأس المال', 'Capital'),
                '3200': ('الأرباح المحتجزة', 'Retained Earnings'),
            },
            'REVENUE': {
                '4000': ('الإيرادات', 'Revenue'),
                '4010': ('مبيعات الفروع الرئيسية', 'Branch Sales'),
                '4011': ('China Town – Sales', 'China Town – Sales'),
                '4012': ('Place India – Sales', 'Place India – Sales'),
                '4013': ('Keeta Online – Sales', 'Keeta Online – Sales'),
                '4014': ('HungerStation Online – Sales', 'HungerStation Online – Sales'),
                '4020': ('مبيعات الفروع الفرعية', 'Sub-Branch Sales'),
                '4021': ('China Town – Sub-Sales', 'China Town – Sub-Sales'),
                '4022': ('Place India – Sub-Sales', 'Place India – Sub-Sales'),
                '4023': ('Keeta – Sub-Sales', 'Keeta – Sub-Sales'),
                '4030': ('عمولات بنكية مستلمة', 'Bank Commissions Received'),
                '4040': ('عمولات بنكية مستلمة', 'Bank Commissions (مكرر – تم دمجه)'),
                '4140': ('خصومات على المبيعات', 'Sales Discounts'),
            },
            'EXPENSE': {
                '5010': ('رواتب الموظفين', 'Salaries & Wages'),
                '5020': ('كهرباء وماء وصيانة', 'Utilities & Maintenance'),
                '5030': ('إيجار', 'Rent'),
                '5040': ('ديزل', 'Diesel'),
                '5050': ('إنترنت', 'Internet'),
                '5060': ('أدوات مكتبية', 'Office Supplies'),
                '5070': ('مواد تنظيف', 'Cleaning Supplies'),
                '5080': ('غسيل ملابس', 'Laundry Expense'),
                '5090': ('عمولات بنكية', 'Bank Charges'),
                '5100': ('رسوم حكومية', 'Government Fees'),
                '5110': ('تسويق', 'Marketing'),
                '5120': ('مصاريف حكومية', 'Government Expenses'),
                '5130': ('مصروفات أخرى', 'Other Expenses'),
                '5140': ('مصروفات غير تشغيلية', 'Non-Operating Expenses'),
                '5150': ('صيانة عامة', 'General Maintenance'),
                '5310': ('مصروف رواتب', 'Salary Expense'),
                '5320': ('سلف موظفين (مصروف)', 'Employee Loans Expense'),
                '5330': ('تسوية سلف رواتب', 'Payroll Advance Settlements'),
            },
            'COGS': {
                '5000': ('تكلفة المواد الغذائية المباشرة', 'Direct Food Cost'),
                '5005': ('تكلفة المواد الغذائية', 'Food Cost'),
            },
            'TAX': {
                '6000': ('تسوية ضريبة المدخلات والمخرجات', 'VAT Settlement'),
                '6200': ('ضريبة المدخلات', 'Input VAT'),
                '6300': ('ضريبة القيمة المضافة', 'VAT Adjustment'),
            }
        }
        created = []
        for t, codes in chart.items():
            for code, (ar, en) in codes.items():
                a = Account.query.filter(Account.code == code).first()
                if a:
                    continue
                nm = f"{ar} / {en}".strip()
                a = Account(code=code.strip(), name=nm, type=t.strip())
                try:
                    setattr(a, 'name_ar', ar)
                    setattr(a, 'name_en', en)
                except Exception:
                    pass
                db.session.add(a)
                created.append(code)
        if created:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                from flask import jsonify
                return jsonify({'ok': False, 'error': 'commit_failed', 'created': created}), 500
        return jsonify({'ok': True, 'created_count': len(created), 'created': created})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/accounts/apply_official_names', methods=['POST'])
@csrf.exempt
def api_accounts_apply_official_names():
    try:
        from flask import jsonify
        OFFICIAL = {
            'ASSET': {
                '1000': 'الأصول / Assets',
                '1010': 'النقدية / Cash',
                '1011': 'صندوق رئيسي / Main Cash',
                '1012': 'درج كاش نقاط البيع / POS Cash Drawer',
                '1013': 'بنك – حساب رئيسي / Bank – Main Account',
                '1014': 'بنك – حساب إضافي / Bank – Additional Account',
                '1020': 'المدينون / Accounts Receivable',
                '1021': 'عملاء المطعم / Restaurant Customers',
                '1022': 'العملاء الإلكترونيون / Online Customers',
                '1025': 'مخزون – مستلزمات أخرى / Inventory – Other Supplies',
                '1030': 'سلف الموظفين المستحقة / Employee Advances Receivable',
                '1031': 'مواد غذائية / Food Supplies',
                '1032': 'مشروبات / Beverages',
                '1033': 'مستلزمات أخرى / Other Supplies',
                '1034': 'أدوات تشغيل / Operating Supplies',
                '1040': 'مصروفات مدفوعة مقدماً / Prepaid Expenses',
                '1041': 'إيجار مدفوع مقدماً / Prepaid Rent',
                '1042': 'تأمين مدفوع مقدماً / Prepaid Insurance',
                '1051': 'معدات وتجهيزات المطعم / Equipment',
                '1052': 'أثاث وديكور / Furniture & Decoration',
                '1053': 'أجهزة كمبيوتر وبرمجيات / Computers & Software',
                '1054': 'قيمة شراء من المالك السابق / Previous Owner Purchase Value',
                '1060': 'أصول ثابتة / Fixed Assets',
                '1070': 'مخزون مواد غذائية / Food Inventory',
                '1080': 'هدر مواد – مراقب / Wastage – Supervisor',
                '1100': 'ضريبة مدخلات (قديم) / Input VAT (Legacy)',
                '1130': 'حسابات التحصيل – Keeta / Receivables – Keeta',
                '1140': 'حسابات التحصيل – HungerStation / Receivables – HungerStation',
                '1210': 'مواد وأدوات تشغيل / Operating Materials & Tools',
                '1310': 'إيجار مدفوع مقدماً / Prepaid Rent (احتفظ بالأول فقط)',
                '1320': 'تأمين مدفوع مقدماً / Prepaid Insurance (احتفظ بالأول فقط)',
                '1510': 'معدات وتجهيزات / Equipment (حُذفت النسخة المكررة)',
                '1520': 'أثاث وديكور / Furniture (حُذفت النسخة المكررة)',
                '1530': 'كمبيوتر وبرمجيات / Software & Computers (حُذفت النسخة المكررة)',
                '1540': 'قيمة شراء المطعم من المالك السابق / Restaurant Purchase Value',
            },
            'LIABILITY': {
                '2000': 'الالتزامات العامة / General Liabilities',
                '2010': 'الموردون / Suppliers',
                '2020': 'التزامات أخرى / Other Liabilities',
                '2023': 'ضريبة القيمة المضافة المستحقة / VAT Payable',
                '2024': 'ضريبة المخرجات / Output VAT',
                '2030': 'الرواتب المستحقة / Salaries Payable',
                '2040': 'سلف الموظفين المستحقة / Employee Advance Payable',
                '2050': 'ضريبة مخرجات / Output VAT (مكرر – تم دمجه)',
                '2060': 'ضريبة المخرجات / Output VAT (احتفظ بالأعلى)',
                '2110': 'الموردون – عام / Suppliers – General',
                '2120': 'ضريبة القيمة المضافة مستحقة / VAT Payable',
                '2130': 'رواتب مستحقة / Salaries Payable',
                '2200': 'التزامات طويلة الأجل / Long-Term Liabilities',
            },
            'EQUITY': {
                '3000': 'حقوق الملكية / Equity',
                '3010': 'رأس المال عند التأسيس / Initial Capital',
                '3020': 'المسحوبات الشخصية / Owner Withdrawals',
                '3030': 'صافي الربح/الخسارة / Net Profit or Loss',
                '3100': 'رأس المال / Capital',
                '3200': 'الأرباح المحتجزة / Retained Earnings',
            },
            'REVENUE': {
                '4000': 'الإيرادات / Revenue',
                '4010': 'مبيعات الفروع الرئيسية / Branch Sales',
                '4011': 'China Town – Sales',
                '4012': 'Place India – Sales',
                '4013': 'Keeta Online – Sales',
                '4014': 'HungerStation Online – Sales',
                '4020': 'مبيعات الفروع الفرعية / Sub-Branch Sales',
                '4021': 'China Town – Sub-Sales',
                '4022': 'Place India – Sub-Sales',
                '4023': 'Keeta – Sub-Sales',
                '4030': 'عمولات بنكية مستلمة / Bank Commissions Received',
                '4040': 'عمولات بنكية مستلمة / Bank Commissions (مكرر – تم دمجه)',
                '4140': 'خصومات على المبيعات / Sales Discounts',
            },
            'EXPENSE': {
                '5000': 'تكلفة المواد الغذائية المباشرة / Direct Food Cost',
                '5005': 'تكلفة المواد الغذائية / Food Cost',
                '5010': 'رواتب الموظفين / Salaries & Wages',
                '5020': 'كهرباء وماء وصيانة / Utilities & Maintenance',
                '5030': 'إيجار / Rent',
                '5040': 'ديزل / Diesel',
                '5050': 'إنترنت / Internet',
                '5060': 'أدوات مكتبية / Office Supplies',
                '5070': 'مواد تنظيف / Cleaning Supplies',
                '5080': 'غسيل ملابس / Laundry Expense',
                '5090': 'عمولات بنكية / Bank Charges',
                '5100': 'رسوم حكومية / Government Fees',
                '5110': 'تسويق / Marketing',
                '5120': 'مصاريف حكومية / Government Expenses',
                '5130': 'مصروفات أخرى / Other Expenses',
                '5140': 'مصروفات غير تشغيلية / Non-Operating Expenses',
                '5150': 'صيانة عامة / General Maintenance',
                '5310': 'مصروف رواتب / Salary Expense',
                '5320': 'سلف موظفين (مصروف) / Employee Loans Expense',
                '5330': 'تسوية سلف رواتب / Payroll Advance Settlements',
            },
            'TAX': {
                '6000': 'تسوية ضريبة المدخلات والمخرجات / VAT Settlement',
                '6200': 'ضريبة المدخلات / Input VAT',
                '6300': 'ضريبة القيمة المضافة / VAT Adjustment',
            }
        }
        updated = []
        for t, codes in OFFICIAL.items():
            for code, nm in codes.items():
                a = Account.query.filter(Account.code == code).first()
                if not a:
                    continue
                a.name = nm
                a.type = t
                try:
                    parts = (nm or '').split(' / ', 1)
                    if len(parts) == 2:
                        setattr(a, 'name_ar', parts[0].strip())
                        setattr(a, 'name_en', parts[1].strip())
                except Exception:
                    pass
                updated.append(code)
        if updated:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return jsonify({'ok': False, 'error': 'commit_failed', 'updated': updated}), 500
        return jsonify({'ok': True, 'updated_count': len(updated), 'updated': updated})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/batch')
def batch_transactions():
    return render_template('financials/batch.html')

def _resolve_method(pm: str):
    s = (pm or '').strip().upper()
    if s in ('BANK','TRANSFER','CARD','VISA','MASTERCARD','POS','WALLET'):
        return '1013'
    return '1011'

def _resolve_expense(desc: str):
    s = (desc or '').strip().lower()
    if ('كهرب' in s) or ('electric' in s) or ('power' in s):
        return '5020'
    if ('ماء' in s) or ('water' in s):
        return '5020'
    if ('صيانة' in s) or ('maint' in s):
        return '5150'
    if ('ايجار' in s) or ('rent' in s):
        return '5030'
    if ('انترنت' in s) or ('net' in s) or ('wifi' in s):
        return '5050'
    if ('مكتب' in s) or ('office' in s):
        return '5060'
    if ('تنظيف' in s) or ('clean' in s):
        return '5070'
    if ('غسيل' in s) or ('laundry' in s):
        return '5080'
    if ('عمول' in s) or ('fee' in s) or ('commission' in s):
        return '5090'
    if ('حكومي' in s) or ('gov' in s):
        return '5100'
    return '5120'

@bp.route('/api/batch/generate', methods=['POST'])
@csrf.exempt
def api_batch_generate():
    try:
        from flask import jsonify
        payload = request.get_json(force=True, silent=True) or {}
        rows = payload.get('rows') or []
        date_s = (payload.get('date') or '').strip()
        from datetime import datetime as _dt
        try:
            dval = _dt.strptime(date_s, '%Y-%m-%d').date() if date_s else get_saudi_now().date()
        except Exception:
            dval = get_saudi_now().date()
        entries = []
        for r in rows:
            typ = (r.get('type') or '').strip().lower()
            party = (r.get('party') or '').strip()
            amt = float(r.get('amount') or 0)
            method = (r.get('method') or '').strip()
            desc = (r.get('description') or '').strip()
            cat = (r.get('category') or '').strip().lower()
            if amt <= 0:
                continue
            cash_code = _resolve_method(method)
            if typ in ('supplier_payment','دفعة لمورد','supplier'):
                lines = [
                    {'account_code': '2010', 'debit': amt, 'credit': 0.0, 'description': f"Pay Supplier {party} {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            elif typ in ('customer_receipt','استلام من عميل','customer'):
                lines = [
                    {'account_code': cash_code, 'debit': amt, 'credit': 0.0, 'description': f"Receive Customer {party} {desc}", 'date': str(dval)},
                    {'account_code': '1020', 'debit': 0.0, 'credit': amt, 'description': f"Accounts Receivable", 'date': str(dval)}
                ]
            elif typ in ('owner_draw','مسحوبات شخصية','drawings'):
                lines = [
                    {'account_code': '3020', 'debit': amt, 'credit': 0.0, 'description': f"Owner Draw {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            elif typ in ('employee_advance','سلفة موظف','advance'):
                lines = [
                    {'account_code': '1030', 'debit': amt, 'credit': 0.0, 'description': f"Employee Advance {party} {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            elif typ in ('supplier_ap','مورد دائن','add_ap'):
                exp_code = '1210' if cat in ('inventory','stock','مخزون') else '5100'
                lines = [
                    {'account_code': exp_code, 'debit': amt, 'credit': 0.0, 'description': f"Supplier AP {party} {desc}", 'date': str(dval)},
                    {'account_code': '2010', 'debit': 0.0, 'credit': amt, 'description': f"Accounts Payable", 'date': str(dval)}
                ]
            elif typ in ('operating_expense','مصروف تشغيل','expense'):
                exp_code = _resolve_expense(desc)
                lines = [
                    {'account_code': exp_code, 'debit': amt, 'credit': 0.0, 'description': f"Operating Expense {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            elif typ in ('bank_deposit','ايداع بالبنك','deposit'):
                lines = [
                    {'account_code': '1013', 'debit': amt, 'credit': 0.0, 'description': f"Bank Deposit {desc}", 'date': str(dval)},
                    {'account_code': '1011', 'debit': 0.0, 'credit': amt, 'description': f"Cash", 'date': str(dval)}
                ]
            else:
                lines = [
                    {'account_code': '5120', 'debit': amt, 'credit': 0.0, 'description': f"Expense {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            entries.append({'date': str(dval), 'description': desc or typ, 'source_ref_type': 'batch', 'source_ref_id': f"{int(amt*100)}-{typ[:4]}", 'lines': lines})
        created = []
        errors = []
        try:
            from flask import current_app
            data = {'entries': entries}
            import json as _json
            with current_app.test_request_context('/journal/api/transactions/post', method='POST', data=_json.dumps(data), content_type='application/json'):
                try:
                    from routes.journal import api_transactions_post
                    resp = api_transactions_post()
                    j = getattr(resp, 'json', None)
                    if j and j.get('ok'):
                        created.extend(j.get('created') or [])
                    else:
                        errors.append(j.get('error') if j else 'post_failed')
                except Exception as e:
                    errors.append(str(e))
        except Exception as e:
            errors.append(str(e))
        return jsonify({'ok': True, 'created': created, 'errors': errors, 'count': len(entries)})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500
@bp.route('/api/accounts/enforce_official', methods=['POST'])
@csrf.exempt
def api_accounts_enforce_official():
    try:
        from flask import jsonify
        try:
            from app.routes import CHART_OF_ACCOUNTS
        except Exception:
            CHART_OF_ACCOUNTS = {}
        official_codes = {str(k).strip() for k in (CHART_OF_ACCOUNTS or {}).keys()}
        rows = Account.query.all()
        deactivated = []
        kept = []
        for a in rows:
            code = (a.code or '').strip()
            if code in official_codes:
                kept.append(code)
                try:
                    setattr(a, 'active', True)
                except Exception:
                    pass
            else:
                try:
                    setattr(a, 'active', False)
                except Exception:
                    pass
                deactivated.append(code)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({'ok': True, 'kept_count': len(kept), 'deactivated_count': len(deactivated), 'deactivated': deactivated})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/integrity_check', methods=['GET'])
def api_integrity_check():
    try:
        from flask import jsonify
        try:
            from app.routes import CHART_OF_ACCOUNTS
        except Exception:
            CHART_OF_ACCOUNTS = {}
        official_codes = {str(k).strip() for k in (CHART_OF_ACCOUNTS or {}).keys()}
        acc_rows = Account.query.all()
        invalid_accounts = [ (a.code or '') for a in acc_rows if (a.code or '').strip() not in official_codes ]
        bilingual_ok = 0
        bilingual_missing = []
        for a in acc_rows:
            ar = (getattr(a,'name_ar',None) or '').strip()
            en = (getattr(a,'name_en',None) or '').strip()
            if ar and en:
                bilingual_ok += 1
            else:
                bilingual_missing.append(a.code)
        from sqlalchemy import func
        lines_total = int(db.session.query(func.count(JournalLine.id)).scalar() or 0)
        # Lines with account not in official set
        bad_lines = []
        try:
            q = db.session.query(JournalLine, Account).join(Account, JournalLine.account_id == Account.id)
            for ln, a in q.all():
                code = (a.code or '').strip()
                if code not in official_codes:
                    bad_lines.append(int(getattr(ln,'id',0) or 0))
        except Exception:
            pass
        # Trial balance totals
        today = get_saudi_now().date()
        tb_q = db.session.query(
            Account.type.label('type'),
            func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
            func.coalesce(func.sum(JournalLine.credit), 0).label('credit')
        ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
         .filter((JournalLine.line_date <= today) | (JournalLine.id.is_(None))) \
         .group_by(Account.type).all()
        total_debit = float(sum([float(r.debit or 0) for r in tb_q]))
        total_credit = float(sum([float(r.credit or 0) for r in tb_q]))
        balanced = abs(total_debit - total_credit) < 0.005
        return jsonify({
            'ok': True,
            'official_codes_count': len(official_codes),
            'accounts_total': len(acc_rows),
            'invalid_accounts': invalid_accounts,
            'invalid_accounts_count': len(invalid_accounts),
            'journal_lines_total': lines_total,
            'journal_lines_bad_code_count': len(bad_lines),
            'balanced': balanced,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'bilingual_ok_count': bilingual_ok,
            'bilingual_missing': bilingual_missing
        })
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500
