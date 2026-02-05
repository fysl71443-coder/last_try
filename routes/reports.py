# Phase 2 – Reports blueprint. Same URLs.
from __future__ import annotations

import json
import re
from datetime import datetime, date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_babel import gettext as _
from flask_login import login_required, current_user
from sqlalchemy import func, or_, text
from sqlalchemy.orm import selectinload

from app import db
from models import (
    SalesInvoice,
    SalesInvoiceItem,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    ExpenseInvoice,
    ExpenseInvoiceItem,
    Payment,
    Settings,
    Employee,
    Salary,
    JournalEntry,
    JournalLine,
    get_saudi_now,
)
from routes.common import BRANCH_LABELS

bp = Blueprint("reports", __name__)


def _report_header_context():
    """ترويسة موحدة لجميع التقارير من الإعدادات: اسم المطعم، الرقم الضريبي، البيانات الرسمية."""
    try:
        s = Settings.query.first()
        if not s:
            return {
                "company_name": "Company",
                "tax_number": "",
                "address": "",
                "phone": "",
                "email": "",
                "logo_url": None,
                "show_logo": False,
            }
        return {
            "company_name": (s.company_name or "Company").strip(),
            "tax_number": (s.tax_number or "").strip(),
            "address": (s.address or "").strip(),
            "phone": (getattr(s, "phone", None) or "").strip(),
            "email": (getattr(s, "email", None) or "").strip(),
            "logo_url": getattr(s, "logo_url", None),
            "show_logo": bool(getattr(s, "receipt_show_logo", False)),
        }
    except Exception:
        return {
            "company_name": "Company",
            "tax_number": "",
            "address": "",
            "phone": "",
            "email": "",
            "logo_url": None,
            "show_logo": False,
        }


# يوم المبيعات: 10 صباحاً → 2 صباحاً اليوم التالي. sales_day = date إذا الساعة >= 10 وإلا date - 1.
def _sales_day_date(dt):
    from datetime import datetime as _dt, timedelta as _td
    if not dt:
        return None
    d = dt.date() if hasattr(dt, 'date') else dt
    h = getattr(dt, 'hour', 0) + getattr(dt, 'minute', 0) / 60.0 + getattr(dt, 'second', 0) / 3600.0
    if h >= 10:
        return d
    return (d - _td(days=1)) if hasattr(d, '__sub__') else d


def _sales_report_data(start_d, end_d, branch):
    """تقرير المبيعات: فلاتر تاريخ وفرع، يوم مبيعات 10ص–2ص."""
    from datetime import datetime as _dt, time as _time, timedelta as _td
    rows = []
    by_pm = {}
    total_cash = 0.0
    total_card = 0.0
    total_before_tax = 0.0
    total_discount = 0.0
    total_tax = 0.0
    total_after = 0.0
    q = SalesInvoice.query
    if branch and branch != 'all':
        q = q.filter(SalesInvoice.branch == branch)
    if start_d and end_d:
        d_start = start_d - _td(days=1)
        d_end = end_d + _td(days=1)
        if hasattr(SalesInvoice, 'date') and SalesInvoice.date is not None:
            q = q.filter(SalesInvoice.date >= d_start, SalesInvoice.date <= d_end)
        elif hasattr(SalesInvoice, 'created_at'):
            q = q.filter(
                func.date(SalesInvoice.created_at) >= d_start,
                func.date(SalesInvoice.created_at) <= d_end,
            )
    invs = q.order_by(SalesInvoice.created_at.asc() if hasattr(SalesInvoice, 'created_at') else SalesInvoice.date.asc()).all()
    for inv in invs:
        # Use invoice date for report day so report matches journal (journal uses inv.date for line_date).
        # Only use sales_day from created_at when inv.date is not set.
        if getattr(inv, 'date', None) is not None:
            sd = inv.date
        else:
            dt = getattr(inv, 'created_at', None) or (getattr(inv, 'date', None) and _dt.combine(inv.date, _time(12, 0)))
            if not dt and getattr(inv, 'date', None):
                dt = _dt.combine(inv.date, _time(12, 0))
            sd = _sales_day_date(dt)
        if sd is None:
            continue
        if start_d and sd < start_d:
            continue
        if end_d and sd > end_d:
            continue
        bt = float(inv.total_before_tax or 0)
        disc = float(inv.discount_amount or 0)
        tax = float(inv.tax_amount or 0)
        ta = float(inv.total_after_tax_discount or 0)
        pm = (inv.payment_method or '').strip().upper()
        pm_ar = 'نقدي' if pm in ('CASH', 'نقد', 'نقدي') else ('آجل' if pm in ('PENDING', 'CREDIT', 'آجل') else 'بطاقة')
        br = BRANCH_LABELS.get((inv.branch or '').strip(), (inv.branch or '—'))
        rows.append({
            'branch': br,
            'amount': bt,
            'tax': tax,
            'discount': disc,
            'total': ta,
            'payment_method': pm_ar,
            'invoice_number': getattr(inv, 'invoice_number', ''),
            'date': sd.isoformat(),
        })
        by_pm[pm] = by_pm.get(pm, 0.0) + ta
        total_before_tax += bt
        total_discount += disc
        total_tax += tax
        total_after += ta
    by_pm_use = {}
    for pm_raw, v in by_pm.items():
        pm_u = (pm_raw or '').upper()
        if pm_u in ('CASH', 'نقد', 'نقدي'):
            by_pm_use['نقدي'] = by_pm_use.get('نقدي', 0) + v
        elif pm_u in ('CARD', 'BANK', 'TRANSFER', 'VISA', 'MADA', 'مدى', 'فيزا', 'بنك', 'بطاقة'):
            by_pm_use['بطاقة'] = by_pm_use.get('بطاقة', 0) + v
        else:
            by_pm_use['آجل'] = by_pm_use.get('آجل', 0) + v
    total_cash = by_pm_use.get('نقدي', 0)
    total_card = by_pm_use.get('بطاقة', 0)
    total_credit = by_pm_use.get('آجل', 0)
    return {
        'rows': rows,
        'total_cash': total_cash,
        'total_card': total_card,
        'total_credit': total_credit,
        'total_before_tax': total_before_tax,
        'total_discount': total_discount,
        'total_tax': total_tax,
        'total_after': total_after,
        'count': len(rows),
        'by_pm': by_pm,
    }


@bp.route('/reports/print/payments', methods=['GET'], endpoint='reports_print_payments')
@login_required
def reports_print_payments():
    try:
        from datetime import datetime as _dt, date as _date
        from sqlalchemy import func
        from models import PurchaseInvoice, ExpenseInvoice, Payment, Settings

        inv_type = (request.args.get('type') or 'purchase').strip().lower()
        if inv_type not in ('purchase','expense'):
            inv_type = 'purchase'

        start_s = request.args.get('start_date') or ''
        end_s = request.args.get('end_date') or ''
        try:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date() if start_s else _date.min
        except Exception:
            start_d = _date.min
        try:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date() if end_s else _date.max
        except Exception:
            end_d = _date.max

        rows = []
        totals_by_party = {}

        if inv_type == 'purchase':
            q = PurchaseInvoice.query.options(selectinload(PurchaseInvoice.items)).filter(PurchaseInvoice.date.between(start_d, end_d))
            for inv in q.order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc()).all():
                total = float(inv.total_after_tax_discount or 0.0)
                paid = float(
                    db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                      .filter(Payment.invoice_type=='purchase', Payment.invoice_id==inv.id).scalar() or 0.0
                )
                remaining = max(total - paid, 0.0)
                party = getattr(inv, 'supplier_name', '-') or '-'
                rows.append({
                    'BILL NO': inv.invoice_number,
                    'DATE': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                    'SUPPLIER': party,
                    'ITEMS/QTY/TOTAL': f"{len(getattr(inv,'items',[]) or [])} items",
                    'PAID': paid,
                    'REMAINING': remaining,
                    'METHOD': (inv.payment_method or '').upper(),
                    'STATUS': (inv.status or '').upper()
                })
                t = totals_by_party.setdefault(party, {'TOTAL':0.0,'PAID':0.0,'REMAINING':0.0})
                t['TOTAL'] += total; t['PAID'] += paid; t['REMAINING'] += remaining
        else:
            q = ExpenseInvoice.query.options(selectinload(ExpenseInvoice.items)).filter(ExpenseInvoice.date.between(start_d, end_d))
            for inv in q.order_by(ExpenseInvoice.date.desc(), ExpenseInvoice.id.desc()).all():
                total = float(inv.total_after_tax_discount or 0.0)
                paid = float(
                    db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                      .filter(Payment.invoice_type=='expense', Payment.invoice_id==inv.id).scalar() or 0.0
                )
                remaining = max(total - paid, 0.0)
                party = 'Expense'
                rows.append({
                    'BILL NO': inv.invoice_number,
                    'DATE': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                    'SUPPLIER': party,
                    'ITEMS/QTY/TOTAL': f"{len(getattr(inv,'items',[]) or [])} items",
                    'PAID': paid,
                    'REMAINING': remaining,
                    'METHOD': (inv.payment_method or '').upper(),
                    'STATUS': (inv.status or '').upper()
                })
                t = totals_by_party.setdefault(party, {'TOTAL':0.0,'PAID':0.0,'REMAINING':0.0})
                t['TOTAL'] += total; t['PAID'] += paid; t['REMAINING'] += remaining

        columns = ['BILL NO','DATE','SUPPLIER','ITEMS/QTY/TOTAL','PAID','REMAINING','METHOD','STATUS']
        data = rows
        totals = {
            'PAID': sum(r.get('PAID',0.0) for r in rows),
            'REMAINING': sum(r.get('REMAINING',0.0) for r in rows),
        }
        settings = Settings.query.first()
        # Render with payment totals by method per the template optional block
        payment_totals = {}
        for r in rows:
            pm = r.get('METHOD') or 'UNKNOWN'
            payment_totals[pm] = payment_totals.get(pm, 0.0) + float(r.get('PAID') or 0.0)

        # Supplier totals: show remaining by supplier; adapt labels
        supplier_totals = { k: v['REMAINING'] for k, v in totals_by_party.items() }

        return render_template('print_report.html',
                               report_title=("Purchases" if inv_type=='purchase' else "Expenses"),
                               columns=columns,
                               data=data,
                               totals=totals,
                               totals_columns=['PAID','REMAINING'],
                               totals_colspan=4,
                               settings=settings,
                               start_date=start_s, end_date=end_s,
                               payment_method=request.args.get('payment_method') or 'all',
                               generated_at=get_saudi_now().strftime('%Y-%m-%d %H:%M'),
                               item_totals=supplier_totals,
                               item_totals_title=('Supplier Totals' if inv_type=='purchase' else 'Expense Totals'),
                               item_totals_name_label=('Supplier' if inv_type=='purchase' else 'Expense'),
                               item_totals_value_label='Remaining',
                               payment_totals=payment_totals)
    except Exception:
        return redirect(url_for('payments'))



@bp.route('/reports/print/salaries', methods=['GET'], endpoint='reports_print_salaries')
@login_required
def reports_print_salaries():
    # Redirect to detailed payroll statement to ensure new screen is used everywhere
    try:
        q = request.query_string.decode('utf-8') if request.query_string else ''
    except Exception:
        q = ''
    target = url_for('reports.reports_print_salaries_detailed')
    if q:
        target = f"{target}?{q}"
    return redirect(target)



@bp.route('/reports/print/salaries_detailed', methods=['GET'], endpoint='reports_print_salaries_detailed')
@login_required
def reports_print_salaries_detailed():
    # توحيد العرض مع كشف الرواتب: إعادة توجيه إلى print_payroll بنفس الشهر
    month_param = (request.args.get('month') or '').strip()
    if '-' in month_param:
        try:
            y, m = month_param.split('-')
            if 1 <= int(m) <= 12:
                return redirect(url_for('reports.print_payroll', month=month_param))
        except (ValueError, IndexError):
            pass
    year = request.args.get('year', type=int) or get_saudi_now().year
    month = request.args.get('month', type=int) or get_saudi_now().month
    month_str = f"{year:04d}-{month:02d}"
    return redirect(url_for('reports.print_payroll', month=month_str))




@bp.route('/reports/print/salaries', methods=['GET'], endpoint='reports_print_salaries_legacy')
@login_required
def reports_print_salaries_legacy():
    return ('', 404)




@bp.route('/reports', endpoint='reports')
@login_required
def reports():
    return render_template('reports.html')


@bp.route('/reports/sales', methods=['GET'], endpoint='reports_sales')
@login_required
def reports_sales():
    """تقرير المبيعات — معاينة/طباعة، يوم مبيعات 10ص–2ص، فروع."""
    from datetime import datetime as _dt, date as _date
    start_s = (request.args.get('from') or request.args.get('start_date') or '').strip()
    end_s = (request.args.get('to') or request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip()
    start_d = end_d = None
    try:
        if start_s:
            start_d = _dt.strptime(start_s, '%Y-%m-%d').date()
        if end_s:
            end_d = _dt.strptime(end_s, '%Y-%m-%d').date()
    except Exception:
        pass
    if not start_d and end_d:
        start_d = end_d
    if not end_d and start_d:
        end_d = start_d
    if not start_d:
        today = get_saudi_now().date()
        start_d = end_d = today
    data = _sales_report_data(start_d, end_d, branch)
    # عرض طريقة الدفع حسب لغة النظام (يدعم التبديل الكامل عربي/إنجليزي)
    _pm_display = {'نقدي': _('Cash'), 'بطاقة': _('Card'), 'آجل': _('Credit')}
    for r in (data.get('rows') or []):
        r['payment_method_display'] = _pm_display.get((r.get('payment_method') or '').strip(), _('Credit'))
    header = _report_header_context()
    branch_label = 'الكل' if not branch or branch == 'all' else BRANCH_LABELS.get(branch, branch)
    ctx = {
        **header,
        "start_date": start_d,
        "end_date": end_d,
        "branch": branch,
        "branch_label": branch_label,
        "data": data,
    }
    return render_template("reports/sales_report.html", **ctx)


def _expenses_report_data(start_d, end_d, branch):
    """تقرير المصروفات — فلاتر تاريخ وفرع. يعمل مع أو بدون عمود liability_account_code."""
    rows = []
    total = 0.0
    try:
        q = ExpenseInvoice.query
        if start_d and end_d:
            q = q.filter(ExpenseInvoice.date >= start_d, ExpenseInvoice.date <= end_d)
        if branch and branch != 'all' and hasattr(ExpenseInvoice, 'branch'):
            q = q.filter(ExpenseInvoice.branch == branch)
        for inv in q.order_by(ExpenseInvoice.date.asc()).all():
            ta = float(inv.total_after_tax_discount or 0)
            total += ta
            desc = getattr(inv, 'notes', None) or getattr(inv, 'description', None) or '—'
            rows.append({
                'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
                'invoice_number': getattr(inv, 'invoice_number', ''),
                'description': (desc or '').strip() or '—',
                'payment_method': (inv.payment_method or '—').upper(),
                'total': ta,
            })
    except Exception as e:
        err = str(e).lower()
        if 'liability_account_code' in err or 'no such column' in err:
            # جدول قديم بدون العمود: استعلام خام
            sql = text("""
                SELECT id, invoice_number, date, payment_method, total_after_tax_discount
                FROM expense_invoices
                WHERE (:start_d IS NULL OR date >= :start_d) AND (:end_d IS NULL OR date <= :end_d)
                ORDER BY date ASC
            """)
            res = db.session.execute(sql, {'start_d': start_d, 'end_d': end_d})
            for row in res:
                ta = float(row.total_after_tax_discount or 0)
                total += ta
                rows.append({
                    'date': row.date.strftime('%Y-%m-%d') if row.date else '',
                    'invoice_number': row.invoice_number or '',
                    'description': '—',
                    'payment_method': (row.payment_method or '—').upper(),
                    'total': ta,
                })
        else:
            raise
    return {'rows': rows, 'total': total, 'count': len(rows)}


def _purchases_report_data(start_d, end_d, branch):
    """تقرير المشتريات — تفاصيل فواتير وموردين."""
    rows = []
    total = 0.0
    q = PurchaseInvoice.query
    if start_d and end_d:
        q = q.filter(PurchaseInvoice.date >= start_d, PurchaseInvoice.date <= end_d)
    if branch and branch != 'all' and hasattr(PurchaseInvoice, 'branch'):
        q = q.filter(PurchaseInvoice.branch == branch)
    for inv in q.order_by(PurchaseInvoice.date.asc()).all():
        ta = float(inv.total_after_tax_discount or 0)
        total += ta
        rows.append({
            'date': inv.date.strftime('%Y-%m-%d') if inv.date else '',
            'invoice_number': getattr(inv, 'invoice_number', ''),
            'supplier': getattr(inv, 'supplier_name', '') or '—',
            'payment_method': (inv.payment_method or '—').upper(),
            'total': ta,
        })
    return {'rows': rows, 'total': total, 'count': len(rows)}


@bp.route('/reports/expenses', methods=['GET'], endpoint='reports_expenses')
@login_required
def reports_expenses():
    from datetime import datetime as _dt
    start_s = (request.args.get('from') or request.args.get('start_date') or '').strip()
    end_s = (request.args.get('to') or request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip()
    start_d = end_d = None
    try:
        if start_s: start_d = _dt.strptime(start_s, '%Y-%m-%d').date()
        if end_s: end_d = _dt.strptime(end_s, '%Y-%m-%d').date()
    except Exception:
        pass
    if not start_d and end_d: start_d = end_d
    if not end_d and start_d: end_d = start_d
    if not start_d:
        today = get_saudi_now().date()
        start_d = end_d = today
    data = _expenses_report_data(start_d, end_d, branch)
    header = _report_header_context()
    branch_label = _('All') if not branch or branch == 'all' else _(BRANCH_LABELS.get(branch, branch))
    ctx = {**header, "start_date": start_d, "end_date": end_d, "branch": branch, "branch_label": branch_label, "data": data}
    return render_template("reports/expenses_report.html", **ctx)


@bp.route('/reports/print/expenses', methods=['GET'], endpoint='reports_print_expenses')
@login_required
def reports_print_expenses():
    """طباعة تقرير المصروفات (ملخص) — قالب موحد مع باقي التقارير."""
    from datetime import datetime as _dt
    start_s = (request.args.get('from') or request.args.get('start_date') or '').strip()
    end_s = (request.args.get('to') or request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip()
    start_d = end_d = None
    try:
        if start_s: start_d = _dt.strptime(start_s, '%Y-%m-%d').date()
        if end_s: end_d = _dt.strptime(end_s, '%Y-%m-%d').date()
    except Exception:
        pass
    if not start_d and end_d: start_d = end_d
    if not end_d and start_d: end_d = start_d
    if not start_d:
        start_d = end_d = get_saudi_now().date()
    data = _expenses_report_data(start_d, end_d, branch)
    branch_label = _('All') if not branch or branch == 'all' else _(BRANCH_LABELS.get(branch, branch))
    try:
        settings = Settings.query.first()
        company_name = (settings.company_name or 'Company').strip() if settings else 'Company'
        tax_number = (settings.tax_number or '').strip() if settings else ''
        address = (getattr(settings, 'address', None) or '').strip() if settings else ''
        logo_url = getattr(settings, 'logo_url', None) if settings else None
        show_logo = bool(getattr(settings, 'receipt_show_logo', False)) if settings else False
    except Exception:
        company_name, tax_number, address, logo_url = 'Company', '', '', None
        show_logo = False
    generated_at = get_saudi_now().strftime('%Y-%m-%d %H:%M')
    return render_template(
        'reports/expenses_print.html',
        data=data,
        company_name=company_name,
        tax_number=tax_number,
        address=address,
        logo_url=logo_url,
        show_logo=show_logo,
        start_date=start_d,
        end_date=end_d,
        branch_label=branch_label,
        generated_at=generated_at,
    )


@bp.route('/reports/print/purchases', methods=['GET'], endpoint='reports_print_purchases')
@login_required
def reports_print_purchases():
    """طباعة تقرير المشتريات — قالب موحد مع تقارير المصروفات وكشف الرواتب."""
    from datetime import datetime as _dt
    start_s = (request.args.get('from') or request.args.get('start_date') or '').strip()
    end_s = (request.args.get('to') or request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip()
    start_d = end_d = None
    try:
        if start_s: start_d = _dt.strptime(start_s, '%Y-%m-%d').date()
        if end_s: end_d = _dt.strptime(end_s, '%Y-%m-%d').date()
    except Exception:
        pass
    if not start_d and end_d: start_d = end_d
    if not end_d and start_d: end_d = start_d
    if not start_d:
        start_d = end_d = get_saudi_now().date()
    data = _purchases_report_data(start_d, end_d, branch)
    branch_label = _('All') if not branch or branch == 'all' else _(BRANCH_LABELS.get(branch, branch))
    try:
        settings = Settings.query.first()
        company_name = (settings.company_name or 'Company').strip() if settings else 'Company'
        tax_number = (settings.tax_number or '').strip() if settings else ''
        address = (getattr(settings, 'address', None) or '').strip() if settings else ''
        logo_url = getattr(settings, 'logo_url', None) if settings else None
        show_logo = bool(getattr(settings, 'receipt_show_logo', False)) if settings else False
    except Exception:
        company_name, tax_number, address, logo_url = 'Company', '', '', None
        show_logo = False
    generated_at = get_saudi_now().strftime('%Y-%m-%d %H:%M')
    return render_template(
        'reports/purchases_print.html',
        data=data,
        company_name=company_name,
        tax_number=tax_number,
        address=address,
        logo_url=logo_url,
        show_logo=show_logo,
        start_date=start_d,
        end_date=end_d,
        branch_label=branch_label,
        generated_at=generated_at,
    )


@bp.route('/reports/purchases', methods=['GET'], endpoint='reports_purchases')
@login_required
def reports_purchases():
    from datetime import datetime as _dt
    start_s = (request.args.get('from') or request.args.get('start_date') or '').strip()
    end_s = (request.args.get('to') or request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip()
    start_d = end_d = None
    try:
        if start_s: start_d = _dt.strptime(start_s, '%Y-%m-%d').date()
        if end_s: end_d = _dt.strptime(end_s, '%Y-%m-%d').date()
    except Exception:
        pass
    if not start_d and end_d: start_d = end_d
    if not end_d and start_d: end_d = start_d
    if not start_d:
        today = get_saudi_now().date()
        start_d = end_d = today
    data = _purchases_report_data(start_d, end_d, branch)
    header = _report_header_context()
    branch_label = _('All') if not branch or branch == 'all' else _(BRANCH_LABELS.get(branch, branch))
    ctx = {**header, "start_date": start_d, "end_date": end_d, "branch": branch, "branch_label": branch_label, "data": data}
    return render_template("reports/purchases_report.html", **ctx)


def _reports_preview_fetch(inv_type, start_d, end_d, branch, pm):
    from datetime import datetime as _dt, time as _time
    rows = []
    if inv_type == 'sales':
        q = db.session.query(SalesInvoice)
        if start_d and end_d:
            try:
                if hasattr(SalesInvoice, 'created_at'):
                    start_dt = _dt.combine(start_d, _time.min)
                    end_dt = _dt.combine(end_d, _time.max)
                    q = q.filter(SalesInvoice.created_at >= start_dt, SalesInvoice.created_at <= end_dt)
                elif hasattr(SalesInvoice, 'date'):
                    q = q.filter(SalesInvoice.date.between(start_d, end_d))
            except Exception:
                pass
        if branch and branch != 'all':
            q = q.filter(SalesInvoice.branch == branch)
        if pm and pm != 'all':
            q = q.filter(SalesInvoice.payment_method == pm)
        order_col = SalesInvoice.created_at if hasattr(SalesInvoice, 'created_at') else SalesInvoice.date
        for r in q.order_by(order_col.asc()).all():
            rows.append({
                'date': (r.created_at.date().isoformat() if getattr(r, 'created_at', None) else (r.date.isoformat() if getattr(r, 'date', None) else '')),
                'branch': BRANCH_LABELS.get(r.branch, r.branch),
                'customer': (r.customer_name or ''),
                'type': 'sales',
                'payment': (r.payment_method or ''),
                'total': float(r.total_after_tax_discount or 0.0),
            })
    elif inv_type == 'purchases':
        q = db.session.query(PurchaseInvoice)
        if start_d and end_d:
            q = q.filter(PurchaseInvoice.date.between(start_d, end_d))
        if pm and pm != 'all':
            q = q.filter(PurchaseInvoice.payment_method == pm)
        for r in q.order_by(PurchaseInvoice.date.asc()).all():
            rows.append({
                'date': r.date.isoformat() if r.date else '',
                'branch': '—',
                'customer': (r.supplier_name or ''),
                'type': 'purchases',
                'payment': (r.payment_method or ''),
                'total': float(r.total_after_tax_discount or 0.0),
            })
    else:
        q = db.session.query(ExpenseInvoice)
        if start_d and end_d:
            q = q.filter(ExpenseInvoice.date.between(start_d, end_d))
        if pm and pm != 'all':
            q = q.filter(ExpenseInvoice.payment_method == pm)
        for r in q.order_by(ExpenseInvoice.date.asc()).all():
            rows.append({
                'date': r.date.isoformat() if r.date else '',
                'branch': '—',
                'customer': '',
                'type': 'expenses',
                'payment': (r.payment_method or ''),
                'total': float(r.total_after_tax_discount or 0.0),
            })
    return {'ok': True, 'rows': rows}


@bp.route('/api/reports/preview', methods=['GET'], endpoint='api_reports_preview')
def api_reports_preview():
    try:
        from datetime import datetime as _dt
        from utils.cache_helpers import (
            get_cached_reports_preview,
            reports_preview_cache_key,
            REPORTS_PREVIEW_TTL,
        )
        inv_type = (request.args.get('type') or 'sales').strip().lower()
        start_s = (request.args.get('start_date') or '').strip()
        end_s = (request.args.get('end_date') or '').strip()
        branch = (request.args.get('branch') or 'all').strip()
        pm = (request.args.get('payment_method') or 'all').strip().lower()
        def _parse(s):
            try:
                return _dt.strptime(s, '%Y-%m-%d').date()
            except Exception:
                return None
        start_d = _parse(start_s)
        end_d = _parse(end_s)
        if (start_d is None) and (end_d is not None):
            start_d = end_d
        if (end_d is None) and (start_d is not None):
            end_d = start_d
        key = reports_preview_cache_key(inv_type, start_s, end_s, branch, pm)

        def fetcher():
            return _reports_preview_fetch(inv_type, start_d, end_d, branch, pm)

        data = get_cached_reports_preview(key, fetcher, REPORTS_PREVIEW_TTL)
        if data is None:
            return jsonify({'ok': False, 'error': 'Failed to fetch preview'}), 500
        return jsonify(data)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/reports/customer-sales', methods=['GET'], endpoint='api_reports_customer_sales')
def api_reports_customer_sales():
    try:
        from datetime import datetime as _dt
        names_csv = (request.args.get('customers') or '').strip()
        start_s = (request.args.get('start_date') or '').strip()
        end_s = (request.args.get('end_date') or '').strip()
        branch = (request.args.get('branch') or 'all').strip()
        groups = [x.strip() for x in names_csv.split(',') if x.strip()]
        def _parse(s):
            try:
                return _dt.strptime(s, '%Y-%m-%d').date()
            except Exception:
                return None
        start_d = _parse(start_s)
        end_d = _parse(end_s)
        q = db.session.query(SalesInvoice)
        if start_d and end_d:
            q = q.filter(SalesInvoice.date.between(start_d, end_d))
        if branch and branch != 'all':
            q = q.filter(SalesInvoice.branch == branch)
        if groups:
            q = q.filter(SalesInvoice.customer_name.in_(groups))
        rows = []
        for r in q.order_by(SalesInvoice.date.asc()).limit(1000).all():
            rows.append({
                'date': r.date.isoformat() if r.date else '',
                'branch': BRANCH_LABELS.get(r.branch, r.branch),
                'customer': (r.customer_name or ''),
                'type': 'sales',
                'payment': (r.payment_method or ''),
                'total': float(r.total_after_tax_discount or 0.0),
            })
        return jsonify({'ok': True, 'rows': rows})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/reports/monthly', methods=['GET'], endpoint='reports_monthly')
@login_required
def reports_monthly():
    try:
        from models import Employee
        return render_template('reports_monthly.html', employees=Employee.query.all())
    except Exception:
        return render_template('reports_monthly.html', employees=[])


def _branch_sales_daily_rows(year: int, month: int, branch: str):
    """Aggregate sales by day for a given year/month/branch. Returns (rows, total_count, grand_total)."""
    from datetime import date as _date
    try:
        start_d = _date(int(year), int(month), 1)
        if month == 12:
            end_d = _date(int(year) + 1, 1, 1)
        else:
            end_d = _date(int(year), int(month) + 1, 1)
    except Exception:
        return [], 0, 0.0
    q = SalesInvoice.query
    if branch and branch != 'all':
        q = q.filter(func.lower(SalesInvoice.branch) == branch.lower())
    date_col = getattr(SalesInvoice, 'date', None) or func.date(SalesInvoice.created_at)
    q = q.filter(date_col >= start_d, date_col < end_d)
    invs = q.all()
    by_date = {}
    for inv in invs:
        d = None
        if getattr(inv, 'date', None):
            d = inv.date
        elif getattr(inv, 'created_at', None):
            d = inv.created_at.date() if hasattr(inv.created_at, 'date') else inv.created_at
        if d is None:
            continue
        total = float(inv.total_after_tax_discount or inv.total_before_tax or 0)
        pm = (getattr(inv, 'payment_method', None) or 'CASH').strip().upper()
        if d not in by_date:
            by_date[d] = {'count': 0, 'total': 0.0, 'methods': {}}
        by_date[d]['count'] += 1
        by_date[d]['total'] += total
        by_date[d]['methods'][pm] = by_date[d]['methods'].get(pm, 0.0) + total
    rows = []
    total_count = 0
    grand_total = 0.0
    for d in sorted(by_date.keys()):
        r = by_date[d]
        cnt = r['count']
        tot = r['total']
        total_count += cnt
        grand_total += tot
        rows.append({
            'date': d.strftime('%Y-%m-%d'),
            'count': cnt,
            'total': tot,
            'avg': tot / cnt if cnt else 0,
            'methods': r['methods'],
        })
    return rows, total_count, grand_total


@bp.route('/reports/branch_sales', methods=['GET'], endpoint='reports_branch_sales')
@login_required
def reports_branch_sales():
    """Branch sales by day — filters: year, month, branch."""
    now = get_saudi_now()
    try:
        year = request.args.get('year', type=int) or now.year
    except Exception:
        year = now.year
    try:
        month = request.args.get('month', type=int) or now.month
    except Exception:
        month = now.month
    branch = (request.args.get('branch') or 'all').strip()
    rows, total_count, grand_total = _branch_sales_daily_rows(year, month, branch)
    return render_template(
        'reports_branch_sales.html',
        year=year,
        month=month,
        branch=branch,
        rows=rows,
        total_count=total_count,
        grand_total=grand_total,
    )


@bp.route('/reports/branch_sales/print', methods=['GET'], endpoint='reports_branch_sales_print')
@login_required
def reports_branch_sales_print():
    """Print view for branch sales report (year/month/branch)."""
    now = get_saudi_now()
    try:
        year = request.args.get('year', type=int) or now.year
    except Exception:
        year = now.year
    try:
        month = request.args.get('month', type=int) or now.month
    except Exception:
        month = now.month
    branch = (request.args.get('branch') or 'all').strip()
    rows, total_count, grand_total = _branch_sales_daily_rows(year, month, branch)
    header = _report_header_context()
    branch_label = 'جميع الفروع' if not branch or branch == 'all' else BRANCH_LABELS.get(branch, branch)
    try:
        generated_at = now.strftime('%Y-%m-%d %H:%M')
    except Exception:
        generated_at = ''
    return render_template(
        'report_branch_sales_print.html',
        year=year,
        month=month,
        branch=branch,
        branch_label=branch_label,
        rows=rows,
        total_count=total_count,
        grand_total=grand_total,
        settings=header,
        generated_at=generated_at,
    )


@bp.route('/api/reports/monthly', methods=['GET'], endpoint='api_reports_monthly')
@login_required
def api_reports_monthly():
    try:
        from datetime import date
        from models import Salary, Employee, JournalLine, JournalEntry, Payment
        month = (request.args.get('month') or '').strip()
        year = request.args.get('year', type=int)
        emp_id = request.args.get('emp_id', type=int) or request.args.get('emp', type=int)
        emp_q = (request.args.get('emp') or '').strip().lower() if not emp_id else ''
        dept_q = (request.args.get('dept') or '').strip()
        start_dt = None; end_dt = None
        if month:
            y, m = month.split('-'); y = int(y); m = int(m)
            start_dt = date(y, m, 1)
            end_dt = date(y + (1 if m==12 else 0), 1 if m==12 else m+1, 1)
        elif year:
            start_dt = date(year, 1, 1)
            end_dt = date(year+1, 1, 1)
        emps = {}
        try:
            for e in Employee.query.all():
                emps[int(e.id)] = {'name': e.full_name, 'dept': (e.department or '').strip()}
        except Exception:
            pass
        sq = db.session.query(Salary)
        if month:
            y, m = month.split('-'); y = int(y); m = int(m)
            sq = sq.filter(Salary.year == y, Salary.month == m)
        elif year:
            sq = sq.filter(Salary.year == year)
        elif start_dt and end_dt:
            sq = sq.filter(Salary.month_date >= start_dt, Salary.month_date < end_dt)
        srows = sq.all()
        # Resolve Employee Advances account (EMP_ADV -> '1151')
        try:
            adv_code = SHORT_TO_NUMERIC.get('EMP_ADV', ('1151',))[0]
            adv_acc = _account(adv_code, CHART_OF_ACCOUNTS.get(adv_code, {}).get('name', 'سلف موظفين'), CHART_OF_ACCOUNTS.get(adv_code, {}).get('type', 'ASSET'))
        except Exception:
            adv_acc = None
        # Deductions within selected period (based on description keywords)
        jlq = db.session.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        if start_dt and end_dt:
            jlq = jlq.filter(JournalEntry.date >= start_dt, JournalEntry.date < end_dt)
        jrows = jlq.all()
        ded_hist_by_emp = {}
        try:
            dq = db.session.query(Salary.employee_id, func.coalesce(func.sum(Salary.deductions), 0.0))
            if end_dt:
                dq = dq.filter(Salary.month_date < end_dt)
            dq = dq.group_by(Salary.employee_id)
            for emp_id_val, ded_sum in dq.all():
                ded_hist_by_emp[int(emp_id_val or 0)] = float(ded_sum or 0.0)
        except Exception:
            ded_hist_by_emp = {}
        # Advances as historical outstanding up to end of period: sum EMP_ADV debits minus credits up to end_dt
        adv_debit_by_emp = {}
        adv_credit_by_emp = {}
        if adv_acc:
            adv_q = db.session.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
            adv_q = adv_q.filter(JournalLine.account_id == adv_acc.id)
            if end_dt:
                adv_q = adv_q.filter(JournalEntry.date < end_dt)
            for jl, je in adv_q.all():
                eid = int(getattr(jl, 'employee_id', 0) or 0)
                adv_debit_by_emp[eid] = adv_debit_by_emp.get(eid, 0.0) + float(getattr(jl, 'debit', 0) or 0)
                adv_credit_by_emp[eid] = adv_credit_by_emp.get(eid, 0.0) + float(getattr(jl, 'credit', 0) or 0)
        rows = []
        payroll_total = 0.0
        for s in srows:
            eid = int(getattr(s, 'employee_id', 0) or 0)
            nm = emps.get(eid, {}).get('name', '')
            dp = (emps.get(eid, {}).get('dept', '') or '').strip()
            if emp_id and eid != emp_id:
                continue
            if emp_q and nm.lower().find(emp_q) < 0:
                continue
            if dept_q and dp.lower() != dept_q.lower():
                continue
            basic = float(getattr(s, 'basic_salary', 0) or 0)
            bonus = float(getattr(s, 'allowances', 0) or 0)
            total = float(getattr(s, 'total_salary', 0) or 0)
            ded_month = float(getattr(s, 'deductions', 0) or 0)
            # Net monthly advances (granted - repaid) within the selected period
            adv_deb = float(adv_debit_by_emp.get(eid, 0.0) or 0.0)
            adv_cre = float(adv_credit_by_emp.get(eid, 0.0) or 0.0)
            advances = max(0.0, adv_deb - adv_cre)
            # Actual payments against this salary
            try:
                paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                             .filter(Payment.invoice_type=='salary', Payment.invoice_id==int(getattr(s,'id',0) or 0)).scalar() or 0.0)
            except Exception:
                paid = 0.0
            remaining = max(0.0, total - paid)
            # Normalize status to avoid marking zero totals as paid
            st = (getattr(s, 'status', '') or '').strip().lower() or 'due'
            if total <= 0:
                st = 'due'
            else:
                if paid >= total:
                    st = 'paid'
                elif paid > 0:
                    st = 'partial'
                else:
                    st = 'due'
            # Skip completely empty rows (no totals, no payments, no advances, no deductions)
            if total <= 0 and paid <= 0 and advances <= 0 and ded_month <= 0:
                continue
            net = max(0.0, total - advances - ded_month)
            rows.append({
                'employee_id': eid,
                'name': nm,
                'dept': dp,
                'basic': basic,
                'ot': 0.0,
                'bonus': bonus,
                'total': total,
                'advances': advances,
                'deductions': float(ded_hist_by_emp.get(eid, 0.0) or 0.0),
                'net': net,
                'status': st,
                'month': f"{int(getattr(s,'year',0) or 0)}-{str(int(getattr(s,'month',0) or 0)).zfill(2)}"
            })
            payroll_total += total
        # KPI totals should reflect only employees included in rows
        adv_total = float(sum([r.get('advances', 0.0) for r in rows]) or 0.0)
        ded_total = float(sum([r.get('deductions', 0.0) for r in rows]) or 0.0)
        entries_count = len(jrows)
        series = {
            'payroll': [float(getattr(sr, 'total_salary', 0) or 0) for sr in srows][0:24],
            'advances': [float(r.get('advances', 0.0)) for r in rows][0:24],
            'deductions': [float(r.get('deductions', 0.0)) for r in rows][0:24],
        }
        return jsonify({'ok': True, 'kpis': { 'payroll_total': payroll_total, 'advances_total': adv_total, 'deductions_total': ded_total, 'entries_count': entries_count }, 'rows': rows, 'series': series})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/reports/print/customer-sales', methods=['GET'], endpoint='reports_print_customer_sales')
@login_required
def reports_print_customer_sales():
    customer = (request.args.get('customer') or '').strip()
    customers_param = (request.args.get('customers') or '').strip()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip()
    rows = []
    totals = {'Amount': 0.0, 'Discount': 0.0, 'VAT': 0.0, 'Total': 0.0}
    payment_totals = {}
    try:
        from sqlalchemy import or_, and_
        import re
        def normalize_group(n: str):
            s = re.sub(r'[^a-z]', '', (n or '').lower())
            if s.startswith('hunger'): return 'hunger'
            if s.startswith('keeta') or s.startswith('keet'): return 'keeta'
            if s.startswith('noon'): return 'noon'
            return s
        # Aggregate items per invoice for amount and VAT
        items_sub = db.session.query(
            SalesInvoiceItem.invoice_id.label('inv_id'),
            func.sum(SalesInvoiceItem.price_before_tax * SalesInvoiceItem.quantity).label('amount_sum'),
            func.sum(SalesInvoiceItem.tax).label('vat_sum')
        ).group_by(SalesInvoiceItem.invoice_id).subquery()

        q = db.session.query(
            SalesInvoice,
            items_sub.c.amount_sum,
            items_sub.c.vat_sum
        ).outerjoin(items_sub, items_sub.c.inv_id == SalesInvoice.id)
        q = q.filter(SalesInvoice.status == 'paid')
        customers_list = []
        if customers_param:
            customers_list = [normalize_group(s) for s in customers_param.split(',') if s.strip()]
        base_filters = []
        if customers_list:
            for base in customers_list:
                if base:
                    base_filters.append(SalesInvoice.customer_name.ilike(base + '%'))
        elif customer:
            base = normalize_group(customer)
            if base:
                base_filters.append(SalesInvoice.customer_name.ilike(base + '%'))
        if base_filters:
            q = q.filter(or_(*base_filters))
        if branch and branch != 'all':
            q = q.filter(SalesInvoice.branch == branch)
        # Date range
        sd_dt = None; ed_dt = None
        try:
            sd_dt = datetime.fromisoformat(start_date) if start_date else None
        except Exception:
            sd_dt = None
        try:
            ed_dt = datetime.fromisoformat(end_date) if end_date else None
        except Exception:
            ed_dt = None
        if sd_dt and ed_dt:
            q = q.filter(or_(SalesInvoice.created_at.between(sd_dt, ed_dt), SalesInvoice.date.between(sd_dt, ed_dt)))
        elif sd_dt and (not ed_dt):
            q = q.filter(or_(SalesInvoice.created_at >= sd_dt, SalesInvoice.date >= sd_dt))
        elif ed_dt and (not sd_dt):
            q = q.filter(or_(SalesInvoice.created_at <= ed_dt, SalesInvoice.date <= ed_dt))

        q = q.order_by(SalesInvoice.created_at.desc(), SalesInvoice.date.desc()).limit(2000)
        for inv, amount_sum, vat_sum in q.all():
            dt = getattr(inv, 'created_at', None) or getattr(inv, 'date', None) or get_saudi_now()
            day_name = dt.strftime('%A')
            amount = float(amount_sum or 0.0)
            discount = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            vat = float(vat_sum or 0.0)
            total = float(amount - discount + vat)
            pm = (inv.payment_method or '').upper()
            rows.append({
                'Date': dt.strftime('%Y-%m-%d'),
                'Day': day_name,
                'Invoice': inv.invoice_number,
                'Payment': pm,
                'Amount': amount,
                'Discount': discount,
                'VAT': vat,
                'Total': total,
            })
            totals['Amount'] += amount
            totals['Discount'] += discount
            totals['VAT'] += vat
            totals['Total'] += total
            payment_totals[pm] = payment_totals.get(pm, 0.0) + total
    except Exception:
        pass

    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    title_customer = (normalize_group(customer) if customer else '')
    if customers_list:
        try:
            title_customer = ', '.join(customers_list)
        except Exception:
            title_customer = title_customer or 'multiple'
    meta = {
        'title': f"Customer Sales — {title_customer}",
        'customer': title_customer,
        'branch': branch,
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    columns = ['Date','Day','Invoice','Payment','Amount','Discount','VAT','Total']
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method='all', branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=['Amount','Discount','VAT','Total'],
                           totals_colspan=4, payment_totals=payment_totals)


@bp.route('/api/reports/all-purchases', methods=['GET'], endpoint='api_reports_all_purchases')
@login_required
def api_reports_all_purchases():
    try:
        payment_method = (request.args.get('payment_method') or '').strip().lower()
        rows = []
        overall = {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0}
        q = db.session.query(PurchaseInvoice, PurchaseInvoiceItem).join(
            PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id
        )
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(PurchaseInvoice.payment_method) == payment_method)
        # ترتيب آمن
        if hasattr(PurchaseInvoice, 'created_at'):
            q = q.order_by(PurchaseInvoice.created_at.desc())
        elif hasattr(PurchaseInvoice, 'date'):
            q = q.order_by(PurchaseInvoice.date.desc())
        q = q.limit(1000)

        results = q.all()
        # اجمع أساس البنود لكل فاتورة لتوزيع الخصم/الضريبة من رأس الفاتورة
        inv_base = {}
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results:
            date_s = (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            # استخدم خصم وضريبة رأس الفاتورة إن توفّرا، وإلا ارجع لقيم البند
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat = inv_vat * (amount / base_total)
            else:
                disc = float(it.discount or 0.0)
                base = max(amount - disc, 0.0)
                vat = float(it.tax or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            total = float(getattr(inv, 'total_after_tax_discount', 0.0) or 0.0)
            if total <= 0:
                total = base_after_disc + vat
            rows.append({
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.raw_material_name,
                'quantity': float(it.quantity or 0.0),
                'price': float(it.price_before_tax or 0.0),
                'amount': amount,
                'discount': round(disc, 2),
                'vat': round(vat, 2),
                'total': round(base_after_disc + vat, 2),
                'payment_method': (inv.payment_method or '').upper(),
            })
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += (base_after_disc + vat)
        return jsonify({'purchases': rows, 'overall_totals': overall})
    except Exception:
        return jsonify({'purchases': [], 'overall_totals': {'amount':0,'discount':0,'vat':0,'total':0}, 'note': 'stub'}), 200



@bp.route('/reports/print/all-invoices/sales', methods=['GET'], endpoint='reports_print_all_invoices_sales')
@login_required
def reports_print_all_invoices_sales():
    # Reuse same data generation as api_all_invoices but render print template
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    fmt = (request.args.get('format') or '').strip().lower()
    rows = []
    branch_totals = {}
    overall = {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0}
    try:
        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(
            SalesInvoiceItem, SalesInvoiceItem.invoice_id == SalesInvoice.id
        )
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(SalesInvoice.payment_method) == payment_method)
        # Optional branch filter (sales only)
        branch = (request.args.get('branch') or 'all').strip().lower()
        if branch and branch != 'all':
            q = q.filter(func.lower(SalesInvoice.branch) == branch)
        # Optional date range filter
        if start_date:
            try:
                if hasattr(SalesInvoice, 'created_at'):
                    q = q.filter(func.date(SalesInvoice.created_at) >= start_date)
                elif hasattr(SalesInvoice, 'date'):
                    q = q.filter(SalesInvoice.date >= start_date)
            except Exception:
                pass
        if end_date:
            try:
                if hasattr(SalesInvoice, 'created_at'):
                    q = q.filter(func.date(SalesInvoice.created_at) <= end_date)
                elif hasattr(SalesInvoice, 'date'):
                    q = q.filter(SalesInvoice.date <= end_date)
            except Exception:
                pass
        if hasattr(SalesInvoice, 'created_at'):
            q = q.order_by(SalesInvoice.created_at.desc())
        elif hasattr(SalesInvoice, 'date'):
            q = q.order_by(SalesInvoice.date.desc())

        results = q.all()
        # اجمع أساس البنود لكل فاتورة لتوزيع الخصم/الضريبة من رأس الفاتورة
        inv_base = {}
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results:
            branch = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
            if getattr(inv, 'created_at', None):
                date_s = inv.created_at.date().isoformat()
            elif getattr(inv, 'date', None):
                date_s = inv.date.isoformat()
            else:
                date_s = ''
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat  = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat  = inv_vat  * (amount / base_total)
            else:
                disc = float(getattr(it, 'discount', 0.0) or 0.0)
                base = max(amount - disc, 0.0)
                vat  = float(getattr(it, 'tax', 0.0) or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            total = base_after_disc + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'branch': branch,
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.product_name,
                'quantity': float(it.quantity or 0.0),
                'amount': amount,
                'discount': round(disc, 2),
                'vat': round(vat, 2),
                'total': round(total, 2),
                'payment_method': pm,
            })
            bt = branch_totals.setdefault(branch, {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0})
            bt['amount'] += amount; bt['discount'] += disc; bt['vat'] += vat; bt['total'] += total
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += total
    except Exception:
        pass

    # Settings for header
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None

    # Payment method totals
    payment_totals = {}
    for r in rows:
        pm = (r.get('payment_method') or '').upper()
        payment_totals[pm] = payment_totals.get(pm, 0.0) + float(r.get('total') or 0.0)

    # Aggregate item totals (by quantity) for display
    item_totals = {}
    try:
        for r in rows:
            name = (r.get('item_name') or '').strip()
            qty = float(r.get('quantity') or 0.0)
            if name:
                item_totals[name] = item_totals.get(name, 0.0) + qty
    except Exception:
        item_totals = {}

    grouped_invoices = []
    try:
        inv_map = {}
        for inv, it in results:
            key = getattr(inv, 'invoice_number', None) or str(getattr(inv, 'id', ''))
            if key not in inv_map:
                if getattr(inv, 'created_at', None):
                    date_s = inv.created_at.date().isoformat()
                elif getattr(inv, 'date', None):
                    date_s = inv.date.isoformat()
                else:
                    date_s = ''
                branch = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
                subtotal = float(inv_base.get(inv.id, 0.0) or 0.0)
                disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
                vat = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
                total = float(getattr(inv, 'total_after_tax_discount', 0.0) or (subtotal - disc + vat))
                inv_map[key] = {
                    'branch': branch,
                    'date': date_s,
                    'invoice_number': getattr(inv, 'invoice_number', key),
                    'payment_method': (inv.payment_method or '').upper(),
                    'subtotal': round(subtotal, 2),
                    'discount': round(disc, 2),
                    'vat': round(vat, 2),
                    'total': round(total, 2),
                    'items': []
                }
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat  = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc_part = inv_disc * (amount / base_total)
                vat_part  = inv_vat  * (amount / base_total)
            else:
                disc_part = float(getattr(it, 'discount', 0.0) or 0.0)
                vat_part  = float(getattr(it, 'tax', 0.0) or 0.0)
            line_total = max(amount - disc_part, 0.0) + vat_part
            inv_map[key]['items'].append({
                'item_name': it.product_name,
                'quantity': float(it.quantity or 0.0),
                'amount': round(amount, 2),
                'discount': round(disc_part, 2),
                'vat': round(vat_part, 2),
                'total': round(line_total, 2),
            })
        grouped_invoices = list(inv_map.values())
    except Exception:
        grouped_invoices = []

    meta = {
        'title': 'Sales Invoices (All) — Print',
        'payment_method': payment_method or 'all',
        'branch': (branch or 'all'),
        'start_date': request.args.get('start_date') or '',
        'end_date': request.args.get('end_date') or '',
        'generated_at': get_saudi_now().strftime('%Y-%m-%d %H:%M')
    }
    # Use unified print_report.html like purchases/expenses
    columns = ['Branch','Date','Invoice No.','Item','Qty','Amount','Discount','VAT','Total','Payment']
    data = []
    for r in rows:
        data.append({
            'Branch': r.get('branch') or '',
            'Date': r.get('date') or '',
            'Invoice No.': r.get('invoice_number') or '',
            'Item': r.get('item_name') or '',
            'Qty': float(r.get('quantity') or 0.0),
            'Amount': float(r.get('amount') or 0.0),
            'Discount': float(r.get('discount') or 0.0),
            'VAT': float(r.get('vat') or 0.0),
            'Total': float(r.get('total') or 0.0),
            'Payment': r.get('payment_method') or '',
        })
    totals = {
        'Amount': float(overall.get('amount') or 0.0),
        'Discount': float(overall.get('discount') or 0.0),
        'VAT': float(overall.get('vat') or 0.0),
        'Total': float(overall.get('total') or 0.0),
    }
    totals_columns = ['Amount','Discount','VAT','Total']
    totals_colspan = len(columns) - len(totals_columns)
    # CSV export
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for r in data:
                writer.writerow([r.get('Branch',''), r.get('Date',''), r.get('Invoice No.',''), r.get('Item',''),
                                 r.get('Qty',0.0), r.get('Amount',0.0), r.get('Discount',0.0), r.get('VAT',0.0),
                                 r.get('Total',0.0), r.get('Payment','')])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="sales_invoices.csv"'})
        except Exception:
            pass

    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=data, totals=totals, totals_columns=totals_columns,
                           totals_colspan=totals_colspan, payment_totals=payment_totals,
                           item_totals=item_totals, grouped_invoices=grouped_invoices)



@bp.route('/reports/print/daily-sales', methods=['GET'], endpoint='reports_print_daily_sales')
@login_required
def reports_print_daily_sales():
    pm = (request.args.get('payment_method') or 'all').strip().lower()
    branch = (request.args.get('branch') or 'all').strip().lower()
    fmt = (request.args.get('format') or '').strip().lower()
    now = get_saudi_now()
    from datetime import datetime as _dt, timedelta as _td
    try:
        from models import KSA_TZ
        tz = KSA_TZ
    except Exception:
        tz = getattr(now, 'tzinfo', None)
    anchor = now.date() if now.hour >= 11 else (now - _td(days=1)).date()
    start_dt = tz.localize(_dt(anchor.year, anchor.month, anchor.day, 11, 0, 0)) if hasattr(tz, 'localize') else _dt(anchor.year, anchor.month, anchor.day, 11, 0, 0)
    end_dt = start_dt + _td(hours=14)
    rows = []
    results = []
    inv_base = {}
    branch_totals = {}
    overall = {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0}
    try:
        q = db.session.query(SalesInvoice, SalesInvoiceItem).join(
            SalesInvoiceItem, SalesInvoiceItem.invoice_id == SalesInvoice.id
        )
        if pm and pm != 'all':
            q = q.filter(func.lower(SalesInvoice.payment_method) == pm)
        if branch and branch != 'all':
            q = q.filter(func.lower(SalesInvoice.branch) == branch)
        if hasattr(SalesInvoice, 'created_at'):
            q = q.filter(SalesInvoice.created_at >= start_dt, SalesInvoice.created_at < end_dt)
            q = q.order_by(SalesInvoice.created_at.asc())
        else:
            q = q.filter(SalesInvoice.date.in_([start_dt.date(), end_dt.date()]))
            q = q.order_by(SalesInvoice.date.asc())
        results = q.all()
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base
        for inv, it in results:
            b = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
            if getattr(inv, 'created_at', None):
                try:
                    base_dt = inv.created_at
                    if getattr(base_dt, 'tzinfo', None):
                        date_s = base_dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')
                    else:
                        date_s = tz.localize(base_dt).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    date_s = get_saudi_now().strftime('%Y-%m-%d %H:%M')
            elif getattr(inv, 'date', None):
                date_s = inv.date.isoformat()
            else:
                date_s = ''
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat  = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat  = inv_vat  * (amount / base_total)
            else:
                disc = float(getattr(it, 'discount', 0.0) or 0.0)
                vat  = float(getattr(it, 'tax', 0.0) or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            total = base_after_disc + vat
            pmu = (inv.payment_method or '').upper()
            rows.append({
                'branch': b,
                'date': date_s,
                'invoice_number': inv.invoice_number,
                'item_name': it.product_name,
                'quantity': float(it.quantity or 0.0),
                'amount': amount,
                'discount': round(disc, 2),
                'vat': round(vat, 2),
                'total': round(total, 2),
                'payment_method': pmu,
            })
            bt = branch_totals.setdefault(b, {'amount': 0.0, 'discount': 0.0, 'vat': 0.0, 'total': 0.0})
            bt['amount'] += amount; bt['discount'] += disc; bt['vat'] += vat; bt['total'] += total
            overall['amount'] += amount; overall['discount'] += disc; overall['vat'] += vat; overall['total'] += total
    except Exception:
        pass
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    payment_totals = {}
    for r in rows:
        pmu = (r.get('payment_method') or '').upper()
        payment_totals[pmu] = payment_totals.get(pmu, 0.0) + float(r.get('total') or 0.0)
    item_totals = {}
    try:
        for r in rows:
            name = (r.get('item_name') or '').strip()
            qty = float(r.get('quantity') or 0.0)
            if name:
                item_totals[name] = item_totals.get(name, 0.0) + qty
    except Exception:
        item_totals = {}
    meta = {
        'title': 'Daily Sales — Print',
        'payment_method': pm or 'all',
        'branch': branch or 'all',
        'start_date': start_dt.strftime('%Y-%m-%d %H:%M'),
        'end_date': end_dt.strftime('%Y-%m-%d %H:%M'),
        'generated_at': get_saudi_now().strftime('%Y-%m-%d %H:%M')
    }
    inv_map = {}
    try:
        for inv, it in results:
            key = getattr(inv, 'invoice_number', None) or str(getattr(inv, 'id', ''))
            if key not in inv_map:
                b = getattr(inv, 'branch', None) or getattr(inv, 'branch_code', None) or 'unknown'
                if getattr(inv, 'created_at', None):
                    try:
                        base_dt = inv.created_at
                        if getattr(base_dt, 'tzinfo', None):
                            date_s = base_dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')
                        else:
                            date_s = tz.localize(base_dt).strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        date_s = get_saudi_now().strftime('%Y-%m-%d %H:%M')
                elif getattr(inv, 'date', None):
                    date_s = inv.date.isoformat()
                else:
                    date_s = ''
                subtotal = float(inv_base.get(inv.id, 0.0) or 0.0)
                disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
                vat = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
                total = float(getattr(inv, 'total_after_tax_discount', 0.0) or (subtotal - disc + vat))
                inv_map[key] = {
                    'branch': b,
                    'date': date_s,
                    'invoice_number': getattr(inv, 'invoice_number', key),
                    'payment_method': (inv.payment_method or '').upper(),
                    'subtotal': round(subtotal, 2),
                    'discount': round(disc, 2),
                    'vat': round(vat, 2),
                    'total': round(total, 2),
                    'items': [],
                    'item_count': 0
                }
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat  = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc_part = inv_disc * (amount / base_total)
                vat_part  = inv_vat  * (amount / base_total)
            else:
                disc_part = float(getattr(it, 'discount', 0.0) or 0.0)
                vat_part  = float(getattr(it, 'tax', 0.0) or 0.0)
            line_total = max(amount - disc_part, 0.0) + vat_part
            inv_map[key]['items'].append({
                'item_name': it.product_name,
                'quantity': float(it.quantity or 0.0),
                'amount': round(amount, 2),
                'discount': round(disc_part, 2),
                'vat': round(vat_part, 2),
                'total': round(line_total, 2),
            })
            inv_map[key]['item_count'] = int(inv_map[key].get('item_count', 0)) + 1
        grouped_invoices = list(inv_map.values())
    except Exception:
        grouped_invoices = []
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Branch','Date','Invoice No.','Items','Payment','Subtotal','Discount','VAT','Total'])
            for inv in grouped_invoices:
                writer.writerow([
                    inv.get('branch',''),
                    inv.get('date',''),
                    inv.get('invoice_number',''),
                    int(inv.get('item_count') or (len(inv.get('items') or []))),
                    inv.get('payment_method',''),
                    inv.get('subtotal',0.0),
                    inv.get('discount',0.0),
                    inv.get('vat',0.0),
                    inv.get('total',0.0)
                ])
            from flask import Response
            fname = f"daily_sales_{anchor.isoformat()}.csv"
            return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{fname}"'})
        except Exception:
            pass
    if fmt == 'pdf':
        try:
            import io
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            w, h = A4
            y = h - 20*mm
            p.setFont("Helvetica-Bold", 14)
            p.drawString(20*mm, y, "Daily Sales Report")
            y -= 8*mm
            p.setFont("Helvetica", 10)
            p.drawString(20*mm, y, f"Period: {meta['start_date']} → {meta['end_date']}")
            y -= 6*mm
            p.drawString(20*mm, y, f"Generated: {meta['generated_at']}")
            y -= 10*mm
            p.setFont("Helvetica-Bold", 9)
            headers = ["Branch","Date","Invoice","Items","PM","Subtotal","Discount","VAT","Total"]
            xs = [10*mm, 30*mm, 70*mm, 100*mm, 115*mm, 130*mm, 150*mm, 170*mm, 190*mm]
            for i, hdr in enumerate(headers):
                p.drawString(xs[i], y, hdr)
            y -= 5*mm
            p.setFont("Helvetica", 9)
            for inv in grouped_invoices:
                row = [
                    str(inv.get('branch','')),
                    str(inv.get('date','')),
                    str(inv.get('invoice_number','')),
                    str(int(inv.get('item_count') or (len(inv.get('items') or [])))) ,
                    str(inv.get('payment_method','')),
                    f"{inv.get('subtotal',0.0):.2f}",
                    f"{inv.get('discount',0.0):.2f}",
                    f"{inv.get('vat',0.0):.2f}",
                    f"{inv.get('total',0.0):.2f}",
                ]
                if y < 20*mm:
                    p.showPage(); y = h - 20*mm; p.setFont("Helvetica", 9)
                for i, val in enumerate(row):
                    p.drawString(xs[i], y, val)
                y -= 5*mm
            y -= 6*mm
            p.setFont("Helvetica-Bold", 10)
            p.drawString(130*mm, y, f"Totals: {overall['total']:.2f}")
            p.showPage(); p.save()
            pdf_bytes = buffer.getvalue()
            from flask import Response
            fname = f"daily_sales_{anchor.isoformat()}.pdf"
            return Response(pdf_bytes, mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename="{fname}"'})
        except Exception:
            pass
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=get_saudi_now().strftime('%Y-%m-%d %H:%M'), start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=['Branch','Date','Invoice No.','Item','Qty','Amount','Discount','VAT','Total','Payment'], data=rows,
                           totals={'Amount': overall['amount'], 'Discount': overall['discount'], 'VAT': overall['vat'], 'Total': overall['total']},
                           totals_columns=['Amount','Discount','VAT','Total'], totals_colspan=6,
                           payment_totals=payment_totals, item_totals=item_totals,
                           branch_totals=branch_totals, overall=overall,
                           grouped_invoices=grouped_invoices, summary_mode=True)



@bp.route('/reports/print/all-invoices/purchases', methods=['GET'], endpoint='reports_print_all_invoices_purchases')
@login_required
def reports_print_all_invoices_purchases():
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip().lower()
    fmt = (request.args.get('format') or '').strip().lower()
    rows = []
    totals = {'Amount': 0.0, 'Discount': 0.0, 'VAT': 0.0, 'Total': 0.0}
    payment_totals = {}
    try:
        q = db.session.query(PurchaseInvoice, PurchaseInvoiceItem).join(
            PurchaseInvoiceItem, PurchaseInvoiceItem.invoice_id == PurchaseInvoice.id
        )
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(PurchaseInvoice.payment_method) == payment_method)
        # Date filtering if fields exist
        if start_date:
            try:
                q = q.filter(PurchaseInvoice.date >= start_date)
            except Exception:
                pass
        if end_date:
            try:
                q = q.filter(PurchaseInvoice.date <= end_date)
            except Exception:
                pass
        if branch and branch != 'all' and hasattr(PurchaseInvoice, 'branch'):
            q = q.filter(func.lower(PurchaseInvoice.branch) == branch)
        if hasattr(PurchaseInvoice, 'created_at'):
            q = q.order_by(PurchaseInvoice.created_at.desc())
        elif hasattr(PurchaseInvoice, 'date'):
            q = q.order_by(PurchaseInvoice.date.desc())
        q = q.limit(2000)

        results = q.all()
        # Aggregate base per invoice for proportional discount/VAT allocation
        inv_base = {}
        for inv, it in results:
            line_base = float(it.price_before_tax or 0.0) * float(it.quantity or 0.0)
            inv_base[inv.id] = inv_base.get(inv.id, 0.0) + line_base

        for inv, it in results:
            d = (inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '')
            amount = float((it.price_before_tax or 0.0) * (it.quantity or 0.0))
            base_total = float(inv_base.get(inv.id, 0.0) or 0.0)
            inv_disc = float(getattr(inv, 'discount_amount', 0.0) or 0.0)
            inv_vat = float(getattr(inv, 'tax_amount', 0.0) or 0.0)
            if base_total > 0 and (inv_disc > 0 or inv_vat > 0):
                disc = inv_disc * (amount / base_total)
                vat = inv_vat * (amount / base_total)
            else:
                disc = float(it.discount or 0.0)
                base = max(amount - disc, 0.0)
                vat = float(it.tax or 0.0)
            base_after_disc = max(amount - disc, 0.0)
            line_total = base_after_disc + vat
            pm = (inv.payment_method or '').upper()
            rows.append({
                'Date': d,
                'Invoice No.': inv.invoice_number,
                'Item': it.raw_material_name,
                'Qty': float(it.quantity or 0.0),
                'Amount': amount,
                'Discount': round(disc, 2),
                'VAT': round(vat, 2),
                'Total': round(line_total, 2),
                'Payment': pm,
            })
            totals['Amount'] += amount; totals['Discount'] += disc; totals['VAT'] += vat; totals['Total'] += line_total
            payment_totals[pm] = payment_totals.get(pm, 0.0) + line_total
    except Exception:
        pass

    # Settings & meta
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    meta = {
        'title': 'Purchase Invoices — Print',
        'payment_method': payment_method or 'all',
        'branch': branch or 'all',
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': get_saudi_now().strftime('%Y-%m-%d %H:%M')
    }
    columns = ['Date','Invoice No.','Item','Qty','Amount','Discount','VAT','Total','Payment']
    # CSV export
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for r in rows:
                writer.writerow([r.get('Date',''), r.get('Invoice No.',''), r.get('Item',''), r.get('Qty',0.0),
                                 r.get('Amount',0.0), r.get('Discount',0.0), r.get('VAT',0.0), r.get('Total',0.0),
                                 r.get('Payment','')])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="purchase_invoices.csv"'})
        except Exception:
            pass
    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=['Amount','Discount','VAT','Total'],
                           totals_colspan=4, payment_totals=payment_totals)



@bp.route('/reports/print/daily-items-summary', methods=['GET'], endpoint='reports_print_daily_items_summary')
@login_required
def reports_print_daily_items_summary():
    """Print a daily summary of items (by quantity) for a given day.
    By default, summarizes from Order Invoices (pre-payment) so printed orders show up.
    Optional source param: source=orders (default) or source=sales.
    """
    from sqlalchemy import func
    source = (request.args.get('source') or 'orders').strip().lower()
    branch_f = (request.args.get('branch') or '').strip()

    # Determine target date (YYYY-MM-DD) - defaults to today
    date_str = (request.args.get('date') or '').strip()
    from datetime import date as _date, datetime as _dt, time as _time
    try:
        target_date = _date.fromisoformat(date_str) if date_str else _date.today()
    except Exception:
        target_date = _date.today()

    # Compute start/end of day (00:00:00 -> 23:59:59)
    start_dt = _dt.combine(target_date, _time.min)
    end_dt = _dt.combine(target_date, _time.max)

    data = []
    try:
        if source == 'orders':
            from models import OrderInvoice
            # Fetch orders within day window and aggregate from JSON items
            q = OrderInvoice.query.filter(
                OrderInvoice.invoice_date >= start_dt,
                OrderInvoice.invoice_date <= end_dt
            )
            if branch_f:
                q = q.filter(OrderInvoice.branch == branch_f)
            orders = q.limit(5000).all()

            totals_map = {}
            for o in orders:
                try:
                    for it in (o.items or []):
                        name = (it.get('name') if isinstance(it, dict) else None) or '-'
                        qty_val = it.get('qty') if isinstance(it, dict) else 0
                        try:
                            qty = float(qty_val or 0)
                        except Exception:
                            qty = 0.0
                        totals_map[name] = totals_map.get(name, 0.0) + qty
                except Exception:
                    continue
            data = [
                {'Item': k, 'Total Qty': float(v)}
                for k, v in sorted(totals_map.items(), key=lambda x: (-x[1], x[0]))
            ]
        else:
            from models import SalesInvoice, SalesInvoiceItem
            # Sales invoices use date (Date) column; filter by equality if Date only
            q = db.session.query(
                SalesInvoiceItem.product_name.label('item_name'),
                func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label('total_qty')
            ).join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
            q = q.filter(SalesInvoice.date == target_date)
            if branch_f and hasattr(SalesInvoice, 'branch'):
                q = q.filter(SalesInvoice.branch == branch_f)
            if hasattr(SalesInvoice, 'status'):
                q = q.filter(func.lower(SalesInvoice.status) == 'paid')
            q = q.group_by(SalesInvoiceItem.product_name).order_by(func.sum(SalesInvoiceItem.quantity).desc())
            rows = q.all()
            data = [
                {'Item': (r.item_name or '-'), 'Total Qty': float(r.total_qty or 0.0)} for r in rows
            ]
    except Exception:
        data = []

    # Settings & meta
    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    meta_title = f"Daily Items Summary — {target_date.isoformat()} ({'orders' if source=='orders' else 'sales'})"
    columns = ['Item', 'Total Qty']

    return render_template(
        'print_report.html',
        report_title=meta_title,
        settings=settings,
        generated_at=get_saudi_now().strftime('%Y-%m-%d %H:%M'),
        start_date=target_date.isoformat(),
        end_date=target_date.isoformat(),
        payment_method=source,
        branch=(branch_f or 'all'),
        columns=columns,
        data=data,
        totals={},
        totals_columns=[],
        totals_colspan=len(columns)
    )


@bp.route('/reports/print/all-invoices/expenses', methods=['GET'], endpoint='reports_print_all_invoices_expenses')
@login_required
def reports_print_all_invoices_expenses():
    payment_method = (request.args.get('payment_method') or 'all').strip().lower()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    branch = (request.args.get('branch') or 'all').strip().lower()
    fmt = (request.args.get('format') or '').strip().lower()
    rows = []
    totals = {'Amount': 0.0}
    payment_totals = {}
    try:
        q = ExpenseInvoice.query
        if payment_method and payment_method != 'all':
            q = q.filter(func.lower(ExpenseInvoice.payment_method) == payment_method)
        if start_date:
            try:
                q = q.filter(ExpenseInvoice.date >= start_date)
            except Exception:
                pass
        if end_date:
            try:
                q = q.filter(ExpenseInvoice.date <= end_date)
            except Exception:
                pass
        if branch and branch != 'all' and hasattr(ExpenseInvoice, 'branch'):
            q = q.filter(func.lower(ExpenseInvoice.branch) == branch)
        q = q.order_by(ExpenseInvoice.created_at.desc()).limit(2000)
        for exp in q.all():
            d = (exp.date.strftime('%Y-%m-%d') if getattr(exp, 'date', None) else '')
            pm = (exp.payment_method or '').upper()
            # Print per item
            try:
                items = ExpenseInvoiceItem.query.filter_by(invoice_id=exp.id).all()
            except Exception:
                items = []
            for it in items:
                qty = float(getattr(it, 'quantity', 0.0) or 0.0)
                price = float(getattr(it, 'price_before_tax', 0.0) or 0.0)
                tax = float(getattr(it, 'tax', 0.0) or 0.0)
                disc = float(getattr(it, 'discount', 0.0) or 0.0)
                line_total = float(getattr(it, 'total_price', None) or (max(price*qty - disc, 0.0) + tax) or 0.0)
                rows.append({
                    'Date': d,
                    'Expense No.': exp.invoice_number,
                    'Description': getattr(it, 'description', '') or '',
                    'Qty': qty,
                    'Amount': price * qty,
                    'Tax': tax,
                    'Discount': disc,
                    'Line Total': line_total,
                    'Payment': pm,
                })
                totals['Amount'] += (price * qty)
                totals['Tax'] = float(totals.get('Tax', 0.0) or 0.0) + tax
                totals['Discount'] = float(totals.get('Discount', 0.0) or 0.0) + disc
                totals['Line Total'] = float(totals.get('Line Total', 0.0) or 0.0) + line_total
                payment_totals[pm] = payment_totals.get(pm, 0.0) + line_total
    except Exception:
        pass

    try:
        settings = Settings.query.first()
    except Exception:
        settings = None
    meta = {
        'title': _('Expenses') + ' — ' + _('Print'),
        'payment_method': payment_method or 'all',
        'branch': branch or 'all',
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': get_saudi_now().strftime('%Y-%m-%d %H:%M')
    }
    columns = ['Date','Expense No.','Description','Qty','Amount','Tax','Discount','Line Total','Payment']
    totals_columns = ['Amount','Tax','Discount','Line Total']
    totals_colspan = len(columns) - len(totals_columns)
    # CSV export
    if fmt == 'csv':
        try:
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for r in rows:
                writer.writerow([r.get('Date',''), r.get('Expense No.',''), r.get('Description',''), r.get('Qty',0.0),
                                 r.get('Amount',0.0), r.get('Tax',0.0), r.get('Discount',0.0), r.get('Line Total',0.0), r.get('Payment','')])
            from flask import Response
            return Response(output.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': 'attachment; filename="expense_invoices.csv"'})
        except Exception:
            pass

    return render_template('print_report.html', report_title=meta['title'], settings=settings,
                           generated_at=meta['generated_at'], start_date=meta['start_date'], end_date=meta['end_date'],
                           payment_method=meta['payment_method'], branch=meta['branch'],
                           columns=columns, data=rows, totals=totals, totals_columns=totals_columns,
                           totals_colspan=totals_colspan, payment_totals=payment_totals)


# ================= Salaries/Payroll Print Reports =================

@bp.route('/reports/print/payroll', methods=['GET'], endpoint='print_payroll')
@login_required
def print_payroll():
    # Params — معالجة أخطاء لعرض رسالة واضحة للمستخدم
    from datetime import date as _date
    # اختيار شهر واحد: ?month=YYYY-MM ؛ أو فترة: ?month_from=YYYY-MM&month_to=YYYY-MM
    month_param = (request.args.get('month') or '').strip()
    month_from_param = (request.args.get('month_from') or '').strip()
    month_to_param = (request.args.get('month_to') or '').strip()
    if month_param and '-' in month_param:
        try:
            y_from = int(month_param.split('-')[0])
            m_from = int(month_param.split('-')[1])
            if 1 <= m_from <= 12:
                y_to, m_to = y_from, m_from
            else:
                y_from = _date.today().year
                m_from = 1
                y_to = _date.today().year
                m_to = _date.today().month
        except (ValueError, IndexError):
            y_from = _date.today().year
            m_from = 1
            y_to = _date.today().year
            m_to = _date.today().month
    elif month_from_param and month_to_param and '-' in month_from_param and '-' in month_to_param:
        try:
            y_from = int(month_from_param.split('-')[0])
            m_from = int(month_from_param.split('-')[1])
            y_to = int(month_to_param.split('-')[0])
            m_to = int(month_to_param.split('-')[1])
            if not (1 <= m_from <= 12 and 1 <= m_to <= 12):
                raise ValueError('invalid month')
            if (y_from, m_from) > (y_to, m_to):
                y_from, m_from, y_to, m_to = y_to, m_to, y_from, m_from
        except (ValueError, IndexError):
            y_from = _date.today().year
            m_from = 1
            y_to = _date.today().year
            m_to = _date.today().month
    else:
        try:
            y_from = int(request.args.get('year_from') or 0) or _date.today().year
        except Exception:
            y_from = _date.today().year
        try:
            m_from = int(request.args.get('month_from') or 0) or 1
        except Exception:
            m_from = 1
        try:
            y_to = int(request.args.get('year_to') or 0) or _date.today().year
        except Exception:
            y_to = _date.today().year
        try:
            m_to = int(request.args.get('month_to') or 0) or _date.today().month
        except Exception:
            m_to = _date.today().month
    raw_codes = (request.args.get('employee_codes') or '').strip()
    raw_ids = (request.args.get('employee_ids') or '').strip()
    selected_ids = []
    for x in request.args.getlist('employee_ids'):
        try:
            selected_ids.append(int(x))
        except (TypeError, ValueError):
            pass
    if not selected_ids and raw_ids:
        for x in raw_ids.split(','):
            try:
                selected_ids.append(int(x.strip()))
            except (TypeError, ValueError):
                pass
    selected_codes = [c.strip() for c in raw_codes.split(',') if c.strip()] if raw_codes else []

    # Models
    try:
        from models import Employee, EmployeeSalaryDefault, Salary, Payment
    except Exception:
        try:
            from app.models import Employee, EmployeeSalaryDefault, Salary, Payment
        except Exception:
            Employee = None; Salary = None; Payment = None; EmployeeSalaryDefault = None

    if not Employee or not Salary or not Payment:
        flash('Payroll models not available', 'danger')
        return redirect(url_for('main.dashboard'))

    def iter_months(y1, m1, y2, m2):
        y = int(y1); m = int(m1)
        end_key = (int(y2) * 100 + int(m2))
        while (y * 100 + m) <= end_key:
            yield y, m
            if m == 12:
                y += 1; m = 1
            else:
                m += 1

    # قائمة كل الموظفين للفلترة في صفحة الطباعة
    all_employees = [{'id': e.id, 'full_name': e.full_name, 'department': getattr(e, 'department', None) or ''}
                     for e in Employee.query.order_by(Employee.full_name.asc()).all()]
    # Resolve employees: employee_ids (preferred) or employee_codes; empty = all
    emp_q = Employee.query
    if selected_ids:
        try:
            emp_q = emp_q.filter(Employee.id.in_(selected_ids))
        except Exception:
            pass
    elif selected_codes:
        try:
            emp_q = emp_q.filter(Employee.employee_code.in_(selected_codes))
        except Exception:
            pass
    employees = emp_q.order_by(Employee.full_name.asc()).all()

    # Helper: defaults
    def get_defaults(emp_id):
        try:
            d = EmployeeSalaryDefault.query.filter_by(employee_id=emp_id).first()
            if d:
                return float(d.base_salary or 0.0), float(d.allowances or 0.0), float(d.deductions or 0.0)
        except Exception:
            pass
        return 0.0, 0.0, 0.0

    employees_ctx = []
    try:
        grand = {'basic': 0.0, 'allowances': 0.0, 'deductions': 0.0, 'prev_due': 0.0, 'total': 0.0, 'paid': 0.0, 'remaining': 0.0}
        for emp in employees:
            basic_sum = allow_sum = ded_sum = prev_sum = total_sum = paid_sum = 0.0
            months_rows = []
            unpaid_count = 0
            for (yy, mm) in iter_months(y_from, m_from, y_to, m_to):
                s = Salary.query.filter_by(employee_id=emp.id, year=int(yy), month=int(mm)).first()
                if not s:
                    b, a, d = get_defaults(emp.id)
                    ex = ab = inc_val = 0.0
                    prev = 0.0
                    tot = float(b + ex - ab + inc_val + a - d + prev)
                    sal_id = None
                else:
                    b = float(s.basic_salary or 0.0)
                    ex = float(getattr(s, 'extra', 0) or 0)
                    ab = float(getattr(s, 'absence', 0) or 0)
                    inc_val = float(getattr(s, 'incentive', 0) or 0)
                    a = float(s.allowances or 0.0)
                    d = float(s.deductions or 0.0)
                    prev = float(s.previous_salary_due or 0.0)
                    tot = float(s.total_salary or (b + ex - ab + inc_val + a - d + prev))
                    sal_id = int(s.id)
                # Paid for this month
                if sal_id:
                    paid = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                        .filter(Payment.invoice_type == 'salary', Payment.invoice_id == sal_id).scalar() or 0.0)
                else:
                    paid = 0.0
                remaining = max(tot - paid, 0.0)
                status = 'paid' if remaining <= 0.01 and tot > 0 else ('partial' if paid > 0 else 'due')
                if status != 'paid':
                    unpaid_count += 1
                # عرض فقط الأشهر التي بها استحقاق لا يساوي صفر أو مدفوع لا يساوي صفر
                if tot != 0 or paid != 0:
                    months_rows.append({
                        'year': yy, 'month': mm,
                        'basic': b, 'extra': ex, 'absence': ab, 'incentive': inc_val, 'allowances': a, 'deductions': d,
                        'prev_due': prev, 'total': tot, 'paid': paid, 'remaining': remaining, 'status': status
                    })
                    basic_sum += b; allow_sum += a; ded_sum += d; prev_sum += prev; total_sum += tot; paid_sum += paid

            # إظهار الموظف في تفصيل الأشهر فقط إذا كان لديه شهر واحد على الأقل باستحقاق أو مدفوع غير صفر
            if months_rows:
                employees_ctx.append(type('Emp', (), {
                    'name': emp.full_name,
                    'department': getattr(emp, 'department', None) or '',
                    'salaries': months_rows,
                })())

        # جدول واحد للطباعة: صف لكل موظف للشهر النهائي — فقط من لهم استحقاق أو مدفوع غير صفر
        payroll_table_rows = []
        for emp in employees:
            s = Salary.query.filter_by(employee_id=emp.id, year=int(y_to), month=int(m_to)).first()
            if not s:
                b, a, d = get_defaults(emp.id)
                ex = ab = inc_val = 0.0
                tot = max(0.0, b + a - d)
            else:
                b = float(s.basic_salary or 0.0)
                ex = float(getattr(s, 'extra', 0) or 0)
                ab = float(getattr(s, 'absence', 0) or 0)
                inc_val = float(getattr(s, 'incentive', 0) or 0)
                a = float(s.allowances or 0.0)
                d = float(s.deductions or 0.0)
                tot = float(s.total_salary or (b + ex - ab + inc_val + a - d))
            paid_end = 0.0
            if s:
                paid_end = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                    .filter(Payment.invoice_type == 'salary', Payment.invoice_id == s.id).scalar() or 0.0)
            if tot != 0 or paid_end != 0:
                payroll_table_rows.append({
                    'name': emp.full_name,
                    'department': getattr(emp, 'department', None) or '',
                    'basic': b, 'extra': ex, 'absence': ab, 'incentive': inc_val, 'allowances': a, 'deductions': d,
                    'total': tot,
                })

        # ترتيب موحد: حسب القسم ثم الاسم (جميع الموظفين في جدول واحد بدون تقسيم صفحات)
        _dept_order = {'admin': 0, 'hall': 1, 'kitchen': 2}
        def _sort_key(r):
            dept = (r.get('department') or '').strip().lower()
            return (_dept_order.get(dept, 99), (r.get('name') or ''))
        payroll_table_rows.sort(key=_sort_key)

        # إجماليات للقالب الموحد (صف توديع)
        payroll_totals = None
        if payroll_table_rows:
            payroll_totals = {
                'basic': sum(r.get('basic') or 0 for r in payroll_table_rows),
                'extra': sum(r.get('extra') or 0 for r in payroll_table_rows),
                'absence': sum(r.get('absence') or 0 for r in payroll_table_rows),
                'incentive': sum(r.get('incentive') or 0 for r in payroll_table_rows),
                'allowances': sum(r.get('allowances') or 0 for r in payroll_table_rows),
                'deductions': sum(r.get('deductions') or 0 for r in payroll_table_rows),
                'total': sum(r.get('total') or 0 for r in payroll_table_rows),
            }

        period_label = f"من {y_from:04d}-{m_from:02d} إلى {y_to:04d}-{m_to:02d}" if (y_from, m_from) != (y_to, m_to) else f"{y_from:04d}-{m_from:02d}"
        return render_template(
            'print/payroll_statement.html',
            period_label=period_label,
            year=y_to,
            month=m_to,
            year_from=y_from,
            month_from=m_from,
            year_to=y_to,
            month_to=m_to,
            generated_at=get_saudi_now().strftime('%Y-%m-%d %H:%M'),
            employees=employees_ctx,
            payroll_table_rows=payroll_table_rows,
            payroll_totals=payroll_totals,
            all_employees=all_employees,
            selected_employee_ids=selected_ids,
            **_report_header_context(),
        )
    except Exception as e:
        current_app.logger.exception('print_payroll failed')
        return render_template(
            'print/payroll_statement_error.html',
            error_message=str(e),
            **_report_header_context(),
        ), 500


@bp.route('/reports/print/payroll/selected', methods=['POST'], endpoint='print_selected')
@login_required
def print_selected():
    # Accept codes (employee_code) from text field, split by comma
    raw = (request.form.get('employee_ids') or '').strip()
    y_from = request.form.get('year_from') or request.args.get('year_from') or ''
    m_from = request.form.get('month_from') or request.args.get('month_from') or ''
    y_to = request.form.get('year_to') or request.args.get('year_to') or ''
    m_to = request.form.get('month_to') or request.args.get('month_to') or ''
    qs = {
        'year_from': y_from or '',
        'month_from': m_from or '',
        'year_to': y_to or '',
        'month_to': m_to or '',
    }
    if raw:
        qs['employee_codes'] = ','.join([c.strip() for c in raw.split(',') if c.strip()])
    # Redirect to GET printer with params to avoid resubmission issues
    return redirect(url_for('reports.print_payroll', **qs))
