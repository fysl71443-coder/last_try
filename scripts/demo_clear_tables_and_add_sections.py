import os, sys
os.environ.setdefault('USE_EVENTLET','0')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import User, DraftOrder
from flask_bcrypt import Bcrypt

TARGET_BRANCH = 'china_town'
TARGET_TABLES = [1, 5, 6]


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


def list_drafts_for_tables():
    ids = []
    with app.app_context():
        for t in TARGET_TABLES:
            ds = DraftOrder.query.filter_by(branch_code=TARGET_BRANCH, table_number=str(t), status='draft').all()
            ids.extend([d.id for d in ds])
            print(f"Table {t}: draft_ids={ [d.id for d in ds] }")
    return ids


def main():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    ensure_admin()
    c = app.test_client()

    # Login
    r = c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    print('LOGIN:', r.status_code)

    # Before state: list drafts
    draft_ids = list_drafts_for_tables()

    # Cancel drafts via API (simulate user), with supervisor_password 1991
    for did in draft_ids:
        resp = c.post(f'/api/draft_orders/{did}/cancel', json={'supervisor_password': '1991'})
        try:
            data = resp.get_json(silent=True)
        except Exception:
            data = None
        print(f'CANCEL draft_id={did}:', resp.status_code, data)

    # After state: list drafts again
    list_drafts_for_tables()

    # Sections: show current, then update to المطلوب
    print('\n-- Sections (before) --')
    r = c.get(f'/api/table-sections/{TARGET_BRANCH}')
    print('GET sections:', r.status_code, (r.json or {}))

    payload = {
        'sections': [
            {'name': 'العائلة', 'sort_order': 1},
            {'name': 'الاطفال', 'sort_order': 2},
            {'name': 'HUNGER', 'sort_order': 3},
        ],
        'assignments': []
    }
    rp = c.post(f'/api/table-sections/{TARGET_BRANCH}', json=payload)
    print('POST sections:', rp.status_code, (rp.json or {}))

    print('\n-- Sections (after) --')
    r2 = c.get(f'/api/table-sections/{TARGET_BRANCH}')
    print('GET sections:', r2.status_code, (r2.json or {}))


if __name__ == '__main__':
    main()

