import os
import sys
import requests, re

BASE_URL = os.environ.get('POS_BASE_URL', 'http://127.0.0.1:5000')
BRANCH = os.environ.get('POS_BRANCH', 'china_town')  # 'china_town' or 'place_india'
TABLE = int(os.environ.get('POS_TABLE', '1'))
USERNAME = os.environ.get('POS_USER', 'admin')
PASSWORD = os.environ.get('POS_PASS', 'admin')

S = requests.Session()
CSRF_TOKEN = ''




def login():
    # Basic form login to obtain session cookies
    r = S.post(f"{BASE_URL}/login", data={
        'username': USERNAME,
        'password': PASSWORD,
    }, allow_redirects=True)
    r.raise_for_status()
    # After login, refresh CSRF token from any HTML page (tables page contains meta)
    refresh_csrf(BRANCH)
    return r


def refresh_csrf(branch: str):
    """Fetch CSRF token from a page meta tag and cache it in CSRF_TOKEN."""
    global CSRF_TOKEN
    # Use tables page which extends base.html and includes <meta name="csrf-token">
    r = S.get(f"{BASE_URL}/sales/{branch}/tables")
    r.raise_for_status()
    m = re.search(r'name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
    if m:
        CSRF_TOKEN = m.group(1)
        return CSRF_TOKEN
    # Fallback: try home page
    r2 = S.get(f"{BASE_URL}/")
    if r2.ok:
        m2 = re.search(r'name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']', r2.text, re.IGNORECASE)
        if m2:
            CSRF_TOKEN = m2.group(1)
            return CSRF_TOKEN
    CSRF_TOKEN = ''
    return CSRF_TOKEN



def get_table_status(branch: str, table_no: int) -> str:
    r = S.get(f"{BASE_URL}/api/tables/{branch}/{table_no}/status")
    r.raise_for_status()
    return r.json().get('status')


def get_or_create_draft(branch: str, table_no: int, items):
    """Create or update draft for a table and return draft_id."""
    # items format for /api/draft-order: [{'id':..., 'name':..., 'price':..., 'quantity':...}]
    r = S.post(f"{BASE_URL}/api/draft-order/{branch}/{table_no}", json={
        'items': items,
        'customer': {'name': '', 'phone': ''}
    })
    r.raise_for_status()
    data = r.json()
    if not data.get('success'):
        raise RuntimeError(f"Save draft failed: {data}")
    draft_id = data.get('draft_id')
    if not draft_id:
        # Fallback: GET current draft
        g = S.get(f"{BASE_URL}/api/draft-order/{branch}/{table_no}")
        g.raise_for_status()
        draft_id = g.json().get('draft_id')
    if not draft_id:
        raise RuntimeError('No draft_id obtained')
    return draft_id


def cancel_current_draft(draft_id: int, supervisor_password: str = '1991'):
    r = S.post(f"{BASE_URL}/api/draft_orders/{draft_id}/cancel", json={'supervisor_password': supervisor_password})
    r.raise_for_status()
    data = r.json()
    if not data.get('success'):
        raise RuntimeError(f"Cancel draft failed: {data}")
    return data


def checkout_draft(draft_id: int, payment_method: str = 'CASH'):
    payload = {
        'draft_id': draft_id,
        'customer_name': '',
        'customer_phone': '',
        'payment_method': payment_method,
        'discount_pct': 0
    }
    headers = {'X-CSRFToken': CSRF_TOKEN} if CSRF_TOKEN else None
    r = S.post(f"{BASE_URL}/api/draft/checkout", json=payload, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"Checkout failed HTTP {r.status_code}: {r.text}")
    data = r.json()
    if not data.get('ok'):
        raise RuntimeError(f"Checkout failed: {data}")
    return data


def confirm_print_payment(invoice_id: int, total_amount: float, payment_method: str = 'CASH'):
    headers = {'X-CSRFToken': CSRF_TOKEN} if CSRF_TOKEN else None
    r = S.post(f"{BASE_URL}/api/invoice/confirm-print", json={
        'invoice_id': invoice_id,
        'payment_method': payment_method,
        'total_amount': total_amount
    }, headers=headers)
    r.raise_for_status()
    data = r.json()
    if not data.get('ok'):
        raise RuntimeError(f"Confirm print failed: {data}")
    return data


def main():
    print(f"BASE_URL={BASE_URL}, BRANCH={BRANCH}, TABLE={TABLE}")
    login()

    # Test items: adapt IDs/names/prices to your DB
    items = [
        {'id': 1, 'name': 'Noodles', 'price': 50.0, 'quantity': 2}
    ]

    # --- Create draft (acts as 'create invoice' in table POS) ---
    draft_id = get_or_create_draft(BRANCH, TABLE, items)
    print(f"[CREATE] Draft created: id={draft_id}")
    status = get_table_status(BRANCH, TABLE)
    print(f"[TABLE STATUS] after create: {status}")
    assert status in ('occupied', 'reserved'), f"Unexpected status: {status}"

    # --- Cancel draft ---
    cancel_current_draft(draft_id)
    status = get_table_status(BRANCH, TABLE)
    print(f"[TABLE STATUS] after cancel: {status}")
    assert status == 'available', f"Expected 'available', got {status}"

    # --- Recreate draft and checkout (creates unpaid invoice) ---
    draft_id = get_or_create_draft(BRANCH, TABLE, items)
    chk = checkout_draft(draft_id)
    invoice_id = chk.get('invoice_id')
    total_amount = chk.get('total_amount')
    print(f"[CHECKOUT] invoice_id={invoice_id}, total_amount={total_amount}")

    # --- Confirm print (register payment) ---
    confirm_print_payment(invoice_id, total_amount, payment_method='CASH')
    status = get_table_status(BRANCH, TABLE)
    print(f"[TABLE STATUS] after payment: {status}")
    assert status == 'available', f"Expected 'available', got {status}"

    print("✅ All POS flow tests passed successfully!")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)

