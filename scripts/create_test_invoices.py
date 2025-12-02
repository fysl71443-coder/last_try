from app import create_app
from extensions import db
from models import SalesInvoice, User
import random

def main():
    app = create_app()
    try:
        app.config['WTF_CSRF_ENABLED'] = False
    except Exception:
        pass
    with app.app_context():
        client = app.test_client()
        user = db.session.query(User).first()
        # Ensure admin user exists with known password
        if not user:
            user = User(username='admin', email='admin@example.com', role='admin')
            user.set_password('admin123')
            db.session.add(user); db.session.commit()
        client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
        client.get('/dashboard')
        csrf_token = None
        try:
            for c in client.cookie_jar:
                if c.name.lower() == 'csrf_token':
                    csrf_token = c.value
                    break
        except Exception:
            csrf_token = None

        payloads = []
        for i in range(10):
            items = [
                {'meal_id': None, 'name': f'Test Meal {i}-A', 'price': round(random.uniform(10,40),2), 'qty': random.randint(1,3)},
                {'meal_id': None, 'name': f'Test Meal {i}-B', 'price': round(random.uniform(5,30),2), 'qty': random.randint(1,2)}
            ]
            if i % 3 == 0:
                items.append({'meal_id': None, 'name': f'Test Meal {i}-C', 'price': round(random.uniform(8,25),2), 'qty': 1})
            disc_pct = 10.0 if (i % 2 == 0) else 0.0
            tax_pct = 15.0 if (i % 4 != 0) else 0.0
            payloads.append({
                'branch_code': 'china_town' if (i % 2 == 0) else 'place_india',
                'table_number': (i % 5) + 1,
                'items': items,
                'customer_name': 'KEETA' if (i % 5 == 0) else ('HUNGER' if (i % 7 == 0) else f'Test Cust {i}'),
                'customer_phone': '',
                'discount_pct': disc_pct,
                'tax_pct': tax_pct,
                'payment_method': 'CASH'
            })

        created_ids = []
        for p in payloads:
            headers = {}
            if csrf_token:
                headers['X-CSRFToken'] = csrf_token
            res = client.post('/api/sales/checkout', json=p, headers=headers)
            txt = None
            try:
                txt = res.get_data(as_text=True)
            except Exception:
                txt = None
            data = res.get_json(silent=True) or {}
            print('POST', res.status_code, data if data else txt)
            inv_no = data.get('invoice_id')
            if inv_no:
                created_ids.append(inv_no)
                # Fetch print page to verify currency display
                client.get(data.get('print_url','') or f"/receipt/print/{inv_no}")

        print('Created invoices:', created_ids)

        # Delete test invoices
        for inv_no in created_ids:
            inv = db.session.query(SalesInvoice).filter(SalesInvoice.invoice_number == inv_no).first()
            if inv:
                try:
                    db.session.delete(inv); db.session.commit()
                except Exception:
                    db.session.rollback()
        print('Deleted test invoices:', len(created_ids))

if __name__ == '__main__':
    main()
