import os
os.environ.setdefault('USE_EVENTLET','0')
os.environ.setdefault('PYTHONPATH','.')

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
        c.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
        r = c.get('/sales', follow_redirects=True)
        html = r.data.decode('utf-8','ignore')
        print('STATUS=', r.status_code)
        print('CONTAINS_PLACE_INDIA=', 'Place India' in html)
        print('CONTAINS_CHINA_TOWN=', 'China Town' in html)
        print('SNIPPET=', html[:400].replace('\n',' '))

if __name__ == '__main__':
    run()

