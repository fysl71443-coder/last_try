# Phase 2 – Suppliers blueprint. Same URLs.
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app import db
from models import Supplier
from app.routes import ext_db

bp = Blueprint('suppliers', __name__)


def _suppliers_query(q: str | None):
    query = Supplier.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Supplier.name.ilike(like))
            | (Supplier.contact_person.ilike(like))
            | (Supplier.phone.ilike(like))
            | (Supplier.email.ilike(like))
            | (Supplier.tax_number.ilike(like))
            | (Supplier.address.ilike(like))
            | (Supplier.notes.ilike(like))
        )
    return query.order_by(Supplier.name.asc())


@bp.route('/suppliers/edit/<int:sid>', methods=['GET', 'POST'], endpoint='suppliers_edit')
@login_required
def suppliers_edit(sid):
    supplier = Supplier.query.get_or_404(sid)
    if request.method == 'POST':
        supplier.name = request.form.get('name', supplier.name)
        supplier.contact_person = request.form.get('contact_person', supplier.contact_person)
        supplier.phone = request.form.get('phone', supplier.phone)
        supplier.email = request.form.get('email', supplier.email)
        supplier.tax_number = request.form.get('tax_number', supplier.tax_number)
        supplier.address = request.form.get('address', supplier.address)
        supplier.notes = request.form.get('notes', supplier.notes)
        supplier.active = (
            str(request.form.get('active', supplier.active)).lower() in ['1', 'true', 'yes', 'on']
        )
        try:
            db.session.commit()
            flash('✅ Supplier updated successfully', 'success')
            return redirect(url_for('suppliers.suppliers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating supplier: {e}', 'danger')
    return render_template('supplier_edit.html', supplier=supplier)


@bp.route('/suppliers', methods=['GET', 'POST'], endpoint='suppliers')
@login_required
def suppliers():
    if request.method == 'POST':
        try:
            cr = (request.form.get('cr_number') or '').strip() or None
            iban = (request.form.get('iban') or '').strip() or None
            notes_in = (request.form.get('notes') or '').strip() or None
            notes_extra = []
            if notes_in:
                notes_extra.append(notes_in)
            if cr:
                notes_extra.append(f"CR: {cr}")
            if iban:
                notes_extra.append(f"IBAN: {iban}")
            notes_text = ' | '.join(notes_extra) if notes_extra else None

            s = Supplier(
                name=(request.form.get('name') or '').strip(),
                contact_person=request.form.get('contact_person') or None,
                phone=request.form.get('phone') or None,
                email=request.form.get('email') or None,
                tax_number=request.form.get('tax_number') or None,
                address=request.form.get('address') or None,
                payment_method=(request.form.get('payment_method') or 'CASH').strip().upper(),
                notes=notes_text,
                active=(
                    str(request.form.get('active', '')).lower() in ['1', 'true', 'yes', 'on']
                ),
            )
            if not s.name:
                raise ValueError('Name is required')
            if ext_db is not None:
                ext_db.session.add(s)
                ext_db.session.commit()
            else:
                db.session.add(s)
                db.session.commit()
            flash('Supplier added', 'success')
        except Exception as e:
            if ext_db is not None:
                ext_db.session.rollback()
            else:
                db.session.rollback()
            flash(f'Could not add supplier: {e}', 'danger')
        return redirect(url_for('suppliers.suppliers'))
    try:
        q = (request.args.get('q') or '').strip()
        all_suppliers = _suppliers_query(q).all()
    except Exception:
        all_suppliers = []
    return render_template('suppliers.html', suppliers=all_suppliers)


@bp.route('/suppliers/list', methods=['GET'], endpoint='suppliers_list')
@login_required
def suppliers_list():
    try:
        # Pagination and filtering
        q = (request.args.get('q') or '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        sort_by = request.args.get('sort', 'name', type=str)
        sort_order = request.args.get('order', 'asc', type=str)
        status_filter = request.args.get('status', 'all', type=str)
        payment_filter = request.args.get('payment', 'all', type=str)
        
        # Build query
        qry = Supplier.query
        if status_filter == 'active':
            qry = qry.filter_by(active=True)
        elif status_filter == 'inactive':
            qry = qry.filter_by(active=False)
        
        if payment_filter != 'all':
            qry = qry.filter_by(payment_method=payment_filter.upper())
        
        if q:
            like = f"%{q}%"
            qry = qry.filter(
                (Supplier.name.ilike(like))
                | (Supplier.contact_person.ilike(like))
                | (Supplier.phone.ilike(like))
                | (Supplier.email.ilike(like))
                | (Supplier.tax_number.ilike(like))
                | (Supplier.address.ilike(like))
                | (Supplier.notes.ilike(like))
            )
        
        # Sorting
        if sort_by == 'name':
            qry = qry.order_by(Supplier.name.asc() if sort_order == 'asc' else Supplier.name.desc())
        elif sort_by == 'phone':
            qry = qry.order_by(Supplier.phone.asc() if sort_order == 'asc' else Supplier.phone.desc())
        elif sort_by == 'tax_number':
            qry = qry.order_by(Supplier.tax_number.asc() if sort_order == 'asc' else Supplier.tax_number.desc())
        elif sort_by == 'payment':
            qry = qry.order_by(Supplier.payment_method.asc() if sort_order == 'asc' else Supplier.payment_method.desc())
        else:
            qry = qry.order_by(Supplier.name.asc())
        
        # Pagination
        pagination = qry.paginate(page=page, per_page=per_page, error_out=False)
        suppliers_list = pagination.items
        
        # Get totals
        total_suppliers = Supplier.query.count()
        active_suppliers = Supplier.query.filter_by(active=True).count()
        
        return render_template('suppliers_list.html', 
                             suppliers=suppliers_list,
                             pagination=pagination,
                             q=q,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             status_filter=status_filter,
                             payment_filter=payment_filter,
                             total_suppliers=total_suppliers,
                             active_suppliers=active_suppliers)
    except Exception as e:
        current_app.logger.error(f'Error loading suppliers list: {e}', exc_info=True)
        return render_template('suppliers_list.html', 
                             suppliers=[],
                             pagination=None,
                             q='',
                             sort_by='name',
                             sort_order='asc',
                             status_filter='all',
                             payment_filter='all',
                             total_suppliers=0,
                             active_suppliers=0)


@bp.route('/suppliers/<int:sid>/toggle', methods=['POST'], endpoint='supplier_toggle')
@login_required
def supplier_toggle(sid):
    try:
        s = Supplier.query.get(sid)
        if not s:
            flash('Supplier not found', 'warning')
            return redirect(url_for('suppliers.suppliers_list'))
        s.active = not bool(getattr(s, 'active', True))
        if ext_db is not None:
            ext_db.session.commit()
        else:
            db.session.commit()
        flash('Supplier status updated', 'success')
    except Exception as e:
        if ext_db is not None:
            ext_db.session.rollback()
        else:
            db.session.rollback()
        flash(f'Error updating supplier: {e}', 'danger')
    # Preserve query parameters
    q = request.args.get('q', '')
    page = request.args.get('page', '1')
    return redirect(url_for('suppliers.suppliers_list', q=q, page=page))


@bp.route('/suppliers/export', methods=['GET'], endpoint='suppliers_export')
@login_required
def suppliers_export():
    try:
        q = (request.args.get('q') or '').strip()
        rows = _suppliers_query(q).all()

        def escape_csv(val):
            if val is None:
                return ''
            s = str(val)
            if any(c in s for c in [',', '"', '\n', '\r']):
                s = '"' + s.replace('"', '""') + '"'
            return s

        parts = []
        header = [
            'Name', 'Contact Person', 'Phone', 'Email', 'Tax Number',
            'CR Number', 'IBAN', 'Address', 'Notes', 'Active',
        ]
        parts.append(','.join(header))
        for s in rows:
            cr = getattr(s, 'cr_number', None)
            iban = getattr(s, 'iban', None)
            if (not cr or not iban) and getattr(s, 'notes', None):
                try:
                    for part in (s.notes or '').split('|'):
                        p = (part or '').strip()
                        if not cr and len(p) >= 3 and p[:3] == 'CR:':
                            cr = p[3:].strip()
                        if not iban and len(p) >= 5 and p[:5] == 'IBAN:':
                            iban = p[5:].strip()
                except Exception:
                    pass
            row = [
                escape_csv(s.name),
                escape_csv(s.contact_person or ''),
                escape_csv(s.phone or ''),
                escape_csv(s.email or ''),
                escape_csv(s.tax_number or ''),
                escape_csv(cr or ''),
                escape_csv(iban or ''),
                escape_csv(s.address or ''),
                escape_csv(s.notes or ''),
                '1' if getattr(s, 'active', True) else '0',
            ]
            parts.append(','.join(row))
        csv_data = '\n'.join(parts)
        return current_app.response_class(
            csv_data,
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename="suppliers.csv"'},
        )
    except Exception as e:
        flash(f'Failed to export suppliers: {e}', 'danger')
        return redirect(url_for('suppliers.suppliers'))


@bp.route('/suppliers/payments-statements', methods=['GET'], endpoint='suppliers_payments_statements')
@login_required
def suppliers_payments_statements():
    """متابعة سداد فواتير الموردين ومستحقاتهم وطباعة الكشوفات."""
    from datetime import date
    suppliers_all = Supplier.query.order_by(Supplier.name.asc()).all()
    today = date.today().strftime('%Y-%m-%d')
    return render_template('suppliers_payments.html', suppliers=suppliers_all, today=today)


@bp.route('/suppliers/statement', methods=['GET'], endpoint='supplier_statement')
@bp.route('/suppliers/<int:sid>/statement', methods=['GET'], endpoint='supplier_statement_id')
@login_required
def supplier_statement(sid=None):
    """كشف حساب مورد — المدفوع والدفعات من القيود المنشورة (مصدر الحقيقة). إن لم يُربط القيد بفاتورة يُستكمل من جدول الدفعات للتوافق مع القيود القديمة."""
    from models import PurchaseInvoice, Account, JournalEntry, JournalLine, Payment
    from sqlalchemy import func

    if sid is None:
        sid = request.args.get('supplier_id') or request.args.get('sid')
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            sid = None
    if not sid:
        flash('Supplier required / المورد مطلوب', 'warning')
        return redirect(url_for('suppliers.suppliers_payments_statements'))
    supplier = Supplier.query.get_or_404(sid)
    start_arg = request.args.get('start_date')
    end_arg = request.args.get('end_date')
    today = __import__('models', fromlist=['get_saudi_now']).get_saudi_now().date()
    try:
        start_date = __import__('datetime').datetime.strptime(start_arg, '%Y-%m-%d').date() if start_arg else __import__('datetime').datetime(2025, 1, 1).date()
        end_date = __import__('datetime').datetime.strptime(end_arg, '%Y-%m-%d').date() if end_arg else today
    except Exception:
        start_date = __import__('datetime').datetime(2025, 1, 1).date()
        end_date = today

    invs = PurchaseInvoice.query.filter(
        (PurchaseInvoice.supplier_id == sid) | (PurchaseInvoice.supplier_name == supplier.name),
        PurchaseInvoice.date >= start_date,
        PurchaseInvoice.date <= end_date
    ).order_by(PurchaseInvoice.date.asc(), PurchaseInvoice.invoice_number.asc()).all()

    acc_2111 = Account.query.filter_by(code='2111').first()
    # المدفوع من القيود المرتبطة بفاتورة + استكمال من Payment للقديم
    paid_per_inv = {}
    for inv in invs:
        paid = 0.0
        if acc_2111:
            s = db.session.query(func.coalesce(func.sum(JournalLine.debit), 0)).join(
                JournalEntry, JournalLine.journal_id == JournalEntry.id
            ).filter(
                JournalLine.account_id == acc_2111.id,
                JournalLine.invoice_id == inv.id,
                JournalLine.invoice_type == 'purchase',
                JournalEntry.status == 'posted'
            ).scalar() or 0
            paid = round(float(s), 2)
        if paid < 0.01:
            leg = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                Payment.invoice_type == 'purchase', Payment.invoice_id == inv.id
            ).scalar() or 0
            paid = round(float(leg), 2)
        paid_per_inv[inv.id] = paid

    # لا نخصص قيوداً قديمة (2111 بدون invoice_id) لهذا المورد — قد تكون لمورد آخر وتُظهر مدفوعات زائدة.

    invoices_ctx = []
    total_inv = 0.0
    total_paid = 0.0
    for inv in invs:
        paid = paid_per_inv.get(inv.id, 0)
        tot = float(inv.total_after_tax_discount or 0)
        rem = max(0.0, tot - paid)
        total_inv += tot
        total_paid += paid
        # الحالة من الرصيد الفعلي: مدفوع كامل = paid، جزء = partial، لا شيء = unpaid
        status = 'paid' if rem <= 0.01 else ('partial' if paid > 0 else 'unpaid')
        invoices_ctx.append({
            'invoice_number': inv.invoice_number,
            'date': inv.date,
            'total': tot,
            'paid': paid,
            'remaining': rem,
            'status': status,
        })

    inv_ids = [int(inv.id) for inv in invs]
    # قائمة الدفعات: فقط الدفعات المرتبطة بفواتير هذا المورد (لا قيود قديمة غير مربوطة)
    pay_rows = []
    if acc_2111 and inv_ids:
        lines = db.session.query(JournalLine, JournalEntry).join(
            JournalEntry, JournalLine.journal_id == JournalEntry.id
        ).filter(
            JournalLine.account_id == acc_2111.id,
            JournalLine.invoice_id.in_(inv_ids),
            JournalLine.invoice_type == 'purchase',
            JournalLine.debit > 0,
            JournalEntry.status == 'posted'
        ).order_by(JournalEntry.date.asc(), JournalEntry.id.asc(), JournalLine.id.asc()).all()
        for jl, je in lines:
            dt = getattr(je, 'created_at', None) or getattr(je, 'date', None)
            pay_rows.append((
                dt,
                float(jl.debit or 0),
                getattr(je, 'payment_method', None) or ''
            ))
    if not pay_rows and inv_ids:
        leg_pays = db.session.query(Payment.payment_date, Payment.amount_paid, Payment.payment_method).filter(
            Payment.invoice_type == 'purchase',
            Payment.invoice_id.in_(inv_ids)
        ).order_by(Payment.payment_date.asc()).all()
        pay_rows = [(r[0], float(r[1] or 0), r[2] or '') for r in leg_pays]

    from datetime import datetime
    def _payment_date_display(d):
        if d is None:
            return '-'
        if isinstance(d, datetime) and (d.hour != 0 or d.minute != 0):
            return d.strftime('%Y-%m-%d %H:%M')
        return d.strftime('%Y-%m-%d')
    payments_ctx = [
        {'date': r[0], 'date_display': _payment_date_display(r[0]), 'amount': round(r[1], 2), 'method': r[2] or ''}
        for r in pay_rows
    ]

    return render_template('supplier_statement.html',
        supplier=supplier,
        start_date=start_date,
        end_date=end_date,
        invoices=invoices_ctx,
        payments=payments_ctx,
        total_invoices=round(total_inv, 2),
        total_paid=round(total_paid, 2),
        balance_due=round(max(0.0, total_inv - total_paid), 2)
    )


@bp.route('/suppliers/<int:sid>/delete', methods=['POST'], endpoint='supplier_delete')
@login_required
def supplier_delete(sid):
    try:
        s = Supplier.query.get(sid)
        if not s:
            flash('Supplier not found', 'warning')
        else:
            try:
                if ext_db is not None:
                    ext_db.session.delete(s)
                    ext_db.session.commit()
                else:
                    db.session.delete(s)
                    db.session.commit()
                flash('Supplier deleted', 'success')
            except IntegrityError:
                if ext_db is not None:
                    ext_db.session.rollback()
                    s.active = False
                    ext_db.session.commit()
                else:
                    db.session.rollback()
                    s.active = False
                    db.session.commit()
                flash('Supplier has related records; deactivated instead', 'warning')
    except Exception as e:
        if ext_db is not None:
            ext_db.session.rollback()
        else:
            db.session.rollback()
        flash(f'Error deleting supplier: {e}', 'danger')
    # Preserve query parameters
    q = request.args.get('q', '')
    page = request.args.get('page', '1')
    return redirect(url_for('suppliers.suppliers_list', q=q, page=page))
