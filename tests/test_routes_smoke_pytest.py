import os, sys
from datetime import datetime
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import User, Meal, SalesInvoice
from flask_bcrypt import Bcrypt

@pytest.fixture(scope='module', autouse=True)
def seed_minimal():
    with app.app_context():
        # Admin user and one meal
        u = User.query.filter_by(username='admin').first()
        if not u:
            b = Bcrypt(app)
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        if not Meal.query.first():
            m = Meal(name='Route Test Meal', name_ar='وجبة اختبار المسارات', selling_price=10, total_cost=7, profit_margin_percent=30, active=True, user_id=u.id)
            db.session.add(m); db.session.commit()

@pytest.fixture()
def authed_client(client):
    client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    return client


def get(client, path, expect=200):
    r = client.get(path, follow_redirects=True)
    assert r.status_code in (expect, 302 if expect==200 else expect), f"GET {path} -> {r.status_code}"
    return r


def test_core_routes(authed_client):
    c = authed_client
    # Home and dashboard
    get(c, '/')
    # Sales pages
    get(c, '/sales')
    get(c, '/sales/place_india')
    get(c, '/sales/china_town')
    # POS
    get(c, '/pos/place_india')
    get(c, '/pos/place_india/table/1')
    get(c, '/pos/china_town')
    get(c, '/pos/china_town/table/1')
    # Menu admin
    get(c, '/menu')
    # Customers
    get(c, '/customers')
    # Invoices list
    get(c, '/invoices')
    # VAT
    today = datetime.utcnow().date()
    quarter = (today.month - 1) // 3 + 1
    get(c, '/vat')
    get(c, f"/vat/print?year={today.year}&quarter={quarter}")
    # Branch sales report
    get(c, f"/reports/branch_sales?year={today.year}&month={today.month}&branch=place_india")
    get(c, f"/reports/branch_sales/print?year={today.year}&month={today.month}&branch=place_india")

