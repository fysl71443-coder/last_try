from app import create_app
app = create_app()
client = app.test_client()

results = {}

# 1) Login page reachable
r = client.get('/login')
results['GET /login'] = r.status_code

# 2) Seed default admin if none and login
r = client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
results['POST /login admin/admin123'] = r.status_code

# 3) Authenticated pages
paths = [
    '/dashboard','/purchases','/expenses','/inventory','/payments','/reports',
]
for p in paths:
    try:
        rr = client.get(p, follow_redirects=True)
        results[f'GET {p}'] = rr.status_code
    except Exception as e:
        results[f'GET {p}'] = f'ERR:{e}'

for k in sorted(results):
    print(f"{k}: {results[k]}")
