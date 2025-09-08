import os, sys
os.environ.setdefault('USE_EVENTLET', '0')

# Ensure project root on sys.path when running from scripts/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import json
from datetime import datetime
from urllib.parse import urlencode

from app import app, db
from flask_bcrypt import Bcrypt


def ensure_admin_login(client):
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        from models import User, Meal
        u = User.query.filter_by(username='admin').first()
        if not u:
            b = Bcrypt(app)
            u = User(username='admin', email='admin@example.com', role='admin', active=True)
            u.set_password('admin123', b)
            db.session.add(u)
            db.session.commit()
        m = Meal.query.first()
        if not m:
            m = Meal(name='Smoke Test Meal', name_ar='وجبة اختبار', selling_price=10, total_cost=7, profit_margin_percent=30, active=True, user_id=u.id)
            db.session.add(m)
            db.session.commit()
    r = client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    return r.status_code in (200, 302)


def hit(client, method, path, expect=200, params=None):
    url = path
    if params:
        url += ('?' + urlencode(params))
    if method == 'GET':
        r = client.get(url, follow_redirects=True)
    else:
        r = client.post(url, data=params or {}, follow_redirects=True)
    ok = (r.status_code == expect) or (expect == 200 and r.status_code in (200, 302))
    return ok, r.status_code, (r.data[:200] if r.data else b'')


def run_smoke():
    results = {
        'started_at': datetime.utcnow().isoformat() + 'Z',
        'passes': [],
        'fails': [],
    }
    client = app.test_client()

    # Login
    if not ensure_admin_login(client):
        results['fails'].append({'step': 'login', 'status': 'login_failed'})
        return results

    # Optional: seed sample data endpoint (best-effort)
    try:
        ok, code, _ = hit(client, 'GET', '/admin/create-sample-data')
        if ok:
            results['passes'].append({'endpoint': '/admin/create-sample-data', 'code': code})
        else:
            results['fails'].append({'endpoint': '/admin/create-sample-data', 'code': code})
    except Exception as e:
        results['fails'].append({'endpoint': '/admin/create-sample-data', 'error': str(e)})

    checks = [
        ('GET', '/health'),
        ('GET', '/'),
        ('GET', '/dashboard'),
        ('GET', '/sales'),
        ('GET', '/sales/china_town'),
        ('GET', '/sales/place_india'),
        ('GET', '/sales/china_town/tables'),
        ('GET', '/sales/place_india/tables'),
        ('GET', '/pos/china_town'),
        ('GET', '/pos/china_town/table/1'),
        ('GET', '/pos/place_india'),
        ('GET', '/pos/place_india/table/1'),
        ('GET', '/menu'),
        ('GET', '/customers'),
        ('GET', '/employees'),
        ('GET', '/invoices'),
        ('GET', '/settings'),
        ('GET', '/api/categories'),
        ('GET', '/api/table-settings'),
        ('GET', '/api/tables/china_town'),
        ('GET', '/api/tables/place_india'),
    ]

    for method, path in checks:
        try:
            ok, code, snippet = hit(client, method, path)
            if ok:
                results['passes'].append({'endpoint': path, 'code': code})
            else:
                results['fails'].append({'endpoint': path, 'code': code, 'snippet': snippet.decode('utf-8','ignore')})
        except Exception as e:
            results['fails'].append({'endpoint': path, 'error': str(e)})

    # VAT print sample
    today = datetime.utcnow().date()
    quarter = (today.month - 1)//3 + 1
    ok, code, snippet = hit(client, 'GET', '/vat/print', params={'year': today.year, 'quarter': quarter})
    if ok:
        results['passes'].append({'endpoint': '/vat/print', 'code': code})
    else:
        results['fails'].append({'endpoint': '/vat/print', 'code': code, 'snippet': snippet.decode('utf-8','ignore')})

    results['finished_at'] = datetime.utcnow().isoformat() + 'Z'
    return results


if __name__ == '__main__':
    res = run_smoke()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    # exit non-zero if failures to integrate with CI later
    if res['fails']:
        raise SystemExit(1)

