import os
from datetime import datetime

os.environ.setdefault('USE_EVENTLET', '0')

# Robust import: prefer packaged create_app; fallback to monolith app.py if needed
try:
    from app import create_app, db  # package import
    app = create_app()
except Exception:
    import importlib.util, pathlib, sys
    root = pathlib.Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("monolith_app", str(root / "app.py"))
    monolith = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(monolith)
    app = getattr(monolith, 'app')
    db = getattr(monolith, 'db')

from models import User, Meal, SalesInvoice, SalesInvoiceItem, Payment

# Optional helpers from repo
try:
    from create_user import create_admin_user
except Exception:
    create_admin_user = None

try:
    from create_sample_meals import create_sample_meals_system
except Exception:
    create_sample_meals_system = None


def ensure_admin():
    if create_admin_user:
        create_admin_user()
    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username='admin').first()
        if not u:
            # Fallback minimal admin
            from flask_bcrypt import Bcrypt
            b = Bcrypt(app)
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        return u


def ensure_meal():
    with app.app_context():
        m = Meal.query.first()
        if m:
            return m
        if create_sample_meals_system:
            create_sample_meals_system()
            m = Meal.query.first()
            if m:
                return m
        # Fallback: create a minimal meal if not present
        from models import Meal
        m = Meal(name='Test Meal', name_ar='وجبة اختبار', total_cost=10, profit_margin_percent=30, selling_price=13, active=True, user_id=User.query.filter_by(username='admin').first().id)
        db.session.add(m)
        db.session.commit()
        return m


def login_admin(client):
    return client.post('/login', data={'username':'admin','password':'admin123','remember':'y'}, follow_redirects=True)


def run():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    ensure_admin()
    ensure_meal()

    results = []
    with app.app_context():
        with app.test_client() as c:
            r = login_admin(c)
            assert r.status_code == 200, 'Login failed'
            results.append('Login OK')

            # Create/open POS invoice for China Town table 1
            r = c.get('/pos/china_town/table/1', follow_redirects=True)
            assert r.status_code == 200, 'Open POS china_town failed'
            inv = SalesInvoice.query.filter_by(branch='china_town', table_number=1).order_by(SalesInvoice.id.desc()).first()
            assert inv is not None, 'Invoice not created'
            results.append(f'POS open OK invoice_id={inv.id}')

            # Add item
            m = Meal.query.first()
            r = c.post(f'/pos/invoice/{inv.id}/add', data={'meal_id': m.id, 'qty': '2'}, follow_redirects=True)
            assert r.status_code == 200, 'Add item failed'
            db.session.refresh(inv)
            items = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).all()
            assert items, 'No items after add'
            results.append(f'Add item OK (count={len(items)})')

            # Update quantity
            it = items[0]
            r = c.post(f'/pos/invoice/{inv.id}/update', data={'item_id': it.id, 'qty': '3'}, follow_redirects=True)
            assert r.status_code == 200, 'Update item failed'
            db.session.refresh(inv)
            results.append('Update item OK')

            # Remove item
            r = c.post(f'/pos/invoice/{inv.id}/remove', data={'item_id': it.id}, follow_redirects=True)
            assert r.status_code == 200, 'Remove item failed'
            left = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).count()
            results.append(f'Remove item OK (remaining={left})')

            # Add item again then finalize (pay & print)
            c.post(f'/pos/invoice/{inv.id}/add', data={'meal_id': m.id, 'qty': '1'}, follow_redirects=True)
            r = c.post(f'/pos/invoice/{inv.id}/finalize', data={'action':'pay_and_print','payment_method':'CASH'}, follow_redirects=True)
            assert r.status_code == 200, 'Finalize pay&print failed'
            inv = SalesInvoice.query.get(inv.id)
            assert inv.status == 'paid', f'Expected paid, got {inv.status}'
            results.append('Finalize Pay&Print OK (status=paid)')

            # Create another invoice and delete it
            r = c.get('/pos/china_town/table/2', follow_redirects=True)
            inv2 = SalesInvoice.query.filter_by(branch='china_town', table_number=2).order_by(SalesInvoice.id.desc()).first()
            assert inv2 is not None
            delr = c.post(f'/delete_sales_invoice/{inv2.id}', follow_redirects=True)
            assert delr.status_code == 200, 'Delete sales invoice failed'
            gone = SalesInvoice.query.get(inv2.id)
            assert gone is None, 'Invoice still exists after delete'
            results.append('Delete sales invoice OK')

            # Register partial payment on a fresh unpaid invoice (place_india)
            r = c.get('/pos/place_india/table/1', follow_redirects=True)
            inv3 = SalesInvoice.query.filter_by(branch='place_india', table_number=1).order_by(SalesInvoice.id.desc()).first()
            assert inv3 is not None
            # Ensure unpaid by not finalizing, but add item to have amount
            c.post(f'/pos/invoice/{inv3.id}/add', data={'meal_id': m.id, 'qty': '2'}, follow_redirects=True)
            # Pay 5 via AJAX route
            payr = c.post('/register_payment', data={'invoice_id': inv3.id, 'invoice_type':'sales', 'amount':'5'}, follow_redirects=True)
            assert payr.status_code == 200, 'Register payment failed'
            pexist = Payment.query.filter_by(invoice_id=inv3.id, invoice_type='sales').first()
            assert pexist is not None, 'Payment not recorded'
            results.append('Register payment OK')

            # VAT dashboard and print
            v1 = c.get('/vat')
            assert v1.status_code == 200, 'VAT dashboard failed'
            today = datetime.utcnow().date()
            quarter = (today.month - 1) // 3 + 1
            v2 = c.get(f'/vat/print?year={today.year}&quarter={quarter}', follow_redirects=True)
            assert v2.status_code == 200, 'VAT print failed'
            results.append('VAT dashboard/print OK')

            # Branch sales report HTML + PDF
            bs = c.get(f'/reports/branch_sales?year={today.year}&month={today.month}&branch=china_town')
            assert bs.status_code == 200, 'Branch sales HTML failed'
            bsp = c.get(f'/reports/branch_sales/print?year={today.year}&month={today.month}&branch=china_town')
            assert bsp.status_code == 200, 'Branch sales PDF failed'
            results.append('Branch sales report HTML/PDF OK')

            print('\n'.join(results))


if __name__ == '__main__':
    run()

