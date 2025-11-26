from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from models import get_saudi_now
from sqlalchemy import func
from extensions import db
from models import Account, JournalEntry, JournalLine, SalesInvoice, PurchaseInvoice, ExpenseInvoice, Salary, Payment, LedgerEntry

bp = Blueprint('financials', __name__, url_prefix='/financials')


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
            '1010': '1110',
            '1020': '1120',
            '1.1.4.2': '1030',
            '3010': '3000',
            '3100': '3000',
            '5060': '5190',
            '4040': '5190'
        }
        # User-approved merges
        num_map.update({
            '1025': '1210',
            '5030': '5330',
            '5320': '5330'
        })
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
        try:
            target_comm = Account.query.filter(Account.code == '5190').first()
            if not target_comm:
                target_comm = Account(code='5190', name='عمولات بنكية', type='EXPENSE')
                db.session.add(target_comm); db.session.flush()
            # Merge any expense accounts named as bank fees synonyms into 5190
            syn_names = ['%عمولات بنكية%', '%مصاريف بنكية%', '%مصروفات بنكية%']
            cand = Account.query.filter(Account.type == 'EXPENSE').filter(
                (Account.name.ilike(syn_names[0])) | (Account.name.ilike(syn_names[1])) | (Account.name.ilike(syn_names[2]))
            ).all()
            for acc in cand:
                if acc.code == '5190':
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
    period = request.args.get('period', 'this_year')
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    branch = (request.args.get('branch') or 'all').strip()
    start_date, end_date = period_range(period)
    try:
        if (period or '') == 'custom' and start_arg and end_arg:
            start_date = datetime.strptime(start_arg, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_arg, '%Y-%m-%d').date()
    except Exception:
        pass

    try:
        from app.routes import CHART_OF_ACCOUNTS
        for code, meta in (CHART_OF_ACCOUNTS or {}).items():
            if not Account.query.filter_by(code=code).first():
                db.session.add(Account(code=code, name=meta.get('name',''), type=meta.get('type','EXPENSE')))
        db.session.commit()
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
        inv_codes = ['1210','1025']
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
            .filter(Account.code == '1220') \
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
        .filter(Account.code == '6100')
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
        .filter(Account.code == '4100')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    rev_pi = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4110')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    rev_keeta = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4120')
        .filter(JournalLine.line_date.between(start_date, end_date)).scalar() or 0)
    rev_hunger = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.code == '4130')
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
    ca_codes = {'1110','1120','1210','1310','6200','1030','1050'}
    cl_codes = {'2110','2130','6100'}
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

    hide_codes = {'AR','AP','CASH','BANK','VAT_IN','VAT_OUT','VAT_SETTLE','COGS','4040','4.1.2.1','4.1.2.2'}
    rows = [r for r in rows if (r.code not in hide_codes) and not (float(r.debit or 0) == 0.0 and float(r.credit or 0) == 0.0 and (r.code in {'1010','1020'}))]

    total_debit = float(sum([float(r.debit or 0) for r in rows]))
    total_credit = float(sum([float(r.credit or 0) for r in rows]))
    type_totals = {}
    for r in rows:
        t = (getattr(r, 'type', None) or '').upper()
        d = float(r.debit or 0); c = float(r.credit or 0)
        if t not in type_totals:
            type_totals[t] = {'debit': 0.0, 'credit': 0.0}
        type_totals[t]['debit'] += d
        type_totals[t]['credit'] += c

    return render_template('financials/trial_balance.html', data={
        'date': asof, 'rows': rows, 'total_debit': total_debit, 'total_credit': total_credit,
        'type_totals': type_totals
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

    ca_codes = {'1000','1010','1050','1020','1025','1030'}
    cl_codes = {'2000','2020'}
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
        vat_out_code = '6100'
        total_before = float(inv.total_before_tax or 0)
        discount_amt = float(inv.discount_amount or 0)
        tax_amt = float(inv.tax_amount or 0)
        net_rev = max(0.0, total_before - discount_amt)
        total_inc_tax = float(inv.total_after_tax_discount or (net_rev + tax_amt))
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
        total_inc_tax = float(inv.total_after_tax_discount or (total_before + tax_amt))
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
        total_inc_tax = float(inv.total_after_tax_discount or (total_before + tax_amt))
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
