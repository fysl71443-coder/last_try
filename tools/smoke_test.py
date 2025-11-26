import os
import sys
import json
from contextlib import contextmanager

# Ensure test database (in-memory) and testing mode
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.setdefault('SECRET_KEY', 'dev')

# Ensure repo root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db
from app.models import User
from models import (
    SalesInvoice, SalesInvoiceItem,
    PurchaseInvoice, PurchaseInvoiceItem,
    ExpenseInvoice, ExpenseInvoiceItem,
)

@contextmanager
def app_ctx():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
        yield app


def ensure_admin():
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(username='admin')
        u.set_password('admin123')
        db.session.add(u)
        db.session.commit()
    return u


def assert_close(a, b, eps=1e-2, msg=''):
    if abs(float(a) - float(b)) > eps:
        raise AssertionError(msg or f"Not close: {a} vs {b}")


def test_sales_flow(app):
    client = app.test_client()
    # 1) Login
    r = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert r.status_code == 200, f"Login failed: {r.status_code}"

    # 2) Direct checkout (CASH)
    payload_cash = {
        'branch_code': 'china_town',
        'table_number': 1,
        'payment_method': 'CASH',
        'tax_pct': 15,
        'discount_pct': 12,
        'items': [
            {'name': 'Btr dal / بتردال', 'price': 26.96, 'qty': 4},
            {'name': 'Fried Rice', 'price': 25.0, 'qty': 1},
        ],
    }
    r = client.post('/api/sales/checkout', data=json.dumps(payload_cash), content_type='application/json')
    assert r.status_code == 200, f"checkout status {r.status_code} body={r.data[:200]}"
    co = r.get_json()
    assert co.get('ok') is True
    inv_no = co['invoice_id']
    total_amount = float(co['total_amount'])

    # 3) Print receipt page contains QR
    r = client.get(co['print_url'])
    assert r.status_code == 200
    assert b'data:image/png;base64' in r.data, 'QR not found in receipt'

    # 4) Confirm print
    r = client.post('/api/invoice/confirm-print', data=json.dumps({'invoice_id': inv_no, 'total_amount': total_amount}), content_type='application/json')
    assert r.status_code == 200, f"confirm-print status {r.status_code} body={r.data[:200]}"

    # 5) Another checkout (CARD) to test different payment method
    payload_card = {
        'branch_code': 'china_town',
        'table_number': 2,
        'payment_method': 'CARD',
        'tax_pct': 15,
        'discount_pct': 0,
        'items': [
            {'name': 'Fried Rice', 'price': 25.0, 'qty': 2},
        ],
    }
    r = client.post('/api/sales/checkout', data=json.dumps(payload_card), content_type='application/json')
    assert r.status_code == 200
    co2 = r.get_json()
    inv2 = co2['invoice_id']
    tot2 = float(co2['total_amount'])
    r = client.post('/api/invoice/confirm-print', data=json.dumps({'invoice_id': inv2, 'total_amount': tot2}), content_type='application/json')
    assert r.status_code == 200

    # 6) All invoices API must include invoices and obey invariants
    r = client.get('/api/all-invoices')
    assert r.status_code == 200
    data = r.get_json()
    inv_numbers = [row.get('invoice_number') for row in data.get('invoices', [])]
    assert inv_no in inv_numbers and inv2 in inv_numbers
    for row in data.get('invoices', []):
        amount = float(row['amount'])
        discount = float(row['discount'])
        vat = float(row['vat'])
        total = float(row['total'])
        assert_close(total, max(amount - discount, 0.0) + vat, msg=f"Row total mismatch for {row.get('invoice_number')}")

    # 7) Sales print reports load
    r = client.get('/reports/print/all-invoices/sales')
    assert r.status_code == 200


def test_purchase_report_alloc(app):
    # Seed one purchase invoice directly, then verify report math
    inv = PurchaseInvoice(
        invoice_number='PINV-TEST-1',
        payment_method='CASH',
        total_before_tax=1000.00,
        tax_amount=150.00,
        discount_amount=120.00,
        total_after_tax_discount=1030.00,
        user_id=1,
    )
    db.session.add(inv)
    db.session.flush()
    items = [
        PurchaseInvoiceItem(invoice_id=inv.id, raw_material_id=1, raw_material_name='Rice', quantity=10, price_before_tax=50.00, tax=0, discount=0, total_price=0),
        PurchaseInvoiceItem(invoice_id=inv.id, raw_material_id=2, raw_material_name='Dal', quantity=5, price_before_tax=100.00, tax=0, discount=0, total_price=0),
    ]
    for it in items:
        db.session.add(it)
    db.session.commit()

    client = app.test_client()
    client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    r = client.get('/api/reports/all-purchases')
    assert r.status_code == 200
    data = r.get_json()
    overall = data.get('overall_totals') or {}
    amount = float(overall.get('amount') or 0)
    discount = float(overall.get('discount') or 0)
    vat = float(overall.get('vat') or 0)
    total = float(overall.get('total') or 0)
    assert_close(total, max(amount - discount, 0.0) + vat, msg='Purchases overall totals mismatch')

    # Purchases print report loads
    r = client.get('/reports/print/all-invoices/purchases')
    assert r.status_code == 200


def test_expenses_and_vat_pages(app):
    # Seed an expense invoice and verify API and print pages
    exp = ExpenseInvoice(
        invoice_number='EXP-TEST-1',
        payment_method='CASH',
        total_before_tax=200.00,
        tax_amount=30.00,
        discount_amount=0.00,
        total_after_tax_discount=230.00,
        user_id=1,
    )
    db.session.add(exp)
    db.session.flush()
    db.session.add(ExpenseInvoiceItem(invoice_id=exp.id, description='Cleaning', quantity=1, price_before_tax=200.00, tax=0, discount=0, total_price=230.00))
    db.session.commit()

    client = app.test_client()
    client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

    r = client.get('/api/all-expenses')
    assert r.status_code == 200

    # VAT pages (render only)
    r = client.get('/vat/')
    assert r.status_code == 200
    r = client.get('/vat/print')
    assert r.status_code == 200

def test_payments_page_groupings(app):
    client = app.test_client()
    client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

    # Seed sample purchase invoice for a supplier
    inv = PurchaseInvoice(
        invoice_number='PINV-GROUP-1',
        payment_method='BANK',
        total_before_tax=500.00,
        tax_amount=75.00,
        discount_amount=0.00,
        total_after_tax_discount=575.00,
        user_id=1,
        supplier_name='Supplier A',
    )
    db.session.add(inv)
    db.session.flush()
    db.session.add(PurchaseInvoiceItem(invoice_id=inv.id, raw_material_id=1, raw_material_name='Rice', quantity=5, price_before_tax=50.00, tax=0, discount=0, total_price=0))
    # Partial payment
    from models import Payment as Pay
    db.session.add(Pay(invoice_id=inv.id, invoice_type='purchase', amount_paid=200.00, payment_method='BANK'))
    db.session.commit()

    # Seed sales invoice for keeta
    s_inv = SalesInvoice(
        invoice_number='SINV-GROUP-1',
        payment_method='CASH',
        branch='china_town',
        total_before_tax=300.00,
        tax_amount=45.00,
        discount_amount=0.00,
        total_after_tax_discount=345.00,
        user_id=1,
        customer_name='Keeta Platform',
    )
    db.session.add(s_inv)
    db.session.flush()
    db.session.add(SalesInvoiceItem(invoice_id=s_inv.id, product_name='Fried Rice', quantity=2, price_before_tax=50.00, tax=0, discount=0, total_price=0))
    db.session.add(Pay(invoice_id=s_inv.id, invoice_type='sales', amount_paid=100.00, payment_method='CASH'))
    db.session.commit()

    r = client.get('/payments')
    assert r.status_code == 200
    body = r.data.decode('utf-8')
    assert 'Suppliers (Creditors)' in body or 'الموردون' in body
    assert 'Sales Debtors' in body or 'مدينون من المبيعات' in body


def test_users_permissions(app):
    client = app.test_client()
    client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

    # Create user
    r = client.post('/api/users', data=json.dumps({'username': 'tester1', 'password': 'p@ss', 'active': True}), content_type='application/json')
    assert r.status_code == 200
    res = r.get_json()
    assert res.get('ok')
    uid = res['id']

    # Set permissions for china_town
    payload = {
        'branch_scope': 'china_town',
        'items': [
            {'screen_key': 'sales', 'view': True, 'add': True, 'edit': False, 'delete': False, 'print': True},
            {'screen_key': 'reports', 'view': True, 'add': False, 'edit': False, 'delete': False, 'print': True},
        ],
    }
    r = client.post(f'/api/users/{uid}/permissions', data=json.dumps(payload), content_type='application/json')
    assert r.status_code == 200

    # Get permissions and verify
    r = client.get(f'/api/users/{uid}/permissions?branch_scope=china_town')
    assert r.status_code == 200
    items = r.get_json().get('items') or []
    sales_perm = next((i for i in items if i['screen_key'] == 'sales'), None)
    assert sales_perm and sales_perm['view'] and sales_perm['add'] and sales_perm['print']

    # Deactivate user
    r = client.patch(f'/api/users/{uid}', data=json.dumps({'active': False}), content_type='application/json')
    assert r.status_code == 200

    # Delete user
    r = client.delete('/api/users', data=json.dumps({'ids': [uid]}), content_type='application/json')
    assert r.status_code == 200


def main():
    with app_ctx() as app:
        ensure_admin()
        # Clean possible leftovers for deterministic results
        db.session.query(SalesInvoiceItem).delete()
        db.session.query(SalesInvoice).delete()
        db.session.commit()
        # Run tests
        test_sales_flow(app)
        test_purchase_report_alloc(app)
        test_expenses_and_vat_pages(app)
        test_users_permissions(app)
        test_payments_page_groupings(app)
    print('SMOKE_OK')


if __name__ == '__main__':
    main()

