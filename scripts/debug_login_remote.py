#!/usr/bin/env python3
import re
import sys
import time
import requests
from urllib.parse import urljoin

def extract_csrf(html: str) -> str | None:
    # Look for input name="csrf_token" value="..."
    m = re.search(r'name=["\']csrf_token["\']\s+type=["\']hidden["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    # Alternate ordering
    m = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    return None


def main():
    base = 'https://restaurant-system-fnbm.onrender.com'
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0'})

    # Step 1: GET /login
    r1 = s.get(urljoin(base, '/login'), timeout=15)
    print('GET /login:', r1.status_code)
    csrf = extract_csrf(r1.text)
    print('csrf_token found:', bool(csrf))

    # Step 2: POST credentials with CSRF
    data = {'username': 'admin', 'password': 'admin123'}
    if csrf:
        data['csrf_token'] = csrf

    r2 = s.post(urljoin(base, '/login'), data=data, timeout=20, allow_redirects=True)
    print('POST /login:', r2.status_code, 'final_url:', r2.url)

    txt_low = r2.text.lower()
    ok_indicators = ['dashboard', 'logout', 'welcome']
    print('Indicators present:', any(k in txt_low for k in ok_indicators))

    # Print brief snippet if warning appears
    warn = re.search(r'(يرجى[^<\n]+الحقول[^<\n]+|please[^<\n]+required)', r2.text, re.I)
    if warn:
        print('Warning snippet:', warn.group(1))

    # Try get /dashboard to see if we are logged in
    rd = s.get(urljoin(base, '/dashboard'), timeout=15)
    print('GET /dashboard:', rd.status_code)
    print('Dashboard contains username?', 'admin' in rd.text.lower())

if __name__ == '__main__':
    main()

