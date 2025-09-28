import json
from app import create_app

app = create_app()
client = app.test_client()

out = []

# 1) Login (bootstrap admin if needed)
resp = client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
out.append(('login', resp.status_code))

# 2) Create a purchase invoice
from datetime import date
purchase_payload = {
    'date': date.today().strftime('%Y-%m-%d'),
    'supplier_name': 'Test Supplier',
    'payment_method': 'CASH',
    'items-0-raw_material_name': 'Flour 1kg',
    'items-0-quantity': '5',
    'items-0-price_before_tax': '10',
    'items-0-tax': '0',
}
resp = client.post('/purchases', data=purchase_payload, follow_redirects=True)
out.append(('create_purchase', resp.status_code))

# 3) Payments page loads
resp = client.get('/payments')
out.append(('payments', resp.status_code))

# 4) Inventory page loads
resp = client.get('/inventory')
out.append(('inventory', resp.status_code))

# 5) Bulk pay unpaid purchases
resp = client.post('/api/payments/pay_all', json={'type':'purchase','payment_method':'CASH'})
out.append(('bulk_pay', resp.status_code))

for k,v in out:
    print(f"{k}:{v}")
