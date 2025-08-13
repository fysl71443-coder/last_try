from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from sqlalchemy import func
from extensions import db
from models import Account, LedgerEntry, SalesInvoice, PurchaseInvoice, ExpenseInvoice, Salary, Payment

bp = Blueprint('financials', __name__, url_prefix='/financials')


def period_range(kind: str):
    today = datetime.utcnow().date()
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

    # Helper to sum by account type
    def sum_type(acc_type):
        return float(db.session.query(func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0))
            .join(Account, LedgerEntry.account_id == Account.id)
            .filter(Account.type == acc_type)
            .filter(LedgerEntry.date.between(start_date, end_date))
            .scalar() or 0)

    # For P&L, revenue accounts are usually credit-nature => use (credit - debit)
    def sum_revenue():
        return float(db.session.query(func.coalesce(func.sum(LedgerEntry.credit - LedgerEntry.debit), 0))
            .join(Account, LedgerEntry.account_id == Account.id)
            .filter(Account.type.in_(['REVENUE', 'OTHER_INCOME']))
            .filter(LedgerEntry.date.between(start_date, end_date))
            .scalar() or 0)

    def sum_expense(types):
        return float(db.session.query(func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0))
            .join(Account, LedgerEntry.account_id == Account.id)
            .filter(Account.type.in_(types))
            .filter(LedgerEntry.date.between(start_date, end_date))
            .scalar() or 0)

    revenue = sum_revenue()
    cogs = sum_expense(['COGS'])
    operating_expenses = sum_expense(['EXPENSE'])
    other_income = 0.0
    other_expenses = sum_expense(['OTHER_EXPENSE'])
    tax = sum_expense(['TAX'])

    # Fallback if ledger is empty: derive from existing invoices (approximation)
    if revenue == 0 and cogs == 0 and operating_expenses == 0 and other_income == 0 and other_expenses == 0 and tax == 0:
        revenue = float(db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0))
            .filter(SalesInvoice.date.between(start_date, end_date)).scalar() or 0)
        cogs = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax), 0))
            .filter(PurchaseInvoice.date.between(start_date, end_date)).scalar() or 0)
        operating_expenses = float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0))
            .filter(ExpenseInvoice.date.between(start_date, end_date)).scalar() or 0)
        # VAT not included here; income tax assumed 0 for now
        tax = 0.0

    gross_profit = revenue - cogs
    operating_profit = gross_profit - operating_expenses
    net_profit_before_tax = operating_profit + other_income - other_expenses
    net_profit_after_tax = net_profit_before_tax - tax

    return render_template('financials/income_statement.html', data={
        'period': period, 'start_date': start_date, 'end_date': end_date,
        'revenue': revenue, 'cogs': cogs, 'gross_profit': gross_profit,
        'operating_expenses': operating_expenses, 'operating_profit': operating_profit,
        'other_income': other_income, 'other_expenses': other_expenses,
        'net_profit_before_tax': net_profit_before_tax, 'tax': tax,
        'net_profit_after_tax': net_profit_after_tax
    })

@bp.route('/balance_sheet')
def balance_sheet():
    asof_str = request.args.get('date')
    today = datetime.utcnow().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today

    # Assets balance: debit - credit
    assets = float(db.session.query(func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0))
        .join(Account, LedgerEntry.account_id == Account.id)
        .filter(Account.type == 'ASSET', LedgerEntry.date <= asof)
        .scalar() or 0)

    # Liabilities balance: credit - debit
    liabilities = float(db.session.query(func.coalesce(func.sum(LedgerEntry.credit - LedgerEntry.debit), 0))
        .join(Account, LedgerEntry.account_id == Account.id)
        .filter(Account.type == 'LIABILITY', LedgerEntry.date <= asof)
        .scalar() or 0)

    # Equity (computed) = Assets - Liabilities (simple model)
    equity = assets - liabilities

    return render_template('financials/balance_sheet.html', data={
        'date': asof, 'assets': assets, 'liabilities': liabilities, 'equity': equity
    })


@bp.route('/trial_balance')
def trial_balance():
    asof_str = request.args.get('date')
    today = datetime.utcnow().date()
    try:
        asof = datetime.strptime(asof_str, '%Y-%m-%d').date() if asof_str else today
    except Exception:
        asof = today

    rows = db.session.query(
        Account.code.label('code'),
        Account.name.label('name'),
        func.coalesce(func.sum(LedgerEntry.debit), 0).label('debit'),
        func.coalesce(func.sum(LedgerEntry.credit), 0).label('credit'),
    ).join(LedgerEntry, LedgerEntry.account_id == Account.id) \
     .filter(LedgerEntry.date <= asof) \
     .group_by(Account.id) \
     .order_by(Account.code.asc()).all()

    total_debit = float(sum([float(r.debit or 0) for r in rows]))
    total_credit = float(sum([float(r.credit or 0) for r in rows]))

    return render_template('financials/trial_balance.html', data={
        'date': asof, 'rows': rows, 'total_debit': total_debit, 'total_credit': total_credit
    })

