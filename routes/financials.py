from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from models import get_saudi_now
from sqlalchemy import func, or_, and_
from extensions import db
from sqlalchemy.exc import IntegrityError
from models import Account, JournalEntry, JournalLine, SalesInvoice, PurchaseInvoice, ExpenseInvoice, Salary, Payment, LedgerEntry, Settings, Employee

bp = Blueprint('financials', __name__, url_prefix='/financials')

# CSRF exempt helper (for JSON APIs)
try:
    from app import csrf
except Exception:
    class _CSRF:
        def exempt(self, f):
            return f
    csrf = _CSRF()


def _new_coa_codes():
    """رموز الشجرة الجديدة فقط – للتصفية في ميزان المراجعة وغيره. لا يُرجع أبداً قائمة فارغة."""
    try:
        from data.coa_new_tree import build_coa_dict
        return list(build_coa_dict().keys())
    except Exception:
        try:
            from data.coa_new_tree import NEW_COA_TREE
            return [r[0] for r in NEW_COA_TREE]
        except Exception:
            return []


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
            target_salaries_payable = Account.query.filter(Account.code == '2121').first()
            if not target_salaries_payable:
                target_salaries_payable = Account(code='2121', name='رواتب مستحقة', type='LIABILITY')
                db.session.add(target_salaries_payable); db.session.flush()
            sal_names = ['%رواتب مستحقة%','%الرواتب المستحقة%','%salaries payable%','%payroll payable%']
            q = Account.query
            f = None
            for p in sal_names:
                cond = Account.name.ilike(p)
                f = cond if f is None else (f | cond)
            cand = q.filter(f).all()
            for acc in cand:
                if acc.code == '2121':
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


# P&L account groups (COA-aligned)
_COGS_CODES = ['5110', '5120', '5130', '5140', '5150']
_OPEX_CODES = [
    '5210', '5220', '5230', '5240', '5250', '5260', '5270', '5280',
    '5310', '5320', '5330', '5340', '5350', '5360',
    '5410', '5420', '5430', '5440', '5450', '5460', '5470',
    '5510', '5520', '5530', '5540', '5610', '5620', '5630',
]
_OTHER_EXP_CODES = ['5710', '5720', '5730', '5810', '5820']
_REV_OP_CODES = ['4111', '4112', '4120']
_OTHER_REV_CODES = ['4210', '4211', '4212', '4310']


def _jl_sum_codes(codes, credit_minus_debit, start_date, end_date, branch):
    """Sum JournalLine by account codes (posted only). credit_minus_debit=True for revenue."""
    q = db.session.query(
        func.coalesce(
            func.sum(JournalLine.credit - JournalLine.debit if credit_minus_debit else JournalLine.debit - JournalLine.credit),
            0
        )
    ).join(Account, JournalLine.account_id == Account.id).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(
        Account.code.in_(codes),
        JournalLine.line_date.between(start_date, end_date),
        JournalEntry.status == 'posted',
    )
    if branch and branch != 'all' and branch in ('china_town', 'place_india'):
        q = q.filter(JournalEntry.branch_code == branch)
    return float(q.scalar() or 0)


def _jl_sum_by_code(codes, credit_minus_debit, start_date, end_date, branch):
    """Per-account sums (posted only). Returns list of (code, name, amount)."""
    q = (
        db.session.query(
            Account.code,
            Account.name,
            func.coalesce(
                func.sum(JournalLine.credit - JournalLine.debit if credit_minus_debit else JournalLine.debit - JournalLine.credit),
                0,
            ).label('amt'),
        )
        .join(Account, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        .filter(Account.code.in_(codes), JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted')
    )
    if branch and branch != 'all' and branch in ('china_town', 'place_india'):
        q = q.filter(JournalEntry.branch_code == branch)
    rows = q.group_by(Account.id).all()
    return [(r.code, r.name or '', float(r.amt or 0)) for r in rows]


@bp.route('/income_statement')
def income_statement():
    period = request.args.get('period', 'this_month')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    branch = (request.args.get('branch') or 'all').strip()
    detail = request.args.get('detail', '0').strip() in ('1', 'true', 'on', 'yes')
    start_date, end_date = period_range(period)
    try:
        if (period or '') == 'custom':
            if start_arg and end_arg:
                start_date = datetime.strptime(start_arg, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_arg, '%Y-%m-%d').date()
            else:
                start_date = datetime(2025, 10, 1).date()
                end_date = get_saudi_now().date()
    except Exception:
        pass

    # ---------- P&L from journals (COA-based), branch-aware ----------
    rev_op = _jl_sum_codes(_REV_OP_CODES, True, start_date, end_date, branch)
    other_rev = _jl_sum_codes(_OTHER_REV_CODES, True, start_date, end_date, branch)
    revenue_total = rev_op + other_rev

    cogs_j = _jl_sum_codes(_COGS_CODES, False, start_date, end_date, branch)
    cogs_lines = _jl_sum_by_code(_COGS_CODES, False, start_date, end_date, branch)

    def inv_balance(code, end_dt):
        q = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).join(
            Account, JournalLine.account_id == Account.id
        ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(
            Account.code == code, JournalLine.line_date <= end_dt, JournalEntry.status == 'posted'
        )
        return float(q.scalar() or 0)

    try:
        opening_dt = start_date - timedelta(days=1)
        inv_codes = ['1161', '1162', '1163']
        opening_inv = sum(inv_balance(c, opening_dt) for c in inv_codes)
        closing_inv = sum(inv_balance(c, end_date) for c in inv_codes)
    except Exception:
        opening_inv = closing_inv = 0.0

    try:
        purch_q = db.session.query(
            func.coalesce(func.sum(PurchaseInvoice.total_before_tax - PurchaseInvoice.discount_amount), 0)
        ).filter(PurchaseInvoice.date.between(start_date, end_date))
        if branch in ('china_town', 'place_india'):
            purch_q = purch_q.filter(PurchaseInvoice.branch == branch)
        purchases_amt = float(purch_q.scalar() or 0)
    except Exception:
        purchases_amt = 0.0

    waste_amt = 0.0

    cogs_computed = max(0.0, opening_inv + purchases_amt - closing_inv) + max(0.0, waste_amt)
    cogs = cogs_computed if cogs_computed > 0 else cogs_j
    cogs_total = cogs

    opex_total = _jl_sum_codes(_OPEX_CODES, False, start_date, end_date, branch)
    opex_lines = _jl_sum_by_code(_OPEX_CODES, False, start_date, end_date, branch)

    other_exp = _jl_sum_codes(_OTHER_EXP_CODES, False, start_date, end_date, branch)

    gross_profit = revenue_total - cogs_total
    operating_profit = gross_profit - opex_total
    net_before_other = operating_profit + other_rev - other_exp

    vat_out = float(
        db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        .filter(Account.code == '2141', JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted')
        .scalar() or 0
    )
    vat_in = float(
        db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        .filter(Account.code == '1170', JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted')
        .scalar() or 0
    )
    if branch in ('china_town', 'place_india'):
        voq = db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0)).join(
            Account, JournalLine.account_id == Account.id
        ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(
            Account.code == '2141', JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted', JournalEntry.branch_code == branch
        ).scalar() or 0
        viq = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).join(
            Account, JournalLine.account_id == Account.id
        ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(
            Account.code == '1170', JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted', JournalEntry.branch_code == branch
        ).scalar() or 0
        vat_out = float(voq)
        vat_in = float(viq)
    if vat_out == 0 or vat_in == 0:
        try:
            qs = db.session.query(func.coalesce(func.sum(SalesInvoice.tax_amount), 0)).filter(
                SalesInvoice.date.between(start_date, end_date)
            )
            qp = db.session.query(func.coalesce(func.sum(PurchaseInvoice.tax_amount), 0)).filter(
                PurchaseInvoice.date.between(start_date, end_date)
            )
            if branch in ('china_town', 'place_india'):
                qs = qs.filter(SalesInvoice.branch == branch)
                qp = qp.filter(PurchaseInvoice.branch == branch)
            vat_out = vat_out or float(qs.scalar() or 0)
            vat_in = vat_in or float(qp.scalar() or 0)
        except Exception:
            pass
    vat_net = vat_out - vat_in
    tax = max(vat_net, 0.0)
    net_profit_after_tax = net_before_other - tax

    rev_detail = _jl_sum_by_code(_REV_OP_CODES, True, start_date, end_date, branch)
    other_rev_lines = _jl_sum_by_code(_OTHER_REV_CODES, True, start_date, end_date, branch)
    other_exp_lines = _jl_sum_by_code(_OTHER_EXP_CODES, False, start_date, end_date, branch)

    cogs_breakdown = {
        'opening': opening_inv,
        'purchases': purchases_amt,
        'closing': closing_inv,
        'waste': waste_amt,
        'computed': cogs_computed,
        'journal': cogs_j,
        'used': 'computed' if cogs == cogs_computed else 'journal',
    }

    branch_totals = {}
    branch_channels = {}
    try:
        q_si = db.session.query(SalesInvoice).filter(SalesInvoice.date.between(start_date, end_date))
        if branch in ('china_town', 'place_india'):
            q_si = q_si.filter(SalesInvoice.branch == branch)
        for inv in q_si.all():
            br = (getattr(inv, 'branch', '') or '').strip() or 'unknown'
            s = (getattr(inv, 'customer_name', '') or '').lower()
            ch = 'hunger' if any(x in s for x in ('hunger', 'هنقر', 'هونقر')) else (
                'keeta' if any(x in s for x in ('keeta', 'كيتا', 'كيت')) else 'offline'
            )
            bt = branch_totals.setdefault(br, {'gross': 0.0, 'discount': 0.0, 'vat': 0.0, 'net': 0.0})
            bt['gross'] += float(inv.total_before_tax or 0)
            bt['discount'] += float(inv.discount_amount or 0)
            bt['vat'] += float(inv.tax_amount or 0)
            bt['net'] += float(inv.total_after_tax_discount or 0)
            bc = branch_channels.setdefault(br, {})
            row = bc.setdefault(ch, {'gross': 0.0, 'discount': 0.0, 'vat': 0.0, 'net': 0.0, 'count': 0})
            row['gross'] += float(inv.total_before_tax or 0)
            row['discount'] += float(inv.discount_amount or 0)
            row['vat'] += float(inv.tax_amount or 0)
            row['net'] += float(inv.total_after_tax_discount or 0)
            row['count'] += 1
    except Exception:
        pass

    data = {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'branch': branch,
        'detail': detail,
        'revenue': revenue_total,
        'cogs': cogs_total,
        'gross_profit': gross_profit,
        'operating_expenses': opex_total,
        'operating_profit': operating_profit,
        'other_income': other_rev,
        'other_expenses': other_exp,
        'net_profit_before_tax': net_before_other,
        'net_profit_after_tax': net_profit_after_tax,
        'tax': tax,
        'vat_out': vat_out,
        'vat_in': vat_in,
        'vat_net': vat_net,
        'cogs_breakdown': cogs_breakdown,
        'cogs_lines': cogs_lines,
        'opex_lines': opex_lines,
        'rev_detail': rev_detail,
        'other_rev_lines': other_rev_lines,
        'other_exp_lines': other_exp_lines,
        'branch_totals': branch_totals,
        'branch_channels': branch_channels,
    }
    if request.args.get('embed'):
        return render_template('financials/income_statement_embed.html', data=data)
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

# Balance sheet: current vs non-current (COA-aligned)
_BS_CURRENT_ASSET_PREFIX = ('11',)  # 1100–1180
_BS_NONCURRENT_ASSET_PREFIX = ('12',)  # 1200+
_BS_CURRENT_LIAB_PREFIX = ('21',)  # 2100–2160
_BS_NONCURRENT_LIAB_PREFIX = ('22',)  # 2200+
_BS_EXCLUDE_CODES = frozenset({'0006', '1000', '2000', '3000'})  # نظامية وجذور – لا تعرض في التفاصيل


def _is_current_asset(code):
    c = (code or '').strip()
    return any(c.startswith(p) for p in _BS_CURRENT_ASSET_PREFIX) and not c.startswith('12')


def _is_current_liab(code):
    c = (code or '').strip()
    return any(c.startswith(p) for p in _BS_CURRENT_LIAB_PREFIX) and not c.startswith('22')


def _bs_has_movement(row):
    b = float(row.get('balance') or 0)
    return abs(b) > 1e-9


def _bs_show_in_detail(row):
    code = (row.get('code') or '').strip()
    if code in _BS_EXCLUDE_CODES:
        return False
    return _bs_has_movement(row)


# Trial balance: movement-only, expandable groups (same exclude as BS)
_TB_EXCLUDE_CODES = _BS_EXCLUDE_CODES


def _tb_has_movement(d, c):
    return abs(float(d or 0)) > 1e-9 or abs(float(c or 0)) > 1e-9


def _tb_show(row, exclude=None):
    code = (getattr(row, 'code', None) or '').strip()
    ex = exclude or _TB_EXCLUDE_CODES
    if code in ex:
        return False
    d = getattr(row, 'debit', None)
    c = getattr(row, 'credit', None)
    return _tb_has_movement(d, c)


@bp.route('/balance_sheet')
def balance_sheet():
    asof_str = request.args.get('date')
    branch = (request.args.get('branch') or 'all').strip()
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today
    new_codes = _new_coa_codes()
    q = (
        db.session.query(
            Account.code.label('code'),
            Account.name.label('name'),
            Account.type.label('type'),
            func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
            func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
        )
        .outerjoin(JournalLine, JournalLine.account_id == Account.id)
        .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted')))
        .filter(Account.code.in_(new_codes))
    )
    rows = q.group_by(Account.id).order_by(Account.type.asc(), Account.code.asc()).all()
    current_assets = 0.0
    noncurrent_assets = 0.0
    current_liabilities = 0.0
    noncurrent_liabilities = 0.0
    asset_rows_detail = []
    liability_rows_detail = []
    equity_rows_detail = []
    for r in rows:
        if r.type == 'ASSET':
            if (r.code or '').strip() == '0006':
                continue
            bal = float(r.debit or 0) - float(r.credit or 0)
            curr = _is_current_asset(r.code)
            if curr:
                current_assets += bal
            else:
                noncurrent_assets += bal
            asset_rows_detail.append({
                'code': r.code, 'name': r.name, 'balance': bal,
                'class': 'Current' if curr else 'Non-current',
            })
        elif r.type == 'LIABILITY':
            bal = float(r.credit or 0) - float(r.debit or 0)
            curr = _is_current_liab(r.code)
            if curr:
                current_liabilities += bal
            else:
                noncurrent_liabilities += bal
            liability_rows_detail.append({
                'code': r.code, 'name': r.name, 'balance': bal,
                'class': 'Current' if curr else 'Non-current',
            })
        elif r.type == 'EQUITY':
            bal = float(r.credit or 0) - float(r.debit or 0)
            equity_rows_detail.append({'code': r.code, 'name': r.name, 'balance': bal})
    assets = current_assets + noncurrent_assets
    liabilities = current_liabilities + noncurrent_liabilities
    equity = assets - liabilities
    type_totals = {}
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        d, c = float(r.debit or 0), float(r.credit or 0)
        if t not in type_totals:
            type_totals[t] = {'debit': 0.0, 'credit': 0.0}
        type_totals[t]['debit'] += d
        type_totals[t]['credit'] += c
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    company_name = (settings.company_name or 'Company').strip() if settings else 'Company'
    branch_label = 'الكل' if not branch or branch == 'all' else ('China Town' if branch == 'china_town' else 'Place India')

    def _filter_movement(lst, class_name=None):
        out = [x for x in lst if _bs_show_in_detail(x)]
        if class_name:
            out = [x for x in out if x.get('class') == class_name]
        return out

    asset_current_active = _filter_movement(asset_rows_detail, 'Current')
    asset_noncurrent_active = _filter_movement(asset_rows_detail, 'Non-current')
    liab_current_active = _filter_movement(liability_rows_detail, 'Current')
    liab_noncurrent_active = _filter_movement(liability_rows_detail, 'Non-current')
    equity_active = [x for x in equity_rows_detail if _bs_show_in_detail(x)]

    n_ca = len(asset_current_active)
    n_nca = len(asset_noncurrent_active)
    n_cl = len(liab_current_active)
    n_ncl = len(liab_noncurrent_active)
    n_eq = len(equity_active)

    logo_url = (getattr(settings, 'logo_url', None) or '').strip() if settings else None
    data = {
        'date': asof,
        'branch': branch,
        'branch_label': branch_label,
        'company_name': company_name,
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'current_assets': current_assets,
        'noncurrent_assets': noncurrent_assets,
        'current_liabilities': current_liabilities,
        'noncurrent_liabilities': noncurrent_liabilities,
        'asset_current_active': asset_current_active,
        'asset_noncurrent_active': asset_noncurrent_active,
        'liab_current_active': liab_current_active,
        'liab_noncurrent_active': liab_noncurrent_active,
        'equity_active': equity_active,
        'type_totals': type_totals,
        'n_asset_current': n_ca,
        'n_asset_noncurrent': n_nca,
        'n_liab_current': n_cl,
        'n_liab_noncurrent': n_ncl,
        'n_equity': n_eq,
    }
    if request.args.get('embed'):
        return render_template('financials/balance_sheet_embed.html', data=data)
    return render_template('financials/balance_sheet.html', data=data, settings=settings, logo_url=logo_url)


@bp.route('/trial_balance')
def trial_balance():
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today
    new_codes = _new_coa_codes()
    q = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted'))) \
     .filter(Account.code.in_(new_codes))
    raw = q.group_by(Account.id).order_by(Account.type.asc(), Account.code.asc()).all()
    rows = [r for r in raw if _tb_show(r)]

    total_debit = float(sum([float(r.debit or 0) for r in rows]))
    total_credit = float(sum([float(r.credit or 0) for r in rows]))
    type_totals = {}
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        if t not in type_totals:
            type_totals[t] = {'debit': 0.0, 'credit': 0.0}
        type_totals[t]['debit'] += float(r.debit or 0)
        type_totals[t]['credit'] += float(r.credit or 0)

    def _row_dict(r):
        return {'code': r.code, 'name': r.name, 'debit': float(r.debit or 0), 'credit': float(r.credit or 0)}

    tb_groups = []
    order = ['ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', 'COGS', 'TAX']
    for t in order:
        accs = [_row_dict(r) for r in rows if (getattr(r, 'type', None) or '').upper() == t]
        if not accs:
            continue
        if t == 'ASSET':
            cur = [a for a in accs if _is_current_asset(a['code'])]
            ncur = [a for a in accs if not _is_current_asset(a['code'])]
            if cur:
                tb_groups.append({
                    'type': t, 'group_name': 'أصول متداولة', 'group_key': 'ASSET_C',
                    'accounts': cur,
                    'debit': sum(a['debit'] for a in cur), 'credit': sum(a['credit'] for a in cur),
                })
            if ncur:
                tb_groups.append({
                    'type': t, 'group_name': 'أصول غير متداولة', 'group_key': 'ASSET_NC',
                    'accounts': ncur,
                    'debit': sum(a['debit'] for a in ncur), 'credit': sum(a['credit'] for a in ncur),
                })
        elif t == 'LIABILITY':
            cur = [a for a in accs if _is_current_liab(a['code'])]
            ncur = [a for a in accs if not _is_current_liab(a['code'])]
            if cur:
                tb_groups.append({
                    'type': t, 'group_name': 'التزامات متداولة', 'group_key': 'LIAB_C',
                    'accounts': cur,
                    'debit': sum(a['debit'] for a in cur), 'credit': sum(a['credit'] for a in cur),
                })
            if ncur:
                tb_groups.append({
                    'type': t, 'group_name': 'التزامات غير متداولة', 'group_key': 'LIAB_NC',
                    'accounts': ncur,
                    'debit': sum(a['debit'] for a in ncur), 'credit': sum(a['credit'] for a in ncur),
                })
        else:
            tb_groups.append({
                'type': t,
                'group_name': {'EQUITY': 'حقوق الملكية', 'REVENUE': 'الإيرادات', 'EXPENSE': 'المصروفات', 'COGS': 'تكلفة المبيعات', 'TAX': 'ضرائب'}.get(t, t),
                'group_key': t,
                'accounts': accs,
                'debit': sum(a['debit'] for a in accs), 'credit': sum(a['credit'] for a in accs),
            })

    try:
        settings = Settings.query.first()
        company_name = (settings.company_name or 'Company').strip() if settings else 'Company'
    except Exception:
        company_name = 'Company'

    tb_data = {
        'date': asof,
        'company_name': company_name,
        'rows': rows,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'type_totals': type_totals,
        'tb_groups': tb_groups,
        'order': order,
    }
    if request.args.get('embed'):
        return render_template('financials/trial_balance_embed.html', data=tb_data)
    return render_template('financials/trial_balance.html', data=tb_data)


@bp.route('/print/trial_balance')
def print_trial_balance():
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today
    new_codes = _new_coa_codes()
    q = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).join(JournalLine, JournalLine.account_id == Account.id) \
     .join(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(JournalLine.line_date <= asof, JournalEntry.status == 'posted') \
     .filter(Account.code.in_(new_codes))
    rows = q.group_by(Account.id).order_by(Account.code.asc()).all()

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
    new_codes = _new_coa_codes()
    q = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted'))) \
     .filter(Account.code.in_(new_codes))
    rows = q.group_by(Account.id).order_by(Account.code.asc()).all()
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
            .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
            .filter(Account.type.in_(['REVENUE', 'OTHER_INCOME']), JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted')
            .scalar() or 0)
    def sum_expense(types):
        return float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(Account, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
            .filter(Account.type.in_(types), JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted')
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
    """مصدر الحقيقة: قيود اليومية المنشورة فقط (JournalLine + JournalEntry.status=posted)."""
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today
    new_codes = _new_coa_codes()
    q = (
        db.session.query(
            Account.code.label('code'),
            Account.name.label('name'),
            Account.type.label('type'),
            func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
            func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
        )
        .outerjoin(JournalLine, JournalLine.account_id == Account.id)
        .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted')))
        .filter(Account.code.in_(new_codes))
    )
    rows = q.group_by(Account.id).order_by(Account.type.asc(), Account.code.asc()).all()

    current_assets = 0.0
    noncurrent_assets = 0.0
    current_liabilities = 0.0
    noncurrent_liabilities = 0.0
    for r in rows:
        if (r.code or '').strip() == '0006':
            continue
        if r.type == 'ASSET':
            bal = float(r.debit or 0) - float(r.credit or 0)
            if _is_current_asset(r.code):
                current_assets += bal
            else:
                noncurrent_assets += bal
        elif r.type == 'LIABILITY':
            bal = float(r.credit or 0) - float(r.debit or 0)
            if _is_current_liab(r.code):
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


@bp.route('/export/balance_sheet')
def export_balance_sheet():
    from flask import Response
    asof_str = request.args.get('date')
    today = get_saudi_now().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today
    new_codes = _new_coa_codes()
    q = (
        db.session.query(
            Account.code, Account.name, Account.type,
            func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
            func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
        )
        .outerjoin(JournalLine, JournalLine.account_id == Account.id)
        .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted')))
        .filter(Account.code.in_(new_codes))
    )
    rows = q.group_by(Account.id).order_by(Account.type.asc(), Account.code.asc()).all()
    import csv
    from io import StringIO
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(['Code', 'Name', 'Type', 'Debit', 'Credit', 'Balance'])
    for r in rows:
        d, c = float(r.debit or 0), float(r.credit or 0)
        if (r.type or '') == 'ASSET':
            bal = d - c
        else:
            bal = c - d
        w.writerow([r.code, r.name or '', r.type or '', f'{d:.2f}', f'{c:.2f}', f'{bal:.2f}'])
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=balance_sheet_{asof}.csv'}
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

    # استخدام الحسابات من الشجرة الجديدة فقط
    from data.coa_new_tree import build_coa_dict
    new_coa = build_coa_dict()
    new_codes = list(new_coa.keys())
    
    rows = db.session.query(
        Account.id.label('id'), Account.code.label('code'), Account.name.label('name'), Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit')
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(Account.code.in_(new_codes)) \
     .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted'))) \
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
    if code and str(code).strip() not in _new_coa_codes():
        return render_template('financials/account_statement.html', acc=None, entries=[], start_date=start_date, end_date=end_date, opening_balance=0.0)

    entries = db.session.query(JournalLine, JournalEntry.entry_number, JournalEntry.description) \
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
        .filter(JournalEntry.status == 'posted') \
        .filter(JournalLine.account_id == acc.id) \
        .filter(JournalLine.line_date.between(start_date, end_date)) \
        .order_by(JournalLine.line_date.asc(), JournalLine.id.asc()).all()

    opening_debit = float(db.session.query(func.coalesce(func.sum(JournalLine.debit), 0))
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalEntry.status == 'posted')
        .filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date < start_date).scalar() or 0)
    opening_credit = float(db.session.query(func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalEntry.status == 'posted')
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
        SHORT_TO_NUMERIC = {'CASH': ('1111', '', ''), 'BANK': ('1121', '', ''), 'REV_CT': ('4111', '', ''), 'REV_PI': ('4111', '', '')}
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
        rev_code = SHORT_TO_NUMERIC.get('REV_CT', ('4111',))[0]
        cash_code = SHORT_TO_NUMERIC['BANK'][0] if (inv.payment_method or '').upper() in ('BANK','TRANSFER') else SHORT_TO_NUMERIC['CASH'][0]
        vat_out_code = '2141'
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
        exp_acc = acc_by_code('1161')
        vat_in_acc = acc_by_code('1170')
        ap_acc = acc_by_code('2111')
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
        vat_in_acc = acc_by_code('1170')
        ap_acc = acc_by_code('2111')
        total_before = float(inv.total_before_tax or 0)
        tax_amt = float(inv.tax_amount or 0)
        total_inc_tax = round(total_before + tax_amt, 2)
        je = JournalEntry(entry_number=f"JE-EXP-{inv.invoice_number}", date=inv.date, branch_code=None, description=f"Expense {inv.invoice_number}", status='posted', total_debit=total_inc_tax, total_credit=total_inc_tax)
        db.session.add(je); db.session.flush()
        if total_before > 0:
            exp_acc = acc_by_code('5410')
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
    rows = db.session.query(JournalLine).join(Account, JournalLine.account_id == Account.id).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(Account.code.in_(['1111','1112','1121','1122','1123']), JournalLine.line_date.between(start_date, end_date), JournalEntry.status == 'posted').all()
    inflow = float(sum([float(r.debit or 0) for r in rows]))
    outflow = float(sum([float(r.credit or 0) for r in rows]))
    net = round(inflow - outflow, 2)
    data = {'title': 'Cash Flow', 'start_date': start_date, 'end_date': end_date, 'inflow': inflow, 'outflow': outflow, 'net': net, 'rows': [{'code': r.account.code, 'name': r.account.name, 'debit': float(r.debit or 0), 'credit': float(r.credit or 0), 'date': r.line_date} for r in rows]}
    if request.args.get('embed'):
        return render_template('financials/cash_flow_embed.html', data=data)
    return render_template('financials/cash_flow.html', data=data)

@bp.route('/statements')
def statements_hub():
    """صفحة موحدة للقوائم المالية مع التبديل بين قائمة الدخل، ميزان المراجعة، الميزانية، التدفق النقدي."""
    today = get_saudi_now().date()
    return render_template('financials/statements_hub.html', today=today, today_iso=today.isoformat())


@bp.route('/accounts_hub')
def accounts_hub():
    """شاشة الحسابات المتكاملة – البيانات تُجلب من /api/accounts/list فقط (لا تضمين في HTML)."""
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
    new_codes = _new_coa_codes()
    try:
        from data.coa_new_tree import OLD_TO_NEW_MAP
        new_codes = list(set(new_codes) | set(OLD_TO_NEW_MAP.keys()))
    except Exception:
        pass
    # Leaf balances from JournalLine
    q = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        getattr(Account, 'name_ar', Account.name).label('name_ar'),
        getattr(Account, 'name_en', Account.name).label('name_en'),
        Account.type.label('type'),
        func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
        func.coalesce(func.sum(JournalLine.credit), 0).label('credit')
    ).outerjoin(JournalLine, JournalLine.account_id == Account.id) \
     .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
     .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= asof, JournalEntry.status == 'posted'))) \
     .filter(Account.code.in_(new_codes))
    rows = q.group_by(Account.id).order_by(Account.type.asc(), Account.code.asc()).all()
    leaf_balances = {}
    try:
        from data.coa_new_tree import OLD_TO_NEW_MAP
        def _norm_code(c):
            return OLD_TO_NEW_MAP.get(str(c), str(c))
    except Exception:
        def _norm_code(c):
            return str(c)
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        d = float(r.debit or 0)
        c = float(r.credit or 0)
        bal = (d - c) if t not in ('LIABILITY', 'EQUITY') else (c - d)
        code_norm = _norm_code(r.code)
        if code_norm in leaf_balances:
            leaf_balances[code_norm]['debit'] += d
            leaf_balances[code_norm]['credit'] += c
        else:
            leaf_balances[code_norm] = {'debit': d, 'credit': c, 'type': t}
        b = leaf_balances[code_norm]
        bt = (b.get('type') or t or 'ASSET').upper()
        b['balance'] = (b['debit'] - b['credit']) if bt not in ('LIABILITY', 'EQUITY') else (b['credit'] - b['debit'])
    # Build hierarchy and aggregate group balances from coa_new_tree
    try:
        from data.coa_new_tree import build_coa_dict, NEW_COA_TREE, LEAF_CODES
        coa = build_coa_dict()
    except Exception:
        coa = {}
        LEAF_CODES = set()
        NEW_COA_TREE = []
    # Aggregate: group balance = sum of all descendant leaf balances
    def descendants(code):
        out = []
        for c, info in coa.items():
            if info.get('parent_account_code') == code:
                out.append(c)
                out.extend(descendants(c))
        return out
    def all_descendant_leaves(code):
        kids = []
        for c, info in coa.items():
            if info.get('parent_account_code') == code:
                if c in LEAF_CODES:
                    kids.append(c)
                else:
                    kids.extend(all_descendant_leaves(c))
        return kids
    def agg_balance(code):
        if code in leaf_balances:
            return leaf_balances[code]
        leaves = all_descendant_leaves(code)
        d = sum(leaf_balances.get(c, {}).get('debit', 0) for c in leaves)
        c = sum(leaf_balances.get(c, {}).get('credit', 0) for c in leaves)
        t = coa.get(code, {}).get('type', 'ASSET')
        bal = (d - c) if t not in ('LIABILITY', 'EQUITY') else (c - d)
        return {'debit': d, 'credit': c, 'balance': bal, 'type': t}
    # Build tree order: root -> children depth-first, grouped by type
    order = ['ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', 'COGS', 'TAX']
    type_order_map = {t: i for i, t in enumerate(order)}
    def tree_walk(code, parent_code, level, acc_type):
        info = coa.get(code, {})
        name = info.get('name', code)
        t = (info.get('type') or 'ASSET').upper()
        if acc_type and t != acc_type:
            return []
        data = agg_balance(code)
        leaves = all_descendant_leaves(code)
        has_children = len(leaves) > 0 if code not in LEAF_CODES else False
        # If group with no leaves, check direct children
        if not has_children and code not in LEAF_CODES:
            direct = [c for c, inf in coa.items() if inf.get('parent_account_code') == code]
            has_children = len(direct) > 0
        row = {
            'code': code, 'name': name, 'debit': data['debit'], 'credit': data['credit'],
            'balance': data['balance'], 'type': t, 'parent': parent_code, 'level': level,
            'has_children': has_children
        }
        out = [row]
        children = sorted([c for c, inf in coa.items() if inf.get('parent_account_code') == code],
                         key=lambda x: (x not in LEAF_CODES, x))
        for c in children:
            if not acc_type or coa.get(c, {}).get('type', '') == acc_type:
                out.extend(tree_walk(c, code, level + 1, None))
        return out
    grouped = {}
    top_level = []
    for t in order:
        roots = [r[0] for r in NEW_COA_TREE if (r[3] or '').upper() == t and (r[4] is None or (coa.get(r[4], {}).get('type', '') or '').upper() != t)]
        roots.sort(key=lambda c: (c in LEAF_CODES, c))
        arr = []
        for code in roots:
            arr.extend(tree_walk(code, None, 1, None))
            info = coa.get(code, {})
            data = agg_balance(code)
            top_level.append({
                'code': code, 'name': info.get('name', code),
                'debit': round(data['debit'], 2), 'credit': round(data['credit'], 2),
                'balance': round(data['balance'], 2), 'type': t
            })
        grouped[t] = arr
    total_debit = sum(v['debit'] for v in leaf_balances.values())
    total_credit = sum(v['credit'] for v in leaf_balances.values())
    return jsonify({'ok': True, 'date': str(asof), 'total_debit': total_debit, 'total_credit': total_credit, 'grouped': grouped, 'order': order, 'top_level': top_level})

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
    if code and str(code).strip() not in _new_coa_codes():
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'account_not_in_coa'}), 404
    q = db.session.query(JournalLine, JournalEntry.entry_number) \
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
        .filter(JournalEntry.status == 'posted') \
        .filter(JournalLine.account_id == acc.id) \
        .filter(JournalLine.line_date.between(start_date, end_date)) \
        .order_by(JournalLine.line_date.asc(), JournalLine.id.asc())
    rows = []
    bal = 0.0
    opening_debit = float(db.session.query(func.coalesce(func.sum(JournalLine.debit), 0)).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalEntry.status == 'posted').filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date < start_date).scalar() or 0)
    opening_credit = float(db.session.query(func.coalesce(func.sum(JournalLine.credit), 0)).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalEntry.status == 'posted').filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date < start_date).scalar() or 0)
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
    """تُرجع الحسابات من coa_new_tree + الحسابات المُنشأة من الشاشة (قاعدة البيانات)."""
    from flask import jsonify
    try:
        from data.coa_new_tree import build_coa_dict
        coa = build_coa_dict()
        codes = sorted(coa.keys())
        out = []
        code_to_level = {}
        for code in codes:
            info = coa.get(code, {})
            name = info.get('name', info.get('name_ar', code))
            name_ar = info.get('name_ar', name)
            name_en = info.get('name_en', '')
            level = int(info.get('level') or 1)
            code_to_level[code] = level
            out.append({
                'code': code,
                'name': name,
                'name_ar': name_ar,
                'name_en': name_en,
                'type': (info.get('type') or 'ASSET').strip().upper(),
                'active': True,
                'parent_account_code': info.get('parent_account_code'),
                'level': level,
            })
        # دمج الحسابات المُنشأة من الشاشة (من قاعدة البيانات)
        parent_col = getattr(Account, 'parent_account_code', None)
        if parent_col is not None:
            try:
                db_accounts = Account.query.filter(~Account.code.in_(codes)).all()
                for acc in db_accounts:
                    parent_code = getattr(acc, 'parent_account_code', None) or None
                    parent_level = code_to_level.get(parent_code, 3)
                    level = parent_level + 1
                    code_to_level[acc.code] = level
                    name_ar = getattr(acc, 'name_ar', None) or acc.name
                    name_en = getattr(acc, 'name_en', None) or ''
                    out.append({
                        'code': acc.code,
                        'name': name_ar,
                        'name_ar': name_ar,
                        'name_en': name_en,
                        'type': (acc.type or 'EXPENSE').strip().upper(),
                        'active': True,
                        'parent_account_code': parent_code,
                        'level': level,
                    })
            except Exception:
                pass
        out.sort(key=lambda x: (x['code'],))
        return jsonify({'ok': True, 'coa_codes': codes, 'accounts': out})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'coa_codes': [], 'accounts': []}), 500

@bp.route('/api/db_check')
def api_db_check():
    """التحقق من أن النظام يستخدم SQLite المحلي فقط ولا يتصل بـ Render."""
    from flask import jsonify, current_app
    uri = (current_app.config.get('SQLALCHEMY_DATABASE_URI') or '').strip()
    is_sqlite = uri.startswith('sqlite:///')
    path = uri.replace('sqlite:///', '') if is_sqlite else ''
    no_render = 'render.com' not in uri.lower() and 'postgres' not in uri.lower()
    coa_codes = []
    db_codes = []
    try:
        from data.coa_new_tree import build_coa_dict
        coa_codes = sorted(build_coa_dict().keys())
    except Exception:
        pass
    try:
        db_codes = [str(a.code) for a in Account.query.order_by(Account.code.asc()).all()]
    except Exception:
        pass
    return jsonify({
        'ok': True,
        'database': 'sqlite' if is_sqlite else 'other',
        'path': path,
        'using_only_local': is_sqlite and no_render,
        'coa_count': len(coa_codes),
        'db_account_count': len(db_codes),
        'db_codes_sample': db_codes[:20],
        'coa_codes_sample': coa_codes[:20],
    })

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


@bp.route('/api/list_employees')
def api_list_employees():
    try:
        rows = db.session.query(Employee).order_by(getattr(Employee, 'full_name', 'id').asc()).all()
        out = [{'id': int(getattr(e, 'id', 0) or 0), 'name': getattr(e, 'full_name', '') or ''} for e in rows]
        from flask import jsonify
        return jsonify({'ok': True, 'employees': out})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/operations/outstanding')
def api_operations_outstanding():
    """الفواتير/المستحقات المرتبطة بعملية: للمورد، العميل، المسير، أو حساب مستحقات.
    يُستخدم في شاشة العمليات لعرض الفاتورة والمبلغ المطلوب تحصيله/سداده."""
    try:
        party_type = (request.args.get('party_type') or '').strip().lower()
        party_name = (request.args.get('party_name') or '').strip()
        liability_code = (request.args.get('liability_code') or '').strip()
        payroll_year = request.args.get('payroll_year', type=int)
        payroll_month = request.args.get('payroll_month', type=int)
        invoices = []
        total_remaining = 0.0
        label = ''

        if party_type == 'supplier' and party_name:
            # فواتير مشتريات ومصروفات للمورد (غير مسددة أو مسددة جزئياً)
            p_rows = PurchaseInvoice.query.filter(
                or_(PurchaseInvoice.supplier_name == party_name, func.coalesce(PurchaseInvoice.supplier_name, '').ilike('%' + party_name + '%'))
            ).order_by(PurchaseInvoice.date.desc()).limit(50).all()
            p_ids = [inv.id for inv in p_rows]
            p_paid = {}
            if p_ids:
                for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'purchase', Payment.invoice_id.in_(p_ids)
                ).group_by(Payment.invoice_id).all():
                    p_paid[int(i)] = float(s or 0)
            for inv in p_rows:
                total = float(inv.total_after_tax_discount or 0)
                paid = float(p_paid.get(inv.id, 0))
                rem = max(0.0, total - paid)
                if rem >= 0.01:
                    invoices.append({
                        'invoice_number': getattr(inv, 'invoice_number', None) or str(inv.id),
                        'date': str(inv.date) if getattr(inv, 'date', None) else '',
                        'total': round(total, 2),
                        'paid': round(paid, 2),
                        'remaining': round(rem, 2),
                        'type': 'purchase',
                    })
                    total_remaining += rem
            e_rows = ExpenseInvoice.query.filter(
                or_(ExpenseInvoice.supplier_name == party_name, func.coalesce(ExpenseInvoice.supplier_name, '').ilike('%' + party_name + '%'))
            ).order_by(ExpenseInvoice.date.desc()).limit(50).all()
            e_ids = [inv.id for inv in e_rows]
            e_paid = {}
            if e_ids:
                for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'expense', Payment.invoice_id.in_(e_ids)
                ).group_by(Payment.invoice_id).all():
                    e_paid[int(i)] = float(s or 0)
            for inv in e_rows:
                total = float(inv.total_after_tax_discount or 0)
                paid = float(e_paid.get(inv.id, 0))
                rem = max(0.0, total - paid)
                if rem >= 0.01:
                    invoices.append({
                        'invoice_number': getattr(inv, 'invoice_number', None) or str(inv.id),
                        'date': str(inv.date) if getattr(inv, 'date', None) else '',
                        'total': round(total, 2),
                        'paid': round(paid, 2),
                        'remaining': round(rem, 2),
                        'type': 'expense',
                    })
                    total_remaining += rem
            label = f'مستحقات المورد: {party_name}'

        elif party_type == 'customer' and party_name:
            # فواتير مبيعات للعميل (غير محصلة أو جزئياً)
            s_rows = SalesInvoice.query.filter(
                or_(SalesInvoice.customer_name == party_name, func.coalesce(SalesInvoice.customer_name, '').ilike('%' + party_name + '%'))
            ).order_by(SalesInvoice.date.desc()).limit(50).all()
            s_ids = [inv.id for inv in s_rows]
            s_paid = {}
            if s_ids:
                for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'sales', Payment.invoice_id.in_(s_ids)
                ).group_by(Payment.invoice_id).all():
                    s_paid[int(i)] = float(s or 0)
            for inv in s_rows:
                total = float(inv.total_after_tax_discount or 0)
                paid = float(s_paid.get(inv.id, 0))
                rem = max(0.0, total - paid)
                if rem >= 0.01:
                    invoices.append({
                        'invoice_number': getattr(inv, 'invoice_number', None) or str(inv.id),
                        'date': str(inv.date) if getattr(inv, 'date', None) else '',
                        'total': round(total, 2),
                        'paid': round(paid, 2),
                        'remaining': round(rem, 2),
                        'type': 'sales',
                    })
                    total_remaining += rem
            label = f'مستحقات العميل: {party_name}'

        elif party_type == 'payroll' and payroll_year is not None and payroll_month is not None:
            sal_rows = Salary.query.filter_by(year=payroll_year, month=payroll_month).order_by(Salary.employee_id.asc()).all()
            sid_list = [s.id for s in sal_rows]
            pay_map = {}
            if sid_list:
                for sid, psum in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'salary', Payment.invoice_id.in_(sid_list)
                ).group_by(Payment.invoice_id).all():
                    pay_map[int(sid)] = float(psum or 0)
            run_total = sum(float(s.total_salary or 0) for s in sal_rows)
            run_paid = sum(pay_map.get(s.id, 0) for s in sal_rows)
            run_remaining = max(0.0, run_total - run_paid)
            if run_remaining >= 0.01:
                invoices.append({
                    'invoice_number': f'مسير {payroll_year}-{payroll_month:02d}',
                    'date': f'{payroll_year}-{payroll_month:02d}-01',
                    'total': round(run_total, 2),
                    'paid': round(run_paid, 2),
                    'remaining': round(run_remaining, 2),
                    'type': 'salary',
                })
                total_remaining = run_remaining
            label = f'مسير رواتب: {payroll_year}-{payroll_month:02d}'

        elif party_type == 'liability' and liability_code:
            # رصيد حساب المستحقات (قيود مرحّلة فقط) — المبلغ المستحق للسداد = دائن - مدين
            acc = Account.query.filter_by(code=liability_code).first()
            if acc:
                from models import get_saudi_now as _now
                end_d = _now().date()
                bal, _ = _account_balance_as_of(liability_code, end_d)
                if bal > 0.01:
                    name = next((n for c, n in QUICK_TXN_LIABILITY_OPTIONS if c == liability_code), acc.name)
                    invoices.append({
                        'invoice_number': liability_code,
                        'date': str(end_d),
                        'total': round(bal, 2),
                        'paid': 0,
                        'remaining': round(bal, 2),
                        'type': 'liability',
                    })
                    total_remaining = round(bal, 2)
                    label = f'مستحقات: {name} (الرصيد المستحق: {total_remaining:.2f} ر.س)'
                else:
                    name = next((n for c, n in QUICK_TXN_LIABILITY_OPTIONS if c == liability_code), acc.name)
                    label = f'لا يوجد رصيد مستحق لحساب {name} — لا يمكن تنفيذ السداد'

        return jsonify({
            'ok': True,
            'invoices': invoices,
            'total_remaining': round(total_remaining, 2),
            'label': label or 'لا يوجد مستحقات',
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


def _account_balance_as_of(account_code, asof_date):
    """رصيد حساب حتى تاريخ معين (قيود مرحّلة فقط). للحسابات الدائنة: رصيد = دائن - مدين؛ للأصول: مدين - دائن."""
    acc = Account.query.filter_by(code=(account_code or '').strip()).first()
    if not acc:
        return 0.0, None
    debit_sum = db.session.query(func.coalesce(func.sum(JournalLine.debit), 0)).join(
        JournalEntry, JournalLine.journal_id == JournalEntry.id
    ).filter(
        JournalLine.account_id == acc.id,
        JournalLine.line_date <= asof_date,
        JournalEntry.status == 'posted'
    ).scalar() or 0
    credit_sum = db.session.query(func.coalesce(func.sum(JournalLine.credit), 0)).join(
        JournalEntry, JournalLine.journal_id == JournalEntry.id
    ).filter(
        JournalLine.account_id == acc.id,
        JournalLine.line_date <= asof_date,
        JournalEntry.status == 'posted'
    ).scalar() or 0
    debit_sum = float(debit_sum)
    credit_sum = float(credit_sum)
    if (acc.type or '').upper() in ('LIABILITY', 'EQUITY'):
        balance = credit_sum - debit_sum
    else:
        balance = debit_sum - credit_sum
    return round(balance, 2), (acc.type or '').upper()


# Liability account options for "سداد مستحقات"
QUICK_TXN_LIABILITY_OPTIONS = [
    ('2121', 'رواتب مستحقة'),
    ('2122', 'بدلات مستحقة'),
    ('2141', 'ضريبة قيمة مضافة مستحقة'),
    ('2131', 'GOSI'),
    ('2135', 'ضرائب حكومية أخرى'),
    ('2112', 'ذمم دائنة أخرى'),
    # استحقاق المنصات الإلكترونية — ذمم دائنة (عمولات) لكل منصة
    ('2113', 'ذمم دائنة – هنقرستيشن (عمولات)'),
    ('2114', 'ذمم دائنة – كيتا (عمولات)'),
    ('2115', 'ذمم دائنة – جاهز (عمولات)'),
    ('2116', 'ذمم دائنة – نون (عمولات)'),
]

# Platform entity mapping: receivable (تحصيل) + payable (سداد) لكل منصة — للتوسع والتقارير
PLATFORM_ACCOUNTS = [
    {'key': 'hungerstation', 'name_ar': 'هنقرستيشن', 'name_en': 'Hungerstation', 'receivable_code': '1144', 'payable_code': '2113', 'expense_code': '5555'},
    {'key': 'keeta', 'name_ar': 'كيتا', 'name_en': 'Keeta', 'receivable_code': '1145', 'payable_code': '2114', 'expense_code': '5555'},
    {'key': 'jahez', 'name_ar': 'جاهز', 'name_en': 'Jahez', 'receivable_code': '1146', 'payable_code': '2115', 'expense_code': '5555'},
    {'key': 'noon', 'name_ar': 'نون', 'name_en': 'Noon', 'receivable_code': '1146', 'payable_code': '2116', 'expense_code': '5555'},
]


@bp.route('/api/platform_accounts')
def api_platform_accounts():
    """قائمة حسابات المنصات (ذمم دائنة – عمولات) لعرضها في سداد استحقاق المنصات."""
    from flask import jsonify
    platforms = [{'code': p['payable_code'], 'name_ar': p['name_ar'], 'name_en': p.get('name_en', '')} for p in PLATFORM_ACCOUNTS]
    return jsonify({'ok': True, 'platforms': platforms})


@bp.route('/api/unpaid_payroll_runs')
def api_unpaid_payroll_runs():
    """قائمة المسيرات غير المدفوعة (year, month) مع المجموع والمتبقي.
    فلترة اختيارية: from_year, from_month, to_year, to_month (شهر واحد = من==إلى، عدة أشهر = من..إلى)."""
    from flask import jsonify
    try:
        from_year = request.args.get('from_year', type=int)
        from_month = request.args.get('from_month', type=int)
        to_year = request.args.get('to_year', type=int)
        to_month = request.args.get('to_month', type=int)

        def _month_key(y, m):
            return int(y or 0) * 12 + int(m or 1)

        q = (
            db.session.query(Salary.year, Salary.month, func.count(Salary.id).label('n'), func.coalesce(func.sum(Salary.total_salary), 0).label('total'))
            .group_by(Salary.year, Salary.month)
            .order_by(Salary.year.desc(), Salary.month.desc())
        )
        runs = []
        for r in q.all():
            y, m = int(r.year or 0), int(r.month or 0)
            if from_year is not None and from_month is not None:
                if _month_key(y, m) < _month_key(from_year, from_month):
                    continue
            if to_year is not None and to_month is not None:
                if _month_key(y, m) > _month_key(to_year, to_month):
                    continue
            sal_ids = [x.id for x in Salary.query.filter_by(year=y, month=m).all()]
            paid = 0.0
            if sal_ids:
                paid = float(
                    db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                    .filter(Payment.invoice_type == 'salary', Payment.invoice_id.in_(sal_ids))
                    .scalar() or 0
                )
            total = float(r.total or 0)
            remaining = max(0.0, total - paid)
            if remaining < 1e-6:
                continue
            runs.append({
                'year': y,
                'month': m,
                'label': f'{y}-{m:02d}',
                'label_ar': f'{m:02d}/{y}',
                'total': round(total, 2),
                'paid': round(paid, 2),
                'remaining': round(remaining, 2),
                'n_employees': int(r.n or 0),
            })
        return jsonify({'ok': True, 'runs': runs})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/quick-txn', methods=['POST'])
@csrf.exempt
def api_quick_txn():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        op_type = (payload.get('type') or '').strip().lower()
        date_s = (payload.get('date') or '').strip()
        try:
            dval = datetime.strptime(date_s, '%Y-%m-%d').date() if date_s else get_saudi_now().date()
        except Exception:
            dval = get_saudi_now().date()
        amount = float(payload.get('amount') or 0)
        if amount <= 0:
            return jsonify({'ok': False, 'error': 'مبلغ غير صالح'}), 400
        method = (payload.get('payment_method') or 'cash').strip().lower()
        note = (payload.get('note') or '').strip()
        cash_code = _resolve_method(method)

        lines = []
        desc = note or op_type

        if op_type == 'supplier_payment':
            party = (payload.get('supplier_name') or '').strip()
            if not party:
                return jsonify({'ok': False, 'error': 'يجب تحديد المورد'}), 400
            # التحقق من وجود مستحقات فعلية للمورد قبل السماح بالسداد
            p_rows = PurchaseInvoice.query.filter(
                or_(PurchaseInvoice.supplier_name == party, func.coalesce(PurchaseInvoice.supplier_name, '').ilike('%' + party + '%'))
            ).all()
            e_rows = ExpenseInvoice.query.filter(
                or_(ExpenseInvoice.supplier_name == party, func.coalesce(ExpenseInvoice.supplier_name, '').ilike('%' + party + '%'))
            ).all()
            p_ids = [inv.id for inv in p_rows]
            e_ids = [inv.id for inv in e_rows]
            p_paid = {}
            e_paid = {}
            if p_ids:
                for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'purchase', Payment.invoice_id.in_(p_ids)
                ).group_by(Payment.invoice_id).all():
                    p_paid[int(i)] = float(s or 0)
            if e_ids:
                for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'expense', Payment.invoice_id.in_(e_ids)
                ).group_by(Payment.invoice_id).all():
                    e_paid[int(i)] = float(s or 0)
            total_remaining = 0.0
            for inv in p_rows:
                total_remaining += max(0.0, float(inv.total_after_tax_discount or 0) - float(p_paid.get(inv.id, 0)))
            for inv in e_rows:
                total_remaining += max(0.0, float(inv.total_after_tax_discount or 0) - float(e_paid.get(inv.id, 0)))
            total_remaining = round(total_remaining, 2)
            if total_remaining < 0.01:
                return jsonify({'ok': False, 'error': 'لا يوجد مستحقات فعلية لهذا المورد — لا يُسمح بإنشاء عملية سداد بدون دائن فعلي'}), 400
            if amount > total_remaining:
                return jsonify({'ok': False, 'error': f'المبلغ أكبر من المستحقات المتبقية للمورد ({total_remaining:.2f} ر.س)'}), 400
            lines = [
                {'account_code': '2111', 'debit': amount, 'credit': 0.0, 'description': f'دفعة لمورد {party} {note}', 'date': str(dval)},
                {'account_code': cash_code, 'debit': 0.0, 'credit': amount, 'description': 'صندوق/بنك', 'date': str(dval)},
            ]
        elif op_type == 'pay_liability':
            code = (payload.get('liability_code') or '2121').strip()
            name = next((n for c, n in QUICK_TXN_LIABILITY_OPTIONS if c == code), code)
            py = payload.get('payroll_year')
            pm = payload.get('payroll_month')
            try:
                py = int(py) if py is not None else None
                pm = int(pm) if pm is not None else None
            except (TypeError, ValueError):
                py = pm = None
            if code == '2121' and py is not None and pm is not None:
                sal_rows = Salary.query.filter_by(year=py, month=pm).order_by(Salary.employee_id.asc()).all()
                pay_map = {}
                if sal_rows:
                    sid_list = [s.id for s in sal_rows]
                    for sid, psum in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                        Payment.invoice_type == 'salary', Payment.invoice_id.in_(sid_list)
                    ).group_by(Payment.invoice_id).all():
                        pay_map[int(sid)] = float(psum or 0)
                run_total = sum(float(s.total_salary or 0) for s in sal_rows)
                run_paid = sum(pay_map.get(s.id, 0) for s in sal_rows)
                run_remaining = max(0.0, run_total - run_paid)
                if run_remaining < 1e-6:
                    return jsonify({'ok': False, 'error': 'لا يوجد متبقي لهذا المسير'}), 400
                if abs(amount - run_remaining) > 0.02:
                    return jsonify({'ok': False, 'error': f'المبلغ يجب أن يساوي متبقي المسير {run_remaining:.2f}'}), 400
                try:
                    from flask_login import current_user
                    uid = getattr(current_user, 'id', None)
                except Exception:
                    uid = None
                from datetime import datetime as _dt
                pay_dt = _dt(dval.year, dval.month, dval.day, 12, 0, 0)
                entry_number = f"JE-QTX-{int(JournalEntry.query.count() + 1)}"
                je = JournalEntry(
                    entry_number=entry_number,
                    date=dval,
                    branch_code=None,
                    description=(note or f'سداد مسير رواتب {py}-{pm:02d}')[:255],
                    status='posted',
                    total_debit=round(amount, 2),
                    total_credit=round(amount, 2),
                    created_by=uid,
                    posted_by=uid,
                )
                db.session.add(je)
                db.session.flush()
                acc_2121 = Account.query.filter_by(code='2121').first()
                if not acc_2121:
                    acc_2121 = Account(code='2121', name='رواتب مستحقة', type='LIABILITY')
                    db.session.add(acc_2121)
                    db.session.flush()
                acc_cash = Account.query.filter_by(code=cash_code).first()
                if not acc_cash:
                    acc_cash = Account(code=cash_code, name=cash_code, type='EXPENSE')
                    db.session.add(acc_cash)
                    db.session.flush()
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=acc_2121.id, debit=round(amount, 2), credit=0, description=f'سداد رواتب {py}-{pm:02d}', line_date=dval))
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=acc_cash.id, debit=0, credit=round(amount, 2), description='صندوق/بنك', line_date=dval))
                for s in sal_rows:
                    paid_so_far = pay_map.get(s.id, 0)
                    tot = float(s.total_salary or 0)
                    rem = max(0.0, tot - paid_so_far)
                    if rem < 1e-6:
                        continue
                    p = Payment(invoice_id=s.id, invoice_type='salary', amount_paid=round(rem, 2), payment_date=pay_dt, payment_method=method)
                    db.session.add(p)
                    s.status = 'paid'
                try:
                    from models import JournalAudit
                    db.session.add(JournalAudit(journal_id=je.id, action='create', user_id=uid, before_json=None, after_json=None))
                except Exception:
                    pass
                db.session.commit()
                return jsonify({'ok': True, 'entry_number': entry_number})
            # التحقق من وجود رصيد مستحق فعلي قبل السماح بالسداد
            balance, _ = _account_balance_as_of(code, dval)
            if balance <= 0:
                return jsonify({'ok': False, 'error': 'لا يوجد رصيد مستحق لهذا الحساب — لا يُسمح بإنشاء عملية سداد بدون دائن فعلي'}), 400
            if amount > balance:
                return jsonify({'ok': False, 'error': f'المبلغ أكبر من الرصيد المستحق ({balance:.2f} ر.س)'}), 400
            lines = [
                {'account_code': code, 'debit': amount, 'credit': 0.0, 'description': f'سداد {name} {note}', 'date': str(dval)},
                {'account_code': cash_code, 'debit': 0.0, 'credit': amount, 'description': 'صندوق/بنك', 'date': str(dval)},
            ]
        elif op_type == 'collection':
            debtor = (payload.get('debtor_type') or 'customer').strip().lower()
            party = (payload.get('party') or '').strip()
            ar_code = '1141'
            if debtor in ('employee_advance', 'سلفة'):
                ar_code = '1151'
            elif debtor in ('other_receivable', 'أخرى'):
                ar_code = '1142'
            # التحقق من وجود رصيد مدينة فعلي قبل السماح بالتحصيل
            balance, _ = _account_balance_as_of(ar_code, dval)
            if balance <= 0:
                return jsonify({'ok': False, 'error': 'لا يوجد رصيد مدينة لهذا الحساب — لا يُسمح بإنشاء عملية تحصيل بدون مدين فعلي'}), 400
            if amount > balance:
                return jsonify({'ok': False, 'error': f'المبلغ أكبر من الرصيد المدينة ({balance:.2f} ر.س)'}), 400
            lines = [
                {'account_code': cash_code, 'debit': amount, 'credit': 0.0, 'description': f'تحصيل {party} {note}', 'date': str(dval)},
                {'account_code': ar_code, 'debit': 0.0, 'credit': amount, 'description': 'مدينون', 'date': str(dval)},
            ]
        elif op_type == 'bank_deposit':
            lines = [
                {'account_code': '1121', 'debit': amount, 'credit': 0.0, 'description': f'إيداع بنكي {note}', 'date': str(dval)},
                {'account_code': '1111', 'debit': 0.0, 'credit': amount, 'description': 'صندوق رئيسي', 'date': str(dval)},
            ]
        elif op_type == 'owner_draw':
            lines = [
                {'account_code': '3310', 'debit': amount, 'credit': 0.0, 'description': f'سحب المالك {note}', 'date': str(dval)},
                {'account_code': cash_code, 'debit': 0.0, 'credit': amount, 'description': 'صندوق/بنك', 'date': str(dval)},
            ]
        else:
            return jsonify({'ok': False, 'error': 'نوع عملية غير مدعوم'}), 400

        td = sum(l.get('debit', 0) or 0 for l in lines)
        tc = sum(l.get('credit', 0) or 0 for l in lines)
        if round(td - tc, 2) != 0.0:
            return jsonify({'ok': False, 'error': 'قيد غير متوازن'}), 400

        try:
            from flask_login import current_user
            uid = getattr(current_user, 'id', None)
        except Exception:
            uid = None
        entry_number = f"JE-QTX-{int(JournalEntry.query.count() + 1)}"
        je = JournalEntry(
            entry_number=entry_number,
            date=dval,
            branch_code=None,
            description=desc[:255] if desc else 'عملية سريعة',
            status='posted',
            total_debit=round(td, 2),
            total_credit=round(tc, 2),
            created_by=uid,
            posted_by=uid,
        )
        db.session.add(je)
        db.session.flush()
        for i, ln in enumerate(lines, 1):
            code = (ln.get('account_code') or '').strip()
            acc = Account.query.filter_by(code=code).first()
            if not acc:
                acc = Account(code=code, name=code, type='EXPENSE')
                db.session.add(acc)
                db.session.flush()
            db.session.add(JournalLine(
                journal_id=je.id,
                line_no=i,
                account_id=acc.id,
                debit=float(ln.get('debit') or 0),
                credit=float(ln.get('credit') or 0),
                description=(ln.get('description') or '')[:500],
                line_date=dval,
            ))
        try:
            from models import JournalAudit
            db.session.add(JournalAudit(journal_id=je.id, action='create', user_id=uid, before_json=None, after_json=None))
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True, 'entry_number': entry_number})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
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


@bp.route('/api/accounts/add_sub', methods=['POST'])
@csrf.exempt
def api_accounts_add_sub():
    """إنشاء حساب فرعي تحت حساب محدد: يُولّد الكود تلقائياً ويُحفظ في الشجرة وقاعدة البيانات."""
    from flask import jsonify
    try:
        payload = request.get_json(force=True, silent=True) or {}
        parent_code = (payload.get('parent_code') or '').strip()
        name_ar = (payload.get('name_ar') or '').strip()
        name_en = (payload.get('name_en') or '').strip()
        if not parent_code or not name_ar:
            return jsonify({'ok': False, 'error': 'parent_code و name_ar مطلوبان'}), 400
        from data.coa_new_tree import build_coa_dict
        coa = build_coa_dict()
        parent_info = coa.get(parent_code)
        if not parent_info:
            parent_acc = Account.query.filter(Account.code == parent_code).first()
            if not parent_acc:
                return jsonify({'ok': False, 'error': 'الحساب الأب غير موجود'}), 404
            parent_type = (parent_acc.type or 'EXPENSE').strip().upper()
        else:
            parent_type = (parent_info.get('type') or 'EXPENSE').strip().upper()
        # بناء قائمة الحسابات المدمجة لاستخراج الأشقاء
        all_codes = set(coa.keys())
        db_accounts = Account.query.filter(~Account.code.in_(all_codes)).all() if hasattr(Account, 'parent_account_code') else []
        siblings = [a.code for a in db_accounts if getattr(a, 'parent_account_code', None) == parent_code]
        for code, info in coa.items():
            if info.get('parent_account_code') == parent_code:
                siblings.append(code)
        # توليد الكود التالي (نفس طول أشقاء أو 4 أرقام)
        def next_code(sibs):
            if not sibs:
                try:
                    n = int(parent_code)
                    return str(n + 1).zfill(len(parent_code))
                except (ValueError, TypeError):
                    return parent_code + '1'
            numeric = []
            for s in sibs:
                try:
                    numeric.append(int(s))
                except (ValueError, TypeError):
                    pass
            if numeric:
                width = max(len(s) for s in sibs)
                return str(max(numeric) + 1).zfill(width)
            return parent_code + str(len(sibs) + 1)
        new_code = next_code(siblings)
        if Account.query.filter(Account.code == new_code).first() or new_code in coa:
            return jsonify({'ok': False, 'error': 'الكود المُولّد مستخدم'}), 409
        a = Account(code=new_code, name=name_ar, type=parent_type, parent_account_code=parent_code)
        if hasattr(a, 'name_ar'):
            a.name_ar = name_ar
        if hasattr(a, 'name_en'):
            a.name_en = name_en or ''
        db.session.add(a)
        db.session.commit()
        return jsonify({'ok': True, 'code': new_code})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

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
            '5160':'5280','5170':'5280','5180':'5280','5190':'5280','5200':'5210','5310':'5310',
            '4020':'4013','4023':'4013','4030':'4210','4040':'4210',
            '1022':'1020','1220':'1080','1090':'1040','4010':'4011','2130':'2121'
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
    """يزرع الحسابات من الشجرة الجديدة (data.coa_new_tree) فقط – لا يضيف حسابات قديمة."""
    from flask import jsonify
    try:
        from data.coa_new_tree import NEW_COA_TREE
        created = []
        for row in NEW_COA_TREE:
            code, name_ar, name_en, atype, _parent, _level = row
            code = (code or '').strip()
            if not code:
                continue
            a = Account.query.filter(Account.code == code).first()
            if a:
                continue
            name = name_ar or name_en or code
            a = Account(code=code, name=name, type=(atype or 'ASSET').strip().upper())
            try:
                setattr(a, 'name_ar', name_ar)
                setattr(a, 'name_en', name_en)
            except Exception:
                pass
            db.session.add(a)
            created.append(code)
        if created:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return jsonify({'ok': False, 'error': 'commit_failed', 'created': created}), 500
        return jsonify({'ok': True, 'created_count': len(created), 'created': created})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
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
    if s in ('BANK','TRANSFER','CARD','VISA','MASTERCARD','POS','WALLET','CHEQUE','شيك','تحويل'):
        return '1121'
    return '1111'

def _resolve_expense(desc: str):
    s = (desc or '').strip().lower()
    if ('كهرب' in s) or ('electric' in s) or ('power' in s):
        return '5210'
    if ('ماء' in s) or ('water' in s):
        return '5220'
    if ('صيانة' in s) or ('maint' in s):
        return '5240'
    if ('ايجار' in s) or ('rent' in s):
        return '5270'
    if ('انترنت' in s) or ('net' in s) or ('wifi' in s):
        return '5230'
    if ('مكتب' in s) or ('office' in s):
        return '5420'
    if ('تنظيف' in s) or ('clean' in s):
        return '5250'
    if ('غسيل' in s) or ('laundry' in s):
        return '5250'
    if ('عمول' in s) or ('fee' in s) or ('commission' in s):
        return '5610'
    if ('حكومي' in s) or ('gov' in s):
        return '5410'
    return '5470'

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
        errors = []
        for r in rows:
            typ = (r.get('type') or '').strip().lower()
            party = (r.get('party') or '').strip()
            amt = float(r.get('amount') or 0)
            method = (r.get('method') or '').strip()
            desc = (r.get('description') or '').strip()
            cat = (r.get('category') or '').strip().lower()
            branch = (r.get('branch') or '').strip().lower()
            if amt <= 0:
                continue
            cash_code = _resolve_method(method)
            exp_branch = '5110' if branch == 'china_town' else ('5110' if branch == 'place_india' else None)
            if typ in ('supplier_payment','دفعة لمورد','supplier'):
                if not party:
                    errors.append('سداد مورد: يجب تحديد المورد')
                    continue
                p_rows = PurchaseInvoice.query.filter(
                    or_(PurchaseInvoice.supplier_name == party, func.coalesce(PurchaseInvoice.supplier_name, '').ilike('%' + party + '%'))
                ).all()
                e_rows = ExpenseInvoice.query.filter(
                    or_(ExpenseInvoice.supplier_name == party, func.coalesce(ExpenseInvoice.supplier_name, '').ilike('%' + party + '%'))
                ).all()
                p_ids, e_ids = [x.id for x in p_rows], [x.id for x in e_rows]
                p_paid = dict(db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'purchase', Payment.invoice_id.in_(p_ids)).group_by(Payment.invoice_id).all()) if p_ids else {}
                e_paid = dict(db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                    Payment.invoice_type == 'expense', Payment.invoice_id.in_(e_ids)).group_by(Payment.invoice_id).all()) if e_ids else {}
                total_rem = sum(max(0.0, float(inv.total_after_tax_discount or 0) - float(p_paid.get(inv.id, 0))) for inv in p_rows)
                total_rem += sum(max(0.0, float(inv.total_after_tax_discount or 0) - float(e_paid.get(inv.id, 0))) for inv in e_rows)
                if total_rem < 0.01:
                    errors.append(f'سداد مورد ({party}): لا يوجد مستحقات فعلية')
                    continue
                if amt > total_rem:
                    errors.append(f'سداد مورد ({party}): المبلغ أكبر من المستحقات ({total_rem:.2f} ر.س)')
                    continue
                lines = [
                    {'account_code': '2111', 'debit': amt, 'credit': 0.0, 'description': f"Pay Supplier {party} {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            elif typ in ('customer_receipt','استلام من عميل','customer'):
                ar_balance, _ = _account_balance_as_of('1141', dval)
                if ar_balance <= 0:
                    errors.append('تحصيل عميل: لا يوجد رصيد مدينة للتحصيل')
                    continue
                if amt > ar_balance:
                    errors.append(f'تحصيل عميل: المبلغ أكبر من الرصيد المدينة ({ar_balance:.2f} ر.س)')
                    continue
                lines = [
                    {'account_code': cash_code, 'debit': amt, 'credit': 0.0, 'description': f"Receive Customer {party} {desc}", 'date': str(dval)},
                    {'account_code': '1141', 'debit': 0.0, 'credit': amt, 'description': f"Accounts Receivable", 'date': str(dval)}
                ]
            elif typ in ('owner_draw','مسحوبات شخصية','drawings'):
                lines = [
                    {'account_code': '3310', 'debit': amt, 'credit': 0.0, 'description': f"Owner Draw {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            elif typ in ('employee_advance','سلفة موظف','advance'):
                bal_1151, _ = _account_balance_as_of('1151', dval)
                if bal_1151 <= 0:
                    errors.append('تحصيل سلفة موظف: لا يوجد رصيد مدينة للتحصيل')
                    continue
                if amt > bal_1151:
                    errors.append(f'تحصيل سلفة موظف: المبلغ أكبر من الرصيد المدينة ({bal_1151:.2f} ر.س)')
                    continue
                lines = [
                    {'account_code': cash_code, 'debit': amt, 'credit': 0.0, 'description': f"Employee Advance {party} {desc}", 'date': str(dval)},
                    {'account_code': '1151', 'debit': 0.0, 'credit': amt, 'description': f"Employee Advance", 'date': str(dval)}
                ]
            elif typ in ('collection',):
                bal_1142, _ = _account_balance_as_of('1142', dval)
                if bal_1142 <= 0:
                    errors.append('تحصيل أخرى: لا يوجد رصيد مدينة للتحصيل')
                    continue
                if amt > bal_1142:
                    errors.append(f'تحصيل أخرى: المبلغ أكبر من الرصيد المدينة ({bal_1142:.2f} ر.س)')
                    continue
                lines = [
                    {'account_code': cash_code, 'debit': amt, 'credit': 0.0, 'description': f"تحصيل {party} {desc}", 'date': str(dval)},
                    {'account_code': '1142', 'debit': 0.0, 'credit': amt, 'description': f"مدينون", 'date': str(dval)}
                ]
            elif typ in ('supplier_ap','مورد دائن','add_ap'):
                if cat in ('inventory','stock','مخزون'):
                    exp_code = '1161'
                else:
                    exp_code = exp_branch or '5410'
                lines = [
                    {'account_code': exp_code, 'debit': amt, 'credit': 0.0, 'description': f"Supplier AP {party} {desc}", 'date': str(dval)},
                    {'account_code': '2111', 'debit': 0.0, 'credit': amt, 'description': f"Accounts Payable", 'date': str(dval)}
                ]
            elif typ in ('operating_expense','مصروف تشغيل','expense'):
                exp_code = exp_branch or _resolve_expense(desc)
                lines = [
                    {'account_code': exp_code, 'debit': amt, 'credit': 0.0, 'description': f"Operating Expense {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            elif typ in ('bank_deposit','ايداع بالبنك','deposit'):
                lines = [
                    {'account_code': '1121', 'debit': amt, 'credit': 0.0, 'description': f"Bank Deposit {desc}", 'date': str(dval)},
                    {'account_code': '1111', 'debit': 0.0, 'credit': amt, 'description': f"Cash", 'date': str(dval)}
                ]
            else:
                exp_code = exp_branch or '5470'
                lines = [
                    {'account_code': exp_code, 'debit': amt, 'credit': 0.0, 'description': f"Expense {desc}", 'date': str(dval)},
                    {'account_code': cash_code, 'debit': 0.0, 'credit': amt, 'description': f"Cash/Bank", 'date': str(dval)}
                ]
            entries.append({'date': str(dval), 'description': desc or typ, 'source_ref_type': 'batch', 'source_ref_id': f"{int(amt*100)}-{typ[:4]}", 'lines': lines})
        if errors and not entries:
            return jsonify({'ok': False, 'error': '; '.join(errors), 'errors': errors}), 400
        created = []
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
         .outerjoin(JournalEntry, JournalLine.journal_id == JournalEntry.id) \
         .filter(or_(JournalLine.id.is_(None), and_(JournalLine.line_date <= today, JournalEntry.status == 'posted'))) \
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
