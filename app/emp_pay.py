from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Employee, Salary, Payment, JournalEntry, JournalLine, Account
from models import get_saudi_now

emp_pay_bp = Blueprint('emp_pay', __name__)

def _ensure_salary(emp_id: int, year: int, month: int) -> Salary:
    s = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
    if s:
        return s
    today = get_saudi_now().date()
    if (year > today.year) or (year == today.year and month > today.month):
        return None
    try:
        from models import EmployeeSalaryDefault
        d = EmployeeSalaryDefault.query.filter_by(employee_id=int(emp_id)).first()
        if not d:
            return None
        base = float(getattr(d, 'base_salary', 0.0) or 0.0)
        allow = float(getattr(d, 'allowances', 0.0) or 0.0)
        ded = float(getattr(d, 'deductions', 0.0) or 0.0)
        total = max(0.0, base + allow - ded)
        if total <= 0 and base <= 0 and allow <= 0 and ded <= 0:
            return None
    except Exception:
        return None
    s = Salary(employee_id=emp_id, year=year, month=month,
               basic_salary=base, allowances=allow, deductions=ded,
               previous_salary_due=0.0, total_salary=total, status='due')
    db.session.add(s); db.session.flush()
    return s

def _post_ledger_safe(date_val, code, name, typ, dr, cr, ref):
    try:
        from app.routes import _post_ledger
        _post_ledger(date_val, code, name, typ, dr, cr, ref)
    except Exception:
        pass

def _pm_account(method: str):
    try:
        from app.routes import _pm_account as _pm
        return _pm(method)
    except Exception:
        return None

@emp_pay_bp.route('/api/employees/pay-health', methods=['GET'])
@login_required
def api_employee_pay_health():
    try:
        cnt = int(Employee.query.count())
        return jsonify({'ok': True, 'employees': cnt, 'time': get_saudi_now().isoformat()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@emp_pay_bp.route('/api/employees/pay-summary', methods=['GET'])
@login_required
def api_employee_pay_summary():
    try:
        ids_raw = (request.args.get('ids') or '').strip()
        month_raw = (request.args.get('month') or '').strip() or get_saudi_now().strftime('%Y-%m')
        try:
            y, m = month_raw.split('-'); year = int(y); month = int(m)
        except Exception:
            year = get_saudi_now().year; month = get_saudi_now().month
        if ids_raw:
            emp_ids = [int(x) for x in ids_raw.split(',') if x.strip().isdigit()]
        else:
            emp_ids = [int(e.id) for e in Employee.query.all()]
        rows = []
        for emp_id in emp_ids:
            sal = Salary.query.filter_by(employee_id=emp_id, year=year, month=month).first()
            if not sal:
                sal = _ensure_salary(emp_id, year, month)
            if not sal:
                continue
            emp = Employee.query.get(emp_id)
            total = float(sal.total_salary or 0.0)
            basic = float(sal.basic_salary or 0.0)
            paid = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                         .filter(Payment.invoice_type=='salary', Payment.invoice_id==sal.id).scalar() or 0.0)
            remaining = max(0.0, total - paid)
            rows.append({'id': emp_id, 'salary_id': int(sal.id), 'name': getattr(emp, 'full_name', ''), 'dept': getattr(emp, 'department', ''), 'basic': basic, 'total': total, 'paid': paid, 'remaining': remaining, 'status': sal.status or 'due'})
        return jsonify({'ok': True, 'rows': rows, 'month': f'{year}-{str(month).zfill(2)}'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@emp_pay_bp.route('/api/employees/pay-salary', methods=['POST'])
@login_required
def api_employee_pay_salary():
    try:
        emp_id = request.form.get('employee_id', type=int)
        month_raw = (request.form.get('month') or '').strip() or get_saudi_now().strftime('%Y-%m')
        amount = float(request.form.get('paid_amount') or 0)
        method = (request.form.get('payment_method') or 'cash').strip().lower()
        notes = (request.form.get('notes') or '').strip()
        if not emp_id:
            return jsonify({'ok': False, 'error': 'employee_required'}), 400
        try:
            y, m = month_raw.split('-'); year = int(y); month = int(m)
        except Exception:
            year = get_saudi_now().year; month = get_saudi_now().month
        emp = Employee.query.get(emp_id)
        if not emp:
            return jsonify({'ok': False, 'error': 'employee_not_found'}), 404
        sal = _ensure_salary(emp_id, year, month)
        if not sal:
            today = get_saudi_now().date()
            if (year > today.year) or (year == today.year and month > today.month):
                return jsonify({'ok': False, 'error': 'future_month_not_allowed'}), 400
            return jsonify({'ok': False, 'error': 'salary_not_initialized'}), 400
        already = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                        .filter(Payment.invoice_type=='salary', Payment.invoice_id==sal.id).scalar() or 0.0)
        remaining = max(0.0, float(sal.total_salary or 0.0) - already)
        if amount <= 0:
            return jsonify({'ok': False, 'error': 'amount_required'}), 400
        pay_val = amount if remaining <= 0 or amount <= remaining else remaining
        p = Payment(invoice_id=sal.id, invoice_type='salary', amount_paid=pay_val,
                    payment_method=method, payment_date=get_saudi_now())
        db.session.add(p); db.session.flush()

        cash_acc = _pm_account(method)
        try:
            from app.routes import SHORT_TO_NUMERIC, CHART_OF_ACCOUNTS
            liab_code = SHORT_TO_NUMERIC['PAYROLL_LIAB'][0]
            _post_ledger_safe(get_saudi_now().date(), liab_code, CHART_OF_ACCOUNTS[liab_code]['name'], 'liability', pay_val, 0.0, f'PAY SAL {year}-{month} EMP {emp_id}')
            if cash_acc:
                _post_ledger_safe(get_saudi_now().date(), cash_acc.code, cash_acc.name, 'asset', 0.0, pay_val, f'PAY SAL {year}-{month} EMP {emp_id}')
        except Exception:
            pass

        try:
            from app.routes import SHORT_TO_NUMERIC
            liab_code = SHORT_TO_NUMERIC['PAYROLL_LIAB'][0]
            liab_acc = Account.query.filter_by(code=liab_code).first()
            if liab_acc and cash_acc:
                je = JournalEntry(
                    entry_number=f"JE-SALPAY-{int(sal.id)}",
                    date=get_saudi_now().date(),
                    branch_code=None,
                    description=f"Salary payment {year}-{month} EMP {emp_id}",
                    status='posted',
                    total_debit=pay_val,
                    total_credit=pay_val,
                    created_by=getattr(current_user, 'id', None),
                    posted_by=getattr(current_user, 'id', None),
                    salary_id=int(sal.id)
                )
                db.session.add(je); db.session.flush()
                db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=int(liab_acc.id), debit=pay_val, credit=0.0, description='Payroll liability', line_date=get_saudi_now().date(), employee_id=int(emp_id)))
                db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=int(cash_acc.id), debit=0.0, credit=pay_val, description='Cash/Bank', line_date=get_saudi_now().date(), employee_id=int(emp_id)))
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

        already += pay_val
        total = float(sal.total_salary or 0.0)
        if total > 0 and already >= total:
            sal.status = 'paid'
        elif already > 0:
            sal.status = 'partial'
        else:
            sal.status = 'due'
        db.session.commit()
        current_app.logger.info(f"Salary paid: emp={emp_id} month={year}-{month} amount={pay_val}")
        return jsonify({'ok': True, 'payment_id': int(p.id), 'status': sal.status, 'paid': already, 'total': total, 'remaining': max(0.0, total - already)})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        current_app.logger.error(f"Salary payment failed: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 400

@emp_pay_bp.route('/api/employees/pay-salary-bulk', methods=['POST'])
@login_required
def api_employee_pay_salary_bulk():
    try:
        ids_raw = (request.form.get('employee_ids') or '').strip()
        amount_per = float(request.form.get('paid_amount') or 0)
        month_raw = (request.form.get('month') or '').strip() or get_saudi_now().strftime('%Y-%m')
        method = (request.form.get('payment_method') or 'cash').strip().lower()
        notes = (request.form.get('notes') or '').strip()
        try:
            y, m = month_raw.split('-'); year = int(y); month = int(m)
        except Exception:
            year = get_saudi_now().year; month = get_saudi_now().month
        if amount_per <= 0:
            return jsonify({'ok': False, 'error': 'amount_required'}), 400
        if ids_raw.lower() == 'all' or not ids_raw:
            emp_ids = [int(e.id) for e in Employee.query.all()]
        else:
            emp_ids = [int(x) for x in ids_raw.split(',') if x.strip().isdigit()]
        success = 0; failed = 0
        for emp_id in emp_ids:
            try:
                with db.session.begin_nested():
                    sal = _ensure_salary(emp_id, year, month)
                    if not sal:
                        failed += 1
                        continue
                    already = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                                    .filter(Payment.invoice_type=='salary', Payment.invoice_id==sal.id).scalar() or 0.0)
                    remaining = max(0.0, float(sal.total_salary or 0.0) - already)
                    pay_val = amount_per if remaining <= 0 or amount_per <= remaining else remaining
                    if pay_val <= 0:
                        failed += 1; continue
                    p = Payment(invoice_id=sal.id, invoice_type='salary', amount_paid=pay_val,
                                payment_method=method, payment_date=get_saudi_now())
                    db.session.add(p); db.session.flush()
                    cash_acc = _pm_account(method)
                    try:
                        from app.routes import SHORT_TO_NUMERIC, CHART_OF_ACCOUNTS
                        liab_code = SHORT_TO_NUMERIC['PAYROLL_LIAB'][0]
                        _post_ledger_safe(get_saudi_now().date(), liab_code, CHART_OF_ACCOUNTS[liab_code]['name'], 'liability', pay_val, 0.0, f'PAY SAL {year}-{month} EMP {emp_id}')
                        if cash_acc:
                            _post_ledger_safe(get_saudi_now().date(), cash_acc.code, cash_acc.name, 'asset', 0.0, pay_val, f'PAY SAL {year}-{month} EMP {emp_id}')
                    except Exception:
                        pass
                    try:
                        from app.routes import SHORT_TO_NUMERIC
                        liab_code = SHORT_TO_NUMERIC['PAYROLL_LIAB'][0]
                        liab_acc = Account.query.filter_by(code=liab_code).first()
                        if liab_acc and cash_acc:
                            je = JournalEntry(
                                entry_number=f"JE-SALPAY-{int(sal.id)}",
                                date=get_saudi_now().date(),
                                branch_code=None,
                                description=f"Salary payment {year}-{month} EMP {emp_id}",
                                status='posted',
                                total_debit=pay_val,
                                total_credit=pay_val,
                                created_by=getattr(current_user, 'id', None),
                                posted_by=getattr(current_user, 'id', None),
                                salary_id=int(sal.id)
                            )
                            db.session.add(je); db.session.flush()
                            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=int(liab_acc.id), debit=pay_val, credit=0.0, description='Payroll liability', line_date=get_saudi_now().date(), employee_id=int(emp_id)))
                            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=int(cash_acc.id), debit=0.0, credit=pay_val, description='Cash/Bank', line_date=get_saudi_now().date(), employee_id=int(emp_id)))
                    except Exception:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                    # Update status for bulk item
                    already += pay_val
                    total = float(sal.total_salary or 0.0)
                    if total > 0 and already >= total:
                        sal.status = 'paid'
                    elif already > 0:
                        sal.status = 'partial'
                    else:
                        sal.status = 'due'
                    success += 1
            except Exception:
                failed += 1
        db.session.commit()
        current_app.logger.info(f"Bulk salary paid: month={year}-{month} success={success} failed={failed}")
        return jsonify({'ok': True, 'success_count': success, 'failed_count': failed})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        current_app.logger.error(f"Bulk salary payment failed: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 400
