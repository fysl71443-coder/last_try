#!/usr/bin/env python3
"""
E2E smoke: simulate user flows, all main routes, print endpoints, and key APIs.
Run: python tools/e2e_smoke.py
"""
from __future__ import print_function

import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ.setdefault('USE_EVENTLET', '0')
os.environ.setdefault('DISABLE_SOCKETIO', '1')
u = os.environ.get('DATABASE_URL') or ''
if 'postgres' in u.lower() or 'render.com' in u.lower():
    os.environ.pop('DATABASE_URL', None)
instance_dir = os.path.join(ROOT, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, 'accounting_app.db')
os.environ.setdefault('LOCAL_SQLITE_PATH', db_path)
os.environ.setdefault('DATABASE_URL', 'sqlite:///' + db_path.replace('\\', '/'))

def _get(client, path, follow=True, expect=(200, 302)):
    r = client.get(path, follow_redirects=follow)
    ok = r.status_code in (expect if isinstance(expect, tuple) else (expect,))
    return r, ok

def _post(client, path, data=None, json=None, follow=True, expect=(200, 302, 400, 201)):
    kw = {'follow_redirects': follow}
    if data is not None:
        kw['data'] = data
    if json is not None:
        kw['json'] = json
    r = client.post(path, **kw)
    ok = r.status_code in (expect if isinstance(expect, tuple) else (expect,))
    return r, ok

def main():
    from app import create_app
    app = create_app()
    # Ensure DB schema is up to date (e.g. liability_account_code on expense_invoices)
    with app.app_context():
        try:
            from flask_migrate import upgrade
            upgrade()
        except Exception:
            pass
    client = app.test_client()
    fail = []

    def ok(name, cond, note=''):
        if cond:
            print('  OK', name, note)
        else:
            print('  FAIL', name, note)
            fail.append(name)

    print('=== Login ===')
    r, _ = _get(client, '/login')
    ok('GET /login', r.status_code == 200)
    r, _ = _post(client, '/login', data={'username': 'admin', 'password': 'admin123'})
    ok('POST /login', r.status_code in (200, 302))

    print('\n=== Main pages (GET) ===')
    for path in ['/', '/dashboard', '/invoices', '/sales', '/customers', '/suppliers',
                 '/expenses', '/purchases', '/payments', '/reports', '/settings',
                 '/employees', '/menu', '/users', '/vat', '/chart-of-accounts',
                 '/financials/accounts_hub', '/financials/operations', '/journal',
                 '/pos/place_india', '/pos/china_town', '/orders', '/table-settings']:
        r, _ = _get(client, path)
        ok('GET ' + path, r.status_code in (200, 302), '-> %s' % r.status_code)

    print('\n=== Reports & print-style GET ===')
    today = datetime.utcnow().date()
    q = (today.month - 1) // 3 + 1
    # Reports list / sales / expenses / purchases
    r, _ = _get(client, '/reports/sales')
    ok('GET /reports/sales', r.status_code in (200, 302))
    r, _ = _get(client, '/reports/expenses')
    ok('GET /reports/expenses', r.status_code in (200, 302))
    r, _ = _get(client, '/reports/purchases')
    ok('GET /reports/purchases', r.status_code in (200, 302))
    r, _ = _get(client, '/reports/print/salaries_detailed')
    ok('GET /reports/print/salaries_detailed', r.status_code in (200, 302))
    # VAT print
    r, _ = _get(client, '/vat/print?year=%d&quarter=%d' % (today.year, q))
    ok('GET /vat/print', r.status_code in (200, 302, 400))
    # Financials print
    d = today.isoformat()
    r, _ = _get(client, '/financials/print/income_statement?period=month&start_date=%s&end_date=%s&branch=all' % (d, d))
    ok('GET /financials/print/income_statement', r.status_code in (200, 302))
    r, _ = _get(client, '/financials/print/trial_balance?date=%s' % d)
    ok('GET /financials/print/trial_balance', r.status_code in (200, 302))
    r, _ = _get(client, '/financials/print/balance_sheet?date=%s' % d)
    ok('GET /financials/print/balance_sheet', r.status_code in (200, 302))
    # Journal print
    r, _ = _get(client, '/journal/print/all')
    ok('GET /journal/print/all', r.status_code in (200, 302))
    # All-invoices print
    r, _ = _get(client, '/reports/print/all-invoices/sales?start_date=%s&end_date=%s&branch=all' % (d, d))
    ok('GET /reports/print/all-invoices/sales', r.status_code in (200, 302))
    r, _ = _get(client, '/reports/print/all-invoices/purchases?start_date=%s&end_date=%s&branch=all' % (d, d))
    ok('GET /reports/print/all-invoices/purchases', r.status_code in (200, 302))
    r, _ = _get(client, '/reports/print/all-invoices/expenses?start_date=%s&end_date=%s&branch=all' % (d, d))
    ok('GET /reports/print/all-invoices/expenses', r.status_code in (200, 302))

    print('\n=== APIs (JSON) ===')
    r = client.get('/api/chart/list')
    j = r.get_json() if r.content_type and 'json' in r.content_type else None
    ok('GET /api/chart/list', r.status_code == 200 and (j is None or j.get('ok')), 'items=%s' % (len(j.get('items', [])) if j else 0))
    r = client.get('/financials/api/trial_balance_json?date=%s' % d)
    j = r.get_json() if r.content_type and 'json' in r.content_type else None
    ok('GET /financials/api/trial_balance_json', r.status_code == 200)
    r = client.get('/financials/api/accounts/list')
    j = r.get_json() if r.content_type and 'json' in r.content_type else None
    ok('GET /financials/api/accounts/list', r.status_code == 200)
    r = client.get('/journal/api/journals?start=2025-01-01&end=%s' % d)
    ok('GET /journal/api/journals', r.status_code == 200)
    r = client.get('/financials/api/list_customers')
    ok('GET /financials/api/list_customers', r.status_code == 200)
    r = client.get('/financials/api/list_suppliers')
    ok('GET /financials/api/list_suppliers', r.status_code == 200)
    r = client.get('/financials/api/list_employees')
    ok('GET /financials/api/list_employees', r.status_code == 200)
    r = client.get('/financials/api/unpaid_payroll_runs')
    ok('GET /financials/api/unpaid_payroll_runs', r.status_code == 200)
    r = client.get('/financials/api/account_ledger_json?code=1111&start_date=2025-01-01&end_date=%s' % d)
    j = r.get_json() if r.content_type and 'json' in (r.content_type or '') else None
    ok('GET /financials/api/account_ledger_json', r.status_code == 200 and (j is None or isinstance(j.get('ok'), bool)))

    print('\n=== POST operations (minimal) ===')
    # Journal post: minimal manual JE
    payload = {
        'entries': [{
            'date': d,
            'description': 'E2E smoke test JE',
            'lines': [
                {'account_code': '1111', 'debit': 1.0, 'credit': 0, 'description': 'test', 'date': d, 'cost_center': ''},
                {'account_code': '4111', 'debit': 0, 'credit': 1.0, 'description': 'test', 'date': d, 'cost_center': ''},
            ]
        }]
    }
    r = client.post('/journal/api/transactions/post', json=payload, headers={'Content-Type': 'application/json'})
    j = r.get_json() if r.content_type and 'json' in (r.content_type or '') else None
    ok('POST /journal/api/transactions/post', r.status_code == 200 and (j and j.get('ok')), 'msg=%s' % (j.get('error') if j else ''))

    # Quick-txn bank_deposit (creates JE)
    r = client.post('/financials/api/quick-txn', json={'type': 'bank_deposit', 'date': d, 'amount': 0.01, 'payment_method': 'cash', 'note': 'e2e'}, headers={'Content-Type': 'application/json'})
    j = r.get_json() if r.content_type and 'json' in (r.content_type or '') else None
    ok('POST /financials/api/quick-txn (bank_deposit)', r.status_code == 200 and (j and j.get('ok')), 'msg=%s' % (j.get('error') if j else ''))

    # Cleanup duplicates dry-run
    r = client.post('/financials/api/accounts/cleanup_duplicates?dry_run=1', headers={'Content-Type': 'application/json'})
    j = r.get_json() if r.content_type and 'json' in (r.content_type or '') else None
    ok('POST /financials/api/accounts/cleanup_duplicates (dry_run)', r.status_code == 200 and (j is None or j.get('ok') is True), 'msg=%s' % (j.get('error') if j else ''))

    # Type-driven expense (single item: COGS / Beverages, 1 SAR, paid). 400 = CSRF/validation in test client.
    r = client.post('/expenses', data={
        'expense_type': 'cogs', 'expense_sub_type': 'beverages', 'amount': '1',
        'date': d, 'payment_method': 'CASH', 'status': 'paid', 'description': 'e2e smoke expense',
    }, follow_redirects=True)
    ok('POST /expenses (type-driven)', r.status_code in (200, 302, 400), '-> %s' % r.status_code)

    print('\n=== Summary ===')
    if fail:
        print('FAILED:', ', '.join(fail))
        return 1
    print('All checks passed.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
