import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from extensions import db, csrf
from models import Account, LedgerEntry, Employee, JournalEntry, JournalLine, JournalAudit, get_saudi_now

bp = Blueprint('journal', __name__, url_prefix='/journal')

def _can(screen, perm, branch_scope=None):
    try:
        if getattr(current_user,'role','') == 'admin':
            return True
        from app import can_perm
        return can_perm(screen, perm, branch_scope)
    except Exception:
        return False

def _ensure_accounts():
    try:
        from app.routes import CHART_OF_ACCOUNTS
        keys = list((CHART_OF_ACCOUNTS or {}).keys())
        existing = {code for (code,) in db.session.query(Account.code).filter(Account.code.in_(keys)).all()}
        missing = []
        for code, meta in (CHART_OF_ACCOUNTS or {}).items():
            if code not in existing:
                missing.append((code, meta))
        if missing:
            for code, meta in missing:
                db.session.add(Account(code=code, name=meta.get('name',''), type=meta.get('type','EXPENSE')))
            db.session.commit()
    except Exception:
        pass

def _ensure_journal_link_columns():
    try:
        from sqlalchemy import inspect, text
        insp = inspect(db.engine)
        cols = {c.get('name') for c in insp.get_columns('journal_entries')}
        stmts = []
        if 'invoice_id' not in cols:
            stmts.append(text('ALTER TABLE journal_entries ADD COLUMN invoice_id INTEGER'))
        if 'invoice_type' not in cols:
            stmts.append(text("ALTER TABLE journal_entries ADD COLUMN invoice_type VARCHAR(20)"))
        if 'salary_id' not in cols:
            stmts.append(text('ALTER TABLE journal_entries ADD COLUMN salary_id INTEGER'))
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

def _gen_number():
    d = get_saudi_now().date()
    prefix = f"JE-{d.strftime('%Y%m')}"
    seq = 1
    last = JournalEntry.query.filter(JournalEntry.entry_number.like(f"{prefix}-%")).order_by(JournalEntry.entry_number.desc()).first()
    if last:
        try:
            seq = int(str(last.entry_number).rsplit('-',1)[-1]) + 1
        except Exception:
            seq = 1
    return f"{prefix}-{seq:04d}"

def create_missing_journal_entries():
    _ensure_journal_link_columns()
    _ensure_accounts()
    created = []
    errors = []
    from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice
    from sqlalchemy import func
    def _acc_by_code(code: str):
        try:
            from app.routes import CHART_OF_ACCOUNTS
        except Exception:
            CHART_OF_ACCOUNTS = {}
        c = (code or '').strip().upper()
        a = Account.query.filter(func.lower(Account.code) == c.lower()).first()
        if not a:
            meta = CHART_OF_ACCOUNTS.get(c, {'name':'','type':'EXPENSE'})
            a = Account(code=c, name=meta.get('name','') or c, type=meta.get('type','EXPENSE'))
            db.session.add(a); db.session.flush()
        return a
    def _cash_or_bank(pm: str):
        p = (pm or 'CASH').strip().upper()
        if p in ('BANK','CARD','VISA','MASTERCARD','TRANSFER'):
            return _acc_by_code('1120')
        return _acc_by_code('1110')
    def _has_journal(inv_id: int, inv_type: str, inv_number: str):
        try:
            exists = JournalEntry.query.filter(
                JournalEntry.invoice_id == int(inv_id),
                JournalEntry.invoice_type == (inv_type or '').strip().lower()
            ).first()
            if exists:
                return True
        except Exception:
            pass
        try:
            if inv_number:
                exists2 = JournalEntry.query.filter(JournalEntry.description.ilike(f"%{inv_number}%")).first()
                if exists2:
                    return True
        except Exception:
            pass
        return False
        sales = []
        try:
            sales = SalesInvoice.query.all()
        except Exception:
            sales = []
        for inv in sales:
            inv_num = getattr(inv, 'invoice_number', None)
            if _has_journal(inv.id, 'sales', inv_num):
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                discount_amt = float(inv.discount_amount or 0)
                tax_amt = float(inv.tax_amount or 0)
                net_rev = max(0.0, total_before - discount_amt)
                total_inc_tax = float(inv.total_after_tax_discount or (net_rev + tax_amt))
                cust = (getattr(inv, 'customer_name', '') or '').strip().lower()
                def _grp(n: str):
                    s = (n or '').lower()
                    if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                        return 'hunger'
                    if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                        return 'keeta'
                    return ''
                grp = _grp(cust)
                if grp == 'keeta':
                    ar_acc = _acc_by_code('1130')
                    rev_code = '4120'
                elif grp == 'hunger':
                    ar_acc = _acc_by_code('1140')
                    rev_code = '4130'
                else:
                    ar_acc = _acc_by_code('1050')
                    rev_code = '4110' if (inv.branch or '') == 'place_india' else '4100'
                rev_acc = _acc_by_code(rev_code)
                vat_out_acc = _acc_by_code('6100')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(
                    entry_number=f"JE-SAL-{inv_num}",
                    date=(inv.date or get_saudi_now().date()),
                    branch_code=getattr(inv, 'branch', None),
                    description=f"Sales {inv_num}",
                    status='posted',
                    total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax,
                    total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax,
                    created_by=getattr(current_user,'id',None),
                    posted_by=getattr(current_user,'id',None),
                    invoice_id=int(inv.id),
                    invoice_type='sales'
                )
                db.session.add(je); db.session.flush()
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ar_acc.id, debit=total_inc_tax, credit=0, description=f"AR {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                if net_rev > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=rev_acc.id, debit=0, credit=net_rev, description=f"Revenue {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=vat_out_acc.id, debit=0, credit=tax_amt, description=f"VAT Output {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=cash_acc.id, debit=total_inc_tax, credit=0, description=f"Receipt {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=ar_acc.id, debit=0, credit=total_inc_tax, description=f"Clear AR {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                created.append(f"sales:{inv.id}:{inv_num}")
            except Exception as e:
                errors.append(f"sales:{inv.id}:{inv_num}:{str(e)}")
        purchases = []
        try:
            purchases = PurchaseInvoice.query.all()
        except Exception:
            purchases = []
        for inv in purchases:
            inv_num = getattr(inv, 'invoice_number', None)
            if _has_journal(inv.id, 'purchase', inv_num):
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                tax_amt = float(inv.tax_amount or 0)
                total_inc_tax = float(inv.total_after_tax_discount or (total_before + tax_amt))
                exp_acc = _acc_by_code('1210')
                vat_in_acc = _acc_by_code('6200')
                ap_acc = _acc_by_code('2110')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(
                    entry_number=f"JE-PUR-{inv_num}",
                    date=(inv.date or get_saudi_now().date()),
                    branch_code=None,
                    description=f"Purchase {inv_num}",
                    status='posted',
                    total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax,
                    total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax,
                    created_by=getattr(current_user,'id',None),
                    posted_by=getattr(current_user,'id',None),
                    invoice_id=int(inv.id),
                    invoice_type='purchase'
                )
                db.session.add(je); db.session.flush()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Purchase", line_date=(inv.date or get_saudi_now().date())))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=(inv.date or get_saudi_now().date())))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=(inv.date or get_saudi_now().date())))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=(inv.date or get_saudi_now().date())))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=(inv.date or get_saudi_now().date())))
                created.append(f"purchase:{inv.id}:{inv_num}")
            except Exception as e:
                errors.append(f"purchase:{inv.id}:{inv_num}:{str(e)}")
        expenses = []
        try:
            expenses = ExpenseInvoice.query.all()
        except Exception:
            expenses = []
        for inv in expenses:
            inv_num = getattr(inv, 'invoice_number', None)
            if _has_journal(inv.id, 'expense', inv_num):
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                tax_amt = float(inv.tax_amount or 0)
                total_inc_tax = float(inv.total_after_tax_discount or (total_before + tax_amt))
                exp_acc = _acc_by_code('5100')
                vat_in_acc = _acc_by_code('6200')
                ap_acc = _acc_by_code('2110')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(
                    entry_number=f"JE-EXP-{inv_num}",
                    date=(inv.date or get_saudi_now().date()),
                    branch_code=None,
                    description=f"Expense {inv_num}",
                    status='posted',
                    total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax,
                    total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax,
                    created_by=getattr(current_user,'id',None),
                    posted_by=getattr(current_user,'id',None),
                    invoice_id=int(inv.id),
                    invoice_type='expense'
                )
                db.session.add(je); db.session.flush()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Expense", line_date=(inv.date or get_saudi_now().date())))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=(inv.date or get_saudi_now().date())))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=(inv.date or get_saudi_now().date())))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=(inv.date or get_saudi_now().date())))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=(inv.date or get_saudi_now().date())))
                created.append(f"expense:{inv.id}:{inv_num}")
            except Exception as e:
                errors.append(f"expense:{inv.id}:{inv_num}:{str(e)}")
    try:
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return created, errors

@csrf.exempt
@bp.route('/backfill_missing', methods=['GET','POST'])
@login_required
def backfill_missing():
    try:
        created, errors = create_missing_journal_entries()
        try:
            msg = f"Created {len(created)} journal entries; Errors {len(errors)}"
            flash(msg, 'success' if not errors else 'warning')
        except Exception:
            pass
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(f"Backfill failed: {e}", 'danger')
    return render_template('journal_entries.html', entries=JournalEntry.query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).limit(50).all(), page=1, pages=1, total=JournalEntry.query.count(), accounts=[], employees=[], branch='all', mode='list')

def create_missing_journal_entries_for(kind: str):
    _ensure_journal_link_columns()
    _ensure_accounts()
    created = []
    errors = []
    kind = (kind or '').strip().lower()
    from sqlalchemy import func
    def _acc_by_code(code: str):
        try:
            from app.routes import CHART_OF_ACCOUNTS
        except Exception:
            CHART_OF_ACCOUNTS = {}
        c = (code or '').strip().upper()
        a = Account.query.filter(func.lower(Account.code) == c.lower()).first()
        if not a:
            meta = CHART_OF_ACCOUNTS.get(c, {'name':'','type':'EXPENSE'})
            a = Account(code=c, name=meta.get('name','') or c, type=meta.get('type','EXPENSE'))
            db.session.add(a); db.session.flush()
        return a
    def _cash_or_bank(pm: str):
        p = (pm or 'CASH').strip().upper()
        if p in ('BANK','CARD','VISA','MASTERCARD','TRANSFER'):
            return _acc_by_code('1120')
        return _acc_by_code('1110')
    def _has_journal(inv_id: int, inv_type: str, inv_number: str):
        try:
            exists = JournalEntry.query.filter(
                JournalEntry.invoice_id == int(inv_id),
                JournalEntry.invoice_type == (inv_type or '').strip().lower()
            ).first()
            if exists:
                return True
        except Exception:
            pass
        try:
            if inv_number:
                exists2 = JournalEntry.query.filter(JournalEntry.description.ilike(f"%{inv_number}%")).first()
                if exists2:
                    return True
        except Exception:
            pass
        return False
    if kind == 'all':
        kinds = ['salaries','expenses','purchases','sales']
        for k in kinds:
            c, e = create_missing_journal_entries_for(k)
            created.extend(c)
            errors.extend(e)
    elif kind == 'sales':
        from models import SalesInvoice
        rows = []
        try:
            rows = SalesInvoice.query.all()
        except Exception:
            rows = []
        for inv in rows:
            inv_num = getattr(inv, 'invoice_number', None)
            if _has_journal(inv.id, 'sales', inv_num):
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                discount_amt = float(inv.discount_amount or 0)
                tax_amt = float(inv.tax_amount or 0)
                net_rev = max(0.0, total_before - discount_amt)
                total_inc_tax = float(inv.total_after_tax_discount or (net_rev + tax_amt))
                cust = (getattr(inv, 'customer_name', '') or '').strip().lower()
                def _grp(n: str):
                    s = (n or '').lower()
                    if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                        return 'hunger'
                    if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                        return 'keeta'
                    return ''
                grp = _grp(cust)
                if grp == 'keeta':
                    ar_acc = _acc_by_code('1130')
                    rev_code = '4120'
                elif grp == 'hunger':
                    ar_acc = _acc_by_code('1140')
                    rev_code = '4130'
                else:
                    ar_acc = _acc_by_code('1050')
                    rev_code = '4110' if (inv.branch or '') == 'place_india' else '4100'
                rev_acc = _acc_by_code(rev_code)
                vat_out_acc = _acc_by_code('6100')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(entry_number=f"JE-SAL-{inv_num}", date=(inv.date or get_saudi_now().date()), branch_code=getattr(inv, 'branch', None), description=f"Sales {inv_num}", status='posted', total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax, total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=int(inv.id), invoice_type='sales')
                db.session.add(je); db.session.flush()
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ar_acc.id, debit=total_inc_tax, credit=0, description=f"AR {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                if net_rev > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=rev_acc.id, debit=0, credit=net_rev, description=f"Revenue {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=vat_out_acc.id, debit=0, credit=tax_amt, description=f"VAT Output {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=cash_acc.id, debit=total_inc_tax, credit=0, description=f"Receipt {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=ar_acc.id, debit=0, credit=total_inc_tax, description=f"Clear AR {inv_num}", line_date=(inv.date or get_saudi_now().date())))
                created.append(f"sales:{inv.id}:{inv_num}")
            except Exception as e:
                errors.append(f"sales:{inv.id}:{inv_num}:{str(e)}")
    elif kind == 'purchases':
        from models import PurchaseInvoice
        rows = []
        try:
            rows = PurchaseInvoice.query.all()
        except Exception:
            rows = []
        for inv in rows:
            inv_num = getattr(inv, 'invoice_number', None)
            if _has_journal(inv.id, 'purchase', inv_num):
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                tax_amt = float(inv.tax_amount or 0)
                total_inc_tax = float(inv.total_after_tax_discount or (total_before + tax_amt))
                exp_acc = _acc_by_code('1210')
                vat_in_acc = _acc_by_code('6200')
                ap_acc = _acc_by_code('2110')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(entry_number=f"JE-PUR-{inv_num}", date=(inv.date or get_saudi_now().date()), branch_code=None, description=f"Purchase {inv_num}", status='posted', total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax, total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=int(inv.id), invoice_type='purchase')
                db.session.add(je); db.session.flush()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Purchase", line_date=(inv.date or get_saudi_now().date())))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=(inv.date or get_saudi_now().date())))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=(inv.date or get_saudi_now().date())))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=(inv.date or get_saudi_now().date())))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=(inv.date or get_saudi_now().date())))
                created.append(f"purchase:{inv.id}:{inv_num}")
            except Exception as e:
                errors.append(f"purchase:{inv.id}:{inv_num}:{str(e)}")
    elif kind == 'expenses':
        from models import ExpenseInvoice
        rows = []
        try:
            rows = ExpenseInvoice.query.all()
        except Exception:
            rows = []
        for inv in rows:
            inv_num = getattr(inv, 'invoice_number', None)
            if _has_journal(inv.id, 'expense', inv_num):
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                tax_amt = float(inv.tax_amount or 0)
                total_inc_tax = float(inv.total_after_tax_discount or (total_before + tax_amt))
                exp_acc = _acc_by_code('5100')
                vat_in_acc = _acc_by_code('6200')
                ap_acc = _acc_by_code('2110')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(entry_number=f"JE-EXP-{inv_num}", date=(inv.date or get_saudi_now().date()), branch_code=None, description=f"Expense {inv_num}", status='posted', total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax, total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=int(inv.id), invoice_type='expense')
                db.session.add(je); db.session.flush()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Expense", line_date=(inv.date or get_saudi_now().date())))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=(inv.date or get_saudi_now().date())))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=(inv.date or get_saudi_now().date())))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=(inv.date or get_saudi_now().date())))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=(inv.date or get_saudi_now().date())))
                created.append(f"expense:{inv.id}:{inv_num}")
            except Exception as e:
                errors.append(f"expense:{inv.id}:{inv_num}:{str(e)}")
    elif kind in ('salaries','payroll'):
        from models import Salary
        rows = []
        try:
            rows = Salary.query.all()
        except Exception:
            rows = []
        for sal in rows:
            try:
                exists = JournalEntry.query.filter(JournalEntry.salary_id == int(sal.id)).first()
                if exists:
                    continue
            except Exception:
                exists = None
            try:
                total = float(sal.total_salary or 0)
                sal_exp = _acc_by_code('5310')
                sal_pay = _acc_by_code('2130')
                je = JournalEntry(entry_number=f"JE-SAL-{sal.year}{int(sal.month):02d}-{int(sal.employee_id)}", date=get_saudi_now().date(), branch_code=None, description=f"Salary accrual {int(sal.employee_id)}", status='posted', total_debit=total, total_credit=total, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), salary_id=int(sal.id))
                db.session.add(je); db.session.flush()
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=sal_exp.id, debit=total, credit=0, description='Salary expense', line_date=get_saudi_now().date()))
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=sal_pay.id, debit=0, credit=total, description='Salaries payable', line_date=get_saudi_now().date(), employee_id=int(sal.employee_id)))
                created.append(f"salary:{sal.id}")
            except Exception as e:
                errors.append(f"salary:{getattr(sal,'id',None)}:{str(e)}")
    try:
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return created, errors

@csrf.exempt
@bp.route('/backfill_missing/<kind>', methods=['POST','GET'])
@login_required
def backfill_missing_kind(kind):
    created = []
    errors = []
    try:
        created, errors = create_missing_journal_entries_for(kind)
        try:
            msg = f"Created {len(created)} journal entries; Errors {len(errors)}"
            flash(msg, 'success' if not errors else 'warning')
        except Exception:
            pass
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(str(e) or 'Backfill failed', 'danger')
    return render_template('journal_entries.html', entries=JournalEntry.query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).limit(50).all(), page=1, pages=1, total=JournalEntry.query.count(), accounts=[], employees=[], branch='all', mode='list')

@csrf.exempt
@bp.route('/backfill_missing_all', methods=['GET'])
@login_required
def backfill_missing_all():
    created = []
    errors = []
    try:
        created, errors = create_missing_journal_entries_for('all')
        try:
            msg = f"Created {len(created)} journal entries; Errors {len(errors)}"
            flash(msg, 'success' if not errors else 'warning')
        except Exception:
            pass
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(str(e) or 'Backfill failed', 'danger')
    return redirect(url_for('journal.list_entries'))

@csrf.exempt
@bp.route('/remap_sales_channels', methods=['POST','GET'])
@login_required
def remap_sales_channels():
    updated = 0
    errors = []
    try:
        from models import SalesInvoice
        rows = JournalEntry.query.filter(JournalEntry.invoice_type == 'sales').all()
        for je in rows:
            try:
                inv = SalesInvoice.query.get(int(getattr(je,'invoice_id',0)))
            except Exception:
                inv = None
            cust = (getattr(inv,'customer_name','') or '').strip().lower() if inv else ''
            def _grp(n: str):
                s = (n or '').lower()
                if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                    return 'hunger'
                if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                    return 'keeta'
                return ''
            grp = _grp(cust)
            try:
                if grp == 'keeta':
                    rev_acc = Account.query.filter(Account.code=='4120').first() or _acc_by_code('4120')
                    ar_acc = Account.query.filter(Account.code=='1130').first() or _acc_by_code('1130')
                elif grp == 'hunger':
                    rev_acc = Account.query.filter(Account.code=='4130').first() or _acc_by_code('4130')
                    ar_acc = Account.query.filter(Account.code=='1140').first() or _acc_by_code('1140')
                else:
                    rev_acc = None
                    ar_acc = None
                # update revenue line
                if rev_acc:
                    JournalLine.query.filter(JournalLine.journal_id==je.id, JournalLine.credit>0).update({JournalLine.account_id: rev_acc.id})
                # update AR line
                if ar_acc:
                    JournalLine.query.filter(JournalLine.journal_id==je.id, JournalLine.debit>0, JournalLine.description.ilike('%AR%')).update({JournalLine.account_id: ar_acc.id})
                db.session.flush()
                updated += 1
            except Exception as e:
                errors.append(str(e))
        db.session.commit()
        flash(f"تم تحديث {updated} قيود مبيعات حسب القناة", 'success')
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(str(e) or 'Remap failed', 'danger')
    return redirect(url_for('journal.list_entries'))

@csrf.exempt
@bp.route('/', methods=['GET'])
@login_required
def list_entries():
    if not _can('journal','view'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('dashboard'))
    _ensure_journal_link_columns()
    _ensure_accounts()
    q = (request.args.get('q') or '').strip()
    branch = (request.args.get('branch') or '').strip() or 'all'
    entry_number = (request.args.get('entry_number') or '').strip()
    sd = (request.args.get('start_date') or '').strip()
    ed = (request.args.get('end_date') or '').strip()
    user_id = request.args.get('user_id', type=int)
    page = int(request.args.get('page') or 1)
    per_page_arg = (request.args.get('per_page') or '').strip()
    if per_page_arg.lower() == 'all':
        per_page = 100000
    else:
        try:
            per_page = int(per_page_arg or 50)
        except Exception:
            per_page = 50
        per_page = max(1, min(500, per_page))
    query = JournalEntry.query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc())
    if branch and branch != 'all':
        query = query.filter(JournalEntry.branch_code == branch)
    if q:
        query = query.filter(JournalEntry.description.ilike(f"%{q}%"))
    if entry_number:
        query = query.filter(JournalEntry.entry_number.ilike(f"%{entry_number}%"))
    if sd:
        from datetime import datetime as _dt
        try:
            sdt = _dt.strptime(sd, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date >= sdt)
        except Exception:
            pass
    if ed:
        from datetime import datetime as _dt
        try:
            edt = _dt.strptime(ed, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date <= edt)
        except Exception:
            pass
    if user_id:
        query = query.filter((JournalEntry.created_by == user_id) | (JournalEntry.posted_by == user_id) | (JournalEntry.updated_by == user_id))
    pag = query.paginate(page=page, per_page=per_page, error_out=False)
    accounts = Account.query.order_by(Account.code.asc()).all()
    employees = []
    return render_template('journal_entries.html', entries=pag.items, page=pag.page, pages=pag.pages, total=pag.total, accounts=[], employees=employees, branch=branch, mode='list')

@bp.route('/print/all', methods=['GET'])
@login_required
def print_all():
    if not _can('journal','print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('journal.list_entries'))
    _ensure_journal_link_columns()
    _ensure_accounts()
    q = (request.args.get('q') or '').strip()
    branch = (request.args.get('branch') or '').strip() or 'all'
    sd = (request.args.get('start_date') or '').strip()
    ed = (request.args.get('end_date') or '').strip()
    user_id = request.args.get('user_id', type=int)
    query = JournalEntry.query.order_by(JournalEntry.date.asc(), JournalEntry.id.asc())
    if branch and branch != 'all':
        query = query.filter(JournalEntry.branch_code == branch)
    if q:
        query = query.filter(JournalEntry.description.ilike(f"%{q}%"))
    if sd:
        try:
            sdt = datetime.strptime(sd, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date >= sdt)
        except Exception:
            pass
    if ed:
        try:
            edt = datetime.strptime(ed, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date <= edt)
        except Exception:
            pass
    if user_id:
        query = query.filter((JournalEntry.created_by == user_id) | (JournalEntry.posted_by == user_id) | (JournalEntry.updated_by == user_id))
    entries = query.all()
    return render_template('journal_print_all.html', entries=entries, branch=branch, q=q, sd=sd, ed=ed)

@bp.route('/print/all/pdf', methods=['GET'])
@login_required
def print_all_pdf():
    if not _can('journal','print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('journal.list_entries'))
    _ensure_journal_link_columns()
    _ensure_accounts()
    q = (request.args.get('q') or '').strip()
    branch = (request.args.get('branch') or '').strip() or 'all'
    sd = (request.args.get('start_date') or '').strip()
    ed = (request.args.get('end_date') or '').strip()
    user_id = request.args.get('user_id', type=int)
    limit_arg = (request.args.get('limit') or '').strip().lower()
    query = JournalEntry.query.order_by(JournalEntry.date.asc(), JournalEntry.id.asc())
    if branch and branch != 'all':
        query = query.filter(JournalEntry.branch_code == branch)
    if q:
        query = query.filter(JournalEntry.description.ilike(f"%{q}%"))
    if sd:
        try:
            sdt = datetime.strptime(sd, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date >= sdt)
        except Exception:
            pass
    if ed:
        try:
            edt = datetime.strptime(ed, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date <= edt)
        except Exception:
            pass
    if user_id:
        query = query.filter((JournalEntry.created_by == user_id) | (JournalEntry.posted_by == user_id) | (JournalEntry.updated_by == user_id))
    if limit_arg and limit_arg != 'all':
        try:
            query = query.limit(int(limit_arg))
        except Exception:
            query = query.limit(200)
    else:
        query = query.limit(200)  # افتراضي لتسريع الطباعة
    entries = query.all()
    try:
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        import io
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title="Journal Entries")
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("قيود اليومية", styles['Title']))
        meta = []
        meta.append(f"الفرع: {branch}")
        if q: meta.append(f"بحث: {q}")
        if sd: meta.append(f"من: {sd}")
        if ed: meta.append(f"إلى: {ed}")
        elements.append(Paragraph(" ".join(meta), styles['Normal']))
        elements.append(Spacer(1, 6))
        for je in entries:
            block = []
            block.append(Paragraph(f"رقم القيد: {je.entry_number}", styles['Heading3']))
            block.append(Paragraph(f"التاريخ: {je.date}", styles['Normal']))
            block.append(Paragraph(f"الفرع: {je.branch_code or '-'}", styles['Normal']))
            block.append(Paragraph(f"الحالة: {je.status}", styles['Normal']))
            block.append(Paragraph(f"الوصف: {je.description}", styles['Normal']))
            data = [["#","الحساب","الوصف","مركز تكلفة","تاريخ السطر","مدين","دائن"]]
            for ln in je.lines:
                try:
                    acc_label = f"{ln.account.code} – {ln.account.name}"
                except Exception:
                    acc_label = str(getattr(ln, 'account_id', ''))
                data.append([
                    str(ln.line_no),
                    acc_label,
                    ln.description or '',
                    ln.cost_center or '-',
                    str(ln.line_date),
                    f"{float(ln.debit or 0):.2f}",
                    f"{float(ln.credit or 0):.2f}"
                ])
            tbl = Table(data, repeatRows=1)
            tbl.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ALIGN', (5,1), (6,-1), 'RIGHT'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
            ]))
            block.append(tbl)
            block.append(Spacer(1, 6))
            block.append(Paragraph(f"الإجمالي مدين: {float(je.total_debit or 0):.2f} — الإجمالي دائن: {float(je.total_credit or 0):.2f}", styles['Normal']))
            elements.append(KeepTogether(block))
            elements.append(Spacer(1, 10))
        doc.build(elements)
        buf.seek(0)
        from flask import send_file
        return send_file(buf, as_attachment=True, download_name="journal_entries.pdf", mimetype='application/pdf')
    except Exception as e:
        flash(f"PDF generation failed: {e}", 'danger')
        return redirect(url_for('journal.list_entries'))
@bp.route('/export/all', methods=['GET'])
@login_required
def export_all():
    if not _can('journal','print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('journal.list_entries'))
    _ensure_journal_link_columns()
    _ensure_accounts()
    q = (request.args.get('q') or '').strip()
    branch = (request.args.get('branch') or '').strip() or 'all'
    sd = (request.args.get('start_date') or '').strip()
    ed = (request.args.get('end_date') or '').strip()
    user_id = request.args.get('user_id', type=int)
    query = JournalEntry.query.order_by(JournalEntry.date.asc(), JournalEntry.id.asc())
    if branch and branch != 'all':
        query = query.filter(JournalEntry.branch_code == branch)
    if q:
        query = query.filter(JournalEntry.description.ilike(f"%{q}%"))
    if sd:
        try:
            sdt = datetime.strptime(sd, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date >= sdt)
        except Exception:
            pass
    if ed:
        try:
            edt = datetime.strptime(ed, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.date <= edt)
        except Exception:
            pass
    if user_id:
        query = query.filter((JournalEntry.created_by == user_id) | (JournalEntry.posted_by == user_id) | (JournalEntry.updated_by == user_id))
    entries = query.all()
    html = render_template('journal_print_all.html', entries=entries, branch=branch, q=q, sd=sd, ed=ed)
    headers = {
        'Content-Disposition': 'attachment; filename=journal_entries.xls'
    }
    return Response(html, mimetype='application/vnd.ms-excel', headers=headers)

@bp.route('/<int:jid>/delete', methods=['POST'])
@login_required
def delete_entry(jid):
    je = JournalEntry.query.get_or_404(jid)
    try:
        if not _can('journal','edit'):
            flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
            return redirect(url_for('journal.list_entries'))
    except Exception:
        pass
    try:
        from models import JournalLine, LedgerEntry
        JournalAudit.query.filter_by(journal_id=je.id).delete(synchronize_session=False)
        try:
            LedgerEntry.query.filter(LedgerEntry.description.ilike(f"JE {je.entry_number}%")).delete(synchronize_session=False)
        except Exception:
            try:
                LedgerEntry.query.filter(LedgerEntry.description.ilike(f"%{je.entry_number}%")).delete(synchronize_session=False)
            except Exception:
                pass
        try:
            if getattr(je, 'invoice_type', None) and getattr(je, 'invoice_id', None):
                inv_num = None
                itype = (je.invoice_type or '').strip().lower()
                if itype == 'sales':
                    try:
                        from models import SalesInvoice
                        inv = SalesInvoice.query.get(int(je.invoice_id))
                        inv_num = getattr(inv, 'invoice_number', None)
                    except Exception:
                        inv_num = None
                    if inv_num:
                        LedgerEntry.query.filter(LedgerEntry.description == f"Sales {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"VAT Output {inv_num}").delete(synchronize_session=False)
                elif itype == 'purchase':
                    try:
                        from models import PurchaseInvoice
                        inv = PurchaseInvoice.query.get(int(je.invoice_id))
                        inv_num = getattr(inv, 'invoice_number', None)
                    except Exception:
                        inv_num = None
                    if inv_num:
                        LedgerEntry.query.filter(LedgerEntry.description == f"Purchase {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"VAT Input {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"AP for {inv_num}").delete(synchronize_session=False)
                elif itype == 'expense':
                    try:
                        from models import ExpenseInvoice
                        inv = ExpenseInvoice.query.get(int(je.invoice_id))
                        inv_num = getattr(inv, 'invoice_number', None)
                    except Exception:
                        inv_num = None
                    if inv_num:
                        LedgerEntry.query.filter(LedgerEntry.description == f"Expense {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"VAT Input {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"AP for {inv_num}").delete(synchronize_session=False)
        except Exception:
            pass
        try:
            if getattr(je, 'salary_id', None):
                # Delete salary-related postings: payment and advance patterns
                try:
                    from models import Salary
                    sal = Salary.query.get(int(je.salary_id))
                except Exception:
                    sal = None
                if sal:
                    try:
                        emp_id = getattr(sal, 'employee_id', None)
                        yr = getattr(sal, 'year', None)
                        mo = getattr(sal, 'month', None)
                        if emp_id and yr and mo:
                            LedgerEntry.query.filter(LedgerEntry.description == f"PAY SAL {yr}-{mo} EMP {emp_id}").delete(synchronize_session=False)
                            LedgerEntry.query.filter(LedgerEntry.description == f"ADV EMP {emp_id} {yr}-{mo}").delete(synchronize_session=False)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            JournalLine.query.filter_by(journal_id=je.id).delete(synchronize_session=False)
        except Exception:
            pass
        db.session.delete(je)
        db.session.commit()
        flash('تم حذف القيد', 'success')
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        msg = str(e) if str(e) else 'تعذر حذف القيد'
        flash(msg, 'danger')
    return redirect(url_for('journal.list_entries'))

@csrf.exempt
@bp.route('/new', methods=['GET','POST'])
@login_required
def new_entry():
    if not _can('journal','add'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('journal.list_entries'))
    _ensure_accounts()
    accounts = []
    employees = []
    if request.method == 'GET':
        return render_template('journal_entries.html', mode='new', accounts=accounts, employees=employees, today=get_saudi_now().date())
    date_str = (request.form.get('date') or '').strip()
    branch = (request.form.get('branch') or '').strip() or None
    description = (request.form.get('description') or '').strip()
    if not description:
        flash('يرجى إدخال وصف القيد.', 'danger')
        return redirect(url_for('journal.new_entry'))
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else get_saudi_now().date()
    except Exception:
        d = get_saudi_now().date()
    if d > get_saudi_now().date() and getattr(current_user,'role','')!='admin':
        flash('لا يمكن حفظ قيد بتاريخ مستقبلي.', 'danger')
        return redirect(url_for('journal.new_entry'))
    lines = []
    idx = 0
    total_debit = 0.0
    total_credit = 0.0
    upload_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'instance', 'uploads', 'journal')
    try:
        os.makedirs(upload_dir, exist_ok=True)
    except Exception:
        pass
    while True:
        acc_id = request.form.get(f'lines-{idx}-account_id')
        if acc_id is None:
            break
        try:
            acc_id = int(acc_id)
        except Exception:
            idx += 1
            continue
        debit = float(request.form.get(f'lines-{idx}-debit') or 0)
        credit = float(request.form.get(f'lines-{idx}-credit') or 0)
        line_desc = (request.form.get(f'lines-{idx}-description') or '').strip()
        cost_center = (request.form.get(f'lines-{idx}-cost_center') or '').strip() or None
        line_date_str = (request.form.get(f'lines-{idx}-date') or '').strip()
        emp_id = request.form.get(f'lines-{idx}-employee_id')
        try:
            line_date = datetime.strptime(line_date_str, '%Y-%m-%d').date() if line_date_str else d
        except Exception:
            line_date = d
        if not line_desc:
            flash('يرجى إدخال وصف القيد.', 'danger')
            return redirect(url_for('journal.new_entry'))
        if debit and credit:
            flash('لا يسمح بوجود قيمة في المدين والدائن معاً.', 'danger')
            return redirect(url_for('journal.new_entry'))
        if (debit <= 0 and credit <= 0):
            idx += 1
            continue
        emp_id_val = None
        try:
            emp_id_val = int(emp_id) if emp_id else None
        except Exception:
            emp_id_val = None
        acc = Account.query.get(acc_id)
        code = (acc.code or '') if acc else ''
        if code in {'1.1.4.2','2030','2.1.2.1','2130','5320'} and not emp_id_val:
            flash('اختر الموظف عند استخدام حساب السلف أو الرواتب.', 'danger')
            return redirect(url_for('journal.new_entry'))
        f = request.files.get(f'lines-{idx}-attachment')
        attachment_path = None
        if f and getattr(f, 'filename', ''):
            fn = f.filename
            safe_name = f"{get_saudi_now().strftime('%Y%m%d%H%M%S')}_{idx}_{fn}"
            dest = os.path.join(upload_dir, safe_name)
            try:
                f.save(dest)
                attachment_path = dest
            except Exception:
                attachment_path = None
        lines.append({'account_id': acc_id, 'debit': debit, 'credit': credit, 'description': line_desc, 'cost_center': cost_center, 'line_date': line_date, 'employee_id': emp_id_val, 'attachment_path': attachment_path})
        total_debit += debit
        total_credit += credit
        idx += 1
    if round(total_debit,2) != round(total_credit,2) or total_debit <= 0:
        flash('لا يمكن حفظ القيد لأن مجموع المدين لا يساوي مجموع الدائن.', 'danger')
        return redirect(url_for('journal.new_entry'))
    je = JournalEntry(entry_number=_gen_number(), date=d, branch_code=branch, description=description, status='draft', total_debit=total_debit, total_credit=total_credit, created_by=getattr(current_user,'id',None))
    db.session.add(je)
    db.session.flush()
    for i, ln in enumerate(lines, start=1):
        db.session.add(JournalLine(journal_id=je.id, line_no=i, account_id=ln['account_id'], debit=ln['debit'], credit=ln['credit'], cost_center=ln['cost_center'], description=ln['description'], attachment_path=ln['attachment_path'], line_date=ln['line_date'], employee_id=ln['employee_id']))
    db.session.add(JournalAudit(journal_id=je.id, action='create', user_id=getattr(current_user,'id',None), before_json=None, after_json=json.dumps({'id': je.id, 'number': je.entry_number}, ensure_ascii=False)))
    db.session.commit()
    flash('تم إضافة القيد', 'success')
    return redirect(url_for('journal.edit_entry', jid=je.id))

@csrf.exempt
@bp.route('/employees', methods=['GET'])
@login_required
def employees_api():
    rows = db.session.query(Employee.id, Employee.full_name).order_by(Employee.full_name.asc()).all()
    return jsonify([{'id': rid, 'full_name': name} for (rid, name) in rows])

@csrf.exempt
@bp.route('/accounts', methods=['GET'])
@login_required
def accounts_api():
    rows = db.session.query(Account.id, Account.code, Account.name).order_by(Account.code.asc()).all()
    return jsonify([{'id': rid, 'code': code, 'name': name} for (rid, code, name) in rows])

@csrf.exempt
@bp.route('/<int:jid>', methods=['GET','POST'])
@login_required
def edit_entry(jid):
    je = JournalEntry.query.get_or_404(jid)
    if request.method == 'GET':
        if not _can('journal','view'):
            flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
            return redirect(url_for('journal.list_entries'))
        accounts = Account.query.order_by(Account.code.asc()).all()
        employees = Employee.query.order_by(Employee.full_name.asc()).all()
        return render_template('journal_entries.html', mode='edit', entry=je, accounts=accounts, employees=employees)
    if je.status == 'posted' and getattr(current_user,'role','')!='admin':
        flash("لا يمكنك تعديل قيد مرحل بدون صلاحية 'Modify Posted'.", 'danger')
        return redirect(url_for('journal.edit_entry', jid=je.id))
    if not _can('journal','edit'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('journal.edit_entry', jid=je.id))
    before = {'desc': je.description, 'date': str(je.date), 'total_debit': float(je.total_debit or 0), 'total_credit': float(je.total_credit or 0)}
    description = (request.form.get('description') or '').strip()
    if not description:
        flash('يرجى إدخال وصف القيد.', 'danger')
        return redirect(url_for('journal.edit_entry', jid=je.id))
    je.description = description
    je.updated_by = getattr(current_user,'id',None)
    db.session.add(JournalAudit(journal_id=je.id, action='edit', user_id=getattr(current_user,'id',None), before_json=json.dumps(before, ensure_ascii=False), after_json=json.dumps({'desc': je.description}, ensure_ascii=False)))
    db.session.commit()
    flash('تم حفظ التعديل', 'success')
    return redirect(url_for('journal.edit_entry', jid=je.id))

@csrf.exempt
@bp.route('/<int:jid>/post', methods=['POST'])
@login_required
def post_entry(jid):
    je = JournalEntry.query.get_or_404(jid)
    if not _can('journal','edit'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('journal.edit_entry', jid=je.id))
    if je.status == 'posted':
        flash('القيد مرحل مسبقاً', 'warning')
        return redirect(url_for('journal.edit_entry', jid=je.id))
    total_debit = 0.0
    total_credit = 0.0
    for ln in je.lines:
        total_debit += float(ln.debit or 0)
        total_credit += float(ln.credit or 0)
    if round(total_debit,2) != round(total_credit,2) or total_debit <= 0:
        flash('لا يمكن ترحيل القيد لأن مجموع المدين لا يساوي مجموع الدائن.', 'danger')
        return redirect(url_for('journal.edit_entry', jid=je.id))
    for ln in je.lines:
        acc = Account.query.get(ln.account_id)
        db.session.add(LedgerEntry(date=ln.line_date, account_id=acc.id, debit=ln.debit, credit=ln.credit, description=f'JE {je.entry_number} L{ln.line_no} {ln.description}'))
    je.status = 'posted'
    je.posted_by = getattr(current_user,'id',None)
    db.session.add(JournalAudit(journal_id=je.id, action='post', user_id=getattr(current_user,'id',None), before_json=None, after_json=json.dumps({'status': 'posted'}, ensure_ascii=False)))
    db.session.commit()
    flash('تم ترحيل القيد', 'success')
    return redirect(url_for('journal.edit_entry', jid=je.id))

@bp.route('/<int:jid>/print', methods=['GET'])
@login_required
def print_entry(jid):
    if not _can('journal','print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('journal.list_entries'))
    je = JournalEntry.query.get_or_404(jid)
    db.session.add(JournalAudit(journal_id=je.id, action='print', user_id=getattr(current_user,'id',None), before_json=None, after_json=None))
    db.session.commit()
    if (request.args.get('pdf') or '').strip() == '1':
        try:
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            import io
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []
            elements.append(Paragraph(f"Journal Entry: {je.entry_number}", styles['Title']))
            elements.append(Paragraph(f"Date: {je.date}", styles['Normal']))
            elements.append(Paragraph(f"Branch: {je.branch_code or '-'}", styles['Normal']))
            elements.append(Paragraph(f"Status: {je.status}", styles['Normal']))
            elements.append(Paragraph(f"Description: {je.description}", styles['Normal']))
            data = [["#","Account","Description","Cost Center","Line Date","Debit","Credit"]]
            for ln in je.lines:
                data.append([
                    str(ln.line_no),
                    f"{ln.account.code} – {ln.account.name}",
                    ln.description or '',
                    ln.cost_center or '-',
                    str(ln.line_date),
                    f"{float(ln.debit or 0):.2f}",
                    f"{float(ln.credit or 0):.2f}"
                ])
            tbl = Table(data, repeatRows=1)
            tbl.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ALIGN', (5,1), (6,-1), 'RIGHT')
            ]))
            elements.append(tbl)
            doc.build(elements)
            buf.seek(0)
            from flask import send_file
            return send_file(buf, as_attachment=True, download_name=f"journal_{je.entry_number}.pdf", mimetype='application/pdf')
        except Exception:
            pass
    return render_template('journal_print.html', entry=je)
@bp.route('/create_capital_entry', methods=['POST','GET'])
@login_required
def create_capital_entry():
    try:
        amt = float(request.args.get('amount') or 2000)
    except Exception:
        amt = 2000.0
    branch = (request.args.get('branch') or 'china_town').strip()
    cash_acc = _acc_by_code('1110')
    cap_acc = _acc_by_code('3000')
    je = JournalEntry(entry_number=f"JE-CAP-{int(time.time())}", date=get_saudi_now().date(), branch_code=branch, description=f"Capital Injection {amt}", status='posted', total_debit=amt, total_credit=amt, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
    db.session.add(je); db.session.flush()
    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=cash_acc.id, description='Capital Cash', line_date=je.date, debit=amt, credit=0.0))
    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cap_acc.id, description='Owner Capital', line_date=je.date, debit=0.0, credit=amt))
    db.session.commit()
    flash('تم إنشاء قيد رأس المال', 'success')
    return redirect(url_for('journal.list_entries'))

@bp.route('/close_period', methods=['POST','GET'])
@login_required
def close_period():
    period = (request.args.get('period') or 'this_year').strip()
    branch = (request.args.get('branch') or 'all').strip()
    start_date, end_date = period_range(period)
    rev_accounts = Account.query.filter(Account.type == 'REVENUE').all()
    exp_types = ['EXPENSE','COGS','OTHER_EXPENSE']
    exp_accounts = Account.query.filter(Account.type.in_(exp_types)).all()
    lines = []
    total_dr = 0.0
    total_cr = 0.0
    for acc in rev_accounts:
        q = db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0)).filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date.between(start_date, end_date))
        if branch!='all':
            q = q.join(JournalEntry, JournalEntry.id == JournalLine.journal_id).filter(JournalEntry.branch_code == branch)
        amt = float(q.scalar() or 0)
        if amt>0:
            lines.append(('DR', acc.id, amt, 'إقفال إيراد'))
            total_dr += amt
    for acc in exp_accounts:
        q = db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).filter(JournalLine.account_id == acc.id).filter(JournalLine.line_date.between(start_date, end_date))
        if branch!='all':
            q = q.join(JournalEntry, JournalEntry.id == JournalLine.journal_id).filter(JournalEntry.branch_code == branch)
        amt = float(q.scalar() or 0)
        if amt>0:
            lines.append(('CR', acc.id, amt, 'إقفال مصروف/تكلفة'))
            total_cr += amt
    net = total_dr - total_cr
    pl_acc = _acc_by_code('3030')
    if net>0:
        lines.append(('CR', pl_acc.id, net, 'صافي الربح إلى 3030'))
        total_cr += net
    elif net<0:
        lines.append(('DR', pl_acc.id, -net, 'صافي الخسارة من 3030'))
        total_dr += (-net)
    je = JournalEntry(entry_number=f"JE-CLOSE-{int(time.time())}", date=end_date, branch_code=(None if branch=='all' else branch), description=f"إقفال الفترة {period}", status='posted', total_debit=total_dr, total_credit=total_cr, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
    db.session.add(je); db.session.flush()
    ln_no = 1
    for side, acc_id, amt, desc in lines:
        if side=='DR':
            db.session.add(JournalLine(journal_id=je.id, line_no=ln_no, account_id=acc_id, description=desc, line_date=end_date, debit=amt, credit=0.0))
        else:
            db.session.add(JournalLine(journal_id=je.id, line_no=ln_no, account_id=acc_id, description=desc, line_date=end_date, debit=0.0, credit=amt))
        ln_no += 1
    db.session.commit()
    flash('تم إنشاء قيد إقفال الفترة', 'success')
    return redirect(url_for('journal.list_entries'))
