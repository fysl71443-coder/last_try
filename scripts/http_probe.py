import urllib.request, urllib.error
import sys

url = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000/health'
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read().decode('utf-8', errors='ignore')
        print('STATUS:', resp.status)
        print('BODY:', body[:200])
except Exception as e:
    print('ERR:', e)
    sys.exit(1)

