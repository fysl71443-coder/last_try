import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import from package directly (works with root on sys.path)
from app import create_app, db  # type: ignore

# Build app
app = create_app()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

from app.models import User  # type: ignore


def ensure_admin():
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        u = User.query.filter_by(username='admin').first()
        if not u:
            u = User(username='admin')
            u.set_password('admin123')
            db.session.add(u)
            db.session.commit()


def create_user(username: str, password: str) -> int:
    with app.test_client() as c:
        # must be logged in
        c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        r = c.post('/api/users', data=json.dumps({'username': username, 'password': password, 'active': True}), content_type='application/json')
        j = r.get_json(silent=True) or {}
        if r.status_code != 200 or not j.get('ok'):
            # maybe already exists -> fetch id from users page
            with app.app_context():
                u = User.query.filter_by(username=username).first()
                if not u:
                    raise RuntimeError(f"Failed to create user {username}: {r.status_code} {r.data[:200]}")
                return int(u.id)
        return int(j.get('id'))


def set_branch_permissions(uid: int, branch_scope: str, sales_view: bool) -> None:
    items = []
    # screens we know about must be in sync with backend PERM_SCREENS
    screens = ['dashboard','sales','purchases','inventory','expenses','salaries','financials','vat','reports','settings']
    for s in screens:
        rec = {'screen_key': s, 'view': False, 'add': False, 'edit': False, 'delete': False, 'print': False}
        if s == 'sales' and sales_view:
            rec['view'] = True
        items.append(rec)
    payload = {'branch_scope': branch_scope, 'items': items}
    with app.test_client() as c:
        c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        r = c.post(f'/api/users/{uid}/permissions', data=json.dumps(payload), content_type='application/json')
        if r.status_code != 200:
            raise RuntimeError(f"Failed to set permissions for uid={uid} scope={branch_scope}: {r.status_code} {r.data[:200]}")


def verify_screens() -> None:
    with app.test_client() as c:
        # login
        r = c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        assert r.status_code == 200, f"Login failed: {r.status_code}"
        # payments screen
        r = c.get('/payments', follow_redirects=True)
        assert r.status_code == 200, f"/payments failed: {r.status_code}"
        # all invoices API
        r = c.get('/api/all-invoices')
        assert r.status_code == 200, f"/api/all-invoices failed: {r.status_code}"
        data = r.get_json(silent=True)
        assert isinstance(data, dict) and 'invoices' in data, "Invalid all-invoices payload"
        # users (permissions) screen
        r = c.get('/users', follow_redirects=True)
        assert r.status_code == 200, f"/users failed: {r.status_code}"


def run():
    ensure_admin()
    verify_screens()

    # Create two users and assign branch-scoped permissions
    uid_china = create_user('user_china', '123456')
    uid_india = create_user('user_india', '123456')

    # user_china: sales view only in china_town; nothing in place_india
    set_branch_permissions(uid_china, 'china_town', sales_view=True)
    set_branch_permissions(uid_china, 'place_india', sales_view=False)

    # user_india: sales view only in place_india; nothing in china_town
    set_branch_permissions(uid_india, 'place_india', sales_view=True)
    set_branch_permissions(uid_india, 'china_town', sales_view=False)

    print("Verification OK: payments, all-invoices, users screens.")
    print("Created users with branch-scoped permissions:")
    print(f" - user_china (sales view @ china_town only)")
    print(f" - user_india (sales view @ place_india only)")


if __name__ == '__main__':
    run()

