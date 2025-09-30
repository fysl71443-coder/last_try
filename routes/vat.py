from flask import Blueprint, render_template, request, send_file, url_for, redirect, flash, Response
from sqlalchemy import func
from datetime import date, datetime
import io

# Import db and models without circular imports
from extensions import db
from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice, Settings

bp = Blueprint('vat', __name__, url_prefix='/vat')


def quarter_start_end(year: int, quarter: int):
    if quarter == 1:
        return date(year, 1, 1), date(year, 3, 31)
    if quarter == 2:
        return date(year, 4, 1), date(year, 6, 30)
    if quarter == 3:
        return date(year, 7, 1), date(year, 9, 30)
    if quarter == 4:
        return date(year, 10, 1), date(year, 12, 31)
    raise ValueError("quarter must be 1..4")


@bp.route('/', methods=['GET'])
def vat_dashboard():
    today = date.today()
    default_year = today.year
    default_quarter = (today.month - 1) // 3 + 1
    period = (request.args.get('period') or 'quarterly').strip().lower()
    branch = (request.args.get('branch') or 'all').strip()

    # Resolve period to start/end
    start_date: date
    end_date: date
    year = request.args.get('year', type=int) or default_year
    quarter = request.args.get('quarter', type=int) or default_quarter
    if period == 'monthly':
        ym = (request.args.get('month') or '').strip()  # 'YYYY-MM'
        if ym and '-' in ym:
            try:
                y, m = ym.split('-'); yy = int(y); mm = int(m)
                if mm == 12:
                    start_date = date(yy, mm, 1)
                    end_date = date(yy, 12, 31)
                else:
                    start_date = date(yy, mm, 1)
                    end_date = date(yy + (1 if mm == 12 else 0), (1 if mm == 12 else mm + 1), 1) - (date(yy, mm, 1) - date(yy, mm, 1).replace(day=0))
            except Exception:
                # Fallback to current month
                start_date = date(today.year, today.month, 1)
                end_date = today
        else:
            start_date = date(today.year, today.month, 1)
            end_date = today
    else:
        # quarterly default
        year = int(year or default_year)
        quarter = int(quarter or default_quarter)
        start_date, end_date = quarter_start_end(year, quarter)

    # Settings
    s = Settings.query.first()
    vat_rate = float(s.vat_rate)/100.0 if s and s.vat_rate is not None else 0.15
    company_name = s.company_name if s and s.company_name else ''
    tax_number = s.tax_number if s and s.tax_number else ''
    currency = s.currency if s and s.currency else 'SAR'

    # Helper to optionally filter branch
    def branch_filter_sales(q):
        if branch and branch != 'all' and hasattr(SalesInvoice, 'branch'):
            return q.filter(SalesInvoice.branch == branch)
        return q
    def branch_filter_purchases(q):
        return q  # purchases/expenses not per-branch in current schema

    # Sales breakdown (bases)
    sales_standard_base = float(branch_filter_sales(db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0))
        .filter(SalesInvoice.date.between(start_date, end_date))
        .filter((SalesInvoice.tax_amount > 0))).scalar() or 0.0)
    sales_zero_base = float(branch_filter_sales(db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0))
        .filter(SalesInvoice.date.between(start_date, end_date))
        .filter((SalesInvoice.tax_amount == 0))).scalar() or 0.0)
    # Exempt/Exports not tracked separately in schema → default to 0
    sales_exempt_base = 0.0
    sales_exports_base = 0.0

    # Purchases breakdown (bases)
    purchases_deductible_base = float(branch_filter_purchases(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax), 0))
        .filter(PurchaseInvoice.date.between(start_date, end_date))
        .filter((PurchaseInvoice.tax_amount > 0))).scalar() or 0.0)
    purchases_non_deductible_base = float(branch_filter_purchases(db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax), 0))
        .filter(PurchaseInvoice.date.between(start_date, end_date))
        .filter((PurchaseInvoice.tax_amount == 0))).scalar() or 0.0)

    # Expenses breakdown (include into purchases buckets)
    expenses_deductible_base = float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0))
        .filter(ExpenseInvoice.date.between(start_date, end_date))
        .filter((ExpenseInvoice.tax_amount > 0)).scalar() or 0.0)
    expenses_non_deductible_base = float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0))
        .filter(ExpenseInvoice.date.between(start_date, end_date))
        .filter((ExpenseInvoice.tax_amount == 0)).scalar() or 0.0)

    purchases_deductible_base += expenses_deductible_base
    purchases_non_deductible_base += expenses_non_deductible_base

    # VAT amounts from invoices
    output_vat = float(branch_filter_sales(db.session.query(func.coalesce(func.sum(SalesInvoice.tax_amount), 0))
        .filter(SalesInvoice.date.between(start_date, end_date)).scalar() or 0.0))
    input_vat = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.tax_amount), 0)).filter(PurchaseInvoice.date.between(start_date, end_date)).scalar() or 0.0) \
               + float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.tax_amount), 0)).filter(ExpenseInvoice.date.between(start_date, end_date)).scalar() or 0.0)
    net_vat = output_vat - input_vat

    data = {
        'period': period,
        'year': year,
        'quarter': quarter,
        'start_date': start_date,
        'end_date': end_date,
        'branch': branch,
        'company_name': company_name,
        'tax_number': tax_number,
        'currency': currency,
        'sales_standard_base': sales_standard_base,
        'sales_zero_base': sales_zero_base,
        'sales_exempt_base': sales_exempt_base,
        'sales_exports_base': sales_exports_base,
        'purchases_deductible_base': purchases_deductible_base,
        'purchases_non_deductible_base': purchases_non_deductible_base,
        'output_vat': output_vat,
        'input_vat': input_vat,
        'net_vat': net_vat,
        'vat_rate': vat_rate,
    }

    return render_template('vat/vat_dashboard.html', data=data)


@bp.route('/print', methods=['GET'])
def vat_print():
    # Support quarterly, monthly, or explicit date range
    period = (request.args.get('period') or 'quarterly').strip().lower()
    branch = (request.args.get('branch') or 'all').strip()
    year = request.args.get('year', type=int)
    quarter = request.args.get('quarter', type=int)
    fmt = (request.args.get('format') or '').strip().lower()

    if period == 'monthly':
        ym = request.args.get('month')
        if not ym:
            flash("حدد الشهر للطباعة", "danger")
            return redirect(url_for('vat.vat_dashboard'))
        try:
            y, m = ym.split('-'); yy = int(y); mm = int(m)
            start_date = date(yy, mm, 1)
            if mm == 12:
                end_date = date(yy, 12, 31)
            else:
                end_date = date(yy + (1 if mm == 12 else 0), (1 if mm == 12 else mm + 1), 1) - (date(yy, mm, 1) - date(yy, mm, 1).replace(day=0))
        except Exception:
            flash("صيغة الشهر غير صحيحة", "danger")
            return redirect(url_for('vat.vat_dashboard'))
    else:
        try:
            year = int(year or date.today().year)
            quarter = int(quarter or ((date.today().month - 1)//3 + 1))
        except Exception:
            flash("حدد السنة والربع للطباعة", "danger")
            return redirect(url_for('vat.vat_dashboard'))
        start_date, end_date = quarter_start_end(year, quarter)

    sales_place_india = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
        .filter(SalesInvoice.branch == 'place_india') \
        .filter(SalesInvoice.date.between(start_date, end_date)).scalar()
    sales_china_town = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
        .filter(SalesInvoice.branch == 'china_town') \
        .filter(SalesInvoice.date.between(start_date, end_date)).scalar()
    sales_total = (sales_place_india or 0) + (sales_china_town or 0)

    purchases_total = db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax), 0)) \
        .filter(PurchaseInvoice.date.between(start_date, end_date)).scalar()
    expenses_total = db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0)) \
        .filter(ExpenseInvoice.date.between(start_date, end_date)).scalar()

    s = Settings.query.first()
    VAT_RATE = float(s.vat_rate)/100.0 if s and s.vat_rate is not None else 0.15
    # Prefer summing invoice tax amounts
    output_vat = float(db.session.query(func.coalesce(func.sum(SalesInvoice.tax_amount), 0))
        .filter(SalesInvoice.date.between(start_date, end_date)).scalar() or 0.0)
    input_vat = float(db.session.query(func.coalesce(func.sum(PurchaseInvoice.tax_amount), 0))
        .filter(PurchaseInvoice.date.between(start_date, end_date)).scalar() or 0.0) + \
               float(db.session.query(func.coalesce(func.sum(ExpenseInvoice.tax_amount), 0))
        .filter(ExpenseInvoice.date.between(start_date, end_date)).scalar() or 0.0)
    net_vat = output_vat - input_vat

    # company/labels from settings if available
    company_name = s.company_name if s and getattr(s, 'company_name', None) else ''
    tax_number = s.tax_number if s and getattr(s, 'tax_number', None) else ''
    place_lbl = s.place_india_label if s and getattr(s, 'place_india_label', None) else 'Place India'
    china_lbl = s.china_town_label if s and getattr(s, 'china_town_label', None) else 'China Town'
    currency = s.currency if s and getattr(s, 'currency', None) else 'SAR'


    # CSV export (Excel-compatible)
    if fmt == 'csv' or fmt == 'excel':
        try:
            import io, csv
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(['Period', 'Start', 'End'])
            w.writerow([period, start_date.isoformat(), end_date.isoformat()])
            w.writerow([])
            w.writerow(['Metric','Amount'])
            w.writerow(['Sales (Net Base)', float(sales_total or 0)])
            w.writerow(['Purchases (Before VAT)', float(purchases_total or 0)])
            w.writerow(['Expenses (Before VAT)', float(expenses_total or 0)])
            w.writerow(['Output VAT', float(output_vat or 0)])
            w.writerow(['Input VAT', float(input_vat or 0)])
            w.writerow(['Net VAT', float(net_vat or 0)])
            return Response(out.getvalue(), mimetype='text/csv; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="vat_{period}_{start_date}_{end_date}.csv"'})
        except Exception:
            pass

    # Try to generate PDF with reportlab; fallback to HTML if not installed
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        # Fallback: render printable HTML
        return render_template('vat/vat_print_fallback.html',
                               year=year, quarter=quarter, start_date=start_date, end_date=end_date,
                               sales_place_india=float(sales_place_india or 0),
                               sales_china_town=float(sales_china_town or 0),
                               sales_total=float(sales_total or 0),
                               purchases_total=float(purchases_total or 0),
                               expenses_total=float(expenses_total or 0),
                               output_vat=output_vat, input_vat=input_vat, net_vat=net_vat,
                               vat_rate=VAT_RATE,
                               company_name=company_name, tax_number=tax_number,
                               place_lbl=place_lbl, china_lbl=china_lbl, currency=currency)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    # Helpers: register Arabic-capable font and shape Arabic text if libs exist
    def register_ar_font():
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import os as _os
            candidates = [
                r"C:\\Windows\\Fonts\\trado.ttf",  # Traditional Arabic (Windows)
                r"C:\\Windows\\Fonts\\arial.ttf",
                r"C:\\Windows\\Fonts\\Tahoma.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
            ]
            for fp in candidates:
                if _os.path.exists(fp):
                    pdfmetrics.registerFont(TTFont('Arabic', fp))
                    return 'Arabic'
        except Exception:
            pass
        return None

    def shape_ar(text:str)->str:
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text

    # Header with company name and tax number
    ar_font = register_ar_font()
    if ar_font:
        p.setFont(ar_font, 14)
        p.drawString(50, h - 60, shape_ar(company_name or "Company"))
        p.setFont(ar_font, 10)
        if tax_number:
            p.drawString(50, h - 75, shape_ar(f"الرقم الضريبي: {tax_number}"))
        p.drawString(50, h - 95, shape_ar("إقرار ضريبة القيمة المضافة - VAT Return"))
        p.drawString(50, h - 110, shape_ar(f"السنة: {year}    الربع: {quarter}"))
        p.drawString(50, h - 125, shape_ar(f"الفترة: {start_date.isoformat()} إلى {end_date.isoformat()}"))
        # Footer signature area
        p.drawString(50, 60, shape_ar("اسم الشركة: ") + shape_ar(company_name or ""))
        if tax_number:
            p.drawString(50, 45, shape_ar("الرقم الضريبي: ") + shape_ar(str(tax_number)))
    else:
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, h - 60, (company_name or "Company"))
        p.setFont("Helvetica", 10)
        if tax_number:
            p.drawString(50, h - 75, f"الرقم الضريبي: {tax_number}")
        p.drawString(50, h - 95, "إقرار ضريبة القيمة المضافة - VAT Return")
        p.drawString(50, h - 110, f"السنة: {year}    الربع: {quarter}")
        p.drawString(50, h - 125, f"الفترة: {start_date.isoformat()} إلى {end_date.isoformat()}")
        # Footer signature area
        p.drawString(50, 60, "اسم الشركة: " + (company_name or ""))
        if tax_number:
            p.drawString(50, 45, "الرقم الضريبي: " + str(tax_number))

    y = h - 140
    if 'ar_font' in locals() and ar_font:
        p.setFont(ar_font, 11)
        p.drawString(50, y, shape_ar("البند"))
        p.drawString(300, y, shape_ar("Place India"))
        p.drawString(390, y, shape_ar("China Town"))
        p.drawString(480, y, shape_ar("الإجمالي"))
        y -= 18
        p.setFont(ar_font, 10)
    else:
        p.setFont("Helvetica-Bold", 11)
        p.drawString(50, y, "البند")
        p.drawString(300, y, "Place India")
        p.drawString(390, y, "China Town")
        p.drawString(480, y, "الإجمالي")
        y -= 18
        p.setFont("Helvetica", 10)

    # Sales before VAT
    if 'ar_font' in locals() and ar_font:
        p.drawString(50, y, shape_ar("إجمالي المبيعات قبل الضريبة"))
    else:
        p.drawString(50, y, "إجمالي المبيعات قبل الضريبة")
    p.drawRightString(360, y, f"{float(sales_place_india or 0):,.2f}")
    p.drawRightString(450, y, f"{float(sales_china_town or 0):,.2f}")
    p.drawRightString(540, y, f"{float(sales_total or 0):,.2f}")
    y -= 16

    # Purchases and Expenses
    if 'ar_font' in locals() and ar_font:
        p.drawString(50, y, shape_ar("إجمالي المشتريات قبل الضريبة"))
    else:
        p.drawString(50, y, "إجمالي المشتريات قبل الضريبة")
    p.drawRightString(540, y, f"{float(purchases_total or 0):,.2f}")
    y -= 16

    if 'ar_font' in locals() and ar_font:
        p.drawString(50, y, shape_ar("إجمالي المصروفات قبل الضريبة"))
    else:
        p.drawString(50, y, "إجمالي المصروفات قبل الضريبة")
    p.drawRightString(540, y, f"{float(expenses_total or 0):,.2f}")
    y -= 24

    # VAT numbers
    if 'ar_font' in locals() and ar_font:
        p.setFont(ar_font, 11)
        p.drawString(50, y, shape_ar("الإجمالي الضريبي"))
        y -= 16
        p.setFont(ar_font, 10)
        p.drawString(50, y, shape_ar(f"Output VAT @{int(VAT_RATE*100)}%"))
        p.drawRightString(540, y, f"{output_vat:,.2f}")
        y -= 16
        p.drawString(50, y, shape_ar("Input VAT"))
        p.drawRightString(540, y, f"{input_vat:,.2f}")
        y -= 16
        p.drawString(50, y, shape_ar("Net VAT"))
        p.drawRightString(540, y, f"{net_vat:,.2f}")
    else:
        p.setFont("Helvetica-Bold", 11)
        p.drawString(50, y, "الإجمالي الضريبي")
        y -= 16
        p.setFont("Helvetica", 10)
        p.drawString(50, y, f"Output VAT @{int(VAT_RATE*100)}%")
        p.drawRightString(540, y, f"{output_vat:,.2f}")
        y -= 16
        p.drawString(50, y, "Input VAT")
        p.drawRightString(540, y, f"{input_vat:,.2f}")
        y -= 16
        p.drawString(50, y, "Net VAT")
        p.drawRightString(540, y, f"{net_vat:,.2f}")
    y -= 30

    p.drawString(50, y, "اسم الشركة: ____________________________")
    p.drawString(50, y - 18, "الرقم الضريبي: __________________________")
    p.drawString(50, y - 36, "توقيع: ___________________________")
    p.drawString(350, y - 36, f"تاريخ: {date.today().isoformat()}")

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=False,
                     download_name=f"VAT_Return_Q{quarter}_{year}.pdf",
                     mimetype='application/pdf')

