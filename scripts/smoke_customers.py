from app import app

app.testing = True

print('--- Render customers.html directly ---')
with app.test_request_context('/customers'):
    from flask import render_template
    html = render_template('customers.html', customers=[], q='')
    print('Rendered customers.html length:', len(html))

print('--- HTTP GET /customers via test_client ---')
with app.test_client() as c:
    r = c.get('/customers')
    print('GET /customers status =', r.status_code)
    print('Body head =', r.data[:200])

