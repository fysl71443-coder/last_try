import os, sys, json
sys.path.append(os.getcwd())
from app import app, db
from models import User, Customer, Meal
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import generate_csrf


def ensure_data():
    with app.app_context():
        db.create_all()
        b = Bcrypt(app)
        u = User.query.filter_by(username='admin').first()
        if not u:
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        c = Customer.query.filter_by(name='POS Customer').first()
        if not c:
            db.session.add(Customer(name='POS Customer', phone='0501234567', discount_percent=5.0, active=True))
            db.session.commit()
        m = Meal.query.first()
        if not m:
            m = Meal(display_name='Burger', category='Fast Food', selling_price=10.0, active=True)
            db.session.add(m)
            db.session.commit()
        return m.id


def run():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = True
    meal_id = ensure_data()
    with app.test_client() as c:
        # fetch login page to get CSRF token
        r = c.get('/login')
        import re
        m = re.search(r'name=\"csrf_token\" value=\"([^\"]+)\"', r.data.decode('utf-8','ignore'))
        token = m.group(1) if m else ''
        # login with CSRF
        r = c.post('/login', data={'username':'admin','password':'admin123','csrf_token': token}, follow_redirects=True)
        print('LOGIN', r.status_code)
        # customers
        r = c.get('/customers', follow_redirects=True)
        print('CUSTOMERS', r.status_code)
        # lookup
        r = c.get('/api/customers/lookup?q=POS')
        print('LOOKUP', r.status_code, len(r.data))
        # invoice page
        r = c.get('/sales/place_india/table/1', follow_redirects=True)
        print('INVOICE', r.status_code)
        # checkout
        with app.app_context():
            token = generate_csrf()
        headers = {'Content-Type':'application/json', 'X-CSRFToken': token}
        payload = {'branch_code':'place_india','table_no':1,'items':[{'meal_id': meal_id,'qty':2}], 'customer_name':'POS Customer','customer_phone':'0501234567','discount_pct':5.0,'tax_pct':15.0,'payment_method':'CASH'}
        r = c.post('/api/sales/checkout', data=json.dumps(payload), headers=headers)
        print('CHECKOUT', r.status_code, r.data[:120])

if __name__ == '__main__':
    run()

