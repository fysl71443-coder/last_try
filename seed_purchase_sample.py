from app import create_app
from models import db, PurchaseInvoice, PurchaseInvoiceItem, RawMaterial
from datetime import datetime

app = create_app()

with app.app_context():
    # Ensure at least one raw material exists
    rm = RawMaterial.query.first()
    if not rm:
        rm = RawMaterial(name='Rice 5kg', unit='bag', current_stock=0, minimum_stock=0)
        db.session.add(rm)
        db.session.commit()
    # Create a sample purchase invoice
    inv = PurchaseInvoice(
        invoice_number=f'SEED-{int(datetime.utcnow().timestamp())}',
        date=datetime.utcnow().date(),
        supplier_name='Demo Supplier',
        payment_method='CASH',
        total_before_tax=100.00,
        tax_amount=15.00,
        discount_amount=0.00,
        total_after_tax_discount=115.00,
        user_id=1
    )
    db.session.add(inv)
    db.session.flush()

    item = PurchaseInvoiceItem(
        invoice_id=inv.id,
        raw_material_id=rm.id,
        raw_material_name=rm.name,
        quantity=10,
        price_before_tax=10.0,
        tax=15.0,  # total tax amount for invoice or per item depending on model; keep simple
        total_price=100.0
    )
    db.session.add(item)
    db.session.commit()
    print(f'CREATED_INV_ID={inv.id}')
