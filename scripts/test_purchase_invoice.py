from app import create_app
from extensions import db
from models import RawMaterial, PurchaseInvoice

def main():
    app = create_app()
    try:
        app.config['WTF_CSRF_ENABLED'] = False
    except Exception:
        pass
    with app.app_context():
        client = app.test_client()
        # Ensure at least one raw material exists
        rm = RawMaterial.query.first()
        if not rm:
            rm = RawMaterial(name='Test Material', name_ar='مادة اختبار', unit='kg', cost_per_unit=10)
            db.session.add(rm); db.session.commit()
        # Prepare form data
        data = {
            'date': '2025-12-01',
            'payment_method': 'cash',
            'invoice_type': 'VAT',
            'status': 'paid',
            'items-0-raw_material_id': str(rm.id),
            'items-0-quantity': '2.5',
            'items-0-price_before_tax': '12.50',
        }
        resp = client.post('/purchases', data=data, follow_redirects=True)
        print('POST /purchases =>', resp.status_code)
        # Inspect DB to confirm one record created
        inv = PurchaseInvoice.query.order_by(PurchaseInvoice.id.desc()).first()
        if inv:
            print('Created purchase invoice:', inv.invoice_number, inv.total_after_tax_discount)
        else:
            print('No purchase invoice found')

if __name__ == '__main__':
    main()
