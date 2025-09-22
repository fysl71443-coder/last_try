import json
import pathlib
import importlib.util

# Load packaged app from app/__init__.py explicitly to avoid name clash with app.py
ROOT = pathlib.Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("pkg_app", str(ROOT / "app" / "__init__.py"))
app_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(app_mod)

create_app = getattr(app_mod, 'create_app')
db = getattr(app_mod, 'db')

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


def run():
    ensure_admin()
    results = []
    errors = []
    with app.app_context():
        with app.test_client() as c:
            # Login (creates default admin if not exists)
            r = c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
            if r.status_code != 200:
                errors.append(f'Login failed HTTP {r.status_code}')
            else:
                results.append('Login OK')

            # Open POS page (China Town table 1)
            r = c.get('/pos/china_town/table/1', follow_redirects=True)
            if r.status_code != 200:
                errors.append(f'Open POS failed HTTP {r.status_code}')
            else:
                results.append('POS open OK')

            # Checkout directly via sales API (no draft)
            payload = {
                'branch_code': 'china_town',
                'table_number': 1,
                'items': [
                    {'name': 'Test Item', 'price': 10.0, 'qty': 2}
                ],
                'discount_pct': 0,
                'tax_pct': 15,
                'payment_method': 'CASH',
            }
            r = c.post('/api/sales/checkout', data=json.dumps(payload), content_type='application/json')
            if r.status_code != 200:
                errors.append(f'Checkout failed HTTP {r.status_code}: {r.data.decode("utf-8", "ignore")[:200]}')
            else:
                j = r.get_json(silent=True) or {}
                invoice_id = j.get('invoice_id')
                if not invoice_id:
                    errors.append('Checkout response missing invoice_id')
                else:
                    results.append(f'Checkout OK invoice={invoice_id}')
                    # Call confirm-print to finalize/post
                    r2 = c.post('/api/invoice/confirm-print', data=json.dumps({
                        'invoice_id': invoice_id,
                        'payment_method': j.get('payment_method'),
                        'total_amount': j.get('total_amount'),
                        'branch_code': j.get('branch_code'),
                        'table_number': j.get('table_number'),
                    }), content_type='application/json')
                    if r2.status_code != 200:
                        errors.append(f'Confirm-print failed HTTP {r2.status_code}: {r2.data.decode("utf-8", "ignore")[:200]}')
                    else:
                        results.append('Confirm-print OK (invoice posted)')

    for line in results:
        print(line)
    if errors:
        print('ERRORS:')
        for e in errors:
            print(' -', e)
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == '__main__':
    run()

