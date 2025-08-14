import os
os.environ.setdefault('USE_EVENTLET', '0')

from datetime import datetime
from app import app, db
from models import User, Meal, RawMaterial, Employee, SalesInvoice
from flask_bcrypt import Bcrypt


def ensure_admin_client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username='admin').first()
        if not u:
            b = Bcrypt(app)
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        # ensure some base data
        m = Meal.query.first()
        if not m:
            m = Meal(name='Meal X', name_ar='وجبة X', selling_price=10, total_cost=7, profit_margin_percent=30, active=True, user_id=u.id)
            db.session.add(m)
        r = RawMaterial.query.first()
        if not r:
            r = RawMaterial(name='Rice', name_ar='أرز', unit='kg', cost_per_unit=5, stock_quantity=10, category='Grains', active=True)
            db.session.add(r)
        emp = Employee.query.first()
        if not emp:
            emp = Employee(employee_code='E001', national_id='1111', full_name='Test Emp', department='Sales', position='Cashier', status='active')
            db.session.add(emp)
        db.session.commit()
    c = app.test_client()
    c.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    return c


def run():
    c = ensure_admin_client()

    ok = []
    fail = []

    def check_get(path, expect=200):
        r = c.get(path, follow_redirects=True)
        if r.status_code == expect or (expect==200 and r.status_code==302):
            ok.append(f"GET {path} -> {r.status_code}")
        else:
            fail.append(f"GET {path} -> {r.status_code}")
        return r

    def check_post(path, data, expect=200):
        r = c.post(path, data=data, follow_redirects=True)
        if r.status_code == expect or (expect==200 and r.status_code==302):
            ok.append(f"POST {path} -> {r.status_code}")
        else:
            fail.append(f"POST {path} -> {r.status_code}")
        return r

    # Purchases
    check_get('/purchases')
    check_post('/purchases', data={'supplier_name':'ABC','phone':'','discount':0,'tax':0,'status':'open','date':str(datetime.utcnow().date()), 'items-0-material_id':'1','items-0-quantity':'1','items-0-cost_per_unit':'5'})

    # Expenses
    check_get('/expenses')
    check_post('/expenses', data={'vendor_name':'XYZ','phone':'','discount':0,'tax':0,'status':'open','date':str(datetime.utcnow().date()), 'items-0-description':'Note','items-0-amount':'10'})

    # Inventory (raw + meals pages)
    check_get('/inventory')
    check_get('/raw_materials')
    check_post('/raw_materials', data={'name':'Sugar','unit':'kg','cost_per_unit':'4.5','stock_quantity':'20','category':'Grains','active':'y'})
    check_get('/meals')

    # Salaries screens
    check_get('/salaries')
    check_get('/salaries/monthly')
    # Save monthly salaries (no-op update)
    with app.app_context():
        # ensure salaries rows present for current month via monthly page
        pass
    # Statements and print
    check_get('/salaries/statements')
    check_get('/salaries/statements/print?year=%d&month=%d' % (datetime.utcnow().year, datetime.utcnow().month))

    print('OK:\n' + '\n'.join(ok))
    if fail:
        print('FAIL:\n' + '\n'.join(fail))
        raise SystemExit(1)


if __name__ == '__main__':
    run()

