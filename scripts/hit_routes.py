import os
os.environ.setdefault('USE_EVENTLET','0')
os.environ.setdefault('PYTHONPATH','.')

from datetime import datetime
from app import app, db
from models import User, Meal, SalesInvoice
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
        m = Meal.query.first()
        if not m:
            m = Meal(name='Route Test Meal', name_ar='وجبة اختبار المسارات', selling_price=10, total_cost=7, profit_margin_percent=30, active=True, user_id=u.id)
            db.session.add(m); db.session.commit()
    c = app.test_client()
    c.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    return c


def main():
    c = ensure_admin_client()
    paths = [
        '/', '/dashboard', '/sales', '/sales/place_india', '/sales/china_town',
        '/sales/place_india/table/1', '/sales/china_town/table/1',
        '/menu', '/customers', '/employees', '/invoices', '/vat',
    ]
    ok = []
    fail = []
    for p in paths:
        r = c.get(p, follow_redirects=True)
        if r.status_code in (200, 302):
            ok.append(f"GET {p} -> {r.status_code}")
        else:
            fail.append(f"GET {p} -> {r.status_code}")
    print("OK:\n"+"\n".join(ok))
    if fail:
        print("FAIL:\n"+"\n".join(fail))

if __name__ == '__main__':
    main()

