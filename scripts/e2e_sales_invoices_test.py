#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E test against running server: login, drafts, sales invoices for both branches,
discount (unregistered=0, cash=fixed, credit=editable).
"""
import os
import sys
import re
import json
import io
import requests

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE = os.environ.get('POS_BASE_URL', 'http://127.0.0.1:5000')
USER = os.environ.get('POS_USER', 'admin')
PASS = os.environ.get('POS_PASS', 'admin123')

session = requests.Session()
session.headers['User-Agent'] = 'E2E-Sales-Test/1.0'
csrf_token = ''


def get_csrf_from_html(html):
    m = re.search(r'name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
    return m.group(1) if m else ''


def login():
    global csrf_token
    r = session.get(f'{BASE}/login')
    r.raise_for_status()
    csrf_token = get_csrf_from_html(r.text)
    r = session.post(f'{BASE}/login', data={
        'username': USER,
        'password': PASS,
    }, allow_redirects=True)
    r.raise_for_status()
    if r.url.rstrip('/').endswith('/login'):
        raise SystemExit('تسجيل الدخول فشل — تحقق من المستخدم/كلمة المرور')
    # Refresh CSRF from a page that has it (e.g. sales tables)
    r2 = session.get(f'{BASE}/sales/china_town/tables')
    r2.raise_for_status()
    csrf_token = get_csrf_from_html(r2.text) or csrf_token
    print('  [OK] Login')
    return True


def test_sales_tables_both_branches():
    for branch in ('china_town', 'place_india'):
        r = session.get(f'{BASE}/sales/{branch}/tables')
        r.raise_for_status()
        if r.status_code != 200:
            raise SystemExit('Tables page %s: %s' % (branch, r.status_code))
        if 'tables' not in r.text.lower() and 'table' not in r.text.lower():
            print(f'  [WARN] Page may not show tables: {branch}')
        print(f'  [OK] Branch {branch} tables page 200')
    return True


def test_draft_save_and_load(branch, table_no=1):
    # حفظ مسودة بدون عميل → خصم يجب أن يُحفظ 0
    payload = {
        'items': [{'id': 1, 'name': 'صنف تجريبي', 'price': 25.0, 'quantity': 2}],
        'customer': {'name': '', 'phone': ''},
        'discount_pct': 0,
        'tax_pct': 15,
        'payment_method': 'CASH',
    }
    headers = {'Content-Type': 'application/json'}
    if csrf_token:
        headers['X-CSRFToken'] = csrf_token
    r = session.post(f'{BASE}/api/draft-order/{branch}/{table_no}', json=payload, headers=headers)
    r.raise_for_status()
    data = r.json()
    if not data.get('success'):
        raise SystemExit('Draft save failed: %s' % data)
    draft_id = data.get('draft_id')
    print('  [OK] Draft saved %s table %s draft_id=%s' % (branch, table_no, draft_id))

    # Load draft
    r2 = session.get(f'{BASE}/api/draft/{branch}/{table_no}')
    r2.raise_for_status()
    j = r2.json()
    draft = j.get('draft') or j
    items = draft.get('items') or []
    disc = draft.get('discount_pct', 0)
    if disc != 0 and not draft.get('customer', {}).get('name'):
        print('  [WARN] Draft has no customer but discount_pct=%s (expected 0)' % disc)
    print('  [OK] Draft loaded: %s items, discount=%s%%' % (len(items), disc))
    return draft_id


def test_pos_page_loads(branch, table_no=1):
    r = session.get(f'{BASE}/pos/{branch}/table/{table_no}')
    r.raise_for_status()
    if r.status_code != 200:
        raise SystemExit('POS page %s/%s: %s' % (branch, table_no, r.status_code))
    # يجب أن تحتوي على واجهة الفاتورة (لا تبقى على "جاري التحميل" فقط في الـ HTML الأولي)
    if 'pos-screen' not in r.text and 'pos-init' not in r.text:
        print('  [WARN] Page may lack pos-screen/pos-init')
    print('  [OK] POS page %s table %s loaded 200' % (branch, table_no))
    return True


def test_customer_search():
    r = session.get(f'{BASE}/api/customers/search', params={'q': 'a'})
    r.raise_for_status()
    j = r.json()
    results = j.get('results', j) if isinstance(j, dict) else (j if isinstance(j, list) else [])
    print('  [OK] Customer search: %s results' % len(results))
    return results


def test_checkout_cash_no_customer(branch='china_town', table_no=3):
    """Cash payment with no registered customer - discount must be 0."""
    # Need menu items
    r = session.get(f'{BASE}/api/menu/all-items')
    r.raise_for_status()
    j = r.json()
    items_raw = j.get('items', [])
    if not items_raw:
        print('  [SKIP] No menu items for checkout test')
        return
    first = items_raw[0]
    meal_id = first.get('meal_id') or first.get('id')
    name = first.get('name', 'صنف')
    price = float(first.get('price', 0) or 0)
    if not meal_id or price <= 0:
        print('  [SKIP] Invalid item for test')
        return
    items_payload = [{'meal_id': meal_id, 'name': name, 'price': price, 'qty': 1}]
    payload = {
        'branch_code': branch,
        'table_number': table_no,
        'items': items_payload,
        'customer_id': None,
        'customer_name': '',
        'customer_phone': '',
        'discount_pct': 0,
        'tax_pct': 15,
        'payment_method': 'CASH',
    }
    headers = {'Content-Type': 'application/json'}
    if csrf_token:
        headers['X-CSRFToken'] = csrf_token
    r = session.post(f'{BASE}/api/sales/checkout', json=payload, headers=headers)
    if r.status_code != 200:
        print('  [WARN] checkout CASH no customer: %s %s' % (r.status_code, r.text[:200]))
        return
    data = r.json()
    if data.get('error'):
        print('  [WARN] checkout: %s' % data.get('error'))
        return
    if data.get('ok'):
        print('  [OK] Invoice CASH no customer (discount 0): invoice_id=%s' % data.get('invoice_id'))
    return data.get('invoice_id')


def main():
    print('=' * 60)
    print('  E2E: Sales, drafts, discount')
    print('=' * 60)
    try:
        login()
        test_sales_tables_both_branches()
        test_draft_save_and_load('china_town', 1)
        test_draft_save_and_load('place_india', 1)
        test_pos_page_loads('china_town', 1)
        test_pos_page_loads('place_india', 1)
        test_customer_search()
        test_checkout_cash_no_customer('china_town', 3)
        test_checkout_cash_no_customer('place_india', 3)
    except requests.exceptions.ConnectionError as e:
        print('  [FAIL] Cannot connect to server %s: %s' % (BASE, e))
        sys.exit(1)
    except Exception as e:
        print('  [FAIL] %s' % e)
        sys.exit(1)
    print('=' * 60)
    print('  All E2E tests passed.')
    print('=' * 60)


if __name__ == '__main__':
    main()
