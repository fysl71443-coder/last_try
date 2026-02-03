# Phase 2 – Customers blueprint. Same URLs.
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app import db, csrf
from models import Customer, SalesInvoice, Payment, Account, JournalEntry, JournalLine

bp = Blueprint('customers', __name__)


def _ui_to_db_customer_type(ui_value):
    """تحويل قيمة الواجهة إلى قيمة قاعدة البيانات فقط — بدون عكس.
    آجل في الواجهة → credit في القاعدة. نقدي في الواجهة → cash في القاعدة.
    العميل غير المسجل = لا نستخدم هذا (لا خصم).
    منطق الخصم: آجل = نسبة تُدخل يدوياً في كل فاتورة؛ نقدي = نسبة ثابتة من سجل العميل؛ غير مسجل = لا خصم.
    """
    if not ui_value:
        return 'cash'
    v = (ui_value or '').strip().lower()
    if v in ('credit', 'آجل'):
        return 'credit'
    return 'cash'


def _report_header_context():
    """ترويسة موحدة للتقارير: اسم الشركة، الرقم الضريبي، البيانات الرسمية."""
    try:
        from models import Settings
        s = Settings.query.first()
        if not s:
            return {"company_name": "Company", "tax_number": "", "address": "", "phone": "", "email": "", "logo_url": None, "show_logo": False}
        return {
            "company_name": (s.company_name or "Company").strip(),
            "tax_number": (getattr(s, "tax_number", None) or "").strip(),
            "address": (getattr(s, "address", None) or "").strip(),
            "phone": (getattr(s, "phone", None) or "").strip(),
            "email": (getattr(s, "email", None) or "").strip(),
            "logo_url": getattr(s, "logo_url", None),
            "show_logo": bool(getattr(s, "receipt_show_logo", False)),
        }
    except Exception:
        return {"company_name": "Company", "tax_number": "", "address": "", "phone": "", "email": "", "logo_url": None, "show_logo": False}


def _customer_search(q: str | None, limit: int = 20):
    if not q:
        return Customer.query.filter_by(active=True).order_by(Customer.name.asc()).limit(
            min(limit, 10)
        ).all()
    like = f"%{q}%"
    return Customer.query.filter(
        Customer.active == True,
        (Customer.name.ilike(like)) | (Customer.phone.ilike(like)),
    ).order_by(Customer.name.asc()).limit(limit).all()


@bp.route('/api/customers/search', methods=['GET'], endpoint='api_customers_search')
@login_required
def api_customers_search():
    q = (request.args.get('q') or '').strip()
    rows = _customer_search(q, 20)
    data = [{
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'discount_percent': float(c.discount_percent or 0),
        'customer_type': (getattr(c, 'customer_type', '') or 'cash'),
    } for c in rows]
    return jsonify({'results': data})


@bp.route('/api/customers/check-credit', methods=['GET'], endpoint='api_customers_check_credit')
@login_required
def api_customers_check_credit():
    """استعلام: هل العميل المدخل مسجل كعميل آجل؟ يُستخدم عند إدخال اسم العميل في فاتورة المبيعات."""
    q = (request.args.get('q') or request.args.get('name') or '').strip()
    phone = (request.args.get('phone') or '').strip() or None
    if not q:
        return jsonify({'found': False})
    like = f"%{q}%"
    query = Customer.query.filter(Customer.active == True)
    query = query.filter(Customer.name.ilike(like))
    if phone:
        query = query.filter(Customer.phone.ilike(f"%{phone}%"))
    c = query.order_by(Customer.name.asc()).first()
    if not c:
        return jsonify({'found': False})
    ctype = (getattr(c, 'customer_type', '') or 'cash').strip().lower()
    is_credit = ctype in ('credit', 'آجل')
    return jsonify({
        'found': True,
        'is_credit': is_credit,
        'id': c.id,
        'name': c.name,
        'phone': c.phone or '',
        'discount_percent': float(c.discount_percent or 0),
        'customer_type': ctype,
    })


@bp.route('/customers', methods=['GET', 'POST'], endpoint='customers')
@login_required
def customers():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        phone = (request.form.get('phone') or '').strip() or None
        discount = request.form.get('discount_percent', type=float) or 0.0
        ctype = _ui_to_db_customer_type(request.form.get('customer_type'))
        if not name:
            flash('Name is required', 'danger')
        else:
            try:
                c = Customer(name=name, phone=phone, customer_type=ctype, discount_percent=float(discount or 0))
                db.session.add(c)
                db.session.commit()
                flash('Customer added', 'success')
            except Exception as e:
                db.session.rollback()
                flash('Error adding customer', 'danger')
        return redirect(url_for('customers.customers'))
    
    # Pagination and filtering
    q = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort', 'name', type=str)
    sort_order = request.args.get('order', 'asc', type=str)
    status_filter = request.args.get('status', 'all', type=str)
    type_filter = request.args.get('type', 'all', type=str)  # all, cash, credit
    
    # Build query
    qry = Customer.query
    if status_filter == 'active':
        qry = qry.filter_by(active=True)
    elif status_filter == 'inactive':
        qry = qry.filter_by(active=False)
    if type_filter == 'cash':
        qry = qry.filter(db.or_(Customer.customer_type == 'cash', Customer.customer_type.is_(None)))
    elif type_filter == 'credit':
        qry = qry.filter(Customer.customer_type == 'credit')
    
    if q:
        like = f"%{q}%"
        qry = qry.filter((Customer.name.ilike(like)) | (Customer.phone.ilike(like)))
    
    # Sorting
    if sort_by == 'name':
        qry = qry.order_by(Customer.name.asc() if sort_order == 'asc' else Customer.name.desc())
    elif sort_by == 'phone':
        qry = qry.order_by(Customer.phone.asc() if sort_order == 'asc' else Customer.phone.desc())
    elif sort_by == 'discount':
        qry = qry.order_by(Customer.discount_percent.asc() if sort_order == 'asc' else Customer.discount_percent.desc())
    else:
        qry = qry.order_by(Customer.name.asc())
    
    # Pagination
    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)
    customers_list = pagination.items
    
    # Get totals
    total_customers = Customer.query.count()
    active_customers = Customer.query.filter_by(active=True).count()
    
    return render_template('customers.html', 
                         customers=customers_list, 
                         pagination=pagination,
                         q=q,
                         sort_by=sort_by,
                         sort_order=sort_order,
                         status_filter=status_filter,
                         type_filter=type_filter,
                         total_customers=total_customers,
                         active_customers=active_customers)


@bp.route('/customers/<int:cid>/edit', methods=['GET', 'POST'], endpoint='customer_edit')
@login_required
def customer_edit(cid):
    try:
        c = db.session.get(Customer, cid)
        if not c:
            flash('Customer not found', 'warning')
            return redirect(url_for('customers.customers'))
        
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            phone = (request.form.get('phone') or '').strip() or None
            discount = request.form.get('discount_percent', type=float) or 0.0
            ctype = _ui_to_db_customer_type(request.form.get('customer_type'))
            if not name:
                flash('Name is required', 'danger')
            else:
                try:
                    c.name = name
                    c.phone = phone
                    c.customer_type = ctype
                    c.discount_percent = float(discount or 0)
                    db.session.commit()
                    flash('Customer updated successfully', 'success')
                    return redirect(url_for('customers.customers'))
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating customer: {e}', 'danger')
        
        return render_template('customers_edit.html', c=c)
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'danger')
        return redirect(url_for('customers.customers'))


@bp.route('/customers/receivables-statements', methods=['GET'], endpoint='customers_receivables_statements')
@login_required
def customers_receivables_statements():
    """صفحة متابعة المستحقات والكشوفات للعملاء الآجلين: اختيار عميل، فترة، عرض/طباعة كشف الحساب."""
    try:
        from datetime import date
        from models import get_saudi_now
        today = get_saudi_now().date()
    except Exception:
        from datetime import date
        today = date.today()
    credit_customers = Customer.query.filter(
        db.or_(Customer.customer_type == 'credit', Customer.customer_type == 'آجل')
    ).filter_by(active=True).order_by(Customer.name.asc()).all()
    return render_template('customers/receivables_statements.html',
                          customers=credit_customers,
                          today=today.isoformat())


@bp.route('/customers/<int:cid>/statement', methods=['GET'], endpoint='customer_statement')
@login_required
def customer_statement(cid):
    """كشف حساب عميل آجل: فواتير ومسدد من القيود (1141) + جدول الدفعات القديم؛ كل تحصيلة في صف مع التوقيت الفعلي."""
    c = db.session.get(Customer, cid)
    if not c:
        flash('Customer not found', 'warning')
        return redirect(url_for('customers.customers'))
    start_arg = (request.args.get('start_date') or '').strip()
    end_arg = (request.args.get('end_date') or '').strip()
    try:
        from models import get_saudi_now
        today = get_saudi_now().date()
    except Exception:
        from datetime import date
        today = date.today()
    if not start_arg:
        start_arg = today.replace(day=1).isoformat()
    if not end_arg:
        end_arg = today.isoformat()
    try:
        from datetime import datetime as dt_parse
        start_dt = dt_parse.strptime(start_arg, '%Y-%m-%d').date()
        end_dt = dt_parse.strptime(end_arg, '%Y-%m-%d').date()
    except Exception:
        start_dt = today
        end_dt = today
    start = start_arg
    end = end_arg

    invs = SalesInvoice.query.filter(
        SalesInvoice.customer_id == cid,
        SalesInvoice.date >= start_dt,
        SalesInvoice.date <= end_dt
    ).order_by(SalesInvoice.date.asc()).all()
    inv_ids = [int(i.id) for i in invs]

    opening = 0.0
    for inv in SalesInvoice.query.filter(SalesInvoice.customer_id == cid, SalesInvoice.date < start_dt).all():
        opening += float(inv.total_after_tax_discount or 0)
    for p in Payment.query.filter(Payment.invoice_type == 'sales').join(SalesInvoice, Payment.invoice_id == SalesInvoice.id).filter(
        SalesInvoice.customer_id == cid
    ).all():
        pd = getattr(p, 'payment_date', None)
        pdate = (pd.date() if hasattr(pd, 'date') else pd) if pd else None
        if pdate is None or pdate >= start_dt:
            continue
        opening -= float(p.amount_paid or 0)

    acc_1141 = Account.query.filter_by(code='1141').first()
    paid_per_inv = {}
    for inv in invs:
        paid = 0.0
        if acc_1141:
            s = db.session.query(func.coalesce(func.sum(JournalLine.credit), 0)).join(
                JournalEntry, JournalLine.journal_id == JournalEntry.id
            ).filter(
                JournalLine.account_id == acc_1141.id,
                JournalLine.invoice_id == inv.id,
                JournalLine.invoice_type == 'sales',
                JournalEntry.status == 'posted'
            ).scalar() or 0
            paid = round(float(s), 2)
        if paid < 0.01:
            leg = db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                Payment.invoice_type == 'sales', Payment.invoice_id == inv.id
            ).scalar() or 0
            paid = round(float(leg), 2)
        paid_per_inv[inv.id] = paid

    if acc_1141:
        unalloc = db.session.query(func.coalesce(func.sum(JournalLine.credit), 0)).join(
            JournalEntry, JournalLine.journal_id == JournalEntry.id
        ).filter(
            JournalLine.account_id == acc_1141.id,
            JournalLine.credit > 0,
            JournalLine.invoice_id.is_(None),
            JournalEntry.status == 'posted'
        ).scalar() or 0
        unalloc = round(float(unalloc), 2)
        if unalloc >= 0.01:
            for inv in sorted(invs, key=lambda i: (i.date or __import__('datetime').date(1900, 1, 1), i.id)):
                if unalloc <= 0:
                    break
                tot = float(inv.total_after_tax_discount or 0)
                already = paid_per_inv.get(inv.id, 0)
                rem_inv = max(0.0, tot - already)
                if rem_inv < 0.01:
                    continue
                alloc = min(unalloc, rem_inv)
                paid_per_inv[inv.id] = already + alloc
                unalloc -= alloc

    from datetime import datetime
    def _date_display(d):
        if d is None:
            return '-'
        if isinstance(d, datetime) and (d.hour != 0 or d.minute != 0):
            return d.strftime('%Y-%m-%d %H:%M')
        return (d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10])

    rows = []
    total_invoices = 0.0
    total_paid = 0.0
    for inv in invs:
        amt = float(inv.total_after_tax_discount or 0.0)
        rows.append({
            'date': str(inv.date or '')[:10],
            'date_display': None,
            'ref': inv.invoice_number,
            'desc': 'فاتورة مبيعات',
            'debit': amt,
            'credit': 0.0,
            'balance': None
        })
        total_invoices += amt

    pay_rows = []
    if acc_1141:
        je_ids = []
        if inv_ids:
            je_ids = db.session.query(JournalEntry.id).join(
                JournalLine, JournalLine.journal_id == JournalEntry.id
            ).filter(
                JournalLine.account_id == acc_1141.id,
                JournalLine.invoice_id.in_(inv_ids),
                JournalLine.invoice_type == 'sales',
                JournalEntry.status == 'posted'
            ).distinct().all()
            je_ids = [r[0] for r in je_ids]
        je_ids_legacy = db.session.query(JournalEntry.id).join(
            JournalLine, JournalLine.journal_id == JournalEntry.id
        ).filter(
            JournalLine.account_id == acc_1141.id,
            JournalLine.credit > 0,
            JournalLine.invoice_id.is_(None),
            JournalEntry.status == 'posted'
        ).distinct().all()
        je_ids_legacy = [r[0] for r in je_ids_legacy]
        all_je_ids = list(set(je_ids) | set(je_ids_legacy))
        if all_je_ids:
            lines = db.session.query(JournalLine, JournalEntry).join(
                JournalEntry, JournalLine.journal_id == JournalEntry.id
            ).filter(
                JournalLine.journal_id.in_(all_je_ids),
                JournalLine.account_id == acc_1141.id,
                JournalLine.credit > 0
            ).order_by(JournalEntry.date.asc(), JournalEntry.id.asc(), JournalLine.id.asc()).all()
            inv_by_id = {inv.id: inv for inv in invs}
            for jl, je in lines:
                dt = getattr(je, 'created_at', None) or getattr(je, 'date', None)
                ref = ''
                if getattr(jl, 'invoice_id', None):
                    si = inv_by_id.get(jl.invoice_id) or SalesInvoice.query.get(jl.invoice_id)
                    if si:
                        ref = si.invoice_number or ''
                pay_rows.append({
                    'date': dt,
                    'date_display': _date_display(dt),
                    'ref': ref,
                    'desc': 'سداد',
                    'debit': 0.0,
                    'credit': float(jl.credit or 0),
                    'balance': None
                })
    if not pay_rows and inv_ids:
        for p in Payment.query.filter(Payment.invoice_type == 'sales', Payment.invoice_id.in_(inv_ids)).order_by(Payment.payment_date.asc()).all():
            inv = SalesInvoice.query.get(p.invoice_id)
            pd = getattr(p, 'payment_date', None)
            pdate = (pd.date() if hasattr(pd, 'date') else pd) if pd else None
            pd_str = (pdate.strftime('%Y-%m-%d') if pdate and hasattr(pdate, 'strftime') else str(pd or '')[:10])
            if start <= pd_str <= end:
                pay_rows.append({
                    'date': pd_str,
                    'date_display': _date_display(pd) if pd else pd_str,
                    'ref': (inv.invoice_number if inv else ''),
                    'desc': 'سداد',
                    'debit': 0.0,
                    'credit': float(p.amount_paid or 0),
                    'balance': None
                })
    for pr in pay_rows:
        total_paid += pr['credit']
        rows.append(pr)

    def _row_sort_key(r):
        d = r.get('date') or ''
        if hasattr(d, 'strftime'):
            d = d.strftime('%Y-%m-%d')
        return (str(d)[:10], 0 if (r.get('debit') or 0) > 0 else 1)
    rows.sort(key=_row_sort_key)

    bal = opening
    for r in rows:
        bal += (r['debit'] or 0) - (r['credit'] or 0)
        r['balance'] = round(bal, 2)
    remaining = max(0.0, bal)

    for r in rows:
        if r.get('date_display') is None and r.get('date'):
            r['date_display'] = str(r['date'])[:10]

    try:
        generated_at = get_saudi_now().strftime('%Y-%m-%d %H:%M')
    except Exception:
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
    customer_email = getattr(c, 'email', None) or None
    return render_template('customers/statement.html',
        customer=c, customer_email=customer_email, rows=rows, start_date=start, end_date=end,
        opening_balance=opening, total_invoices=total_invoices,
        total_paid=total_paid, remaining=remaining, generated_at=generated_at,
        **_report_header_context())


@bp.route('/customers/<int:cid>/toggle', methods=['POST'], endpoint='customer_toggle')
@login_required
def customer_toggle(cid):
    try:
        c = db.session.get(Customer, cid)
        if not c:
            flash('Customer not found', 'warning')
            return redirect(url_for('customers.customers'))
        c.active = not bool(getattr(c, 'active', True))
        db.session.commit()
        flash('Customer status updated', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating customer: {e}', 'danger')
    return redirect(url_for('customers.customers'))


@bp.route('/customers/<int:cid>/delete', methods=['POST'], endpoint='customer_delete')
@login_required
def customer_delete(cid):
    try:
        c = db.session.get(Customer, cid)
        if not c:
            flash('Customer not found', 'warning')
        else:
            try:
                db.session.delete(c)
                db.session.commit()
                flash('Customer deleted', 'success')
            except IntegrityError:
                db.session.rollback()
                c.active = False
                db.session.commit()
                flash('Customer has related records; deactivated instead', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: {e}', 'danger')
    return redirect(url_for('customers.customers'))


@bp.route('/api/pos/<branch>/customers/search', methods=['GET'], endpoint='api_pos_customers_search')
@login_required
def api_pos_customers_search(branch):
    q = (request.args.get('q') or '').strip()
    rows = _customer_search(q, 20)
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'discount_percent': float(c.discount_percent or 0),
    } for c in rows])


@bp.route('/api/customers', methods=['POST'], endpoint='api_customers_create')
@login_required
@csrf.exempt
def api_customers_create():
    try:
        if request.is_json:
            data = request.get_json() or {}
            name = (data.get('name') or '').strip()
            phone = (data.get('phone') or '').strip() or None
            discount = float((data.get('discount_percent') or 0) or 0)
        else:
            name = (request.form.get('name') or '').strip()
            phone = (request.form.get('phone') or '').strip() or None
            discount = request.form.get('discount_percent', type=float) or 0.0
        if not name:
            return jsonify({'ok': False, 'error': 'Name is required'}), 400
        d = request.get_json(silent=True) or request.form
        ctype = _ui_to_db_customer_type(d.get('customer_type'))
        c = Customer(name=name, phone=phone, customer_type=ctype, discount_percent=float(discount or 0))
        db.session.add(c)
        db.session.commit()
        return jsonify({
            'ok': True,
            'customer': {
                'id': c.id,
                'name': c.name,
                'phone': c.phone,
                'discount_percent': float(c.discount_percent or 0),
                'customer_type': (getattr(c, 'customer_type', '') or 'cash').strip().lower() or 'cash',
            },
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400
