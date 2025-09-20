import re
import json
import sys
import requests

BASE = 'http://127.0.0.1:5000'


def get_csrf_token_from_html(html: str):
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None


def main():
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0'})

    # 1) Login as admin
    r = s.post(f'{BASE}/login', data={'username': 'admin', 'password': 'admin123'}, allow_redirects=True, timeout=30)
    print('LOGIN:', r.status_code)

    # 2) Fetch a page to grab CSRF token
    r = s.get(f'{BASE}/menu', timeout=30)
    token = get_csrf_token_from_html(r.text)
    print('CSRF token detected:', bool(token))

    # 3) Delete invoices 1 and 5 via user-like POST with supervisor password
    for inv_id in (1, 5):
        try:
            r = s.post(f'{BASE}/delete_sales_invoice/{inv_id}', data={'password': '1991', 'csrf_token': token or ''}, allow_redirects=False, timeout=30)
            print(f'DELETE invoice {inv_id}:', r.status_code, r.headers.get('Location'))
        except Exception as e:
            print(f'DELETE invoice {inv_id} error:', e)

    # 4) Add table sections for CHINA TOWN
    payload = {
        'sections': [
            {'name': 'صالة A', 'sort_order': 1},
            {'name': 'صالة B', 'sort_order': 2},
        ],
        'assignments': []
    }
    try:
        r = s.post(f'{BASE}/api/table-sections/china_town', json=payload, headers={'X-CSRFToken': token or ''}, timeout=30)
        print('POST sections china_town:', r.status_code, r.text[:200])
    except Exception as e:
        print('POST sections error:', e)

    # 5) Verify
    try:
        r = s.get(f'{BASE}/api/table-sections/china_town', timeout=30)
        print('GET sections china_town:', r.status_code, r.text[:300])
    except Exception as e:
        print('GET sections error:', e)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('ERROR:', e)
        sys.exit(1)

