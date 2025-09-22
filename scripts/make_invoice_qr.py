import os
import sys
from datetime import datetime

import qrcode
import pytz

# Ensure project root on sys.path for `utils` imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.qr import get_zatca_tlv_base64


def main():
    # بيانات تجريبية كما طلبت
    seller = "شركة الاختبار المحدودة"
    vat_no = "300000000000003"

    # وقت/تاريخ الفاتورة بصيغة ISO8601 بتوقيت السعودية
    tz = pytz.timezone("Asia/Riyadh")
    now = datetime.now(tz)

    total_with_vat = 100.00
    vat_amount = 15.00

    # 1) بناء Base64(TLV) وفق ZATCA المرحلة الأولى
    tlv_b64 = get_zatca_tlv_base64(seller, vat_no, now, total_with_vat, vat_amount)

    # طباعة الـ Base64 (هذا هو المحتوى الذي يجب أن يُشفَّر داخل الـ QR)
    print("TLV Base64:")
    print(tlv_b64)

    # 2) إنشاء صورة QR بحيث يكون محتوى الـ QR هو tlv_b64 نفسه (وليس PNG base64)
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(tlv_b64)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    out_path = "invoice_qr.png"
    img.save(out_path)
    print(f"Saved QR image to {out_path}")


if __name__ == "__main__":
    main()

