# Phase 2 – Payments blueprint. Same URLs.
from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app import db, csrf
from models import (
    PurchaseInvoice,
    ExpenseInvoice,
    SalesInvoice,
    SalesInvoiceItem,
    Payment,
    JournalEntry,
    JournalLine,
    JournalAudit,
    Settings,
    get_saudi_now,
)
from routes.common import BRANCH_LABELS, kv_get
from app.routes import (
    _post_ledger,
    _pm_account,
    _account,
    CHART_OF_ACCOUNTS,
)

bp = Blueprint("payments", __name__)


def _to_ascii_digits(s: str) -> str:
    try:
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, d in enumerate('0123456789'):
            s = s.replace(arabic[i], d)
        return s
    except Exception:
        return s


def _parse_date(s: str) -> datetime | None:
    s = _to_ascii_digits((s or '').strip())
    try:
        if '-' in s:
            return datetime.fromisoformat(s)
        if '/' in s:
            try:
                return datetime.strptime(s, '%d/%m/%Y')
            except Exception:
                return datetime.strptime(s, '%m/%d/%Y')
    except Exception:
        pass
    return None


def to_cents(value):
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal('0.00')


def compute_status(total_amt, paid_amt):
    total_c = to_cents(total_amt)
    paid_c = to_cents(paid_amt)
    if (total_c - paid_c) <= Decimal('0.01'):
        return 'paid'
    if paid_c > Decimal('0.00'):
        return 'partial'
    return 'unpaid'


def _norm_group(n: str) -> str:
    raw = (n or '').lower()
    if ('هنقر' in raw) or ('هونقر' in raw) or ('هَنقَر' in raw):
        return 'hunger'
    if ('كيتا' in raw) or ('كيت' in raw):
        return 'keeta'
    s = re.sub(r'[^a-z]', '', raw)
    if s.startswith('hunger'):
        return 'hunger'
    if s.startswith('keeta') or s.startswith('keet'):
        return 'keeta'
    return ''


def get_original_ar_account_code(invoice_id, invoice_type):
    """Get AR account code from original journal entry."""
    try:
        original_je = JournalEntry.query.filter_by(
            invoice_id=invoice_id,
            invoice_type=invoice_type,
        ).first()
        if original_je:
            ar_line = JournalLine.query.filter(
                JournalLine.journal_id == original_je.id,
                JournalLine.debit > 0,
                JournalLine.description.like('%AR%'),
            ).first()
            if ar_line and ar_line.account:
                return ar_line.account.code
    except Exception:
        pass
    return '1141'  # Default AR (عملاء)

@bp.route('/api/payments/pay_all', methods=['POST'], endpoint='api_payments_pay_all')
@login_required
def api_payments_pay_all():
    # Bulk pay remaining for filtered invoices
    payload = request.get_json(silent=True) or {}
    type_f = (payload.get('type') or request.form.get('type') or '').strip().lower()
    method = (payload.get('payment_method') or request.form.get('payment_method') or 'CASH').strip().upper()
    # Supported: purchase, expense
    kinds = []
    if type_f in ('purchase','expense'):
        kinds = [type_f]
    else:
        kinds = ['purchase','expense']

    from decimal import Decimal, ROUND_HALF_UP
    def to_cents(value):
        try:
            return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal('0.00')

    affected = []
    try:
        for k in kinds:
            if k == 'purchase':
                rows = PurchaseInvoice.query.order_by(PurchaseInvoice.created_at.desc()).all()
            else:
                rows = ExpenseInvoice.query.order_by(ExpenseInvoice.created_at.desc()).all()
            for inv in rows:
                total = to_cents(float(getattr(inv, 'total_after_tax_discount', 0) or 0))
                paid = to_cents(float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                          .filter(Payment.invoice_id == inv.id, Payment.invoice_type == k).scalar() or 0.0))
                remaining = total - paid
                if remaining > Decimal('0.01'):
                    amt = float(remaining)
                    db.session.add(Payment(invoice_id=inv.id, invoice_type=k, amount_paid=amt, payment_method=method))
                    inv.status = 'paid'
                    affected.append({'id': inv.id, 'type': k, 'amount': amt})
        db.session.commit()
        return jsonify({'status':'success', 'count': len(affected), 'items': affected})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error', 'message': str(e)}), 400

@bp.route('/api/payments/supplier/register', methods=['POST'], endpoint='register_payment_supplier')
@login_required
def register_payment_supplier():
    payload = request.get_json(silent=True) or {}
    supplier_name = (request.form.get('supplier') or payload.get('supplier') or '').strip()
    amount = request.form.get('amount') or payload.get('amount')
    method = (request.form.get('payment_method') or payload.get('payment_method') or 'CASH').strip().upper()
    sd_str = (request.form.get('start_date') or payload.get('start_date') or '2025-10-01').strip()
    ed_str = (request.form.get('end_date') or payload.get('end_date') or get_saudi_now().date().isoformat()).strip()
    try:
        amt = float(amount or 0)
    except Exception:
        return jsonify({'status': 'error', 'message': 'Invalid amount'}), 400
    if not supplier_name:
        return jsonify({'status': 'error', 'message': 'Supplier required'}), 400
    if amt <= 0:
        return jsonify({'status': 'error', 'message': 'Amount must be > 0'}), 400
    try:
        sd_dt = datetime.fromisoformat(sd_str)
    except Exception:
        sd_dt = datetime(get_saudi_now().year, 10, 1)
    try:
        ed_dt = datetime.fromisoformat(ed_str)
    except Exception:
        ed_dt = get_saudi_now()

    from decimal import Decimal, ROUND_HALF_UP
    def to_cents(value):
        try:
            return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal('0.00')

    allocations = []
    remaining_pay = amt
    try:
        q = PurchaseInvoice.query
        try:
            q = q.filter(or_(PurchaseInvoice.created_at.between(sd_dt, ed_dt), PurchaseInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        # Case-insensitive supplier name match
        q = q.filter(func.lower(PurchaseInvoice.supplier_name) == supplier_name.lower())
        # Oldest-first FIFO allocation by date/created_at
        q = q.order_by(PurchaseInvoice.date.asc(), PurchaseInvoice.created_at.asc())
        rows = q.all()
        for inv in rows:
            if remaining_pay <= 0:
                break
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                         .filter(Payment.invoice_id == inv.id, Payment.invoice_type == 'purchase').scalar() or 0.0)
            total_c = to_cents(total); paid_c = to_cents(paid)
            remaining = float(max(total_c - paid_c, Decimal('0.00')))
            if remaining <= 0.0:
                continue
            alloc = min(remaining_pay, remaining)
            db.session.add(Payment(invoice_id=inv.id, invoice_type='purchase', amount_paid=float(alloc), payment_method=method))
            new_paid = float(paid + alloc)
            # Update status robustly
            np_c = to_cents(new_paid)
            if (total_c - np_c) <= Decimal('0.01') and total_c > Decimal('0.00'):
                inv.status = 'paid'
            elif np_c > Decimal('0.00'):
                inv.status = 'partial'
            else:
                inv.status = 'unpaid'
            allocations.append({'invoice_id': inv.id, 'invoice_number': getattr(inv, 'invoice_number', None) or inv.id, 'allocated': float(alloc)})
            remaining_pay -= float(alloc)
        db.session.commit()
        try:
            _create_supplier_direct_payment_journal(get_saudi_now().date(), amt, f'PAY SUP {supplier_name}', method or 'CASH')
        except Exception:
            pass
        return jsonify({'status': 'success', 'supplier': supplier_name, 'amount': amt, 'allocated': allocations, 'unallocated': float(max(remaining_pay, 0.0))})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400

@bp.route('/api/payments/register', methods=['POST'], endpoint='register_payment_ajax')
@login_required
def register_payment_ajax():
    # Accept both form and JSON
    payload = request.get_json(silent=True) or {}
    invoice_id = request.form.get('invoice_id') or payload.get('invoice_id')
    invoice_type = (request.form.get('invoice_type') or payload.get('invoice_type') or '').strip().lower()
    amount = request.form.get('amount') or payload.get('amount')
    payment_method = (request.form.get('payment_method') or payload.get('payment_method') or 'CASH').strip().upper()
    try:
        inv_id = int(invoice_id)
        amt = float(amount or 0)
    except Exception:
        return jsonify({'status': 'error', 'message': 'Invalid invoice id or amount'}), 400
    if amt <= 0:
        return jsonify({'status': 'error', 'message': 'Amount must be > 0'}), 400
    if invoice_type not in ('purchase','expense','sales'):
        return jsonify({'status': 'error', 'message': 'Unsupported invoice type'}), 400

    try:
        # Create payment record
        p = Payment(invoice_id=inv_id, invoice_type=invoice_type, amount_paid=amt, payment_method=payment_method)
        db.session.add(p)
        db.session.flush()

        # Fetch invoice and totals
        if invoice_type == 'purchase':
            inv = PurchaseInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0
        elif invoice_type == 'sales':
            inv = SalesInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0
        else:
            inv = ExpenseInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0

        # Sum paid so far (including this payment)
        paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_id == inv_id, Payment.invoice_type == invoice_type).scalar() or 0.0)

        # Robust status calculation with rounding tolerance (0.01)
        from decimal import Decimal, ROUND_HALF_UP
        def to_cents(value):
            try:
                return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return Decimal('0.00')
        total_c = to_cents(total)
        paid_c = to_cents(paid)
        if inv:
            if (total_c - paid_c) <= Decimal('0.01') and total_c > Decimal('0.00'):
                inv.status = 'paid'
            elif paid_c > Decimal('0.00'):
                inv.status = 'partial'
            else:
                inv.status = inv.status or ('unpaid' if invoice_type=='purchase' else 'paid')
        db.session.commit()
        
        # === التحسين الجديد: إنشاء قيود محاسبية متوافقة ===
        try:
            # Create Journal Entry for payment using correct AR account
            from models import JournalEntry, JournalLine
            
            # تحديد حساب المدينين الصحيح بناءً على القيد الأصلي
            ar_account_code = get_original_ar_account_code(inv_id, invoice_type)
            ar_acc = _account(ar_account_code, CHART_OF_ACCOUNTS.get(ar_account_code, {'name':'Accounts Receivable','type':'ASSET'}).get('name','Accounts Receivable'), 'ASSET')
            
            # حساب النقدية المناسب
            cash_account_code = '1121' if payment_method in ('BANK','TRANSFER','CARD','VISA','MASTERCARD') else '1111'
            cash_acc = _account(cash_account_code, CHART_OF_ACCOUNTS.get(cash_account_code, {'name':'صندوق رئيسي','type':'ASSET'}).get('name','صندوق رئيسي'), 'ASSET')
            
            # إنشاء قيد التحصيل
            base_en = f"JE-REC-{invoice_type}-{inv_id}"
            en = base_en
            i = 2
            from sqlalchemy import func
            while JournalEntry.query.filter(func.lower(JournalEntry.entry_number) == en.lower()).first():
                en = f"{base_en}-{i}"; i += 1
            
            je = JournalEntry(
                entry_number=en,
                date=get_saudi_now().date(),
                branch_code=None,
                description=f"Receipt {invoice_type} #{inv_id}",
                status='posted',
                total_debit=amt,
                total_credit=amt,
                created_by=getattr(current_user,'id',None),
                posted_by=getattr(current_user,'id',None),
                invoice_id=int(inv_id),
                invoice_type=f"{invoice_type}_payment"
            )
            db.session.add(je); db.session.flush()
            
            # استخدام نفس حساب المدينين من القيد الأصلي
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=cash_acc.id, debit=amt, credit=0, description=f"Cash receipt {inv_id}", line_date=get_saudi_now().date()))
            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ar_acc.id, debit=0, credit=amt, description=f"Clear AR {inv_id}", line_date=get_saudi_now().date()))
            db.session.commit()
            
            # تسجيل في audit log
            try:
                from models import JournalAudit
                db.session.add(JournalAudit(journal_id=je.id, action='create', user_id=getattr(current_user,'id',None), before_json=None, after_json=json.dumps({'entry_number': je.entry_number, 'total_debit': float(je.total_debit or 0), 'total_credit': float(je.total_credit or 0)})))
                db.session.commit()
            except Exception:
                pass
                
        except Exception as e:
            print(f"Warning: Failed to create journal entry for payment: {e}")
            db.session.rollback()
        
        return jsonify({'status': 'success', 'invoice_id': inv_id, 'amount': amt, 'paid': paid, 'total': total, 'new_status': getattr(inv, 'status', None)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400


@bp.route('/payments/export', methods=['GET'], endpoint='payments_export')
@login_required
def payments_export():
    fmt = (request.args.get('format') or 'pdf').strip().lower()
    group_f = (request.args.get('cust_group') or 'all').strip().lower()
    sd_str = (request.args.get('start_date') or '2025-10-01').strip()
    ed_str = (request.args.get('end_date') or get_saudi_now().date().isoformat()).strip()
    def _to_ascii_digits(s: str):
        try:
            arabic = '٠١٢٣٤٥٦٧٨٩'
            for i, d in enumerate('0123456789'):
                s = s.replace(arabic[i], d)
            return s
        except Exception:
            return s
    def _parse_date(s: str):
        s = _to_ascii_digits((s or '').strip())
        try:
            if '-' in s:
                return datetime.fromisoformat(s)
            if '/' in s:
                try:
                    return datetime.strptime(s, '%d/%m/%Y')
                except Exception:
                    return datetime.strptime(s, '%m/%d/%Y')
        except Exception:
            pass
        return None
    sd_dt = _parse_date(sd_str) or datetime(get_saudi_now().year, 10, 1)
    ed_dt = _parse_date(ed_str) or get_saudi_now()

    groups = {'keeta': {'rows': [], 'sums': {'Amount': 0.0, 'Discount': 0.0, 'VAT': 0.0, 'Total': 0.0}},
              'hunger': {'rows': [], 'sums': {'Amount': 0.0, 'Discount': 0.0, 'VAT': 0.0, 'Total': 0.0}}}
    try:
        from sqlalchemy import or_
        import re
        items_sub = db.session.query(
            SalesInvoiceItem.invoice_id.label('inv_id'),
            func.count(SalesInvoiceItem.id).label('items_count'),
            func.sum(SalesInvoiceItem.price_before_tax * SalesInvoiceItem.quantity).label('amount_sum'),
            func.sum(SalesInvoiceItem.tax).label('tax_sum')
        ).group_by(SalesInvoiceItem.invoice_id).subquery()

        def norm_group(n: str):
            raw = (n or '').lower()
            if ('هنقر' in raw) or ('هونقر' in raw) or ('هَنقَر' in raw):
                return 'hunger'
            if ('كيتا' in raw) or ('كيت' in raw):
                return 'keeta'
            s = re.sub(r'[^a-z]', '', raw)
            if s.startswith('hunger'):
                return 'hunger'
            if s.startswith('keeta') or s.startswith('keet'):
                return 'keeta'
            return ''

        q = db.session.query(
            SalesInvoice,
            items_sub.c.items_count,
            items_sub.c.amount_sum,
            items_sub.c.tax_sum
        ).outerjoin(items_sub, items_sub.c.inv_id == SalesInvoice.id)
        try:
            q = q.filter(or_(SalesInvoice.created_at.between(sd_dt, ed_dt), SalesInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        q = q.order_by(SalesInvoice.created_at.desc()).limit(5000)
        for inv, items_count, amount_sum, tax_sum in q.all():
            grp = norm_group(inv.customer_name or '')
            if grp not in ('keeta','hunger'):
                continue
            if group_f in ('keeta','hunger') and grp != group_f:
                continue
            amount = float(amount_sum or 0.0)
            discount = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            vat = float(tax_sum or 0.0)
            total = float(amount - discount + vat)
            dt = getattr(inv, 'date', None)
            date_str = dt.strftime('%Y-%m-%d') if dt else ''
            branch = getattr(inv, 'branch', None) or ''
            row = {
                'Invoice': getattr(inv, 'invoice_number', None) or f"S-{inv.id}",
                'Items': int(items_count or 0),
                'Amount': amount,
                'Discount': discount,
                'Total': total,
                'VAT': vat,
                'Date': date_str,
                'Branch': branch,
            }
            groups[grp]['rows'].append(row)
            groups[grp]['sums']['Amount'] += amount
            groups[grp]['sums']['Discount'] += discount
            groups[grp]['sums']['VAT'] += vat
            groups[grp]['sums']['Total'] += total
    except Exception:
        groups = {'keeta': {'rows': [], 'sums': {'Amount': 0.0, 'Discount': 0.0, 'VAT': 0.0, 'Total': 0.0}},
                  'hunger': {'rows': [], 'sums': {'Amount': 0.0, 'Discount': 0.0, 'VAT': 0.0, 'Total': 0.0}}}

    if fmt == 'excel':
        try:
            import pandas as pd
            from io import BytesIO
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                for name in ['keeta','hunger']:
                    if group_f in ('keeta','hunger') and name != group_f:
                        continue
                    df = pd.DataFrame(groups[name]['rows'], columns=['Invoice','Items','Amount','Discount','Total','VAT','Date','Branch'])
                    if not df.empty:
                        totals_row = {'Invoice': 'Totals', 'Items': '', 'Amount': groups[name]['sums']['Amount'], 'Discount': groups[name]['sums']['Discount'], 'Total': groups[name]['sums']['Total'], 'VAT': groups[name]['sums']['VAT'], 'Date': '', 'Branch': ''}
                        df = pd.concat([df, pd.DataFrame([totals_row])], ignore_index=True)
                    df.to_excel(writer, index=False, sheet_name=name.upper())
                sum_df = pd.DataFrame([
                    {'Client': 'KEETA', 'Amount': groups['keeta']['sums']['Amount'], 'Discount': groups['keeta']['sums']['Discount'], 'VAT': groups['keeta']['sums']['VAT'], 'Total': groups['keeta']['sums']['Total']},
                    {'Client': 'HUNGER', 'Amount': groups['hunger']['sums']['Amount'], 'Discount': groups['hunger']['sums']['Discount'], 'VAT': groups['hunger']['sums']['VAT'], 'Total': groups['hunger']['sums']['Total']},
                    {'Client': 'GRAND', 'Amount': groups['keeta']['sums']['Amount'] + groups['hunger']['sums']['Amount'], 'Discount': groups['keeta']['sums']['Discount'] + groups['hunger']['sums']['Discount'], 'VAT': groups['keeta']['sums']['VAT'] + groups['hunger']['sums']['VAT'], 'Total': groups['keeta']['sums']['Total'] + groups['hunger']['sums']['Total']}
                ])
                sum_df.to_excel(writer, index=False, sheet_name='SUMMARY')
            buf.seek(0)
            filename = f"payments_keeta_hunger_{sd_dt.date().isoformat()}_{ed_dt.date().isoformat()}.xlsx"
            return send_file(buf, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception:
            return redirect(url_for('payments.payments', cust_group=group_f, start_date=sd_dt.date().isoformat(), end_date=ed_dt.date().isoformat(), type='sales'))

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, LongTable, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from io import BytesIO
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        title = Paragraph('Payments — keeta/hunger', styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        for name in ['keeta','hunger']:
            if group_f in ('keeta','hunger') and name != group_f:
                continue
            elements.append(Paragraph(name.upper(), styles['Heading2']))
            data = [['Invoice','Items','Amount','Discount','Total','VAT','Date','Branch']]
            for r in groups[name]['rows']:
                data.append([
                    r.get('Invoice',''),
                    str(r.get('Items',0)),
                    f"{float(r.get('Amount',0) or 0):.2f}",
                    f"{float(r.get('Discount',0) or 0):.2f}",
                    f"{float(r.get('Total',0) or 0):.2f}",
                    f"{float(r.get('VAT',0) or 0):.2f}",
                    r.get('Date',''),
                    r.get('Branch',''),
                ])
            totals_row = ['Totals','', f"{groups[name]['sums']['Amount']:.2f}", f"{groups[name]['sums']['Discount']:.2f}", f"{groups[name]['sums']['Total']:.2f}", f"{groups[name]['sums']['VAT']:.2f}", '', '']
            data.append(totals_row)
            table = LongTable(data, colWidths=[90,50,70,70,70,70,80,80], repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))
        grand = {
            'Amount': groups['keeta']['sums']['Amount'] + groups['hunger']['sums']['Amount'],
            'Discount': groups['keeta']['sums']['Discount'] + groups['hunger']['sums']['Discount'],
            'VAT': groups['keeta']['sums']['VAT'] + groups['hunger']['sums']['VAT'],
            'Total': groups['keeta']['sums']['Total'] + groups['hunger']['sums']['Total']
        }
        elements.append(Paragraph('GRAND TOTALS', styles['Heading2']))
        gdata = [['Amount','Discount','Total','VAT'], [f"{grand['Amount']:.2f}", f"{grand['Discount']:.2f}", f"{grand['Total']:.2f}", f"{grand['VAT']:.2f}"]]
        gtable = LongTable(gdata, colWidths=[100,100,100,100], repeatRows=1)
        gtable.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(gtable)
        doc.build(elements)
        buf.seek(0)
        filename = f"payments_keeta_hunger_{sd_dt.date().isoformat()}_{ed_dt.date().isoformat()}.pdf"
        return send_file(buf, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception:
        return redirect(url_for('payments.payments', cust_group=group_f, start_date=sd_dt.date().isoformat(), end_date=ed_dt.date().isoformat(), type='sales'))

@bp.route('/payments.json', methods=['GET'], endpoint='payments_json')
@login_required
def payments_json():
    status_f = (request.args.get('status') or '').strip().lower()
    type_f = (request.args.get('type') or '').strip().lower()
    supplier_f = (request.args.get('supplier') or '').strip().lower()
    group_f = (request.args.get('cust_group') or 'all').strip().lower()
    invoices = []
    sd_str = (request.args.get('start_date') or '2025-10-01').strip()
    ed_str = (request.args.get('end_date') or get_saudi_now().date().isoformat()).strip()
    def _to_ascii_digits(s: str):
        try:
            arabic = '٠١٢٣٤٥٦٧٨٩'
            for i, d in enumerate('0123456789'):
                s = s.replace(arabic[i], d)
            return s
        except Exception:
            return s
    def _parse_date(s: str):
        s = _to_ascii_digits((s or '').strip())
        try:
            if '-' in s:
                return datetime.fromisoformat(s)
            if '/' in s:
                try:
                    return datetime.strptime(s, '%d/%m/%Y')
                except Exception:
                    return datetime.strptime(s, '%m/%d/%Y')
        except Exception:
            pass
        return None
    sd_dt = _parse_date(sd_str) or datetime(get_saudi_now().year, 10, 1)
    ed_dt = _parse_date(ed_str) or get_saudi_now()
    try:
        from decimal import Decimal, ROUND_HALF_UP
        def to_cents(value):
            try:
                return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return Decimal('0.00')
        def compute_status(total_amt, paid_amt):
            total_c = to_cents(total_amt)
            paid_c = to_cents(paid_amt)
            if (total_c - paid_c) <= Decimal('0.01'):
                return 'paid'
            if paid_c > Decimal('0.00'):
                return 'partial'
            return 'unpaid'
        q = PurchaseInvoice.query
        try:
            q = q.filter(or_(PurchaseInvoice.created_at.between(sd_dt, ed_dt), PurchaseInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        p_rows = q.order_by(PurchaseInvoice.created_at.desc()).limit(1000).all()
        p_ids = [int(inv.id) for inv in p_rows]
        p_paid = {}
        if p_ids:
            for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type == 'purchase', Payment.invoice_id.in_(p_ids)).group_by(Payment.invoice_id).all():
                p_paid[int(i)] = float(s or 0.0)
        for inv in p_rows:
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(p_paid.get(int(inv.id), 0.0))
            invoices.append({'id': inv.id, 'invoice_number': getattr(inv, 'invoice_number', None) or inv.id, 'type': 'purchase', 'party': inv.supplier_name or 'Supplier', 'total': total, 'paid': paid, 'status': compute_status(total, paid), 'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')})
    except Exception:
        pass
    try:
        q = ExpenseInvoice.query
        try:
            q = q.filter(or_(ExpenseInvoice.created_at.between(sd_dt, ed_dt), ExpenseInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        e_rows = q.order_by(ExpenseInvoice.created_at.desc()).limit(1000).all()
        e_ids = [int(inv.id) for inv in e_rows]
        e_paid = {}
        if e_ids:
            for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type == 'expense', Payment.invoice_id.in_(e_ids)).group_by(Payment.invoice_id).all():
                e_paid[int(i)] = float(s or 0.0)
        for inv in e_rows:
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(e_paid.get(int(inv.id), 0.0))
            invoices.append({'id': inv.id, 'invoice_number': getattr(inv, 'invoice_number', None) or inv.id, 'type': 'expense', 'party': 'Expense', 'total': total, 'paid': paid, 'status': compute_status(total, paid), 'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')})
    except Exception:
        pass
    try:
        import re
        def _norm_group(n: str):
            raw = (n or '').lower()
            if ('هنقر' in raw) or ('هونقر' in raw) or ('هَنقَر' in raw):
                return 'hunger'
            if ('كيتا' in raw) or ('كيت' in raw):
                return 'keeta'
            s = re.sub(r'[^a-z]', '', raw)
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
        s_rows = q.order_by(SalesInvoice.created_at.desc()).limit(1000).all()
        s_ids = [int(inv.id) for inv in s_rows]
        s_paid = {}
        if s_ids:
            for i, s in db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type == 'sales', Payment.invoice_id.in_(s_ids)).group_by(Payment.invoice_id).all():
                s_paid[int(i)] = float(s or 0.0)
        for inv in s_rows:
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(s_paid.get(int(inv.id), 0.0))
            name = (inv.customer_name or '').strip() or 'Customer'
            grp = _norm_group(name)
            if grp not in ('keeta','hunger'):
                continue
            if group_f in ('keeta','hunger') and grp != group_f:
                continue
            invoices.append({'id': inv.id, 'invoice_number': getattr(inv, 'invoice_number', None) or inv.id, 'type': 'sales', 'party': name, 'total': total, 'paid': paid, 'status': compute_status(total, paid), 'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')})
    except Exception:
        pass
    if status_f:
        invoices = [i for i in invoices if (i.get('status') or '').lower() == status_f]
    if type_f:
        if type_f == 'purchases': type_f = 'purchase'
        if type_f == 'expenses': type_f = 'expense'
        invoices = [i for i in invoices if (i.get('type') or '') == type_f]
    return jsonify({'ok': True, 'count': len(invoices), 'invoices': invoices})

@bp.route('/payments', endpoint='payments')
@login_required
def payments():
    # Build unified list of purchase and expense invoices with paid totals
    status_f = (request.args.get('status') or '').strip().lower()
    type_f = (request.args.get('type') or '').strip().lower()
    supplier_f = (request.args.get('supplier') or '').strip().lower()
    group_f = (request.args.get('cust_group') or 'all').strip().lower()
    invoices = []
    PAYMENT_METHODS = ['CASH','CARD','BANK','ONLINE','MADA','VISA']
    sd_str = (request.args.get('start_date') or '2025-10-01').strip()
    ed_str = (request.args.get('end_date') or get_saudi_now().date().isoformat()).strip()
    def _to_ascii_digits(s: str):
        try:
            arabic = '٠١٢٣٤٥٦٧٨٩'
            for i, d in enumerate('0123456789'):
                s = s.replace(arabic[i], d)
            return s
        except Exception:
            return s
    def _parse_date(s: str):
        s = _to_ascii_digits((s or '').strip())
        try:
            if '-' in s:
                return datetime.fromisoformat(s)
            if '/' in s:
                try:
                    return datetime.strptime(s, '%d/%m/%Y')
                except Exception:
                    return datetime.strptime(s, '%m/%d/%Y')
        except Exception:
            pass
        return None
    sd_dt = _parse_date(sd_str) or datetime(get_saudi_now().year, 10, 1)
    ed_dt = _parse_date(ed_str) or get_saudi_now()

    try:
        built_counts = {'purchase':0,'expense':0,'sales':0}
        # Use decimal rounding to avoid float precision issues causing wrong statuses
        from decimal import Decimal, ROUND_HALF_UP
        def to_cents(value):
            try:
                return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return Decimal('0.00')
        def compute_status(total_amt, paid_amt):
            total_c = to_cents(total_amt)
            paid_c = to_cents(paid_amt)
            # Treat small residuals (<= 0.01) as fully paid
            if (total_c - paid_c) <= Decimal('0.01'):
                return 'paid'
            if paid_c > Decimal('0.00'):
                return 'partial'
            return 'unpaid'
        q = PurchaseInvoice.query
        try:
            q = q.filter(or_(PurchaseInvoice.created_at.between(sd_dt, ed_dt), PurchaseInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        p_rows = q.order_by(PurchaseInvoice.created_at.desc()).limit(1000).all()
        p_ids = [int(inv.id) for inv in p_rows]
        p_paid = {}
        if p_ids:
            _rows = (db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_type == 'purchase', Payment.invoice_id.in_(p_ids))
                     .group_by(Payment.invoice_id)
                     .all())
            for i, s in _rows:
                p_paid[int(i)] = float(s or 0.0)
        for inv in p_rows:
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(p_paid.get(int(inv.id), 0.0))
            status_calc = compute_status(total, paid)
            invoices.append({'id': inv.id, 'invoice_number': getattr(inv, 'invoice_number', None) or inv.id, 'type': 'purchase', 'party': inv.supplier_name or 'Supplier', 'total': total, 'paid': paid, 'status': status_calc, 'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')})
            built_counts['purchase'] += 1
    except Exception:
        pass

    try:
        q = ExpenseInvoice.query
        try:
            q = q.filter(or_(ExpenseInvoice.created_at.between(sd_dt, ed_dt), ExpenseInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        e_rows = q.order_by(ExpenseInvoice.created_at.desc()).limit(1000).all()
        e_ids = [int(inv.id) for inv in e_rows]
        e_paid = {}
        if e_ids:
            _rows = (db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_type == 'expense', Payment.invoice_id.in_(e_ids))
                     .group_by(Payment.invoice_id)
                     .all())
            for i, s in _rows:
                e_paid[int(i)] = float(s or 0.0)
        for inv in e_rows:
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(e_paid.get(int(inv.id), 0.0))
            status_calc = compute_status(total, paid)
            invoices.append({'id': inv.id, 'invoice_number': getattr(inv, 'invoice_number', None) or inv.id, 'type': 'expense', 'party': 'Expense', 'total': total, 'paid': paid, 'status': status_calc, 'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')})
            built_counts['expense'] += 1
    except Exception:
        pass

    try:
        import re
        def _norm_group(n: str):
            raw = (n or '').lower()
            if ('هنقر' in raw) or ('هونقر' in raw) or ('هَنقَر' in raw):
                return 'hunger'
            if ('كيتا' in raw) or ('كيت' in raw):
                return 'keeta'
            s = re.sub(r'[^a-z]', '', raw)
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
        s_rows = q.order_by(SalesInvoice.created_at.desc()).limit(1000).all()
        s_ids = [int(inv.id) for inv in s_rows]
        s_paid = {}
        if s_ids:
            _rows = (db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_type == 'sales', Payment.invoice_id.in_(s_ids))
                     .group_by(Payment.invoice_id)
                     .all())
            for i, s in _rows:
                s_paid[int(i)] = float(s or 0.0)
        for inv in s_rows:
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(s_paid.get(int(inv.id), 0.0))
            status_calc = compute_status(total, paid)
            name = (inv.customer_name or '').strip() or 'Customer'
            grp = _norm_group(name)
            if grp not in ('keeta','hunger'):
                continue
            if group_f in ('keeta','hunger') and grp != group_f:
                continue
            invoices.append({'id': inv.id, 'invoice_number': getattr(inv, 'invoice_number', None) or inv.id, 'type': 'sales', 'party': name, 'total': total, 'paid': paid, 'status': status_calc, 'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')})
            built_counts['sales'] += 1
    except Exception:
        pass

    suppliers_groups = []
    suppliers_totals = {'total': 0.0, 'paid': 0.0, 'remaining': 0.0, 'count': 0}
    try:
        by_supplier = {}
        q = PurchaseInvoice.query
        try:
            q = q.filter(or_(PurchaseInvoice.created_at.between(sd_dt, ed_dt), PurchaseInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        q = q.order_by(PurchaseInvoice.created_at.desc()).limit(2000)
        invs = q.all()
        ids = [int(inv.id) for inv in invs]
        paid_map = {}
        if ids:
            _rows = (db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_type == 'purchase', Payment.invoice_id.in_(ids))
                     .group_by(Payment.invoice_id)
                     .all())
            for i, s in _rows:
                paid_map[int(i)] = float(s or 0.0)
        for inv in invs:
            name = (inv.supplier_name or (getattr(inv, 'supplier', None).name if getattr(inv, 'supplier', None) else '') or 'Supplier').strip()
            if supplier_f and (name.lower().find(supplier_f) == -1):
                continue
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(paid_map.get(int(inv.id), 0.0))
            remaining = max(0.0, total - paid)
            status_calc = compute_status(total, paid)
            if status_f in ('due','unpaid') and status_calc == 'paid':
                continue
            if status_f == 'paid' and status_calc != 'paid':
                continue
            by_supplier.setdefault(name, {'supplier': name, 'invoices': [], 'total': 0.0, 'paid': 0.0, 'remaining': 0.0})
            by_supplier[name]['invoices'].append({
                'id': inv.id,
                'invoice_number': getattr(inv, 'invoice_number', None) or inv.id,
                'type': 'purchase',
                'party': name,
                'total': total,
                'paid': paid,
                'remaining': remaining,
                'status': status_calc,
                'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            })
            by_supplier[name]['total'] += total
            by_supplier[name]['paid'] += paid
            by_supplier[name]['remaining'] += remaining
        suppliers_groups = sorted(by_supplier.values(), key=lambda g: g['remaining'], reverse=True)
        suppliers_totals['total'] = sum(g['total'] for g in suppliers_groups)
        suppliers_totals['paid'] = sum(g['paid'] for g in suppliers_groups)
        suppliers_totals['remaining'] = sum(g['remaining'] for g in suppliers_groups)
        suppliers_totals['count'] = len(suppliers_groups)
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        suppliers_groups = []
        suppliers_totals = {'total': 0.0, 'paid': 0.0, 'remaining': 0.0, 'count': 0}

    debtors_groups = []
    debtors_totals = {'total': 0.0, 'paid': 0.0, 'remaining': 0.0, 'count': 0}
    try:
        import re
        def normalize_group(n: str):
            raw = (n or '').lower()
            if ('هنقر' in raw) or ('هونقر' in raw) or ('هَنقَر' in raw):
                return 'hunger'
            if ('كيتا' in raw) or ('كيت' in raw):
                return 'keeta'
            s = re.sub(r'[^a-z]', '', raw)
            if s.startswith('hunger'):
                return 'hunger'
            if s.startswith('keeta') or s.startswith('keet'):
                return 'keeta'
            return ''
        by_group = { 'keeta': {'group': 'keeta', 'invoices': [], 'total': 0.0, 'paid': 0.0, 'remaining': 0.0},
                     'hunger': {'group': 'hunger', 'invoices': [], 'total': 0.0, 'paid': 0.0, 'remaining': 0.0} }
        q = SalesInvoice.query
        try:
            q = q.filter(or_(SalesInvoice.created_at.between(sd_dt, ed_dt), SalesInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        q = q.order_by(SalesInvoice.created_at.desc()).limit(2000)
        invs = q.all()
        ids = [int(inv.id) for inv in invs]
        paid_map = {}
        if ids:
            _rows = (db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_type == 'sales', Payment.invoice_id.in_(ids))
                     .group_by(Payment.invoice_id)
                     .all())
            for i, s in _rows:
                paid_map[int(i)] = float(s or 0.0)
        for inv in invs:
            grp = normalize_group(inv.customer_name or '')
            if grp not in by_group:
                continue
            if group_f in ('keeta','hunger') and grp != group_f:
                continue
            total = float(inv.total_after_tax_discount or 0.0)
            paid = float(paid_map.get(int(inv.id), 0.0))
            remaining = max(0.0, total - paid)
            status_calc = compute_status(total, paid)
            by_group[grp]['invoices'].append({
                'id': inv.id,
                'invoice_number': getattr(inv, 'invoice_number', None) or inv.id,
                'type': 'sales',
                'party': grp,
                'total': total,
                'paid': paid,
                'remaining': remaining,
                'status': status_calc,
                'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            })
            by_group[grp]['total'] += total
            by_group[grp]['paid'] += paid
            by_group[grp]['remaining'] += remaining
        debtors_groups = [by_group['keeta'], by_group['hunger']]
        debtors_totals['total'] = sum(g['total'] for g in debtors_groups)
        debtors_totals['paid'] = sum(g['paid'] for g in debtors_groups)
        debtors_totals['remaining'] = sum(g['remaining'] for g in debtors_groups)
        debtors_totals['count'] = sum(1 for g in debtors_groups if g['invoices'])
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        debtors_groups = []
        debtors_totals = {'total': 0.0, 'paid': 0.0, 'remaining': 0.0, 'count': 0}

    # Apply filters
    if status_f:
        invoices = [i for i in invoices if (i.get('status') or '').lower() == status_f]
    if type_f:
        # normalize: purchases->purchase, expenses->expense, sales ignored
        if type_f == 'purchases': type_f = 'purchase'
        if type_f == 'expenses': type_f = 'expense'
        invoices = [i for i in invoices if (i.get('type') or '') == type_f]

    # Fallback: if no rows (or Sales selected), load sales invoices unconditionally within date range
    if ((type_f or '') == 'sales' or not type_f) and not invoices:
        try:
            q = SalesInvoice.query
            try:
                q = q.filter(or_(SalesInvoice.created_at.between(sd_dt, ed_dt), SalesInvoice.date.between(sd_dt.date(), ed_dt.date())))
            except Exception:
                pass
            invs = q.order_by(SalesInvoice.created_at.desc()).limit(1000).all()
            ids = [int(inv.id) for inv in invs]
            paid_map = {}
            if ids:
                _rows = (db.session.query(Payment.invoice_id, func.coalesce(func.sum(Payment.amount_paid), 0))
                         .filter(Payment.invoice_type == 'sales', Payment.invoice_id.in_(ids))
                         .group_by(Payment.invoice_id)
                         .all())
                for i, s in _rows:
                    paid_map[int(i)] = float(s or 0.0)
            for inv in invs:
                total = float(inv.total_after_tax_discount or 0.0)
                paid = float(paid_map.get(int(inv.id), 0.0))
                status_calc = compute_status(total, paid)
                name = (inv.customer_name or '').strip() or 'Customer'
                import re
                raw = name.lower()
                def _norm_group_fallback(n: str):
                    if ('هنقر' in n) or ('هونقر' in n) or ('هَنقَر' in n):
                        return 'hunger'
                    if ('كيتا' in n) or ('كيت' in n):
                        return 'keeta'
                    s = re.sub(r'[^a-z]', '', n)
                    if s.startswith('hunger'):
                        return 'hunger'
                    if s.startswith('keeta') or s.startswith('keet'):
                        return 'keeta'
                    return ''
                g = _norm_group_fallback(raw)
                if g not in ('keeta','hunger'):
                    continue
                if group_f in ('keeta','hunger') and g != group_f:
                    continue
                invoices.append({
                    'id': inv.id,
                    'invoice_number': getattr(inv, 'invoice_number', None) or inv.id,
                    'type': 'sales',
                    'party': name,
                    'total': total,
                    'paid': paid,
                    'status': status_calc,
                    'date': (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
                })
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            pass

        # Re-apply status/type filters after fallback to honor user selection
        if status_f:
            invoices = [i for i in invoices if (i.get('status') or '').lower() == status_f]
        if type_f:
            invoices = [i for i in invoices if (i.get('type') or '') == type_f]

    try:
        current_app.logger.info(f"payments range sd={sd_dt} ed={ed_dt} built_counts={built_counts} final_count={len(invoices)} type_f={type_f} status_f={status_f} group_f={group_f}")
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"Error in payments logging: {e}")
        traceback.print_exc()
        pass

    return render_template('payments.html', invoices=invoices, PAYMENT_METHODS=PAYMENT_METHODS, status_f=status_f, type_f=type_f,
                           suppliers_groups=suppliers_groups, suppliers_totals=suppliers_totals,
                           debtors_groups=debtors_groups, debtors_totals=debtors_totals, start_date=sd_dt.date().isoformat(), end_date=ed_dt.date().isoformat(), group_f=group_f, supplier_f=supplier_f)
