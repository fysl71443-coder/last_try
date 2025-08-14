import os
os.environ.setdefault('USE_EVENTLET', '0')

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
            # ensure at least one meal
            m = Meal(name='Route Test Meal', name_ar='وجبة اختبار المسارات', selling_price=10, total_cost=7, profit_margin_percent=30, active=True, user_id=u.id)
            db.session.add(m); db.session.commit()
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

    # Core screens
    check_get('/')
    check_get('/dashboard') if hasattr(app.view_functions, 'dashboard') else None

    # Sales branch selector and branches
    r = check_get('/sales')
    check_get('/sales/place_india')
    check_get('/sales/china_town')

    # POS tables and one table ensure invoice
    check_get('/pos/place_india')
    r = check_get('/pos/place_india/table/1')
    r = check_get('/pos/china_town')
    r = check_get('/pos/china_town/table/1')

    # Menu admin (as admin)
    check_get('/menu')

    # Customers
    check_get('/customers')

    # Employees
    check_get('/employees')

    # Invoices listing and sample invoice view if exists
    check_get('/invoices')
    with app.app_context():
        inv = SalesInvoice.query.order_by(SalesInvoice.id.desc()).first()
        if inv:
            check_get(f"/invoices/sales/{inv.id}")
            check_get(f"/sales/{inv.id}/print")

    # VAT dashboard and print
    check_get('/vat')
    today = datetime.utcnow().date()
    quarter = (today.month - 1) // 3 + 1
    check_get(f"/vat/print?year={today.year}&quarter={quarter}")

    # Branch sales report
    check_get(f"/reports/branch_sales?year={today.year}&month={today.month}&branch=place_india")
    check_get(f"/reports/branch_sales/print?year={today.year}&month={today.month}&branch=place_india")

    print("OK:\n" + "\n".join(ok))
    if fail:
        print("FAIL:\n" + "\n".join(fail))
        raise SystemExit(1)


if __name__ == '__main__':
    run()

