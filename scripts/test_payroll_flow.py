from app import create_app
from extensions import db
from models import Employee, EmployeeSalaryDefault, EmployeeHours, Salary, Payment
from app.models import AppKV

def main():
    app = create_app()
    try:
        app.config['WTF_CSRF_ENABLED'] = False
    except Exception:
        pass
    with app.app_context():
        client = app.test_client()
        # ensure admin user and login
        from models import User
        u = User.query.filter_by(username='admin').first()
        if not u:
            u = User(username='admin', email='admin@example.com', role='admin')
            u.set_password('admin123')
            db.session.add(u); db.session.commit()
        client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
        # Create 5 test employees
        specs = [
            {'full_name':'ثابت الراتب', 'national_id':'900001', 'department':'admin', 'base_salary':3000.0, 'salary_type':'fixed'},
            {'full_name':'بالساعة', 'national_id':'900002', 'department':'hall', 'base_salary':0.0, 'salary_type':'hourly', 'hourly_rate':20.0},
            {'full_name':'سعودي', 'national_id':'900003', 'department':'admin', 'base_salary':3500.0, 'salary_type':'fixed'},
            {'full_name':'شيف', 'national_id':'900004', 'department':'kitchen', 'base_salary':0.0, 'salary_type':'hourly', 'hourly_rate':25.0},
            {'full_name':'كاشير', 'national_id':'900005', 'department':'hall', 'base_salary':2500.0, 'salary_type':'fixed'}
        ]
        ids = []
        for s in specs:
            fd = {
                'full_name': s['full_name'],
                'national_id': s['national_id'],
                'department': s['department'],
                'position': '',
                'hire_date': '2025-11-01',
                'branch_code': 'china_town',
                'base_salary': s['base_salary'],
                'salary_type': s.get('salary_type','fixed'),
                'hourly_rate': s.get('hourly_rate', 0)
            }
            r = client.post('/api/employees', data=fd)
            j = r.get_json() or {}
            print('create employee =>', j)
            ids.append(int(j.get('id')))

        # Record hours for hourly employees
        year, month = 2025, 11
        for emp_id in ids:
            kv = AppKV.get(f"emp_settings:{emp_id}") or {}
            if (kv.get('salary_type') or 'fixed') == 'hourly':
                row = EmployeeHours.query.filter_by(employee_id=emp_id, year=year, month=month).first()
                if not row:
                    row = EmployeeHours(employee_id=emp_id, year=year, month=month, hours=160.0)
                    db.session.add(row)
        db.session.commit()

        # Upsert salaries with incentives/deductions
        for emp_id in ids:
            fd = {
                'employee_id': emp_id,
                'month': f"{year:04d}-{month:02d}",
                'absence_hours': 4,
                'overtime_hours': 8,
                'bonus_amount': 100,
                'deduction_amount': 50
            }
            r = client.post('/api/salaries/upsert', data=fd)
            print('upsert salary =>', r.get_json() or r.status_code)

        # Add advances
        for emp_id in ids[:2]:
            fd = {'employee_id': emp_id, 'amount': 500, 'method': 'cash', 'date': f"{year:04d}-{month:02d}-10"}
            r = client.post('/api/advances', data=fd)
            print('advance =>', r.get_json() or r.status_code)

        # Pay partial and full
        # Partial for first employee
        r = client.post('/salaries/pay', data={'employee_id': ids[0], 'month': f"{year:04d}-{month:02d}", 'paid_amount': 800, 'payment_method':'cash'})
        print('pay partial =>', r.status_code)
        # Full group payment for department hall
        r = client.post('/salaries/pay', data={'employee_id': 'all', 'department':'hall', 'month': f"{year:04d}-{month:02d}", 'paid_amount': 5000, 'payment_method':'bank'})
        print('pay dept =>', r.status_code)

        # Generate statements
        r = client.get(f"/api/salaries/statements?month={year:04d}-{month:02d}")
        print('statements =>', r.get_json() or r.status_code)

        # Cleanup test employees
        for emp_id in ids:
            client.delete(f"/api/employees/{emp_id}")
        print('cleanup done')

if __name__ == '__main__':
    main()
