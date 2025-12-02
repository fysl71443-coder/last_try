import os, sys
os.environ.setdefault('USE_EVENTLET','0')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import User
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
    c = app.test_client()
    c.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    return c


def main():
    c = ensure_admin_client()
    r = c.get('/api/archive/list?branch=place_india&page=1&page_size=5')
    print('LIST', r.status_code, r.is_json)
    print((r.json or {}))
    r2 = c.get('/archive/download?month=1&fmt=csv')
    print('DL', r2.status_code, r2.headers.get('Content-Type'))


if __name__ == '__main__':
    main()
