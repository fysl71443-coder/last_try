import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app import create_app, db

# Ensure local settings
os.environ.setdefault('DATABASE_URL', 'sqlite:///local.db')
os.environ.setdefault('SECRET_KEY', 'dev')

app = create_app()

results = {}
with app.app_context():
    db.create_all()

with app.test_client() as c:
    # Hit login page (GET)
    r = c.get('/login')
    results['GET /login'] = r.status_code

    # First login attempt: create default admin if DB empty
    r = c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    results['POST /login admin/admin123'] = r.status_code

    # Authenticated routes
    for path in [
        '/dashboard',
        '/financials/income-statement',
        '/expenses',
        '/settings',
        '/sales',
        '/sales/china_town/tables',
        '/pos/china_town/table/1',
        '/vat/?year=2025&quarter=3',
        '/vat/print?year=2025&quarter=3',
        '/financials/balance-sheet',
        '/financials/trial-balance',
        '/financials/balance-sheet/print',
        '/financials/trial-balance/print',
        # Newly added endpoints to avoid 404s seen in logs
        '/api/all-invoices?payment_method=cash',
        '/api/reports/all-purchases?payment_method=cash',
        '/api/all-expenses?payment_method=cash',
        '/reports/print/all-invoices/sales?payment_method=cash',
        # Additional screens for comprehensive check (GET only)
        '/customers',
        '/suppliers',
        '/menu',
        '/reports',
        '/invoices',
        '/payments',
        '/inventory',
        '/meals',
        '/raw-materials',
        '/users',
        '/table-settings',
    ]:
        rr = c.get(path)
        results[f'GET {path}'] = rr.status_code

# Print concise report
for k,v in results.items():
    print(f'{k}: {v}')

