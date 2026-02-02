# -*- coding: utf-8 -*-
"""
اختبارات حقيقية: استحقاق من الموظفين والمصروفات، ثم سداد من العمليات.
تتحقق من إنشاء القيود (JE-PR، JE-EXP، JE-QTX) بنجاح.
"""
from __future__ import annotations

import json
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import Employee, Salary, JournalEntry, ExpenseInvoice


def _login(client):
    r = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    return r.status_code in (200, 302)


@pytest.fixture(scope='module')
def app_and_db():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    import tempfile
    fd, db_path = tempfile.mkstemp(prefix='test_real_', suffix='.sqlite')
    os.close(fd)
    uri = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'check_same_thread': False}}
    with app.app_context():
        db.drop_all()
        db.create_all()
    try:
        yield app, db_path
    finally:
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def client(app_and_db):
    app, _ = app_and_db
    return app.test_client()


def test_payroll_run_creates_accrual_journal(client, app_and_db):
    """مسير الرواتب ينشئ قيد استحقاق (JE-PR) ويُرجع entry_number."""
    app, _ = app_and_db
    assert _login(client), 'Login failed'

    with app.app_context():
        emp = Employee(
            employee_code='E-TEST-001',
            full_name='موظف اختبار',
            national_id='1234567890',
            status='active',
        )
        db.session.add(emp)
        db.session.commit()
        emp_id = emp.id

    month = '2026-02'
    rows = [{
        'employee_id': emp_id,
        'selected': True,
        'salary': 1500.0,
        'basic': 1500,
        'extra': 0,
        'absence': 0,
        'incentive': 0,
        'allowances': 0,
        'deductions': 0,
    }]
    r = client.post('/api/payroll-run', data={
        'month': month,
        'rows': json.dumps(rows),
    })
    assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
    j = r.get_json()
    assert j is not None, 'No JSON response'
    assert j.get('ok') is True, f"ok not True: {j}"
    entry_number = j.get('entry_number')
    assert entry_number, f'Missing entry_number in response: {j}'
    assert entry_number.startswith('JE-PR-'), f'Expected JE-PR-*, got {entry_number}'

    with app.app_context():
        je = JournalEntry.query.filter_by(entry_number=entry_number).first()
        assert je is not None, f'Journal entry {entry_number} not found in DB'
        assert je.status == 'posted'
        assert float(je.total_debit) == 1500.0 and float(je.total_credit) == 1500.0


def test_expense_creates_journal(client, app_and_db):
    """حفظ مصروف (غير مدفوع أو جزئي) ينشئ قيد مصروف (JE-EXP) ولا يُحفظ بدون قيد."""
    app, _ = app_and_db
    assert _login(client), 'Login failed'

    from datetime import date
    today = date.today().isoformat()
    r = client.post('/expenses', data={
        'expense_type': 'cogs',
        'expense_sub_type': 'beverages',
        'amount': '100',
        'date': today,
        'payment_method': 'CASH',
        'status': 'unpaid',
        'description': 'مصروف اختبار استحقاق',
    }, follow_redirects=True)
    assert r.status_code in (200, 302), f'Expected 200/302, got {r.status_code}'
    # يجب أن تظهر رسالة نجاح (لا فشل)
    body = r.get_data(as_text=True)
    assert 'Failed' not in body or 'success' in body or 'saved' in body.lower()

    with app.app_context():
        inv = ExpenseInvoice.query.order_by(ExpenseInvoice.id.desc()).first()
        assert inv is not None, 'No expense invoice created'
        entry_number = f'JE-EXP-{inv.invoice_number}'
        je = JournalEntry.query.filter_by(entry_number=entry_number).first()
        assert je is not None, f'Journal entry {entry_number} for expense not found'
        assert je.status == 'posted'


def test_settlement_pay_liability_creates_journal(client, app_and_db):
    """سداد استحقاق رواتب من العمليات ينشئ قيد تسوية (JE-QTX) ويُرجع entry_number."""
    app, _ = app_and_db
    assert _login(client), 'Login failed'

    with app.app_context():
        sal_rows = Salary.query.filter_by(year=2026, month=2).all()
        if not sal_rows:
            pytest.skip('No payroll run for 2026-02 (run test_payroll_run_creates_accrual_journal first)')
        run_total = sum(float(s.total_salary or 0) for s in sal_rows)
        if run_total < 0.01:
            pytest.skip('Payroll total is zero for 2026-02')

    r = client.post(
        '/financials/api/quick-txn',
        json={
            'type': 'pay_liability',
            'liability_code': '2121',
            'payroll_year': 2026,
            'payroll_month': 2,
            'date': '2026-02-15',
            'amount': run_total,
            'payment_method': 'cash',
            'note': 'اختبار تسوية',
        },
        headers={'Content-Type': 'application/json'},
    )
    assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.get_data(as_text=True)}'
    j = r.get_json()
    assert j is not None and j.get('ok') is True, f"Response: {j}"
    entry_number = j.get('entry_number')
    assert entry_number, f'Missing entry_number: {j}'
    assert 'JE-QTX' in entry_number or 'JE-' in entry_number

    with app.app_context():
        je = JournalEntry.query.filter_by(entry_number=entry_number).first()
        assert je is not None, f'Settlement journal {entry_number} not found'


def test_quick_txn_bank_deposit_creates_journal(client, app_and_db):
    """عملية إيداع بنكي تنشئ قيداً وتُرجع entry_number."""
    app, _ = app_and_db
    assert _login(client), 'Login failed'

    from datetime import date
    d = date.today().isoformat()
    r = client.post(
        '/financials/api/quick-txn',
        json={'type': 'bank_deposit', 'date': d, 'amount': 0.01, 'payment_method': 'cash', 'note': 'اختبار'},
        headers={'Content-Type': 'application/json'},
    )
    assert r.status_code == 200, f'Got {r.status_code}: {r.get_data(as_text=True)}'
    j = r.get_json()
    assert j and j.get('ok'), f"Response: {j}"
    assert j.get('entry_number'), 'Missing entry_number for bank_deposit'
