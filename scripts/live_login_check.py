import re
import sys
import requests
from urllib.parse import urljoin

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://mt-m-lqry-lsyny.onrender.com'
USER = sys.argv[2] if len(sys.argv) > 2 else 'admin'
PASS = sys.argv[3] if len(sys.argv) > 3 else 'admin123'

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# 1) GET /login and extract CSRF token
r1 = s.get(urljoin(BASE, '/login'), timeout=30)
print('GET /login:', r1.status_code)
html = r1.text
m = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
csrf = m.group(1) if m else None
print('csrf_token found:', bool(csrf))

# 2) POST /login with credentials (+ csrf if present)
form = {'username': USER, 'password': PASS}
if csrf:
    form['csrf_token'] = csrf
r2 = s.post(urljoin(BASE, '/login'), data=form, timeout=30, allow_redirects=True)
print('POST /login:', r2.status_code)
print('Final URL:', r2.url)

# 3) Basic success heuristics: presence of logout link or welcome text
text_low = r2.text.lower()
success = ('logout' in text_low) or ('تسجيل الخروج' in text_low) or ('china town' in text_low) or ('dashboard' in text_low)
print('Heuristic success:', success)

# 4) Try fetching home page after login
r3 = s.get(urljoin(BASE, '/'), timeout=30)
print('GET /:', r3.status_code)
print('Home has logout?', ('logout' in r3.text.lower()) or ('تسجيل الخروج' in r3.text))

# 5) Print short snippet if error-like text appears
m2 = re.search(r'(invalid|خطأ|error)', r2.text, re.I)
if m2:
    print('Snippet around error:')
    idx = m2.start()
    print(r2.text[max(0, idx-80):idx+160].strip().replace('\n',' ')[:240])

