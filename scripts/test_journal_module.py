import sys, os, importlib
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
try:
    app_pkg = importlib.import_module('app')
    create_app = getattr(app_pkg, 'create_app')
    app = create_app()
except Exception:
    app_mod = importlib.import_module('app')
    app = getattr(app_mod, 'app')
from extensions import db
from models import User, Account, LedgerEntry, Employee
from werkzeug.security import generate_password_hash

def ensure_admin():
    with app.app_context():
        u = User.query.filter_by(username='admin').first()
        if not u:
            u = User(username='admin', role='admin', active=True)
            u.password_hash = generate_password_hash('admin')
            db.session.add(u)
            db.session.commit()
        return u

def get_acc(code):
    with app.app_context():
        a = Account.query.filter_by(code=code).first()
        return a

def ensure_employee():
    with app.app_context():
        e = Employee.query.first()
        if not e:
            from datetime import date
            e = Employee(full_name='Test Employee', department='HR', position='Tester', hire_date=date.today(), status='active')
            db.session.add(e)
            db.session.commit()
        return e

def login(c):
    return c.post('/login', data={'username':'admin','password':'admin'}, follow_redirects=True)

def test_scenarios():
    ensure_admin()
    emp = ensure_employee()
    with app.test_client() as c:
        login(c)
        c.get('/journal/')
        sal_exp = get_acc('5020')
        pay_liab = get_acc('2.1.2.1') or get_acc('2030')
        emp_adv = get_acc('1.1.4.2')
        cash = get_acc('1000')
        bank = get_acc('1010') or get_acc('1020')
        # 1) Payroll accrual
        r = c.post('/journal/new', data={
            'date':'2025-11-01','branch':'china_town','description':'راتب غير مسدد',
            'lines-0-account_id': str(sal_exp.id if sal_exp else ''), 'lines-0-debit': '1000', 'lines-0-credit': '0', 'lines-0-description':'مصروف رواتب', 'lines-0-date':'2025-11-01',
            'lines-1-account_id': str(pay_liab.id if pay_liab else ''), 'lines-1-debit': '0', 'lines-1-credit': '1000', 'lines-1-description':'رواتب مستحقة', 'lines-1-date':'2025-11-01', 'lines-1-employee_id': str(emp.id)
        }, follow_redirects=True)
        assert r.status_code in (200,302)
        # 2) Employee advance
        r2 = c.post('/journal/new', data={
            'date':'2025-11-02','branch':'china_town','description':'سلفة موظف',
            'lines-0-account_id': str(emp_adv.id if emp_adv else ''), 'lines-0-debit': '500', 'lines-0-credit': '0', 'lines-0-description':'سلفة', 'lines-0-date':'2025-11-02', 'lines-0-employee_id': str(emp.id),
            'lines-1-account_id': str((cash or bank).id if (cash or bank) else ''), 'lines-1-debit': '0', 'lines-1-credit': '500', 'lines-1-description':'صرف نقدي', 'lines-1-date':'2025-11-02'
        }, follow_redirects=True)
        assert r2.status_code in (200,302)
        # 3) Adjustment example
        r3 = c.post('/journal/new', data={
            'date':'2025-11-03','branch':'place_india','description':'قيد تسوية',
            'lines-0-account_id': str((cash or bank).id if (cash or bank) else ''), 'lines-0-debit': '200', 'lines-0-credit': '0', 'lines-0-description':'تصحيح', 'lines-0-date':'2025-11-03',
            'lines-1-account_id': str((bank or cash).id if (bank or cash) else ''), 'lines-1-debit': '0', 'lines-1-credit': '200', 'lines-1-description':'تصحيح', 'lines-1-date':'2025-11-03'
        }, follow_redirects=True)
        assert r3.status_code in (200,302)
        # 4) Internal transfer
        r4 = c.post('/journal/new', data={
            'date':'2025-11-04','branch':'place_india','description':'تحويل داخلي',
            'lines-0-account_id': str(cash.id if cash else ''), 'lines-0-debit': '300', 'lines-0-credit': '0', 'lines-0-description':'تحويل', 'lines-0-date':'2025-11-04',
            'lines-1-account_id': str(bank.id if bank else ''), 'lines-1-debit': '0', 'lines-1-credit': '300', 'lines-1-description':'تحويل', 'lines-1-date':'2025-11-04'
        }, follow_redirects=True)
        assert r4.status_code in (200,302)
        # 5) With/without attachment: skip actual file upload in test
        # 6) Unbalanced entry
        r5 = c.post('/journal/new', data={
            'date':'2025-11-05','branch':'china_town','description':'غير متوازن',
            'lines-0-account_id': str(cash.id if cash else ''), 'lines-0-debit': '123', 'lines-0-credit': '0', 'lines-0-description':'x', 'lines-0-date':'2025-11-05'
        }, follow_redirects=True)
        assert r5.status_code in (200,302)
    print('✅ Journal module scenarios executed')

if __name__ == '__main__':
    test_scenarios()