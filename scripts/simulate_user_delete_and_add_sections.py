import os, sys
os.environ.setdefault('USE_EVENTLET','0')
# Ensure project root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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


def main():
    # Enable testing to disable CSRF for test client
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    ensure_admin()
    c = app.test_client()

    # Login
    r = c.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    print('LOGIN:', r.status_code)

    # Delete sales invoices 1 and 5 with supervisor password 1991
    for inv_id in (1,5):
        resp = c.post(f'/delete_sales_invoice/{inv_id}', data={'password':'1991'}, follow_redirects=False)
        print(f'DELETE_SALES_INVOICE {inv_id}:', resp.status_code)

    # Add table sections for china_town
    payload = {
        'sections': [
            {'name': 'صالة A', 'sort_order': 1},
            {'name': 'صالة B', 'sort_order': 2},
        ],
        'assignments': []
    }
    resp = c.post('/api/table-sections/china_town', json=payload)
    print('POST /api/table-sections/china_town:', resp.status_code, (resp.json or {}))

    # Verify GET
    resp = c.get('/api/table-sections/china_town')
    print('GET /api/table-sections/china_town:', resp.status_code, (resp.json or {}) )


if __name__ == '__main__':
    main()

