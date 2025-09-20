import os, sys
os.environ.setdefault('USE_EVENTLET','0')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import User, Meal
from flask_bcrypt import Bcrypt


def ensure_admin_and_meal():
    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username='admin').first()
        if not u:
            b = Bcrypt(app)
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        m = Meal.query.first()
        if not m:
            # Create a simple meal usable in checkout
            m = Meal(display_name='Demo Meal', category='Demo', selling_price=10.0, active=True)
            db.session.add(m)
            db.session.commit()
        return u, m


def main():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    ensure_admin_and_meal()
    c = app.test_client()

    # Login
    r = c.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    print('LOGIN:', r.status_code)

    # Create two invoices for china_town
    from models import Meal
    with app.app_context():
        meal = Meal.query.first()
        meal_id = meal.id
    payload = {'branch_code': 'china_town', 'table_number': 1, 'items': [{'meal_id': meal_id, 'qty': 2}], 'payment_method': 'CASH'}
    r1 = c.post('/api/sales/checkout', json=payload)
    print('CHECKOUT #1:', r1.status_code, (r1.json or {}))
    inv1 = (r1.json or {}).get('invoice_id')
    payload2 = {'branch_code': 'china_town', 'table_number': 2, 'items': [{'meal_id': meal_id, 'qty': 1}], 'payment_method': 'CASH'}
    r2 = c.post('/api/sales/checkout', json=payload2)
    print('CHECKOUT #2:', r2.status_code, (r2.json or {}))
    inv2 = (r2.json or {}).get('invoice_id')

    # Delete them using supervisor password
    for inv_id in (inv1, inv2):
        if inv_id:
            d = c.post(f'/delete_sales_invoice/{inv_id}', data={'password':'1991'}, follow_redirects=False)
            print(f'DELETE invoice {inv_id}:', d.status_code)

    # Add sections to china_town
    payload_sections = {'sections':[{'name':'صالة A','sort_order':1},{'name':'صالة B','sort_order':2}], 'assignments': []}
    rs = c.post('/api/table-sections/china_town', json=payload_sections)
    print('POST sections:', rs.status_code, (rs.json or {}))
    rg = c.get('/api/table-sections/china_town')
    print('GET sections:', rg.status_code, (rg.json or {}))


if __name__ == '__main__':
    main()

