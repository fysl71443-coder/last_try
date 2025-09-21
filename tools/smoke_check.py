import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app import create_app, db
# Legacy models (extensions.db) for HR
try:
    from models import Employee
except Exception:
    Employee = None

# Ensure local settings
os.environ.setdefault('DATABASE_URL', 'sqlite:///local.db')
os.environ.setdefault('SECRET_KEY', 'dev')

app = create_app()

results = {}
with app.app_context():
    db.create_all()

with app.test_client() as c:
    # Hit login page (GET)
    r = c.get('/login')
    results['GET /login'] = r.status_code

    # First login attempt: create default admin if DB empty
    r = c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    results['POST /login admin/admin123'] = r.status_code

    # Helper to extract CSRF token from forms
    def get_csrf_token(html: str) -> str:
        token = ''
        try:
            marker = 'name="csrf_token"'
            i = html.find(marker)
            if i != -1:
                # search forward after marker for the next value="..."
                vpos = html.find('value="', i)
                if vpos != -1:
                    vstart = vpos + len('value="')
                    vend = html.find('"', vstart)
                    token = html[vstart:vend]
        except Exception:
            token = ''
        return token

    # Authenticated routes (GET)
    for path in [
        '/dashboard',
        '/financials/income-statement',
        '/expenses',
        '/settings',
        '/sales',
        '/sales/china_town/tables',
        '/pos/china_town/table/1',
        '/vat/?year=2025&quarter=3',
        '/vat/print?year=2025&quarter=3',
        '/financials/balance-sheet',
        '/financials/trial-balance',
        '/financials/balance-sheet/print',
        '/financials/trial-balance/print',
        # Newly added endpoints to avoid 404s seen in logs
        '/api/all-invoices?payment_method=cash',
        '/api/reports/all-purchases?payment_method=cash',
        '/api/all-expenses?payment_method=cash',
        '/reports/print/all-invoices/sales?payment_method=cash',
        # Additional screens for comprehensive check (GET only)
        '/customers',
        '/suppliers',
        '/menu',
        '/reports',
        '/invoices',
        '/payments',
        '/inventory',
        '/meals',
        '/raw-materials',
        '/users',
        '/table-settings',
    ]:
        rr = c.get(path)
        results[f'GET {path}'] = rr.status_code

    # POST flows
    # 1) Add Supplier
    page = c.get('/suppliers')
    token = get_csrf_token(page.get_data(as_text=True))
    rr = c.post('/suppliers', data={
        'csrf_token': token,
        'name': 'Test Supplier',
        'phone': '0500000000',
        'email': 'sup@example.com',
        'tax_number': '1234567890',
        'address': 'Riyadh',
        'active': 'on'
    }, follow_redirects=True)
    results['POST /suppliers add'] = rr.status_code

    # 2) Add Customer
    page = c.get('/customers')
    token = get_csrf_token(page.get_data(as_text=True))
    rr = c.post('/customers', data={
        'csrf_token': token,
        'name': 'Walk-in Test',
        'phone': '0551112222',
        'discount_percent': '0'
    }, follow_redirects=True)
    results['POST /customers add'] = rr.status_code

    # 3) Create Purchase Invoice (1 item)
    page = c.get('/purchases')
    token = get_csrf_token(page.get_data(as_text=True))
    rr = c.post('/purchases', data={
        'csrf_token': token,
        'date': '2025-01-15',
        'payment_method': 'cash',
        'supplier_name': 'Test Supplier',
        'items-0-item_name': 'Flour',
        'items-0-quantity': '5',
        'items-0-price_before_tax': '10.5',
        'items-0-discount': '0',
        'items-0-tax_pct': '15',
    }, follow_redirects=True)
    results['POST /purchases create'] = rr.status_code

    # 4) Create Expense Invoice (1 item)
    page = c.get('/expenses')
    token = get_csrf_token(page.get_data(as_text=True))
    rr = c.post('/expenses', data={
        'csrf_token': token,
        'date': '2025-01-16',
        'payment_method': 'cash',
        'items-0-description': 'Electricity Bill',
        'items-0-quantity': '1',
        'items-0-price_before_tax': '300',
        'items-0-tax': '0',
        'items-0-discount': '0',
    }, follow_redirects=True)
    results['POST /expenses create'] = rr.status_code

    # 5) Create Employee and Salary
    page = c.get('/employees')
    token = get_csrf_token(page.get_data(as_text=True))
    import time
    unique = str(int(time.time()))
    rr = c.post('/employees', data={
        'csrf_token': token,
        'employee_code': 'E' + unique,
        'full_name': 'Employee ' + unique,
        'national_id': unique,
        'department': 'Kitchen',
        'position': 'Chef',
        'phone': '0553334444',
        'email': f'emp{unique}@example.com',
        'hire_date': '2024-12-01',
        'status': 'active',
        'base_salary': '3000',
        'allowances': '500',
        'deductions': '100'
    }, follow_redirects=True)
    results['POST /employees add'] = rr.status_code

    # Create Salary for the most recently created employee
    page = c.get('/employees')
    token = get_csrf_token(page.get_data(as_text=True))
    emp_id = '1'
    try:
        if Employee is not None:
            with app.app_context():
                cnt = Employee.query.count()
                last_emp = Employee.query.order_by(Employee.id.desc()).first()
                if last_emp:
                    emp_id = str(last_emp.id)
                print('Employees in DB:', cnt, 'Using employee_id:', emp_id)
    except Exception as ex:
        print('Error fetching Employee from DB:', ex)
    rr = c.post('/employees/create-salary', data={
        'csrf_token': token,
        'employee_id': emp_id,
        'year': '2025',
        'month': '1',
        'basic_salary': '3000',
        'allowances': '500',
        'deductions': '100',
        'previous_salary_due': '0'
    })
    results['POST /employees/create-salary'] = rr.status_code
    if rr.status_code != 200:
        try:
            print('POST /employees/create-salary body:', rr.get_data(as_text=True)[:500])
        except Exception:
            pass

# Print concise report
for k,v in results.items():
    print(f'{k}: {v}')

