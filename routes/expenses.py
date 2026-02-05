# Phase 2 – Expenses blueprint. Same URLs (/expenses, …), no prefix.
from __future__ import annotations

import json
import os
from decimal import Decimal
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app import db
from models import (
    ExpenseInvoice,
    ExpenseInvoiceItem,
    Payment,
    LedgerEntry,
    JournalEntry,
    JournalLine,
    get_saudi_now,
)
from forms import ExpenseInvoiceForm
from app.routes import (
    _pm_account,
    _create_expense_journal,
    _create_expense_payment_journal,
    _expense_account_by_code,
    _expense_account_for,
)
from services.account_validation import (
    validate_account_for_transaction,
    TRANSACTION_TYPE_EXPENSE,
)

bp = Blueprint('expenses', __name__)


def _parse_decimal(s):
    try:
        t = (s or '').strip()
        if not t:
            return Decimal('0')
        trans = str.maketrans('٠١٢٣٤٥٦٧٨٩٬٫', '0123456789,.')
        t = t.translate(trans).replace(',', '')
        return Decimal(t)
    except Exception:
        return Decimal('0')


def _exp_err_log(section: str, e: Exception, extra: str = ''):
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        p = os.path.join(root, 'static', 'uploads', 'exp_err.txt')
        with open(p, 'a', encoding='utf-8') as f:
            f.write(f'\n=== /expenses {section} ===\n')
            f.write(str(e) + '\n')
            if extra:
                f.write(extra + '\n')
            import traceback
            f.write(traceback.format_exc() + '\n')
    except Exception:
        pass


@bp.route('/expenses/api/expense_types', methods=['GET'], endpoint='expense_types_api')
@login_required
def expense_types_api():
    """Return expense categories and sub-types for type-driven expense form."""
    try:
        from data.expense_types import EXPENSE_CATEGORIES
        return current_app.response_class(
            json.dumps({'categories': EXPENSE_CATEGORIES}, ensure_ascii=False),
            mimetype='application/json',
        )
    except Exception as e:
        _exp_err_log('expense_types_api', e)
        return json.dumps({'categories': []}), 500


@bp.route('/expenses', methods=['GET', 'POST'], endpoint='expenses')
@login_required
def expenses():
    try:
        form = ExpenseInvoiceForm()
    except Exception as e:
        _exp_err_log('form init', e)
        return ('', 500)
    try:
        form.date.data = get_saudi_now().date()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    if request.method == 'POST':
        # Type-driven single expense (نوع المصروف أولاً)
        expense_type = (request.form.get('expense_type') or '').strip()
        expense_sub_type = (request.form.get('expense_sub_type') or '').strip()
        amount_str = request.form.get('amount') or request.form.get('expense_amount') or ''
        if expense_type and expense_sub_type and amount_str:
            try:
                from data.expense_types import get_sub_type_by_ids
                amt = _parse_decimal(amount_str)
                if amt <= 0:
                    flash(_('Invalid amount'), 'danger')
                    return redirect(url_for('expenses.expenses'))
                config = get_sub_type_by_ids(expense_type, expense_sub_type)
                if not config:
                    flash(_('Invalid expense type'), 'danger')
                    return redirect(url_for('expenses.expenses'))
                is_waste = config.get('is_internal_adjustment') and expense_sub_type == 'spoilage_waste'
                date_str = request.form.get('date') or get_saudi_now().date().isoformat()
                if is_waste:
                    pm = 'INTERNAL'
                    status_val = 'posted'
                    use_vat = False
                else:
                    pm = (request.form.get('payment_method') or 'CASH').strip().upper()
                    if pm not in ('CASH', 'BANK'):
                        pm = 'CASH'
                    status_val = (request.form.get('status') or 'paid').strip().lower()
                    if status_val not in ('paid', 'partial', 'unpaid'):
                        status_val = 'paid'
                    # الضريبة تُطبّق فقط عند تفعيل خانة "تطبيق 15% ض.ق.م" — لا نعتمد على default_vat للتصنيف
                    apply_vat = (str(request.form.get('apply_vat') or '').lower() in {'on', 'true', '1', 'yes'})
                    use_vat = bool(apply_vat)
                desc = (request.form.get('description') or request.form.get('expense_description') or '').strip() or 'Expense'
                inv_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                from services.gl_truth import can_create_invoice_on_date
                ok, period_err = can_create_invoice_on_date(inv_date)
                if not ok:
                    flash(period_err or _('الفترة المالية مغلقة لهذا التاريخ.'), 'danger')
                    return redirect(url_for('expenses.expenses'))
                total_before = float(amt)
                tax_amt = (total_before * 0.15) if use_vat else 0.0
                total_inc_tax = round(total_before + tax_amt, 2)
                try:
                    last = ExpenseInvoice.query.order_by(ExpenseInvoice.id.desc()).first()
                    seq = (int(getattr(last, 'id', 0) or 0) + 1) if last else 1
                    inv_no = f"INV-EXP-{get_saudi_now().year}-{seq:04d}"
                except Exception:
                    inv_no = f"INV-EXP-{get_saudi_now().strftime('%Y%m%d%H%M%S')}"
                inv_kw = dict(
                    invoice_number=inv_no,
                    date=inv_date,
                    payment_method=pm,
                    total_before_tax=total_before,
                    tax_amount=tax_amt,
                    discount_amount=0.0,
                    total_after_tax_discount=total_inc_tax,
                    status=status_val,
                    user_id=getattr(current_user, 'id', 1),
                )
                try:
                    from sqlalchemy import inspect
                    insp = inspect(db.engine)
                    cols = [c['name'] for c in insp.get_columns(ExpenseInvoice.__tablename__)]
                    if 'liability_account_code' in cols:
                        inv_kw['liability_account_code'] = config.get('liability_code') or None
                except Exception:
                    pass
                inv = ExpenseInvoice(**inv_kw)
                db.session.add(inv)
                db.session.flush()
                item = ExpenseInvoiceItem(
                    invoice_id=inv.id,
                    description=desc,
                    account_code=config.get('account_code'),
                    quantity=Decimal('1'),
                    price_before_tax=Decimal(str(total_before)),
                    tax=Decimal(str(tax_amt)),
                    discount=Decimal('0'),
                    total_price=Decimal(str(total_inc_tax)),
                )
                db.session.add(item)
                if not is_waste and status_val == 'paid' and total_inc_tax > 0:
                    db.session.add(Payment(invoice_id=inv.id, invoice_type='expense', amount_paid=float(total_inc_tax), payment_method=pm))
                _create_expense_journal(inv)
                if not is_waste and status_val != 'paid' and total_inc_tax > 0:
                    try:
                        _create_expense_payment_journal(inv.date, float(total_inc_tax), inv.invoice_number, pm or 'CASH', getattr(inv, 'liability_account_code', None))
                    except Exception:
                        pass
                flash(_('Expense saved'), 'success')
            except Exception as e:
                db.session.rollback()
                try:
                    current_app.logger.exception('Type-driven expense save: %s', e)
                except Exception:
                    pass
                flash(_('Failed to save expense'), 'danger')
            return redirect(url_for('expenses.expenses'))

        try:
            date_str = request.form.get('date') or get_saudi_now().date().isoformat()
            pm = (request.form.get('payment_method') or 'CASH').strip().upper()
            if pm not in ('CASH', 'BANK'):
                pm = 'CASH'
            status_val = (request.form.get('status') or 'paid').strip().lower()
            if status_val not in ('paid', 'partial', 'unpaid'):
                status_val = 'paid'
            idx = 0
            total_before = Decimal('0.00')
            total_tax = Decimal('0.00')
            total_disc = Decimal('0.00')
            items_buffer = []
            while True:
                prefix = f"items-{idx}-"
                desc = request.form.get(prefix + 'description')
                qty = request.form.get(prefix + 'quantity')
                price = request.form.get(prefix + 'price_before_tax')
                tax = request.form.get(prefix + 'tax')
                disc = request.form.get(prefix + 'discount')
                acc_code = request.form.get(prefix + 'account_code')
                if desc is None and qty is None and price is None and tax is None and disc is None:
                    break
                if not desc and not qty and not price:
                    idx += 1
                    continue
                try:
                    qf = _parse_decimal(qty)
                    pf = _parse_decimal(price)
                    tf = _parse_decimal(tax)
                    df = _parse_decimal(disc)
                except Exception:
                    qf = pf = tf = df = Decimal('0')
                line_total = (qf * pf) - df + tf
                total_before += (qf * pf)
                total_tax += tf
                total_disc += df
                try:
                    current_app.logger.info(
                        "Expense item: desc=%s qty=%s price=%s tax=%s disc=%s acc=%s",
                        (desc or '').strip(), qf, pf, tf, df, (acc_code or '').strip().upper(),
                    )
                except Exception:
                    pass
                items_buffer.append({
                    'description': (desc or '').strip(),
                    'quantity': qf,
                    'price_before_tax': pf,
                    'tax': tf,
                    'discount': df,
                    'total_price': line_total,
                    'account_code': (acc_code or '').strip().upper(),
                })
                idx += 1
            # الضريبة تُطبّق فقط عند تفعيل خانة "تطبيق 15% ض.ق.م" (اسم الحقل: apply_vat أو apply_vat_all)
            apply_vat_all_raw = request.form.get('apply_vat_all') or request.form.get('apply_vat') or ''
            apply_vat_all = (str(apply_vat_all_raw).lower() in {'on', 'true', '1', 'yes'})
            
            # Log for debugging
            try:
                current_app.logger.info(f"Expense VAT calculation: apply_vat_all_raw='{apply_vat_all_raw}', apply_vat_all={apply_vat_all}, total_before={total_before}, total_disc={total_disc}")
            except Exception:
                pass
            
            # إذا لم يُفعّل المستخدم "تطبيق 15% ض.ق.م" نُصفّر الضريبة ولا نعتمد على أي قيمة ضريبة أُرسلت من الواجهة
            if not apply_vat_all:
                total_tax = Decimal('0.00')
                for item in items_buffer:
                    item['tax'] = Decimal('0')
                    item['total_price'] = (item['quantity'] * item['price_before_tax']) - item['discount']
            elif total_before > 0:
                # If apply_vat_all is checked, calculate VAT on subtotal (after discount)
                base_for_vat = total_before - total_disc
                calculated_vat = base_for_vat * Decimal('0.15')
                total_tax = calculated_vat
                if total_before > 0:
                    vat_ratio = calculated_vat / total_before
                    for item in items_buffer:
                        item_before = item['quantity'] * item['price_before_tax']
                        item_tax = item_before * vat_ratio
                        item['tax'] = item_tax
                        item['total_price'] = item_before - item['discount'] + item_tax
                try:
                    current_app.logger.info(f"VAT calculated: base_for_vat={base_for_vat}, calculated_vat={calculated_vat}, total_tax={total_tax}")
                except Exception:
                    pass

            # Validate each expense item account: must be leaf and EXPENSE/COGS (debit side)
            for row in items_buffer:
                ac = (row.get('account_code') or '').strip()
                if ac:
                    ok, err = validate_account_for_transaction(
                        ac, TRANSACTION_TYPE_EXPENSE, role="debit"
                    )
                    if not ok:
                        flash(err or _("الحساب غير صالح للمصروف."), "danger")
                        return redirect(request.url)

            inv_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            from services.gl_truth import can_create_invoice_on_date
            ok, period_err = can_create_invoice_on_date(inv_date)
            if not ok:
                flash(period_err or _('الفترة المالية مغلقة لهذا التاريخ.'), 'danger')
                return redirect(request.url)
            try:
                last = ExpenseInvoice.query.order_by(ExpenseInvoice.id.desc()).first()
                seq = (int(getattr(last, 'id', 0) or 0) + 1) if last else 1
                inv_no = f"INV-EXP-{get_saudi_now().year}-{seq:04d}"
            except Exception:
                inv_no = f"INV-EXP-{get_saudi_now().strftime('%Y%m%d%H%M%S')}"
            inv = ExpenseInvoice(
                invoice_number=inv_no,
                date=inv_date,
                payment_method=pm,
                total_before_tax=float(total_before),
                tax_amount=float(total_tax),
                discount_amount=float(total_disc),
                total_after_tax_discount=float(total_before - total_disc + total_tax),
                status=status_val,
                user_id=getattr(current_user, 'id', 1),
            )
            db.session.add(inv)
            db.session.flush()
            for row in items_buffer:
                item = ExpenseInvoiceItem(
                    invoice_id=inv.id,
                    description=row['description'],
                    account_code=(row.get('account_code') or '').strip() or None,
                    quantity=row['quantity'] or Decimal('0'),
                    price_before_tax=row['price_before_tax'] or Decimal('0'),
                    tax=row['tax'] or Decimal('0'),
                    discount=row['discount'] or Decimal('0'),
                    total_price=row['total_price'] or Decimal('0'),
                )
                db.session.add(item)
            pay_amt = 0.0
            if status_val == 'paid':
                pay_amt = float(inv.total_after_tax_discount or 0.0)
            elif status_val == 'partial':
                pv = request.form.get('partial_paid_amount')
                try:
                    pay_amt = float(_parse_decimal(pv) or Decimal('0'))
                except Exception:
                    pay_amt = 0.0
                total_inc_tax = float(inv.total_after_tax_discount or 0.0)
                if pay_amt > total_inc_tax:
                    pay_amt = total_inc_tax
            if pay_amt > 0.0:
                db.session.add(Payment(invoice_id=inv.id, invoice_type='expense', amount_paid=pay_amt, payment_method=pm))
            _create_expense_journal(inv)
            if pay_amt > 0.0 and status_val != 'paid':
                try:
                    _create_expense_payment_journal(inv.date, pay_amt, inv.invoice_number, pm or 'CASH')
                except Exception:
                    pass
            flash(_('Expense saved'), 'success')
        except Exception as e:
            db.session.rollback()
            try:
                current_app.logger.exception('Failed to save expense: %s', e)
            except Exception:
                pass
            flash(_('Failed to save expense'), 'danger')
        return redirect(url_for('expenses.expenses'))
    invs = []
    invs_json_str = '[]'
    try:
        invs = ExpenseInvoice.query.order_by(ExpenseInvoice.date.desc()).limit(50).all()
        invs_json = []
        for inv in invs:
            items = []
            for it in (getattr(inv, 'items', []) or []):
                items.append({
                    'description': getattr(it, 'description', ''),
                    'account_code': getattr(it, 'account_code', '') or '',
                    'quantity': float(getattr(it, 'quantity', 0) or 0),
                    'price_before_tax': float(getattr(it, 'price_before_tax', 0) or 0),
                    'tax': float(getattr(it, 'tax', 0) or 0),
                    'discount': float(getattr(it, 'discount', 0) or 0),
                    'total_price': float(getattr(it, 'total_price', 0) or 0),
                })
            invs_json.append({
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'date': inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '',
                'payment_method': getattr(inv, 'payment_method', ''),
                'total': float(getattr(inv, 'total_after_tax_discount', 0) or 0),
                'status': getattr(inv, 'status', ''),
                'items': items,
            })
        invs_json_str = json.dumps(invs_json)
    except Exception as e:
        _exp_err_log('query build', e)
        try:
            db.session.rollback()
        except Exception:
            pass
    # الحصول على قائمة الحسابات من الشجرة الجديدة
    expense_accounts_json = '[]'
    try:
        from data.coa_new_tree import leaf_coa_dict
        coa = leaf_coa_dict()
        expense_accounts = []
        for code, info in sorted(coa.items()):
            if info.get('type') == 'EXPENSE':
                expense_accounts.append({
                    'code': code,
                    'name': info.get('name', code),
                    'name_ar': info.get('name_ar', info.get('name', '')),
                    'name_en': info.get('name_en', ''),
                })
        expense_accounts_json = json.dumps(expense_accounts)
    except Exception:
        pass
    
    try:
        return render_template('expenses.html', form=form, invoices=invs, invoices_json=invs_json_str, expense_accounts_json=expense_accounts_json)
    except Exception as e:
        try:
            current_app.logger.exception('Expenses template render error: %s', e)
        except Exception:
            pass
        _exp_err_log('render', e)
        return ('', 500)


@bp.route('/expenses/delete/<int:eid>', methods=['POST'], endpoint='expense_delete')
@login_required
def expense_delete(eid):
    try:
        inv = ExpenseInvoice.query.get(int(eid))
        if not inv:
            flash(_('Expense invoice not found'), 'warning')
            return redirect(url_for('expenses.expenses'))
        for it in (inv.items or []):
            try:
                db.session.delete(it)
            except Exception:
                pass
        try:
            Payment.query.filter(
                Payment.invoice_id == inv.id,
                Payment.invoice_type == 'expense',
            ).delete(synchronize_session=False)
        except Exception:
            pass
        try:
            rows = JournalEntry.query.filter(
                JournalEntry.description.ilike(f'%{inv.invoice_number}%'),
            ).all()
            for je in (rows or []):
                JournalLine.query.filter(JournalLine.journal_id == je.id).delete(synchronize_session=False)
                db.session.delete(je)
        except Exception:
            pass
        try:
            db.session.query(LedgerEntry).filter(
                LedgerEntry.description.ilike(f'%{inv.invoice_number}%'),
            ).delete(synchronize_session=False)
        except Exception:
            pass
        db.session.delete(inv)
        db.session.commit()
        flash(_('Expense invoice deleted'), 'success')
    except Exception:
        db.session.rollback()
        flash(_('Failed to delete expense invoice'), 'danger')
    return redirect(url_for('expenses.expenses'))


@bp.route('/expenses/test', methods=['GET'], endpoint='expenses_test')
@login_required
def expenses_test():
    try:
        form = ExpenseInvoiceForm()
        return render_template('expenses.html', form=form, invoices=[], invoices_json='[]')
    except Exception as e:
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        return ('', 500)
