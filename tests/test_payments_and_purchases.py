import os, sys
import json
from datetime import datetime

# Ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest
from app import app, db
from models import User, Meal, SalesInvoice, PurchaseInvoice, Payment, RawMaterial
from flask_bcrypt import Bcrypt


@pytest.fixture()
def mk_client(client):
    with app.app_context():
        u = User.query.filter_by(username='admin').first()
        if not u:
            b = Bcrypt(app)
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        m = Meal.query.filter_by(active=True).first()
        if not m:
            m = Meal(name='Test Meal', name_ar='وجبة اختبار', selling_price=10, total_cost=7, profit_margin_percent=30, active=True, user_id=u.id)
            db.session.add(m); db.session.commit()
        rm = RawMaterial.query.first()
        if not rm:
            rm = RawMaterial(name='Flour', name_ar='دقيق', unit='kg', cost_per_unit=1)
            db.session.add(rm); db.session.commit()
    client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    return client


def test_purchase_and_payment_flow(mk_client):
    c = mk_client

    # Create simple purchase invoice with one valid item
    with app.app_context():
        rm = RawMaterial.query.first()
        rm_id = rm.id
    data = {
        'date': datetime.utcnow().date().isoformat(),
        'supplier_name': 'ACME',
        'payment_method': 'CASH',
        'items-0-raw_material_id': str(rm_id),
        'items-0-quantity': '2',
        'items-0-price_before_tax': '5',
        'items-0-discount': '0',
    }
    r = c.post('/purchases', data=data, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        inv = PurchaseInvoice.query.order_by(PurchaseInvoice.id.desc()).first()
        assert inv is not None
        total = float(inv.total_after_tax_discount or 0)
        # Register partial payment
        pay = {'invoice_id': str(inv.id), 'invoice_type': 'purchase', 'amount': str(total/2), 'method': 'cash'}
        r2 = c.post('/register_payment', data=pay)
        assert r2.status_code == 200
        # Check payment reflected
        paid = db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0)).filter(Payment.invoice_type=='purchase', Payment.invoice_id==inv.id).scalar() or 0
        assert float(paid) >= total/2

    # Ensure payments listing shows updated paid
    r3 = c.get('/payments', follow_redirects=True)
    assert r3.status_code == 200

