from flask import Blueprint, render_template, request, send_file, url_for, redirect, flash
from sqlalchemy import func
from datetime import date
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


@bp.route('/', methods=['GET', 'POST'])
def vat_dashboard():
    today = date.today()
    default_year = today.year
    default_quarter = (today.month - 1) // 3 + 1

    try:
        year = int(request.values.get('year', default_year))
    except Exception:
        year = default_year
    try:
        quarter = int(request.values.get('quarter', default_quarter))
    except Exception:
        quarter = default_quarter

    start_date, end_date = quarter_start_end(year, quarter)

    # Sales by branch (before VAT)
    sales_place_india = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
        .filter(SalesInvoice.branch == 'place_india') \
        .filter(SalesInvoice.date.between(start_date, end_date)).scalar()
    sales_china_town = db.session.query(func.coalesce(func.sum(SalesInvoice.total_before_tax), 0)) \
        .filter(SalesInvoice.branch == 'china_town') \
        .filter(SalesInvoice.date.between(start_date, end_date)).scalar()
    sales_total = (sales_place_india or 0) + (sales_china_town or 0)

    # Purchases and Expenses (before VAT)
    purchases_total = db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_before_tax), 0)) \
        .filter(PurchaseInvoice.date.between(start_date, end_date)).scalar()
    expenses_total = db.session.query(func.coalesce(func.sum(ExpenseInvoice.total_before_tax), 0)) \
        .filter(ExpenseInvoice.date.between(start_date, end_date)).scalar()

    s = Settings.query.first()
    VAT_RATE = float(s.vat_rate)/100.0 if s and s.vat_rate is not None else 0.15
    output_vat = float(sales_total or 0) * VAT_RATE
    input_vat = float((purchases_total or 0) + (expenses_total or 0)) * VAT_RATE
    net_vat = output_vat - input_vat

    # company/labels from settings if available
    company_name = s.company_name if s and s.company_name else ''
    tax_number = s.tax_number if s and s.tax_number else ''
    place_lbl = s.place_india_label if s and s.place_india_label else 'Place India'
    china_lbl = s.china_town_label if s and s.china_town_label else 'China Town'
    currency = s.currency if s and s.currency else 'SAR'

    data = {
        'year': year,
        'quarter': quarter,
        'start_date': start_date,
        'end_date': end_date,
        'sales_place_india': float(sales_place_india or 0),
        'sales_china_town': float(sales_china_town or 0),
        'sales_total': float(sales_total or 0),
        'purchases_total': float(purchases_total or 0),
        'expenses_total': float(expenses_total or 0),
        'output_vat': output_vat,
        'input_vat': input_vat,
        'net_vat': net_vat,
        'vat_rate': VAT_RATE, 'company_name': company_name, 'tax_number': tax_number, 'place_lbl': place_lbl, 'china_lbl': china_lbl, 'currency': currency,
    }

    return render_template('vat/vat_dashboard.html', data=data)


@bp.route('/print', methods=['GET'])
def vat_print():
    try:
        year = int(request.args.get('year'))
        quarter = int(request.args.get('quarter'))
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
    output_vat = float(sales_total or 0) * VAT_RATE
    input_vat = float((purchases_total or 0) + (expenses_total or 0)) * VAT_RATE
    net_vat = output_vat - input_vat

    # company/labels from settings if available
    company_name = s.company_name if s and getattr(s, 'company_name', None) else ''
    tax_number = s.tax_number if s and getattr(s, 'tax_number', None) else ''
    place_lbl = s.place_india_label if s and getattr(s, 'place_india_label', None) else 'Place India'
    china_lbl = s.china_town_label if s and getattr(s, 'china_town_label', None) else 'China Town'
    currency = s.currency if s and getattr(s, 'currency', None) else 'SAR'


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

