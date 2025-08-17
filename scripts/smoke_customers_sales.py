import os, sys
os.environ.setdefault('USE_EVENTLET','0')
os.environ.setdefault('PYTHONPATH','.')
sys.path.append(os.getcwd())

from app import app, db
from models import User
from flask_bcrypt import Bcrypt


def ensure_admin():
    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username='admin').first()
        if not u:
            b = Bcrypt(app)
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        return u


def run():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    ensure_admin()
    with app.test_client() as c:
        # login
        r = c.post('/login', data={'username':'admin','password':'admin123','remember':'y'}, follow_redirects=True)
        print('LOGIN_STATUS=', r.status_code)
        # customers list
        r = c.get('/customers', follow_redirects=True)
        print('CUSTOMERS_STATUS=', r.status_code)
        # add a customer
        r = c.post('/customers', data={'name':'Test Cust','phone':'0501112222','discount_percent':'5'}, follow_redirects=True)
        print('CUSTOMERS_ADD_STATUS=', r.status_code)
        # lookup api
        r = c.get('/api/customers/lookup?q=Test')
        print('LOOKUP_STATUS=', r.status_code, 'LEN=', len(r.data))
        # sales tables
        r = c.get('/sales/place_india/tables', follow_redirects=True)
        print('SALES_TABLES_STATUS=', r.status_code)
        # sales table invoice
        r = c.get('/sales/place_india/table/1', follow_redirects=True)
        print('SALES_INVOICE_STATUS=', r.status_code)

if __name__ == '__main__':
    run()

