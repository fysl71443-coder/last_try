# Immutable Accounting Backbone: POSTED journals cannot be modified or deleted directly.
# Only reversing entries may adjust balances. Delete/revert rules: docs/IMMUTABLE_ACCOUNTING_RULES.md

import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload, joinedload
from extensions import db, csrf
from models import Account, LedgerEntry, Employee, JournalEntry, JournalLine, JournalAudit, get_saudi_now
from services.gl_truth import is_period_open_for_date, can_mutate_journal, validate_journal_gates
from services.account_validation import is_leaf_account

def _journal_with_lines_options(q):
    """Eager-load lines and account to avoid N+1 in print/export/templates."""
    return q.options(selectinload(JournalEntry.lines).joinedload(JournalLine.account))


def _journal_list_entry_meta(entries):
    """Build ref, op_type_ar, payment_method per entry for compact list. Batch-fetches invoices."""
    from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice
    meta = {}
    sales_ids = []
    purch_ids = []
    exp_ids = []
    for e in entries:
        it = (getattr(e, 'invoice_type') or '').strip().lower()
        iid = getattr(e, 'invoice_id', None)
        sid = getattr(e, 'salary_id', None)
        br = getattr(e, 'branch_code', None) or '-'
        if sid:
            meta[e.id] = {'ref': f'رواتب {sid}', 'op_type_ar': 'رواتب', 'op_type': 'salary', 'payment_method': '-', 'source': 'Salary', 'tax_amount': 0, 'discount_amount': 0, 'branch': br}
            continue
        if not it or not iid:
            meta[e.id] = {'ref': '-', 'op_type_ar': 'قيد يدوي', 'op_type': 'manual', 'payment_method': '-', 'source': 'Manual', 'tax_amount': 0, 'discount_amount': 0, 'branch': br}
            continue
        try:
            iid = int(iid)
        except Exception:
            meta[e.id] = {'ref': '-', 'op_type_ar': it, 'op_type': it, 'payment_method': '-', 'source': it, 'tax_amount': 0, 'discount_amount': 0, 'branch': br}
            continue
        if it == 'sales':
            sales_ids.append((e.id, iid))
        elif it == 'purchase':
            purch_ids.append((e.id, iid))
        elif it == 'expense':
            exp_ids.append((e.id, iid))
        else:
            meta[e.id] = {'ref': '-', 'op_type_ar': it, 'op_type': it, 'payment_method': '-', 'source': it, 'tax_amount': 0, 'discount_amount': 0, 'branch': br}
    sales_invs = {}
    if sales_ids:
        ids = list({x[1] for x in sales_ids})
        for inv in SalesInvoice.query.filter(SalesInvoice.id.in_(ids)).all():
            sales_invs[inv.id] = inv
    purch_invs = {}
    if purch_ids:
        ids = list({x[1] for x in purch_ids})
        for inv in PurchaseInvoice.query.filter(PurchaseInvoice.id.in_(ids)).all():
            purch_invs[inv.id] = inv
    exp_invs = {}
    if exp_ids:
        ids = list({x[1] for x in exp_ids})
        for inv in ExpenseInvoice.query.filter(ExpenseInvoice.id.in_(ids)).all():
            exp_invs[inv.id] = inv
    pm_labels = {'CASH': 'نقداً', 'BANK': 'بنك', 'CARD': 'بطاقة', 'VISA': 'فيزا', 'MADA': 'مدى', 'TRANSFER': 'تحويل', 'CREDIT': 'آجل', 'creditor': 'موردين'}
    def _pm(pm):
        k = (pm or '').strip().upper()
        return pm_labels.get(k) or pm_labels.get((pm or '').strip().lower()) or (pm or '-')
    for eid, iid in sales_ids:
        inv = sales_invs.get(iid)
        br = next((getattr(e, 'branch_code', None) or '-' for e in entries if e.id == eid), '-')
        if inv:
            meta[eid] = {'ref': getattr(inv, 'invoice_number', None) or '-', 'op_type_ar': 'بيع', 'op_type': 'sales', 'payment_method': _pm(getattr(inv, 'payment_method', None)), 'source': 'Invoice', 'tax_amount': float(getattr(inv, 'tax_amount', 0) or 0), 'discount_amount': float(getattr(inv, 'discount_amount', 0) or 0), 'branch': br}
        else:
            meta[eid] = {'ref': '-', 'op_type_ar': 'بيع', 'op_type': 'sales', 'payment_method': '-', 'source': 'Invoice', 'tax_amount': 0, 'discount_amount': 0, 'branch': br}
    for eid, iid in purch_ids:
        inv = purch_invs.get(iid)
        br = next((getattr(e, 'branch_code', None) or '-' for e in entries if e.id == eid), '-')
        if inv:
            meta[eid] = {'ref': getattr(inv, 'invoice_number', None) or '-', 'op_type_ar': 'شراء', 'op_type': 'purchase', 'payment_method': _pm(getattr(inv, 'payment_method', None)), 'source': 'Purchase', 'tax_amount': float(getattr(inv, 'tax_amount', 0) or 0), 'discount_amount': float(getattr(inv, 'discount_amount', 0) or 0), 'branch': br}
        else:
            meta[eid] = {'ref': '-', 'op_type_ar': 'شراء', 'op_type': 'purchase', 'payment_method': '-', 'source': 'Purchase', 'tax_amount': 0, 'discount_amount': 0, 'branch': br}
    for eid, iid in exp_ids:
        inv = exp_invs.get(iid)
        br = next((getattr(e, 'branch_code', None) or '-' for e in entries if e.id == eid), '-')
        if inv:
            meta[eid] = {'ref': getattr(inv, 'invoice_number', None) or '-', 'op_type_ar': 'مصروف', 'op_type': 'expense', 'payment_method': _pm(getattr(inv, 'payment_method', None)), 'source': 'Expense', 'tax_amount': float(getattr(inv, 'tax_amount', 0) or 0), 'discount_amount': float(getattr(inv, 'discount_amount', 0) or 0), 'branch': br}
        else:
            meta[eid] = {'ref': '-', 'op_type_ar': 'مصروف', 'op_type': 'expense', 'payment_method': '-', 'source': 'Expense', 'tax_amount': 0, 'discount_amount': 0, 'branch': br}
    # تمييز القيود المُدخلة بعد إعادة فتح سنة مالية
    try:
        from models import FiscalYear
        reopened_fys = [fy for fy in FiscalYear.query.filter(FiscalYear.reopened_at.isnot(None)).all() if getattr(fy, 'reopened_at')]
        for e in entries:
            m = meta.get(e.id)
            if m is None:
                continue
            m['post_reopen'] = False
            ed = getattr(e, 'date', None)
            ec = getattr(e, 'created_at', None)
            if not ed or not ec:
                continue
            for fy in reopened_fys:
                if fy.start_date <= ed <= fy.end_date and ec >= fy.reopened_at:
                    m['post_reopen'] = True
                    break
    except Exception:
        for e in entries:
            if meta.get(e.id) is not None:
                meta[e.id]['post_reopen'] = False
    return meta


bp = Blueprint('journal', __name__, url_prefix='/journal')


def _redirect_accounts_hub():
    """التوجيه إلى شاشة الحسابات المتكاملة — تبويب قيود اليومية (الشاشة المعتمدة الوحيدة للقيود)."""
    return redirect(url_for('financials.accounts_hub') + '#tab-journal')


def _can(screen, perm, branch_scope=None):
    try:
        # Allow admins
        if getattr(current_user,'username','') == 'admin' or getattr(current_user,'role','') == 'admin' or getattr(current_user,'id',None) == 1:
            return True
        # Development-friendly: allow authenticated users by default
        if getattr(current_user, 'is_authenticated', False):
            return True
        from app import can_perm
        return can_perm(screen, perm, branch_scope)
    except Exception:
        return False


def delete_journal_entry_and_linked_invoice(je):
    """
    القاعدة: حذف القيد = حذف الفاتورة/العملية المرتبطة تلقائياً.
    Deletes the given journal entry and, when linked (invoice_id/invoice_type or salary_id),
    deletes ALL journal entries for that invoice/salary, then Payments, then the invoice/salary.
    Does NOT commit — caller must commit.
    """
    from models import (
        JournalLine, LedgerEntry, Payment,
        SalesInvoice, SalesInvoiceItem, PurchaseInvoice, PurchaseInvoiceItem,
        ExpenseInvoice, ExpenseInvoiceItem, Salary, JournalAudit,
    )
    itype = (getattr(je, 'invoice_type', None) or '').strip().lower()
    iid = getattr(je, 'invoice_id', None)
    sid = getattr(je, 'salary_id', None)

    # Collect all JEs to remove: either all JEs for this invoice/salary, or just this one
    if itype and iid:
        try:
            iid = int(iid)
        except Exception:
            iid = None
    if sid is not None:
        try:
            sid = int(sid)
        except Exception:
            sid = None

    if itype and iid is not None:
        related = list(JournalEntry.query.filter(
            JournalEntry.invoice_type == itype,
            JournalEntry.invoice_id == iid,
        ).all())
    elif sid is not None:
        related = list(JournalEntry.query.filter(JournalEntry.salary_id == sid).all())
    else:
        related = [je]

    je_ids = [e.id for e in related]
    entry_numbers = [e.entry_number for e in related]

    # LedgerEntry by description (legacy)
    for en in entry_numbers:
        try:
            LedgerEntry.query.filter(LedgerEntry.description.ilike(f"JE {en}%")).delete(synchronize_session=False)
        except Exception:
            try:
                LedgerEntry.query.filter(LedgerEntry.description.ilike(f"%{en}%")).delete(synchronize_session=False)
            except Exception:
                pass

    # Invoice/salary–specific LedgerEntry descriptions
    if itype and iid is not None:
        try:
            if itype == 'sales':
                inv = SalesInvoice.query.get(iid)
                if inv:
                    inv_num = getattr(inv, 'invoice_number', None)
                    if inv_num:
                        LedgerEntry.query.filter(LedgerEntry.description == f"Sales {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"VAT Output {inv_num}").delete(synchronize_session=False)
            elif itype == 'purchase':
                inv = PurchaseInvoice.query.get(iid)
                if inv:
                    inv_num = getattr(inv, 'invoice_number', None)
                    if inv_num:
                        LedgerEntry.query.filter(LedgerEntry.description == f"Purchase {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"VAT Input {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"AP for {inv_num}").delete(synchronize_session=False)
            elif itype == 'expense':
                inv = ExpenseInvoice.query.get(iid)
                if inv:
                    inv_num = getattr(inv, 'invoice_number', None)
                    if inv_num:
                        LedgerEntry.query.filter(LedgerEntry.description == f"Expense {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"VAT Input {inv_num}").delete(synchronize_session=False)
                        LedgerEntry.query.filter(LedgerEntry.description == f"AP for {inv_num}").delete(synchronize_session=False)
        except Exception:
            pass
    if sid is not None:
        try:
            sal = Salary.query.get(sid)
            if sal:
                emp_id = getattr(sal, 'employee_id', None)
                yr = getattr(sal, 'year', None)
                mo = getattr(sal, 'month', None)
                if emp_id is not None and yr is not None and mo is not None:
                    LedgerEntry.query.filter(LedgerEntry.description == f"PAY SAL {yr}-{mo} EMP {emp_id}").delete(synchronize_session=False)
                    LedgerEntry.query.filter(LedgerEntry.description == f"ADV EMP {emp_id} {yr}-{mo}").delete(synchronize_session=False)
        except Exception:
            pass

    # JournalAudit and JournalLine for all related JEs
    for jid in je_ids:
        JournalAudit.query.filter_by(journal_id=jid).delete(synchronize_session=False)
        JournalLine.query.filter_by(journal_id=jid).delete(synchronize_session=False)

    # Payments and invoice/salary
    if itype and iid is not None:
        Payment.query.filter(Payment.invoice_type == itype, Payment.invoice_id == iid).delete(synchronize_session=False)
        if itype == 'sales':
            SalesInvoiceItem.query.filter_by(invoice_id=iid).delete(synchronize_session=False)
            inv = SalesInvoice.query.get(iid)
            if inv:
                db.session.delete(inv)
        elif itype == 'purchase':
            PurchaseInvoiceItem.query.filter_by(invoice_id=iid).delete(synchronize_session=False)
            inv = PurchaseInvoice.query.get(iid)
            if inv:
                db.session.delete(inv)
        elif itype == 'expense':
            ExpenseInvoiceItem.query.filter_by(invoice_id=iid).delete(synchronize_session=False)
            inv = ExpenseInvoice.query.get(iid)
            if inv:
                db.session.delete(inv)
    if sid is not None:
        Payment.query.filter(Payment.invoice_type == 'salary', Payment.invoice_id == sid).delete(synchronize_session=False)
        sal = Salary.query.get(sid)
        if sal:
            db.session.delete(sal)

    # Delete the journal entry/entries
    for e in related:
        db.session.delete(e)


def _ensure_accounts():
    """التأكد من وجود جميع الحسابات من الشجرة الجديدة فقط."""
    try:
        from app.routes import CHART_OF_ACCOUNTS
        from data.coa_new_tree import build_coa_dict
        # استخدام الشجرة الجديدة فقط
        new_coa = build_coa_dict()
        keys = list(new_coa.keys())
        existing = {code for (code,) in db.session.query(Account.code).filter(Account.code.in_(keys)).all()}
        missing = []
        for code, meta in new_coa.items():
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
        """الحصول على حساب من الشجرة الجديدة فقط."""
        try:
            from app.routes import CHART_OF_ACCOUNTS
            from data.coa_new_tree import build_coa_dict
            # استخدام الشجرة الجديدة فقط
            new_coa = build_coa_dict()
        except Exception:
            new_coa = {}
        c = (code or '').strip().upper()
        a = Account.query.filter(func.lower(Account.code) == c.lower()).first()
        if not a:
            # إنشاء حساب فقط إذا كان في الشجرة الجديدة
            if c in new_coa:
                meta = new_coa[c]
                a = Account(code=c, name=meta.get('name','') or c, type=meta.get('type','EXPENSE'))
                db.session.add(a); db.session.flush()
            else:
                # إذا لم يكن في الشجرة الجديدة، استخدام افتراضي
                raise ValueError(f"Account code {c} not in new COA tree")
        return a
    def _cash_or_bank(pm: str):
        p = (pm or 'CASH').strip().upper()
        if p in ('BANK','CARD','VISA','MASTERCARD','TRANSFER'):
            return _acc_by_code('1121')
        return _acc_by_code('1112')
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
            entry_date = inv.date or get_saudi_now().date()
            ok, period_msg = is_period_open_for_date(entry_date)
            if not ok:
                errors.append(f"sales:{inv.id}:{inv_num}:{period_msg or 'الفترة مغلقة'}")
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                discount_amt = float(inv.discount_amount or 0)
                tax_amt = float(inv.tax_amount or 0)
                net_rev = max(0.0, total_before - discount_amt)
                total_inc_tax = round(net_rev + tax_amt, 2)
                cust = (getattr(inv, 'customer_name', '') or '').strip().lower()
                def _grp(n: str):
                    s = (n or '').lower()
                    if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                        return 'hunger'
                    if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                        return 'keeta'
                    return ''
                grp = _grp(cust)
                ar_acc = _acc_by_code('1141')
                rev_code = '4112' if (getattr(inv, 'payment_method', '') or '').upper() in ('CREDIT','CREDITOR','آجل') else '4111'
                rev_acc = _acc_by_code(rev_code)
                vat_out_acc = _acc_by_code('2141')
                cash_acc = None if grp in ('keeta','hunger') else _cash_or_bank(inv.payment_method)
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
                _lid, _lty = inv.id, 'sales'
                _d = inv.date or get_saudi_now().date()
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ar_acc.id, debit=total_inc_tax, credit=0, description=f"AR {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if net_rev > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=rev_acc.id, debit=0, credit=net_rev, description=f"Revenue {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=vat_out_acc.id, debit=0, credit=tax_amt, description=f"VAT Output {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=cash_acc.id, debit=total_inc_tax, credit=0, description=f"Receipt {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=ar_acc.id, debit=0, credit=total_inc_tax, description=f"Clear AR {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
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
            entry_date = inv.date or get_saudi_now().date()
            ok, period_msg = is_period_open_for_date(entry_date)
            if not ok:
                errors.append(f"purchase:{inv.id}:{inv_num}:{period_msg or 'الفترة مغلقة'}")
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                tax_amt = float(inv.tax_amount or 0)
                total_inc_tax = round(total_before + tax_amt, 2)
                exp_acc = _acc_by_code('1161')
                vat_in_acc = _acc_by_code('1170')
                ap_acc = _acc_by_code('2111')
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
                _lid, _lty = inv.id, 'purchase'
                _d = inv.date or get_saudi_now().date()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Purchase", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=_d, invoice_id=_lid, invoice_type=_lty))
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
            entry_date = inv.date or get_saudi_now().date()
            ok, period_msg = is_period_open_for_date(entry_date)
            if not ok:
                errors.append(f"expense:{inv.id}:{inv_num}:{period_msg or 'الفترة مغلقة'}")
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                tax_amt = float(inv.tax_amount or 0)
                total_inc_tax = round(total_before + tax_amt, 2)
                exp_acc = _acc_by_code('5110')
                vat_in_acc = _acc_by_code('1170')
                ap_acc = _acc_by_code('2111')
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
                _lid, _lty = inv.id, 'expense'
                _d = inv.date or get_saudi_now().date()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Expense", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=_d, invoice_id=_lid, invoice_type=_lty))
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

@bp.route('/latest_meta', methods=['GET'])
@login_required
def latest_meta():
    try:
        last = JournalEntry.query.order_by(JournalEntry.id.desc()).first()
        cnt = JournalEntry.query.count()
        return jsonify({'ok': True, 'latest_id': int(getattr(last,'id',0) or 0), 'count': int(cnt or 0)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

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
    entries = JournalEntry.query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).limit(50).all()
    return render_template('journal_entries.html', entries=entries, page=1, pages=1, total=JournalEntry.query.count(), accounts=[], employees=[], branch='all', mode='list', entry_meta=_journal_list_entry_meta(entries))

def create_missing_journal_entries_for(kind: str):
    _ensure_journal_link_columns()
    _ensure_accounts()
    created = []
    errors = []
    kind = (kind or '').strip().lower()
    from sqlalchemy import func
    def _acc_by_code(code: str):
        """الحصول على حساب من الشجرة الجديدة فقط."""
        try:
            from app.routes import CHART_OF_ACCOUNTS
            from data.coa_new_tree import build_coa_dict
            # استخدام الشجرة الجديدة فقط
            new_coa = build_coa_dict()
        except Exception:
            new_coa = {}
        c = (code or '').strip().upper()
        a = Account.query.filter(func.lower(Account.code) == c.lower()).first()
        if not a:
            # إنشاء حساب فقط إذا كان في الشجرة الجديدة
            if c in new_coa:
                meta = new_coa[c]
                a = Account(code=c, name=meta.get('name','') or c, type=meta.get('type','EXPENSE'))
                db.session.add(a); db.session.flush()
            else:
                # إذا لم يكن في الشجرة الجديدة، استخدام افتراضي
                raise ValueError(f"Account code {c} not in new COA tree")
        return a
    def _cash_or_bank(pm: str):
        p = (pm or 'CASH').strip().upper()
        if p in ('BANK','CARD','VISA','MASTERCARD','TRANSFER'):
            return _acc_by_code('1121')
        return _acc_by_code('1112')
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
            entry_date = inv.date or get_saudi_now().date()
            ok, period_msg = is_period_open_for_date(entry_date)
            if not ok:
                errors.append(f"sales:{inv.id}:{inv_num}:{period_msg or 'الفترة مغلقة'}")
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                discount_amt = float(inv.discount_amount or 0)
                tax_amt = float(inv.tax_amount or 0)
                net_rev = max(0.0, total_before - discount_amt)
                total_inc_tax = round(net_rev + tax_amt, 2)
                cust = (getattr(inv, 'customer_name', '') or '').strip().lower()
                def _grp(n: str):
                    s = (n or '').lower()
                    if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                        return 'hunger'
                    if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                        return 'keeta'
                    return ''
                grp = _grp(cust)
                ar_acc = _acc_by_code('1141')
                rev_code = '4112' if (getattr(inv, 'payment_method', '') or '').upper() in ('CREDIT','CREDITOR','آجل') else '4111'
                rev_acc = _acc_by_code(rev_code)
                vat_out_acc = _acc_by_code('2141')
                cash_acc = None if grp in ('keeta','hunger') else _cash_or_bank(inv.payment_method)
                je = JournalEntry(entry_number=f"JE-SAL-{inv_num}", date=entry_date, branch_code=getattr(inv, 'branch', None), description=f"Sales {inv_num}", status='posted', total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax, total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=int(inv.id), invoice_type='sales')
                db.session.add(je); db.session.flush()
                _lid, _lty, _d = inv.id, 'sales', inv.date or get_saudi_now().date()
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=ar_acc.id, debit=total_inc_tax, credit=0, description=f"AR {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if net_rev > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=rev_acc.id, debit=0, credit=net_rev, description=f"Revenue {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=vat_out_acc.id, debit=0, credit=tax_amt, description=f"VAT Output {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=cash_acc.id, debit=total_inc_tax, credit=0, description=f"Receipt {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=ar_acc.id, debit=0, credit=total_inc_tax, description=f"Clear AR {inv_num}", line_date=_d, invoice_id=_lid, invoice_type=_lty))
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
            entry_date = inv.date or get_saudi_now().date()
            ok, period_msg = is_period_open_for_date(entry_date)
            if not ok:
                errors.append(f"purchase:{inv.id}:{inv_num}:{period_msg or 'الفترة مغلقة'}")
                continue
            try:
                total_before, tax_amt, total_inc_tax = inv.get_effective_totals()
                exp_acc = _acc_by_code('1161')
                vat_in_acc = _acc_by_code('1170')
                ap_acc = _acc_by_code('2111')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(entry_number=f"JE-PUR-{inv_num}", date=(inv.date or get_saudi_now().date()), branch_code=None, description=f"Purchase {inv_num}", status='posted', total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax, total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=int(inv.id), invoice_type='purchase')
                db.session.add(je); db.session.flush()
                _lid, _lty, _d = inv.id, 'purchase', inv.date or get_saudi_now().date()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Purchase", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=_d, invoice_id=_lid, invoice_type=_lty))
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
            entry_date = inv.date or get_saudi_now().date()
            ok, period_msg = is_period_open_for_date(entry_date)
            if not ok:
                errors.append(f"expense:{inv.id}:{inv_num}:{period_msg or 'الفترة مغلقة'}")
                continue
            try:
                total_before = float(inv.total_before_tax or 0)
                tax_amt = float(inv.tax_amount or 0)
                total_inc_tax = round(total_before + tax_amt, 2)
                exp_acc = _acc_by_code('5110')
                vat_in_acc = _acc_by_code('1170')
                ap_acc = _acc_by_code('2111')
                cash_acc = _cash_or_bank(inv.payment_method)
                je = JournalEntry(entry_number=f"JE-EXP-{inv_num}", date=(inv.date or get_saudi_now().date()), branch_code=None, description=f"Expense {inv_num}", status='posted', total_debit=total_inc_tax * 2 if cash_acc else total_inc_tax, total_credit=total_inc_tax * 2 if cash_acc else total_inc_tax, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None), invoice_id=int(inv.id), invoice_type='expense')
                db.session.add(je); db.session.flush()
                _lid, _lty, _d = inv.id, 'expense', inv.date or get_saudi_now().date()
                if total_before > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=exp_acc.id, debit=total_before, credit=0, description="Expense", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if tax_amt > 0:
                    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=vat_in_acc.id, debit=tax_amt, credit=0, description="VAT Input", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                db.session.add(JournalLine(journal_id=je.id, line_no=3, account_id=ap_acc.id, debit=0, credit=total_inc_tax, description="Accounts Payable", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                if cash_acc:
                    db.session.add(JournalLine(journal_id=je.id, line_no=4, account_id=ap_acc.id, debit=total_inc_tax, credit=0, description="Pay AP", line_date=_d, invoice_id=_lid, invoice_type=_lty))
                    db.session.add(JournalLine(journal_id=je.id, line_no=5, account_id=cash_acc.id, debit=0, credit=total_inc_tax, description="Cash/Bank", line_date=_d, invoice_id=_lid, invoice_type=_lty))
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
                sal_pay = _acc_by_code('2121')
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

@bp.route('/api/fix_aggregator_receipts', methods=['POST'])
@csrf.exempt
def api_fix_aggregator_receipts():
    try:
        fixed = 0
        from models import SalesInvoice
        entries = JournalEntry.query.filter(JournalEntry.invoice_type == 'sales').all()
        for je in entries:
            inv = None
            try:
                inv = SalesInvoice.query.filter(SalesInvoice.id == int(getattr(je,'invoice_id',0) or 0)).first()
            except Exception:
                inv = None
            cust = (getattr(inv, 'customer_name', '') or '').strip().lower()
            s = cust
            grp = 'keeta' if (('keeta' in s) or ('كيتا' in s) or ('كيت' in s)) else ('hunger' if (('hunger' in s) or ('هنقر' in s) or ('هونقر' in s)) else '')
            if grp not in ('keeta','hunger'):
                continue
            lines = JournalLine.query.filter(JournalLine.journal_id == je.id).order_by(JournalLine.line_no.asc()).all()
            to_delete = []
            for ln in lines:
                desc = (getattr(ln,'description','') or '').lower()
                acc = Account.query.filter(Account.id == ln.account_id).first()
                code = (getattr(acc,'code','') or '').strip()
                if desc.startswith('receipt ') and code in ('1112','1121'):
                    to_delete.append(ln)
                if desc.startswith('clear ar '):
                    to_delete.append(ln)
            if not to_delete:
                continue
            for ln in to_delete:
                try:
                    db.session.delete(ln)
                except Exception:
                    pass
            try:
                db.session.flush()
            except Exception:
                pass
            lines_left = JournalLine.query.filter(JournalLine.journal_id == je.id).all()
            td = sum([float(getattr(l,'debit',0) or 0) for l in lines_left])
            tc = sum([float(getattr(l,'credit',0) or 0) for l in lines_left])
            je.total_debit = td
            je.total_credit = tc
            fixed += 1
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({'ok': True, 'fixed_count': fixed})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

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
    entries = JournalEntry.query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).limit(50).all()
    return render_template('journal_entries.html', entries=entries, page=1, pages=1, total=JournalEntry.query.count(), accounts=[], employees=[], branch='all', mode='list', entry_meta=_journal_list_entry_meta(entries))

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
    return _redirect_accounts_hub()

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
                    rev_acc = Account.query.filter(Account.code=='4111').first() or _acc_by_code('4111')
                    ar_acc = Account.query.filter(Account.code=='1141').first() or _acc_by_code('1141')
                elif grp == 'hunger':
                    rev_acc = Account.query.filter(Account.code=='4111').first() or _acc_by_code('4111')
                    ar_acc = Account.query.filter(Account.code=='1141').first() or _acc_by_code('1141')
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
    return _redirect_accounts_hub()


def _parse_audit_dates_from_request():
    """استخراج from_date و to_date من request.form أو request.args."""
    from datetime import datetime as _dt
    from_date = to_date = None
    src = request.args if request.method == 'GET' else request.form
    if src.get('from_date'):
        try:
            from_date = _dt.strptime(src.get('from_date'), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    if src.get('to_date'):
        try:
            to_date = _dt.strptime(src.get('to_date'), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    return from_date, to_date


@bp.route('/audit', methods=['GET', 'POST'])
@login_required
def audit():
    """إجراء تدقيق محاسبي شامل — يشغّل محرك التدقيق ويعرض التقرير."""
    if not _can('journal', 'view'):
        flash('لا تملك صلاحية الوصول', 'danger')
        return _redirect_accounts_hub()
    from modules.audit import run_audit as run_audit_engine
    report = None
    if request.method == 'POST':
        from_date, to_date = _parse_audit_dates_from_request()
        report = run_audit_engine(from_date=from_date, to_date=to_date, persist_findings=False)
        _audit_report_with_ref_urls(report)
    elif request.args.get('run'):
        # تشغيل من شاشة السنوات المالية: ?run=1&from_date=...&to_date=...&fiscal_year_id=...
        from_date, to_date = _parse_audit_dates_from_request()
        fiscal_year_id = request.args.get('fiscal_year_id', type=int)
        if from_date and to_date:
            report = run_audit_engine(
                from_date=from_date,
                to_date=to_date,
                fiscal_year_id=fiscal_year_id,
                persist_findings=bool(fiscal_year_id),
            )
            _audit_report_with_ref_urls(report)
            if report and fiscal_year_id:
                try:
                    from services.audit_snapshot_cache import save_audit_snapshot
                    save_audit_snapshot(fiscal_year_id, report.get("summary") or {}, report.get("meta", {}).get("run_at"))
                except Exception:
                    pass
    if report and report.get("findings"):
        for f in report["findings"]:
            if f.get("ref_type") == "journal" and f.get("ref_id"):
                f["ref_url"] = url_for("journal.edit_entry", jid=f["ref_id"])
            else:
                f["ref_url"] = None
    return render_template('audit_report.html', report=report)


def _audit_report_with_ref_urls(report):
    """إثراء التقرير بروابط فتح القيد."""
    if not report or not report.get("findings"):
        return report
    for f in report["findings"]:
        if f.get("ref_type") == "journal" and f.get("ref_id"):
            f["ref_url"] = url_for("journal.edit_entry", jid=f["ref_id"])
        else:
            f["ref_url"] = None
    return report


@bp.route('/audit/print')
@login_required
def audit_print():
    """نسخة التقرير الجاهزة للطباعة / PDF (بدون إطار التطبيق)."""
    if not _can('journal', 'view'):
        flash('لا تملك صلاحية الوصول', 'danger')
        return _redirect_accounts_hub()
    from services.audit_engine import run_audit
    from datetime import datetime as _dt
    from models import Settings
    from_date = to_date = None
    if request.args.get('from_date'):
        try:
            from_date = _dt.strptime(request.args.get('from_date'), '%Y-%m-%d').date()
        except ValueError:
            pass
    if request.args.get('to_date'):
        try:
            to_date = _dt.strptime(request.args.get('to_date'), '%Y-%m-%d').date()
        except ValueError:
            pass
    report = run_audit(from_date=from_date, to_date=to_date)
    _audit_report_with_ref_urls(report)
    try:
        settings = Settings.query.first()
        company_name = (getattr(settings, 'company_name', None) or 'Company').strip() if settings else 'Company'
    except Exception:
        company_name = 'Company'
    return render_template('audit_report_print.html', report=report, company_name=company_name)


def _closure_info_for_pdf(fiscal_year_id):
    """بناء closure_info لعرض تقرير PDF: is_override, override_reason, closed_by_username, closed_at."""
    try:
        from models import FiscalYear, FiscalYearAuditLog
    except ImportError:
        return None
    fy = FiscalYear.query.get(fiscal_year_id)
    if not fy or fy.status != 'closed':
        return None
    # آخر سجل إقفال (close أو close_override)
    log = None
    if getattr(fy, "audit_logs", None):
        for entry in sorted(fy.audit_logs, key=lambda x: (x.created_at or x.id or 0), reverse=True):
            if entry.action in ("close", "close_override"):
                log = entry
                break
    details = {}
    if log and getattr(log, "details_json", None):
        try:
            details = json.loads(log.details_json) or {}
        except (ValueError, TypeError):
            pass
    closed_at = fy.closed_at if getattr(fy, "closed_at", None) else (log.created_at if log else None)
    closed_at_str = closed_at.strftime('%Y-%m-%d %H:%M') if closed_at else '—'
    username = details.get("closed_by_username") or None
    if not username and getattr(fy, "closed_by", None):
        u = None
        try:
            from models import User
            u = User.query.get(fy.closed_by)
        except Exception:
            pass
        if u:
            username = getattr(u, "username", None)
    return {
        "is_override": log and getattr(log, "action", None) == "close_override",
        "override_reason": details.get("override_reason") or None,
        "closed_by_username": username or "—",
        "closed_at": closed_at_str,
    }


@bp.route('/audit/pdf')
@login_required
def audit_pdf():
    """تقرير التدقيق PDF (رسمي واحترافي). استخدم WeasyPrint إن وُجد، وإلا HTML للطباعة من المتصفح."""
    if not _can('journal', 'view'):
        flash('لا تملك صلاحية الوصول', 'danger')
        return _redirect_accounts_hub()
    from modules.audit.engine import run_audit
    from datetime import datetime as _dt
    from models import Settings
    from_date, to_date = _parse_audit_dates_from_request()
    fiscal_year_id = request.args.get('fiscal_year_id', type=int)
    # عند وجود سنة مالية نستخدم حدودها إن لم تُحدد تواريخ
    if fiscal_year_id and (not from_date or not to_date):
        try:
            from models import FiscalYear
            fy = FiscalYear.query.get(fiscal_year_id)
            if fy:
                from_date = from_date or fy.start_date
                to_date = to_date or fy.end_date
        except Exception:
            pass
    if not from_date or not to_date:
        flash('يجب تحديد من تاريخ وإلى تاريخ (أو سنة مالية) لتوليد التقرير.', 'warning')
        return redirect(url_for('journal.audit'))
    report = run_audit(from_date=from_date, to_date=to_date, fiscal_year_id=fiscal_year_id, persist_findings=False)
    _audit_report_with_ref_urls(report)
    try:
        settings = Settings.query.first()
        company_name = (getattr(settings, 'company_name', None) or 'Company').strip() if settings else 'Company'
        tax_number = (getattr(settings, 'tax_number', None) or '').strip() if settings else ''
        logo_url = (getattr(settings, 'logo_url', None) or '').strip() if settings else ''
        show_logo = getattr(settings, 'receipt_show_logo', True) if settings else True
    except Exception:
        company_name = 'Company'
        tax_number = ''
        logo_url = ''
        show_logo = True
    closure_info = _closure_info_for_pdf(fiscal_year_id) if fiscal_year_id else None
    # لغة التقرير بحسب لغة النظام (جلسة / مستخدم / طلب)
    try:
        from flask import session
        lang = (session.get('locale') or getattr(current_user, 'language_pref', None) or request.args.get('lang') or 'ar')
        lang = (lang or 'ar').strip().lower()[:2]
        if lang not in ('ar', 'en'):
            lang = 'ar'
    except Exception:
        lang = 'ar'
    # تسميات عربي/إنجليزي للقالب
    labels_ar = {
        "report_title": "تقرير التدقيق المحاسبي",
        "vat": "الرقم الضريبي / VAT",
        "period": "الفترة المالية",
        "to": "إلى",
        "issue_date": "تاريخ الإصدار",
        "closure_badge_open": "سنة مفتوحة",
        "closure_badge_normal": "إقفال نظامي",
        "closure_badge_override": "إقفال مع تجاوز",
        "closure_na": "لا يرتبط التقرير بسنة مالية محددة",
        "exec_summary": "الملخص التنفيذي",
        "exec_summary_en": "Executive Summary",
        "item": "البند",
        "count": "العدد",
        "total_findings": "إجمالي الملاحظات",
        "critical": "الحرجة (عالية الخطورة)",
        "medium": "المتوسطة",
        "low": "المنخفضة",
        "closure_status": "حالة الإقفال",
        "year_open": "سنة مفتوحة",
        "year_open_desc": "الفترة المالية مفتوحة (لم يتم إقفالها بعد).",
        "override_reason": "سبب التجاوز",
        "closed_by": "تم بواسطة",
        "normal_closure": "إقفال نظامي",
        "normal_closure_desc": "تم إقفال الفترة المالية بشكل عادي (بدون تجاوز).",
        "closure_na_desc": "حالة الإقفال غير مرتبطة بهذا التقرير (لم يُحدد سنة مالية).",
        "findings_table": "جدول الملاحظات التفصيلي",
        "findings_index": "فهرس الملاحظات (روابط داخلية)",
        "no_findings": "لا توجد ملاحظات.",
        "finding_no": "#",
        "issue_type": "نوع الخلل",
        "entry_no": "رقم القيد",
        "description": "الوصف",
        "root_cause": "السبب",
        "correction": "طريقة التصحيح",
        "severity": "الخطورة",
        "stats_title": "توزيع الخطورة",
        "items_count": "عدد البنود",
        "conclusion": "خاتمة",
        "conclusion_text": "تم إعداد هذا التقرير آليًا من النظام المحاسبي، ويعكس نتائج الفحص وفق القواعد المعتمدة بتاريخ",
        "conclusion_disclaimer": "وهذا التقرير لا يُغني عن المراجعة البشرية ولا يُمثّل رأياً قانونياً أو ضريبياً. يُوصى بالاحتفاظ بنسخة مطبوعة أو PDF مع سجلات الفترة. قابل للتوقيع والختم.",
        "auditor": "المدقق / المراجع",
        "date_stamp": "التاريخ والختم",
        "electronic_seal": "ختم إلكتروني",
        "signature": "توقيع",
        "footer_report": "تقرير التدقيق",
        "page": "صفحة",
    }
    labels_en = {
        "report_title": "Audit Report",
        "vat": "VAT / Tax ID",
        "period": "Fiscal Period",
        "to": "to",
        "issue_date": "Issue Date",
        "closure_badge_open": "Open Year",
        "closure_badge_normal": "Normal Closure",
        "closure_badge_override": "Closure with Override",
        "closure_na": "Report not linked to a fiscal year",
        "exec_summary": "Executive Summary",
        "exec_summary_en": "",
        "item": "Item",
        "count": "Count",
        "total_findings": "Total Findings",
        "critical": "Critical (High)",
        "medium": "Medium",
        "low": "Low",
        "closure_status": "Closure Status",
        "year_open": "Open Year",
        "year_open_desc": "Fiscal period is open (not yet closed).",
        "override_reason": "Override Reason",
        "closed_by": "Closed By",
        "normal_closure": "Normal Closure",
        "normal_closure_desc": "Fiscal period was closed normally (no override).",
        "closure_na_desc": "Closure status not linked to this report.",
        "findings_table": "Detailed Findings Table",
        "findings_index": "Findings Index (internal links)",
        "no_findings": "No findings.",
        "finding_no": "#",
        "issue_type": "Issue Type",
        "entry_no": "Entry No.",
        "description": "Description",
        "root_cause": "Root Cause",
        "correction": "Correction Method",
        "severity": "Severity",
        "stats_title": "Severity Distribution",
        "items_count": "Items",
        "conclusion": "Conclusion",
        "conclusion_text": "This report was prepared automatically by the accounting system and reflects the results of the examination in accordance with the rules in effect as of",
        "conclusion_disclaimer": "This report does not replace human review and does not constitute legal or tax advice. Retain a printed or PDF copy with period records. Ready for signature and stamp.",
        "auditor": "Auditor / Reviewer",
        "date_stamp": "Date & Stamp",
        "electronic_seal": "Electronic Seal",
        "signature": "Signature",
        "footer_report": "Audit Report",
        "page": "Page",
    }
    labels = labels_en if lang == 'en' else labels_ar
    html_content = render_template(
        'audit_report_pdf.html',
        report=report,
        company_name=company_name,
        tax_number=tax_number,
        closure_info=closure_info,
        logo_url=logo_url or None,
        show_logo=show_logo,
        lang=lang,
        labels=labels,
    )
    # محاولة توليد PDF بـ WeasyPrint
    try:
        from weasyprint import HTML
        from io import BytesIO
        pdf_io = BytesIO()
        HTML(string=html_content).write_pdf(pdf_io)
        pdf_io.seek(0)
        return Response(
            pdf_io.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': 'inline; filename=audit_report.pdf'},
        )
    except ImportError:
        pass
    except Exception:
        pass
    # عرض HTML للطباعة من المتصفح (Print → Save as PDF)
    return Response(html_content, mimetype='text/html; charset=utf-8')


@bp.route('/', methods=['GET'])
@login_required
def journal_index():
    """لا توجد شاشة عند /journal/ — التوجيه إلى لوحة التحكم."""
    try:
        return redirect(url_for('main.dashboard'))
    except Exception:
        return redirect('/dashboard')


@bp.route('/entries', methods=['GET'])
@login_required
def list_entries():
    """لا توجد شاشة قيود مستقلة — التوجيه إلى الحسابات المتكاملة (تبويب قيود اليومية)."""
    if not _can('journal', 'view'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.dashboard'))
    return _redirect_accounts_hub()

@bp.route('/print/all', methods=['GET'])
@login_required
def print_all():
    """لا شاشة طباعة قيود مستقلة — التوجيه إلى الحسابات المتكاملة."""
    if not _can('journal', 'print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.dashboard'))
    return _redirect_accounts_hub()


@bp.route('/print/all/pdf', methods=['GET'])
@login_required
def print_all_pdf():
    """لا شاشة PDF قيود مستقلة — التوجيه إلى الحسابات المتكاملة."""
    if not _can('journal', 'print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.dashboard'))
    return _redirect_accounts_hub()


@bp.route('/export/all', methods=['GET'])
@login_required
def export_all():
    """لا شاشة تصدير قيود مستقلة — التوجيه إلى الحسابات المتكاملة."""
    if not _can('journal', 'print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.dashboard'))
    return _redirect_accounts_hub()


@csrf.exempt
@bp.route('/rebalance_rounding', methods=['POST','GET'])
@login_required
def rebalance_rounding():
    updated = 0
    errors = []
    try:
        from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice
        sales = JournalEntry.query.filter(JournalEntry.invoice_type == 'sales').all()
        for je in sales:
            try:
                inv = SalesInvoice.query.get(int(getattr(je, 'invoice_id', 0)))
            except Exception:
                inv = None
            try:
                total_before = float(getattr(inv, 'total_before_tax', 0) or 0)
                discount_amt = float(getattr(inv, 'discount_amount', 0) or 0)
                tax_amt = float(getattr(inv, 'tax_amount', 0) or 0)
                net_rev = max(0.0, total_before - discount_amt)
                total_inc_tax = round(net_rev + tax_amt, 2)
                for ln in je.lines:
                    desc = (ln.description or '').lower()
                    if (float(ln.debit or 0) > 0) and ('ar' in desc):
                        ln.debit = total_inc_tax
                    if (float(ln.credit or 0) > 0) and ('clear ar' in desc):
                        ln.credit = total_inc_tax
                has_cash = any([(ln.description or '').lower().startswith('receipt') for ln in je.lines])
                je.total_debit = total_inc_tax * 2 if has_cash else total_inc_tax
                je.total_credit = total_inc_tax * 2 if has_cash else total_inc_tax
                updated += 1
            except Exception as e:
                errors.append(str(e))
        purch = JournalEntry.query.filter(JournalEntry.invoice_type == 'purchase').all()
        for je in purch:
            try:
                inv = PurchaseInvoice.query.get(int(getattr(je, 'invoice_id', 0)))
            except Exception:
                inv = None
            try:
                total_before = float(getattr(inv, 'total_before_tax', 0) or 0)
                tax_amt = float(getattr(inv, 'tax_amount', 0) or 0)
                total_inc_tax = round(total_before + tax_amt, 2)
                for ln in je.lines:
                    desc = (ln.description or '').lower()
                    if (float(ln.credit or 0) > 0) and ('accounts payable' in desc):
                        ln.credit = total_inc_tax
                    if (float(ln.debit or 0) > 0) and ('pay ap' in desc):
                        ln.debit = total_inc_tax
                has_cash = any([(ln.description or '').lower().startswith('pay ap') for ln in je.lines])
                je.total_debit = total_inc_tax * 2 if has_cash else total_inc_tax
                je.total_credit = total_inc_tax * 2 if has_cash else total_inc_tax
                updated += 1
            except Exception as e:
                errors.append(str(e))
        exp = JournalEntry.query.filter(JournalEntry.invoice_type == 'expense').all()
        for je in exp:
            try:
                inv = ExpenseInvoice.query.get(int(getattr(je, 'invoice_id', 0)))
            except Exception:
                inv = None
            try:
                total_before = float(getattr(inv, 'total_before_tax', 0) or 0)
                tax_amt = float(getattr(inv, 'tax_amount', 0) or 0)
                total_inc_tax = round(total_before + tax_amt, 2)
                for ln in je.lines:
                    desc = (ln.description or '').lower()
                    if (float(ln.credit or 0) > 0) and ('accounts payable' in desc):
                        ln.credit = total_inc_tax
                    if (float(ln.debit or 0) > 0) and ('pay ap' in desc):
                        ln.debit = total_inc_tax
                has_cash = any([(ln.description or '').lower().startswith('pay ap') for ln in je.lines])
                je.total_debit = total_inc_tax * 2 if has_cash else total_inc_tax
                je.total_credit = total_inc_tax * 2 if has_cash else total_inc_tax
                updated += 1
            except Exception as e:
                errors.append(str(e))
        db.session.commit()
        try:
            flash(f"تمت إعادة موازنة القيود: {updated} قيود؛ أخطاء: {len(errors)}", 'success' if not errors else 'warning')
        except Exception:
            pass
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(str(e) or 'Rounding rebalance failed', 'danger')
    return redirect(url_for('financials.trial_balance'))

@bp.route('/<int:jid>/delete', methods=['POST'])
@login_required
def delete_entry(jid):
    je = JournalEntry.query.get_or_404(jid)
    try:
        if not _can('journal','edit'):
            flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
            return _redirect_accounts_hub()
    except Exception:
        pass
    ok, err = can_mutate_journal(je)
    if not ok:
        abort(403, err or 'الفترة المالية مغلقة')
    try:
        delete_journal_entry_and_linked_invoice(je)
        db.session.commit()
        flash('تم حذف القيد والفاتورة/العملية المرتبطة', 'success')
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        msg = str(e) if str(e) else 'تعذر حذف القيد'
        flash(msg, 'danger')
    return _redirect_accounts_hub()

@bp.route('/<int:jid>/detail', methods=['GET'])
@login_required
def entry_detail_json(jid):
    """JSON detail for expandable row: entry, lines, operational, financial."""
    je = _journal_with_lines_options(JournalEntry.query).filter_by(id=jid).first_or_404()
    if not _can('journal', 'view'):
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice
    branch = (je.branch_code or '-')
    branch_label = {'china_town': 'China Town', 'place_india': 'Place India'}.get((branch or '').strip().lower()) or branch
    op = {'op_type': 'manual', 'op_type_ar': 'قيد يدوي', 'source': 'Manual', 'branch': branch_label, 'payment_method': '-', 'party': '-', 'doc_number': '-'}
    financial = None
    it = (getattr(je, 'invoice_type') or '').strip().lower()
    iid = getattr(je, 'invoice_id', None)
    sid = getattr(je, 'salary_id', None)
    if sid:
        op.update({'op_type': 'salary', 'op_type_ar': 'رواتب', 'source': 'Salary', 'party': 'موظفون'})
    elif it and iid:
        try:
            iid = int(iid)
        except Exception:
            iid = None
        if it == 'sales' and iid:
            inv = SalesInvoice.query.get(iid)
            if inv:
                op['doc_number'] = getattr(inv, 'invoice_number', None) or '-'
                op['source'] = 'Invoice'
                op['op_type'] = 'sales'
                op['op_type_ar'] = 'بيع'
                op['party'] = 'العملاء'
                pm = (getattr(inv, 'payment_method', None) or '').strip().upper()
                op['payment_method'] = 'آجل' if pm in ('CREDIT', 'creditor') else ('بنك' if pm in ('BANK', 'CARD', 'VISA', 'MADA', 'TRANSFER') else 'نقداً')
                total_bt = float(inv.total_before_tax or 0)
                discount_amt = float(inv.discount_amount or 0)
                tax_amt = float(inv.tax_amount or 0)
                net = max(0.0, total_bt - discount_amt)
                total = round(net + tax_amt, 2)
                discount_pct = round((discount_amt / total_bt * 100), 1) if total_bt else 0
                tax_pct = 15.0
                financial = {'net_sales': round(net, 2), 'discount': round(discount_amt, 2), 'discount_pct': discount_pct, 'tax': round(tax_amt, 2), 'tax_pct': tax_pct, 'total': total}
        elif it == 'purchase' and iid:
            inv = PurchaseInvoice.query.get(iid)
            if inv:
                op['doc_number'] = getattr(inv, 'invoice_number', None) or '-'
                op['source'] = 'Purchase'
                op['op_type'] = 'purchase'
                op['op_type_ar'] = 'شراء'
                op['party'] = 'موردون'
                pm = (getattr(inv, 'payment_method', None) or '').strip().upper()
                op['payment_method'] = 'آجل' if pm in ('CREDIT',) else ('بنك' if pm in ('BANK', 'CARD', 'VISA', 'MADA', 'TRANSFER') else 'نقداً')
        elif it == 'expense' and iid:
            inv = ExpenseInvoice.query.get(iid)
            if inv:
                op['doc_number'] = getattr(inv, 'invoice_number', None) or '-'
                op['source'] = 'Expense'
                op['op_type'] = 'expense'
                op['op_type_ar'] = 'مصروف'
                op['party'] = 'موردون'
                pm = (getattr(inv, 'payment_method', None) or '').strip().upper()
                op['payment_method'] = 'بنك' if pm in ('BANK', 'CARD', 'VISA', 'MADA', 'TRANSFER') else 'نقداً'
    from data.coa_new_tree import get_account_display_name
    lines = []
    for ln in sorted(je.lines or [], key=lambda x: (x.line_no or 0)):
        acc = ln.account
        code = (getattr(acc, 'code', None) or '')
        name = get_account_display_name(code, getattr(acc, 'name', None))
        lines.append({'account_code': code, 'account_name': name, 'debit': float(ln.debit or 0), 'credit': float(ln.credit or 0)})
    return jsonify({
        'ok': True,
        'entry': {'id': je.id, 'entry_number': je.entry_number, 'date': str(je.date or ''), 'branch_code': je.branch_code, 'description': je.description or '', 'status': je.status or 'draft', 'total_debit': float(je.total_debit or 0), 'total_credit': float(je.total_credit or 0), 'invoice_id': je.invoice_id, 'invoice_type': je.invoice_type, 'salary_id': je.salary_id},
        'lines': lines,
        'operational': op,
        'financial': financial,
    })


@csrf.exempt
@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_entry():
    """لا شاشة قيد جديد مستقلة — GET يوجّه للحسابات المتكاملة؛ POST يُعالج ثم توجيه (لتوافق الطلبات القديمة)."""
    if not _can('journal', 'add'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return redirect(url_for('main.dashboard'))
    if request.method == 'GET':
        return _redirect_accounts_hub()
    _ensure_accounts()
    accounts = []
    employees = []
    date_str = (request.form.get('date') or '').strip()
    branch = (request.form.get('branch') or '').strip() or None
    description = (request.form.get('description') or '').strip()
    if not description:
        flash('يرجى إدخال وصف القيد.', 'danger')
        return _redirect_accounts_hub()
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else get_saudi_now().date()
    except Exception:
        d = get_saudi_now().date()
    if d > get_saudi_now().date() and getattr(current_user,'role','')!='admin':
        flash('لا يمكن حفظ قيد بتاريخ مستقبلي.', 'danger')
        return _redirect_accounts_hub()
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
            return _redirect_accounts_hub()
        if debit and credit:
            flash('لا يسمح بوجود قيمة في المدين والدائن معاً.', 'danger')
            return _redirect_accounts_hub()
        if (debit <= 0 and credit <= 0):
            idx += 1
            continue
        emp_id_val = None
        try:
            emp_id_val = int(emp_id) if emp_id else None
        except Exception:
            emp_id_val = None
        acc = Account.query.get(acc_id)
        if not acc:
            flash('الحساب غير موجود في شجرة الحسابات.', 'danger')
            return _redirect_accounts_hub()
        code = (acc.code or '').strip().upper()
        if not is_leaf_account(code):
            flash(f'الحساب "{code}" تجميعي؛ لا يمكن ترحيل أرصدة عليه. استخدم حساباً ورقياً فقط.', 'danger')
            return _redirect_accounts_hub()
        if code in {'1151','2121','5310'} and not emp_id_val:
            flash('اختر الموظف عند استخدام حساب السلف أو الرواتب.', 'danger')
            return _redirect_accounts_hub()
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
        return _redirect_accounts_hub()
    ok, period_err = is_period_open_for_date(d)
    if not ok:
        abort(403, period_err or 'الفترة المالية مغلقة')
    gate_errors = validate_journal_gates(d, lines)
    if gate_errors:
        flash('؛ '.join(gate_errors[:3]) + (' ...' if len(gate_errors) > 3 else ''), 'danger')
        return _redirect_accounts_hub()
    je = JournalEntry(entry_number=_gen_number(), date=d, branch_code=branch, description=description, status='draft', total_debit=total_debit, total_credit=total_credit, created_by=getattr(current_user,'id',None))
    db.session.add(je)
    db.session.flush()
    for i, ln in enumerate(lines, start=1):
        db.session.add(JournalLine(journal_id=je.id, line_no=i, account_id=ln['account_id'], debit=ln['debit'], credit=ln['credit'], cost_center=ln['cost_center'], description=ln['description'], attachment_path=ln['attachment_path'], line_date=ln['line_date'], employee_id=ln['employee_id']))
    db.session.add(JournalAudit(journal_id=je.id, action='create', user_id=getattr(current_user,'id',None), before_json=None, after_json=json.dumps({'id': je.id, 'number': je.entry_number}, ensure_ascii=False)))
    db.session.commit()
    flash('تم إضافة القيد', 'success')
    return _redirect_accounts_hub()


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
    """تُرجع فقط الحسابات من الشجرة الجديدة (الحسابات الورقية فقط)، مع اسم عرض محلّل (كود – اسم)."""
    try:
        from data.coa_new_tree import leaf_coa_dict, get_account_display_name
        from models import Account
        coa = leaf_coa_dict()
        # الحصول على الحسابات من DB التي تطابق الشجرة الجديدة
        codes = list(coa.keys())
        rows = db.session.query(Account.id, Account.code, Account.name)\
            .filter(Account.code.in_(codes))\
            .order_by(Account.code.asc()).all()
        # إذا لم تكن موجودة في DB، إنشاؤها من الشجرة
        result = []
        for code in sorted(codes):
            # البحث في النتائج من DB
            db_row = next((r for r in rows if str(r[1]) == code), None)
            if db_row:
                result.append({'id': db_row[0], 'code': str(db_row[1]), 'name': get_account_display_name(db_row[1], db_row[2])})
            else:
                # استخدام بيانات الشجرة
                info = coa.get(code, {})
                result.append({'id': None, 'code': code, 'name': info.get('name', code)})
        return jsonify(result)
    except Exception as e:
        # Fallback: استخدام DB فقط مع اسم عرض محلّل
        try:
            from data.coa_new_tree import get_account_display_name
        except Exception:
            get_account_display_name = lambda c, n: n or c
        rows = db.session.query(Account.id, Account.code, Account.name).order_by(Account.code.asc()).all()
        return jsonify([{'id': rid, 'code': code, 'name': get_account_display_name(code, name)} for (rid, code, name) in rows])

@csrf.exempt
@bp.route('/<int:jid>', methods=['GET', 'POST'])
@login_required
def edit_entry(jid):
    """لا شاشة تعديل قيد مستقلة — GET يوجّه للحسابات المتكاملة؛ POST يُعالج ثم توجيه (لتوافق الطلبات)."""
    je = _journal_with_lines_options(JournalEntry.query).filter_by(id=jid).first_or_404()
    if request.method == 'GET':
        if not _can('journal', 'view'):
            flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
            return redirect(url_for('main.dashboard'))
        return _redirect_accounts_hub()
    ok, err = can_mutate_journal(je)
    if not ok:
        abort(403, err or 'الفترة المالية مغلقة')
    if je.status == 'posted' and getattr(current_user,'role','')!='admin':
        flash("لا يمكنك تعديل قيد مرحل بدون صلاحية 'Modify Posted'.", 'danger')
        return _redirect_accounts_hub()
    if not _can('journal','edit'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return _redirect_accounts_hub()
    before = {'desc': je.description, 'date': str(je.date), 'total_debit': float(je.total_debit or 0), 'total_credit': float(je.total_credit or 0)}
    description = (request.form.get('description') or '').strip()
    if not description:
        flash('يرجى إدخال وصف القيد.', 'danger')
        return _redirect_accounts_hub()
    je.description = description
    je.updated_by = getattr(current_user,'id',None)
    db.session.add(JournalAudit(journal_id=je.id, action='edit', user_id=getattr(current_user,'id',None), before_json=json.dumps(before, ensure_ascii=False), after_json=json.dumps({'desc': je.description}, ensure_ascii=False)))
    db.session.commit()
    flash('تم حفظ التعديل', 'success')
    return _redirect_accounts_hub()

@csrf.exempt
@bp.route('/<int:jid>/post', methods=['POST'])
@login_required
def post_entry(jid):
    je = _journal_with_lines_options(JournalEntry.query).filter_by(id=jid).first_or_404()
    ok, err = can_mutate_journal(je)
    if not ok:
        abort(403, err or 'الفترة المالية مغلقة')
    if not _can('journal','edit'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return _redirect_accounts_hub()
    if je.status == 'posted':
        flash('القيد مرحل مسبقاً', 'warning')
        return _redirect_accounts_hub()
    total_debit = 0.0
    total_credit = 0.0
    for ln in je.lines:
        total_debit += float(ln.debit or 0)
        total_credit += float(ln.credit or 0)
    if round(total_debit,2) != round(total_credit,2) or total_debit <= 0:
        flash('لا يمكن ترحيل القيد لأن مجموع المدين لا يساوي مجموع الدائن.', 'danger')
        return _redirect_accounts_hub()
    for ln in je.lines:
        acc = ln.account
        if not acc:
            acc = Account.query.get(ln.account_id)
        if acc:
            db.session.add(LedgerEntry(date=ln.line_date, account_id=acc.id, debit=ln.debit, credit=ln.credit, description=f'JE {je.entry_number} L{ln.line_no} {ln.description}'))
    je.status = 'posted'
    je.posted_by = getattr(current_user,'id',None)
    db.session.add(JournalAudit(journal_id=je.id, action='post', user_id=getattr(current_user,'id',None), before_json=None, after_json=json.dumps({'status': 'posted'}, ensure_ascii=False)))
    db.session.commit()
    flash('تم ترحيل القيد', 'success')
    return _redirect_accounts_hub()

@bp.route('/<int:jid>/print', methods=['GET'])
@login_required
def print_entry(jid):
    if not _can('journal','print'):
        flash('You do not have permission / لا تملك صلاحية الوصول', 'danger')
        return _redirect_accounts_hub()
    je = _journal_with_lines_options(JournalEntry.query).filter_by(id=jid).first_or_404()
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
    cash_acc = _acc_by_code('1111')
    cap_acc = _acc_by_code('3110')
    je = JournalEntry(entry_number=f"JE-CAP-{int(time.time())}", date=get_saudi_now().date(), branch_code=branch, description=f"Capital Injection {amt}", status='posted', total_debit=amt, total_credit=amt, created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
    db.session.add(je); db.session.flush()
    db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=cash_acc.id, description='Capital Cash', line_date=je.date, debit=amt, credit=0.0))
    db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=cap_acc.id, description='Owner Capital', line_date=je.date, debit=0.0, credit=amt))
    db.session.commit()
    flash('تم إنشاء قيد رأس المال', 'success')
    return _redirect_accounts_hub()

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
    pl_acc = _acc_by_code('3220')
    if net>0:
        lines.append(('CR', pl_acc.id, net, 'صافي الربح إلى 3220'))
        total_cr += net
    elif net<0:
        lines.append(('DR', pl_acc.id, -net, 'صافي الخسارة من 3220'))
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
    return _redirect_accounts_hub()
@bp.route('/api/journals', methods=['GET'])
def api_journals():
    try:
        import math
        from datetime import datetime as _dt
        start_s = (request.args.get('start') or '').strip()
        end_s = (request.args.get('end') or '').strip()
        acc_code = (request.args.get('account') or '').strip()
        posted = (request.args.get('posted') or '').strip().lower()
        source = (request.args.get('source') or '').strip()
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(100, max(10, request.args.get('per_page', 25, type=int)))
        q = JournalEntry.query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc())
        if start_s:
            try:
                sdt = _dt.strptime(start_s, '%Y-%m-%d').date(); q = q.filter(JournalEntry.date >= sdt)
            except Exception:
                pass
        if end_s:
            try:
                edt = _dt.strptime(end_s, '%Y-%m-%d').date(); q = q.filter(JournalEntry.date <= edt)
            except Exception:
                pass
        if posted in ('posted','draft'):
            q = q.filter(JournalEntry.status == posted)
        if source:
            try:
                if hasattr(JournalEntry, 'source_ref_type'):
                    q = q.filter(JournalEntry.source_ref_type == source)
            except Exception:
                pass
        total = q.count()
        pages = max(1, math.ceil(total / per_page)) if total else 1
        page = min(page, pages)
        q = _journal_with_lines_options(q)
        rows = q.offset((page - 1) * per_page).limit(per_page).all()
        meta = _journal_list_entry_meta(rows)
        data = []
        for je in rows:
            d = {
                'id': int(getattr(je,'id',0) or 0),
                'entry_number': getattr(je,'entry_number',''),
                'date': str(getattr(je,'date',None) or ''),
                'branch': getattr(je,'branch_code',None),
                'description': getattr(je,'description',''),
                'status': getattr(je,'status',''),
                'total_debit': float(getattr(je,'total_debit',0) or 0),
                'total_credit': float(getattr(je,'total_credit',0) or 0),
                'source_ref_type': getattr(je,'source_ref_type',None),
                'source_ref_id': getattr(je,'source_ref_id',None),
                'lines': [],
                'operation_detail': meta.get(je.id, {})
            }
            for ln in (getattr(je,'lines',[]) or []):
                try:
                    acc = getattr(ln,'account',None)
                    if acc_code and (getattr(acc,'code',None) or '') != acc_code:
                        continue
                    code_val = getattr(acc,'code',None) or ''
                    d['lines'].append({
                        'line_no': int(getattr(ln,'line_no',0) or 0),
                        'account_code': code_val,
                        'account_name': get_account_display_name(code_val, getattr(acc,'name',None)),
                        'debit': float(getattr(ln,'debit',0) or 0),
                        'credit': float(getattr(ln,'credit',0) or 0),
                        'description': getattr(ln,'description',''),
                        'line_date': str(getattr(ln,'line_date',None) or '')
                    })
                except Exception:
                    continue
            if (not acc_code) or d['lines']:
                data.append(d)
        from flask import jsonify
        return jsonify({
            'ok': True,
            'entries': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': pages,
        })
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/transactions/post', methods=['POST'])
@csrf.exempt
def api_transactions_post():
    try:
        # Require admin for posting
        try:
            from flask_login import current_user
            from app.routes import _has_role
            if not _has_role(current_user, ['admin','accountant']):
                return jsonify({'ok': False, 'error': 'forbidden'}), 403
        except Exception:
            pass
        payload = request.get_json(force=True, silent=True) or {}
        entries = payload.get('entries') or []
        created = []
        for e in entries:
            date_s = (e.get('date') or '').strip()
            try:
                from datetime import datetime as _dt
                dval = _dt.strptime(date_s or '', '%Y-%m-%d').date()
            except Exception:
                from models import get_saudi_now
                dval = get_saudi_now().date()
            desc = (e.get('description') or '').strip() or 'API posted'
            branch = (e.get('branch') or '').strip() or None
            src_type = (e.get('source_ref_type') or '').strip() or None
            src_id = (e.get('source_ref_id') or '').strip() or None
            # Idempotency: if source_ref matches existing, skip
            if src_type and src_id:
                try:
                    exist = JournalEntry.query.filter(JournalEntry.source_ref_type == src_type, JournalEntry.source_ref_id == src_id).first()
                    if exist:
                        continue
                except Exception:
                    pass
            # Build totals
            lines = e.get('lines') or []
            td = float(sum([float(l.get('debit') or 0) for l in lines]))
            tc = float(sum([float(l.get('credit') or 0) for l in lines]))
            if round(td - tc, 2) != 0.0:
                continue
            je = JournalEntry(entry_number=f"JE-API-{int(getattr(current_user,'id',0) or 0)}-{int(JournalEntry.query.count()+1)}", date=dval, branch_code=branch, description=desc, status='posted', total_debit=round(td,2), total_credit=round(tc,2), created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
            db.session.add(je); db.session.flush()
            try:
                setattr(je,'source_ref_type',src_type); setattr(je,'source_ref_id',src_id)
            except Exception:
                pass
            ln_no = 0
            for l in lines:
                ln_no += 1
                code = (l.get('account_code') or '').strip()
                debit = float(l.get('debit') or 0)
                credit = float(l.get('credit') or 0)
                ldesc = (l.get('description') or '').strip() or 'API line'
                ldate_s = (l.get('date') or '').strip()
                try:
                    from datetime import datetime as _dt
                    ldate = _dt.strptime(ldate_s, '%Y-%m-%d').date()
                except Exception:
                    ldate = dval
                acc = Account.query.filter(Account.code == code).first()
                if not acc:
                    acc = Account(code=code, name=code, type='EXPENSE'); db.session.add(acc); db.session.flush()
                try:
                    cc = (l.get('cost_center') or '').strip() or None
                except Exception:
                    cc = None
                db.session.add(JournalLine(journal_id=je.id, line_no=ln_no, account_id=acc.id, debit=debit, credit=credit, description=ldesc, line_date=ldate, cost_center=cc))
            try:
                db.session.commit()
                try:
                    from models import JournalAudit
                    db.session.add(JournalAudit(journal_id=je.id, action='post', user_id=getattr(current_user,'id',None), before_json=None, after_json=None))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                created.append(je.entry_number)
            except Exception:
                db.session.rollback()
        return jsonify({'ok': True, 'created': created})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/reconcile/vat', methods=['POST'])
def api_reconcile_vat():
    try:
        from datetime import datetime as _dt
        start_s = (request.args.get('start') or request.form.get('start') or '').strip()
        end_s = (request.args.get('end') or request.form.get('end') or '').strip()
        start = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else get_saudi_now().date().replace(day=1)
        end = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else get_saudi_now().date()
        # Invoices VAT
        out_v = float(db.session.query(func.coalesce(func.sum(SalesInvoice.tax_amount), 0)).filter(SalesInvoice.date.between(start, end)).scalar() or 0)
        in_v = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.tax_amount), 0)).filter(PurchaseInvoice.date.between(start, end)).scalar() or 0) + float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.tax_amount), 0)).filter(ExpenseInvoice.date.between(start, end)).scalar() or 0)
        # Journals VAT
        j_out = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0)).join(Account, JournalLine.account_id == Account.id).filter(Account.code == '2141').filter(JournalLine.line_date.between(start, end)).scalar() or 0)
        j_in = float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).join(Account, JournalLine.account_id == Account.id).filter(Account.code == '1170').filter(JournalLine.line_date.between(start, end)).scalar() or 0)
        from flask import jsonify
        return jsonify({'ok': True, 'invoices': {'output_vat': out_v, 'input_vat': in_v, 'net_vat': (out_v-in_v)}, 'journals': {'output_vat': j_out, 'input_vat': j_in, 'net_vat': (j_out-j_in)}, 'diff': {'output_vat': (out_v - j_out), 'input_vat': (in_v - j_in), 'net_vat': ((out_v-in_v) - (j_out-j_in))}})
    except Exception as e:
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/api/close/year', methods=['POST'])
def api_close_year():
    try:
        from datetime import date as _d
        year = int(request.args.get('year') or request.form.get('year') or get_saudi_now().year)
        start = _d(year, 1, 1); end = _d(year, 12, 31)
        # Sum P&L accounts
        rev = float(db.session.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0)).join(Account, JournalLine.account_id == Account.id).filter(Account.type.in_(['REVENUE','OTHER_INCOME'])).filter(JournalLine.line_date.between(start, end)).scalar() or 0)
        exp = float(db.session.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).join(Account, JournalLine.account_id == Account.id).filter(Account.type.in_(['EXPENSE','OTHER_EXPENSE','COGS','TAX'])).filter(JournalLine.line_date.between(start, end)).scalar() or 0)
        net = round(rev - exp, 2)
        # Create closing entry: move all to 3220 أرباح السنة الحالية
        re_acc = Account.query.filter(Account.code == '3220').first()
        if not re_acc:
            re_acc = Account(code='3220', name='أرباح السنة الحالية', type='EQUITY'); db.session.add(re_acc); db.session.flush()
        je = JournalEntry(entry_number=f"JE-CLOSE-{year}", date=end, branch_code=None, description=f"Year-end close {year}", status='posted', total_debit=(net if net<0 else 0.0), total_credit=(net if net>0 else 0.0), created_by=getattr(current_user,'id',None), posted_by=getattr(current_user,'id',None))
        db.session.add(je); db.session.flush()
        if net > 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=re_acc.id, debit=0.0, credit=net, description='Close to RE', line_date=end))
        elif net < 0:
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=re_acc.id, debit=abs(net), credit=0.0, description='Close to RE', line_date=end))
        db.session.commit()
        from flask import jsonify
        return jsonify({'ok': True, 'year': year, 'net_income': net, 'entry_number': je.entry_number})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import jsonify
        return jsonify({'ok': False, 'error': str(e)}), 500
@bp.route('/api/journals/delete', methods=['POST'])
@csrf.exempt
@login_required
def api_journals_delete():
    try:
        data = request.get_json(silent=True) or {}
        entry_no = (data.get('entry_number') or request.form.get('entry_number') or '').strip()
        if not entry_no:
            return jsonify({'ok': False, 'error': 'missing_entry_number'}), 400
        je = JournalEntry.query.filter(JournalEntry.entry_number == entry_no).first()
        if not je:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        ok, err = can_mutate_journal(je)
        if not ok:
            return jsonify({'ok': False, 'error': 'period_closed', 'message': err or 'الفترة مغلقة؛ لا يمكن حذف القيد.'}), 403
        # القاعدة: حذف القيد = حذف الفاتورة/العملية المرتبطة. إذا القيد مرتبط بفاتورة/عملية يُسمح بحذفه حتى لو منشور.
        has_linked = (getattr(je, 'invoice_id', None) is not None and (getattr(je, 'invoice_type', None) or '').strip()) or getattr(je, 'salary_id', None) is not None
        if not has_linked and (getattr(je, 'status', None) or '').strip().lower() == 'posted':
            return jsonify({'ok': False, 'error': 'cannot_delete_posted', 'message': 'لا يمكن حذف قيد منشور (يدوي). أرجِعْه لمسودة أولاً.'}), 400
        delete_journal_entry_and_linked_invoice(je)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/journals/revert', methods=['POST'])
@csrf.exempt
@login_required
def api_journals_revert():
    """إرجاع لمسودة — منشور فقط."""
    try:
        data = request.get_json(silent=True) or {}
        entry_no = (data.get('entry_number') or request.form.get('entry_number') or '').strip()
        if not entry_no:
            return jsonify({'ok': False, 'error': 'missing_entry_number'}), 400
        je = JournalEntry.query.filter(JournalEntry.entry_number == entry_no).first()
        if not je:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        if (getattr(je, 'status', None) or '').strip().lower() != 'posted':
            return jsonify({'ok': False, 'error': 'not_posted', 'message': 'القيد مسودة بالفعل.'}), 400
        ok, err = can_mutate_journal(je)
        if not ok:
            return jsonify({'ok': False, 'error': 'period_closed', 'message': err or 'الفترة المالية مغلقة'}), 403
        je.status = 'draft'
        je.updated_by = getattr(current_user, 'id', None)
        try:
            db.session.add(JournalAudit(journal_id=je.id, action='revert_to_draft', user_id=getattr(current_user, 'id', None), before_json=json.dumps({'status': 'posted'}, ensure_ascii=False), after_json=json.dumps({'status': 'draft'}, ensure_ascii=False)))
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True, 'status': 'draft'})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/journals/repost', methods=['POST'])
@csrf.exempt
@login_required
def api_journals_repost():
    """إعادة نشر — مسودة فقط."""
    try:
        data = request.get_json(silent=True) or {}
        entry_no = (data.get('entry_number') or request.form.get('entry_number') or '').strip()
        if not entry_no:
            return jsonify({'ok': False, 'error': 'missing_entry_number'}), 400
        je = _journal_with_lines_options(JournalEntry.query).filter(JournalEntry.entry_number == entry_no).first()
        if not je:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        if (getattr(je, 'status', None) or '').strip().lower() == 'posted':
            return jsonify({'ok': False, 'error': 'already_posted', 'message': 'القيد منشور مسبقاً.'}), 400
        ok, err = can_mutate_journal(je)
        if not ok:
            return jsonify({'ok': False, 'error': 'period_closed', 'message': err or 'الفترة المالية مغلقة'}), 403
        total_debit = sum(float(getattr(ln, 'debit', 0) or 0) for ln in (getattr(je, 'lines', []) or []))
        total_credit = sum(float(getattr(ln, 'credit', 0) or 0) for ln in (getattr(je, 'lines', []) or []))
        if round(total_debit, 2) != round(total_credit, 2) or total_debit <= 0:
            return jsonify({'ok': False, 'error': 'imbalanced', 'message': 'مجموع المدين لا يساوي مجموع الدائن.'}), 400
        for ln in (getattr(je, 'lines', []) or []):
            acc = getattr(ln, 'account', None) or Account.query.get(ln.account_id)
            if acc:
                db.session.add(LedgerEntry(date=ln.line_date, account_id=acc.id, debit=ln.debit, credit=ln.credit, description=f'JE {je.entry_number} L{ln.line_no} {ln.description}'))
        je.status = 'posted'
        je.posted_by = getattr(current_user, 'id', None)
        try:
            db.session.add(JournalAudit(journal_id=je.id, action='post', user_id=getattr(current_user, 'id', None), before_json=None, after_json=json.dumps({'status': 'posted'}, ensure_ascii=False)))
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True, 'status': 'posted'})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/journals/reverse', methods=['POST'])
@csrf.exempt
@login_required
def api_journals_reverse():
    """عكس القيد — إنشاء قيد معكوس منشور."""
    try:
        data = request.get_json(silent=True) or {}
        entry_no = (data.get('entry_number') or request.form.get('entry_number') or '').strip()
        if not entry_no:
            return jsonify({'ok': False, 'error': 'missing_entry_number'}), 400
        je = _journal_with_lines_options(JournalEntry.query).filter(JournalEntry.entry_number == entry_no).first()
        if not je:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        rev_num = f"JE-REV-{je.entry_number}"
        if JournalEntry.query.filter(JournalEntry.entry_number == rev_num).first():
            return jsonify({'ok': False, 'error': 'reversal_exists', 'message': 'يوجد قيد معكوس لهذا القيد مسبقاً.'}), 400
        ok, err = can_mutate_journal(je)
        if not ok:
            return jsonify({'ok': False, 'error': 'period_closed', 'message': err or 'الفترة المالية مغلقة'}), 403
        total_dr = sum(float(getattr(ln, 'debit', 0) or 0) for ln in (getattr(je, 'lines', []) or []))
        total_cr = sum(float(getattr(ln, 'credit', 0) or 0) for ln in (getattr(je, 'lines', []) or []))
        rev = JournalEntry(entry_number=rev_num, date=je.date, branch_code=je.branch_code, description=f'عكس قيد {je.entry_number}', status='posted', total_debit=total_cr, total_credit=total_dr, created_by=getattr(current_user, 'id', None), posted_by=getattr(current_user, 'id', None))
        db.session.add(rev)
        db.session.flush()
        for ln in (getattr(je, 'lines', []) or []):
            acc = getattr(ln, 'account', None) or Account.query.get(ln.account_id)
            if not acc:
                continue
            db.session.add(JournalLine(journal_id=rev.id, line_no=ln.line_no, account_id=acc.id, debit=ln.credit, credit=ln.debit, description=f'عكس {ln.description}', line_date=ln.line_date))
            db.session.add(LedgerEntry(date=ln.line_date, account_id=acc.id, debit=ln.credit, credit=ln.debit, description=f'JE {rev_num} rev {je.entry_number}'))
        try:
            db.session.add(JournalAudit(journal_id=rev.id, action='create', user_id=getattr(current_user, 'id', None), before_json=None, after_json=json.dumps({'reverse_of': je.entry_number}, ensure_ascii=False)))
        except Exception:
            pass
        db.session.commit()
        return jsonify({'ok': True, 'entry_number': rev_num})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
