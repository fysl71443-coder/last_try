import os
os.environ.setdefault('USE_EVENTLET','0')

from app import app, db
from flask import json

def main():
    results = {}
    with app.app_context():
        client = app.test_client()
        # Try to login if login route exists
        try:
            resp = client.post('/login', data={'username':'admin','password':'admin'}, follow_redirects=True)
            results['login_status'] = resp.status_code
        except Exception as e:
            results['login_error'] = str(e)

        # 1) Create draft for china_town table 2
        items = [{'id':1,'name':'Test Meal','price':10.0,'quantity':2}]
        resp = client.post('/api/draft-order/china_town/2', json={'items': items})
        results['create_draft_status'] = resp.status_code
        data = resp.get_json()
        results['create_draft_json'] = data
        draft_id = (data or {}).get('draft_id')

        # Verify table status becomes occupied in DB
        try:
            from models import Table
            t = Table.query.filter_by(branch_code='china_town', table_number='2').first()
            results['table_status_after_create'] = getattr(t, 'status', None)
        except Exception as e:
            results['table_status_after_create_error'] = str(e)

        # 2) Cancel draft and expect table available
        if draft_id:
            resp = client.post(f'/api/draft_orders/{draft_id}/cancel', json={'supervisor_password':'1991'})
            results['cancel_status'] = resp.status_code
            results['cancel_json'] = resp.get_json()

        try:
            from models import Table
            t = Table.query.filter_by(branch_code='china_town', table_number='2').first()
            results['table_status_after_cancel'] = getattr(t, 'status', None)
        except Exception as e:
            results['table_status_after_cancel_error'] = str(e)

        # 3) Recreate draft and checkout then confirm print
        resp = client.post('/api/draft-order/china_town/2', json={'items': items})
        data = resp.get_json() or {}
        draft_id = data.get('draft_id')
        results['recreate_draft_status'] = resp.status_code
        results['recreate_draft_json'] = data

        # Checkout draft
        if draft_id:
            resp = client.post('/api/draft/checkout', json={'draft_id': draft_id, 'customer_name':'','customer_phone':'','payment_method':'CASH','discount_pct':0})
            results['checkout_status'] = resp.status_code
            chk = resp.get_json() or {}
            results['checkout_json'] = chk
            invoice_id = chk.get('invoice_id')
            # Confirm print
            if invoice_id:
                total_amount = chk.get('total_amount', 0)
                resp = client.post('/api/invoice/confirm-print', json={'invoice_id': invoice_id, 'payment_method':'CASH', 'total_amount': total_amount})
                results['confirm_status'] = resp.status_code
                results['confirm_json'] = resp.get_json()

        # Table should be available now
        try:
            from models import Table
            t = Table.query.filter_by(branch_code='china_town', table_number='2').first()
            results['table_status_after_confirm'] = getattr(t, 'status', None)
        except Exception as e:
            results['table_status_after_confirm_error'] = str(e)

    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()

