import sys
import requests
from datetime import date

BASE = "http://127.0.0.1:5000"

def main():
    s = requests.Session()
    try:
        r = requests.get(f"{BASE}/debug/db", timeout=5)
        print("DEBUG_DB", r.status_code, r.text)
        r = s.get(f"{BASE}/login", timeout=5)
        r = s.post(f"{BASE}/login", data={"username":"admin","password":"admin123"}, allow_redirects=True, timeout=5)
        print("LOGIN", r.status_code, dict(s.cookies))
        r = s.get(f"{BASE}/employee-uvd", timeout=5)
        print("EMP_UVD", r.status_code, r.url, len(r.text))
        m = f"{date.today().year:04d}-{date.today().month:02d}"
        r = s.get(f"{BASE}/api/salaries/statements", params={"month": m}, timeout=8)
        print("SALARIES", r.status_code, r.url, r.text[:180])
        r = s.get(f"{BASE}/api/advances/metrics", timeout=8)
        print("ADV_METRICS", r.status_code, r.url, r.text[:180])
        r = s.get(f"{BASE}/api/advances/list", timeout=8)
        print("ADV_LIST", r.status_code, r.url, r.text[:180])
        return 0
    except Exception as e:
        print("ERROR", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
