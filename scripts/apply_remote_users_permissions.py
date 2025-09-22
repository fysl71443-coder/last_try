import os
import json
import pathlib
import sys

# Usage: set env DATABASE_URL, then run this script to create users and branch-scoped sales permissions
# Example (PowerShell):
#   $env:DATABASE_URL = "postgresql://..."; python -u scripts/apply_remote_users_permissions.py

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app, db  # type: ignore
from app.models import User  # type: ignore


def ensure_admin(app):
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


def create_user(app, username: str, password: str) -> int:
    with app.test_client() as c:
        # login as admin
        c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        r = c.post('/api/users', data=json.dumps({'username': username, 'password': password, 'active': True}), content_type='application/json')
        j = r.get_json(silent=True) or {}
        if r.status_code != 200 or not j.get('ok'):
            # maybe already exists
            with app.app_context():
                u = User.query.filter_by(username=username).first()
                if not u:
                    raise RuntimeError(f"Failed to create user {username}: {r.status_code} {r.data[:200]}")
                return int(u.id)
        return int(j.get('id'))


def set_branch_permissions(app, uid: int, branch_scope: str, sales_view: bool) -> None:
    # Keep in sync with PERM_SCREENS (server side)
    screens = ['dashboard','sales','purchases','inventory','expenses','salaries','financials','vat','reports','settings']
    items = []
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


def run():
    dsn = os.getenv('DATABASE_URL')
    if not dsn:
        raise SystemExit('DATABASE_URL environment variable is not set.')

    # Normalize postgres:// prefix if present
    if dsn.startswith('postgres://'):
        os.environ['DATABASE_URL'] = dsn.replace('postgres://', 'postgresql://', 1)

    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    ensure_admin(app)

    uid_china = create_user(app, 'user_china', '123456')
    uid_india = create_user(app, 'user_india', '123456')

    set_branch_permissions(app, uid_china, 'china_town', True)
    set_branch_permissions(app, uid_china, 'place_india', False)

    set_branch_permissions(app, uid_india, 'place_india', True)
    set_branch_permissions(app, uid_india, 'china_town', False)

    print('Applied users and branch-scoped permissions to database: OK')
    print(' - user_china / 123456 (sales view @ china_town)')
    print(' - user_india / 123456 (sales view @ place_india)')


if __name__ == '__main__':
    run()

