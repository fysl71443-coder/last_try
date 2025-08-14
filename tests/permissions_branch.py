import os
os.environ.setdefault('USE_EVENTLET', '0')

from app import app, db
from models import User, UserPermission
from flask_bcrypt import Bcrypt


def ensure_user(username):
    with app.app_context():
        u = User.query.filter_by(username=username).first()
        if u:
            return u
        b = Bcrypt(app)
        u = User(username=username, email=f'{username}@example.com', role='user', active=True)
        u.set_password('pass123', b)
        db.session.add(u)
        db.session.commit()
        return u


def set_perms(uid, branch_scope, screens):
    with app.app_context():
        UserPermission.query.filter_by(user_id=uid, branch_scope=branch_scope).delete(synchronize_session=False)
        for screen_key, perms in screens.items():
            p = UserPermission(
                user_id=uid, screen_key=screen_key, branch_scope=branch_scope,
                can_view=perms.get('view', False),
                can_add=perms.get('add', False),
                can_edit=perms.get('edit', False),
                can_delete=perms.get('delete', False),
                can_print=perms.get('print', False),
            )
            db.session.add(p)
        db.session.commit()


def run():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()

    u1 = ensure_user('place_user')
    u2 = ensure_user('china_user')

    set_perms(u1.id, 'place_india', {'sales': {'view': True}})
    set_perms(u2.id, 'china_town', {'sales': {'view': True}})

    with app.test_client() as c:
        # login as place_user and check access
        c.post('/login', data={'username':'place_user','password':'pass123'}, follow_redirects=True)
        r = c.get('/sales')
        assert b'Place India' in r.data and b'China Town' not in r.data, 'place_user should see only Place India card'
        r2 = c.get('/sales/china_town', follow_redirects=True)
        assert r2.status_code == 200 and (b'لا تملك صلاحية' in r2.data or b'permission' in r2.data), 'place_user should be blocked from china_town'

        # login as china_user and check access
        c.get('/logout', follow_redirects=True)
        c.post('/login', data={'username':'china_user','password':'pass123'}, follow_redirects=True)
        r = c.get('/sales')
        assert b'China Town' in r.data and b'Place India' not in r.data, 'china_user should see only China Town card'
        r2 = c.get('/sales/place_india', follow_redirects=True)
        assert r2.status_code == 200 and (b'لا تملك صلاحية' in r2.data or b'permission' in r2.data), 'china_user should be blocked from place_india'

    print('Branch permissions ok')


if __name__ == '__main__':
    run()

