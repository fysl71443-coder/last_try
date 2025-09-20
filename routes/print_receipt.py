from flask import Blueprint, render_template, current_app, url_for, send_file
from io import BytesIO
import base64
from models import SalesInvoice, SalesInvoiceItem, Settings  # عدّل حسب مشروعك
from utils.qr import generate_zatca_qr_from_invoice
from datetime import datetime
import pytz

bp = Blueprint('receipt', __name__)

@bp.route('/receipt/<int:invoice_id>')
def show_receipt(invoice_id):
    """عرض الفاتورة مع دعم العملة كصورة و QR كود ZATCA"""
    invoice = SalesInvoice.query.get_or_404(invoice_id)
    settings = Settings.query.first()

    # تحديد الفرع
    branch_name = 'China Town' if invoice.branch == 'china_town' else 'Palace India'
    branch = type('Branch', (), {'name': branch_name, 'id': invoice.branch})()

    # currency image (support URL or data URL or binary)
    currency_data_url = None
    if settings and hasattr(settings, 'currency_image') and settings.currency_image:
        try:
            ci = settings.currency_image
            if isinstance(ci, str):
                # If already a URL or data URL, use as-is
                if ci.startswith('http') or ci.startswith('/static') or ci.startswith('data:'):
                    currency_data_url = ci
                else:
                    # Try to open as a relative resource path
                    with current_app.open_resource(ci, 'rb') as f:
                        currency_b = f.read()
                    currency_data_url = 'data:image/png;base64,' + base64.b64encode(currency_b).decode()
            else:
                # Binary content
                currency_data_url = 'data:image/png;base64,' + base64.b64encode(ci).decode()
        except Exception as e:
            current_app.logger.error(f"Error loading currency image: {e}")
            currency_data_url = None

    # ZATCA QR base64
    try:
        zatca_b64 = generate_zatca_qr_from_invoice(invoice, settings, branch)
    except Exception as e:
        current_app.logger.error(f"Error generating ZATCA QR: {e}")
        zatca_b64 = None

    # جلب عناصر الفاتورة
    items = SalesInvoiceItem.query.filter_by(invoice_id=invoice.id).all()

    return render_template('receipt.html',
                         invoice=invoice,
                         settings=settings,
                         branch=branch,
                         items=items,
                         currency_data_url=currency_data_url,
                         zatca_b64=zatca_b64)

@bp.route('/receipt/<int:invoice_id>/pdf')
def receipt_pdf(invoice_id):
    """تحويل الفاتورة إلى PDF"""
    try:
        # محاولة استخدام WeasyPrint
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration

            # الحصول على HTML للفاتورة
            html_response = show_receipt(invoice_id)
            if hasattr(html_response, 'get_data'):
                html_content = html_response.get_data(as_text=True)
            else:
                html_content = str(html_response)

            # إنشاء PDF
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content, base_url=current_app.config.get('APPLICATION_ROOT', '/'))

            # CSS للطباعة
            css = CSS(string='''
                @page { margin: 1cm; size: A4; }
                body { font-family: Arial, sans-serif; font-size: 12px; }
                .receipt { max-width: 100%; margin: 0; }
            ''', font_config=font_config)

            pdf_bytes = html_doc.write_pdf(stylesheets=[css], font_config=font_config)

            return send_file(
                BytesIO(pdf_bytes),
                download_name=f"invoice-{invoice_id}.pdf",
                as_attachment=True,
                mimetype='application/pdf'
            )

        except ImportError:
            # إذا لم تكن WeasyPrint متوفرة، استخدم طريقة بديلة
            current_app.logger.warning("WeasyPrint not available, using HTML response")
            return show_receipt(invoice_id)

    except Exception as e:
        current_app.logger.error(f"Error generating PDF: {e}")
        return f"Error generating PDF: {str(e)}", 500

@bp.route('/receipt/print/<int:invoice_id>')
def print_receipt(invoice_id):
    """طباعة الفاتورة (توجيه للعرض العادي)"""
    return show_receipt(invoice_id)

@bp.route('/receipt/thermal/<int:invoice_id>')
def print_thermal_receipt(invoice_id):
    """طباعة حرارية مبسطة"""
    return show_receipt(invoice_id)

@bp.route('/receipt/preview/<int:invoice_id>')
def preview_receipt(invoice_id):
    """معاينة الفاتورة قبل الطباعة"""
    return show_receipt(invoice_id)
