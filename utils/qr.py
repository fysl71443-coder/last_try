"""
توليد كود QR متوافق مع ZATCA (TLV + base64 PNG)
ZATCA QR Code Generation for Saudi Arabia Tax Authority
"""
import qrcode
from io import BytesIO
import base64
from datetime import datetime
import pytz

# TLV helpers
def _tlv(tag: int, value: bytes) -> bytes:
    """إنشاء TLV (Tag-Length-Value) للبيانات"""
    return bytes([tag, len(value)]) + value

def generate_zatca_tlv(seller_name: str, vat_number: str, time: datetime, total_amount: float, vat_amount: float) -> bytes:
    """إنشاء TLV data للـ ZATCA QR code"""
    # جميع القيم يجب تحويلها لبايت
    parts = []
    parts.append(_tlv(1, seller_name.encode('utf-8')))
    parts.append(_tlv(2, vat_number.encode('utf-8')))
    # التأكد من استخدام ISO8601 بدون أجزاء الميكروثانية
    parts.append(_tlv(3, time.isoformat(timespec='seconds').encode('utf-8')))
    parts.append(_tlv(4, f"{total_amount:.2f}".encode('utf-8')))
    parts.append(_tlv(5, f"{vat_amount:.2f}".encode('utf-8')))
    return b''.join(parts)

def get_zatca_tlv_base64(seller_name: str, vat_number: str, time: datetime, total_amount: float, vat_amount: float) -> str:
    """إنشاء Base64 لمحتوى TLV حسب مواصفات ZATCA (لا يُرجِع صورة)."""
    tlv = generate_zatca_tlv(seller_name, vat_number, time, total_amount, vat_amount)
    return base64.b64encode(tlv).decode('ascii')

def generate_zatca_qr_base64(seller_name: str, vat_number: str, time: datetime, total_amount: float, vat_amount: float) -> str:
    """إنشاء صورة QR (PNG) حيث المحتوى هو Base64(TLV) وفق ZATCA، وإرجاع الصورة كـ base64."""
    try:
        # مواصفات ZATCA: محتوى الـ QR يجب أن يكون Base64 لسلسلة TLV
        tlv_b64 = get_zatca_tlv_base64(seller_name, vat_number, time, total_amount, vat_amount)
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2
        )
        qr.add_data(tlv_b64)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buff = BytesIO()
        img.save(buff, format='PNG')
        return base64.b64encode(buff.getvalue()).decode('ascii')
    except Exception as e:
        print(f"Error generating ZATCA QR code: {e}")
        # إرجاع QR code بسيط في حالة الخطأ
        return generate_simple_qr_base64(f"Invoice: {total_amount:.2f} SAR")

def generate_zatca_qr_from_invoice(invoice, settings=None, branch=None) -> str:
    """إنشاء QR code من بيانات الفاتورة مباشرة"""
    try:
        # استخراج البيانات من الفاتورة
        seller_name = getattr(settings, 'company_name', 'Restaurant') if settings else 'Restaurant'
        vat_number = getattr(settings, 'tax_number', '123456789012345') if settings else '123456789012345'

        # استخدام توقيت الفاتورة أو الحالي
        if hasattr(invoice, 'created_at') and invoice.created_at:
            invoice_time = invoice.created_at
            # تحويل للتوقيت السعودي إذا لم يكن محدد
            if invoice_time.tzinfo is None:
                tz = pytz.timezone('Asia/Riyadh')
                invoice_time = tz.localize(invoice_time)
        else:
            tz = pytz.timezone('Asia/Riyadh')
            invoice_time = datetime.now(tz)

        # حساب المبالغ
        total_amount = float(getattr(invoice, 'total_after_tax_discount', 0) or
                           getattr(invoice, 'total', 0) or 0)
        vat_amount = float(getattr(invoice, 'tax_amount', 0) or
                          getattr(invoice, 'vat_amount', 0) or 0)

        return generate_zatca_qr_base64(seller_name, vat_number, invoice_time, total_amount, vat_amount)

    except Exception as e:
        print(f"Error generating ZATCA QR from invoice: {e}")
        return generate_simple_qr_base64(f"Invoice: {getattr(invoice, 'invoice_number', 'N/A')}")

def generate_simple_qr_base64(text: str) -> str:
    """إنشاء QR code بسيط للنص"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2
        )
        qr.add_data(text)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buff = BytesIO()
        img.save(buff, format='PNG')
        b64 = base64.b64encode(buff.getvalue()).decode('ascii')

        return b64

    except Exception as e:
        print(f"Error generating simple QR code: {e}")
        return ""
