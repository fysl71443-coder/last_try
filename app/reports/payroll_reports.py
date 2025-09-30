from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db

# Try multiple model import paths for compatibility
try:
    from models import Employee, Salary, Payment, EmployeeSalaryDefault, DepartmentRate, EmployeeHours
except Exception:
    try:
        from app.models import Employee, Salary, Payment, EmployeeSalaryDefault, DepartmentRate, EmployeeHours
    except Exception:
        Employee = None
        Salary = None
        Payment = None
        EmployeeSalaryDefault = None

reports_bp = Blueprint("reports", __name__)


def _defaults_for(emp_id):
    try:
        d = EmployeeSalaryDefault.query.filter_by(employee_id=emp_id).first()
        if d:
            return float(d.base_salary or 0.0), float(d.allowances or 0.0), float(d.deductions or 0.0)
    except Exception:
        pass
    return 0.0, 0.0, 0.0


def prepare_employee_summary(employees, y_from=None, m_from=None, y_to=None, m_to=None):
    data = []
    for emp in employees:
        # Sum from Salary table within optional range
        q = Salary.query.filter_by(employee_id=emp.id)
        try:
            if y_from and m_from:
                q = q.filter((Salary.year * 100 + Salary.month) >= (int(y_from) * 100 + int(m_from)))
            if y_to and m_to:
                q = q.filter((Salary.year * 100 + Salary.month) <= (int(y_to) * 100 + int(m_to)))
        except Exception:
            pass
        rows = q.all() if Salary else []
        # If no rows, provide defaults-based single synthetic row for totals
        if not rows:
            b, a, d = _defaults_for(emp.id)
            prev = 0.0
            tot = b + a - d + prev
            paid = 0.0
            remaining = tot
            unpaid_months = 1 if remaining > 0 else 0
            data.append({
                "id": emp.id,
                "name": getattr(emp, 'full_name', '') or getattr(emp, 'employee_code', ''),
                "unpaid_months": unpaid_months,
                "basic_total": b,
                "allowances_total": a,
                "deductions_total": d,
                "prev_due": prev,
                "total": tot,
                "paid": paid,
                "remaining": remaining,
            })
            continue
        basic_total = sum(float(r.basic_salary or 0.0) for r in rows)
        allowances_total = sum(float(r.allowances or 0.0) for r in rows)
        deductions_total = sum(float(r.deductions or 0.0) for r in rows)
        prev_due = sum(float(r.previous_salary_due or 0.0) for r in rows)
        total = sum(float(r.total_salary or 0.0) for r in rows)
        paid = 0.0
        for r in rows:
            try:
                paid += float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                              .filter(Payment.invoice_type == 'salary', Payment.invoice_id == r.id).scalar() or 0.0)
            except Exception:
                pass
        remaining = max(total - paid, 0.0)
        unpaid_months = 0
        for r in rows:
            try:
                rp = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                           .filter(Payment.invoice_type == 'salary', Payment.invoice_id == r.id).scalar() or 0.0)
            except Exception:
                rp = 0.0
            rtot = float(r.total_salary or 0.0)
            if (rtot - rp) > 0.01:
                unpaid_months += 1
        data.append({
            "id": emp.id,
            "name": getattr(emp, 'full_name', '') or getattr(emp, 'employee_code', ''),
            "unpaid_months": unpaid_months,
            "basic_total": basic_total,
            "allowances_total": allowances_total,
            "deductions_total": deductions_total,
            "prev_due": prev_due,
            "total": total,
            "paid": paid,
            "remaining": remaining,
        })
    return data


def prepare_employee_detail(emp, y_from=None, m_from=None, y_to=None, m_to=None):
    q = Salary.query.filter_by(employee_id=emp.id)
    try:
        if y_from and m_from:
            q = q.filter((Salary.year * 100 + Salary.month) >= (int(y_from) * 100 + int(m_from)))
        if y_to and m_to:
            q = q.filter((Salary.year * 100 + Salary.month) <= (int(y_to) * 100 + int(m_to)))
    except Exception:
        pass
    rows = q.order_by(Salary.year.asc(), Salary.month.asc()).all() if Salary else []
    if not rows:
        b, a, d = _defaults_for(emp.id)
        prev = 0.0
        tot = b + a - d + prev
        paid = 0.0
        remaining = tot
        unpaid_months = 1 if remaining > 0 else 0
        return {
            "id": emp.id,
            "name": getattr(emp, 'full_name', '') or getattr(emp, 'employee_code', ''),
            "unpaid_months": unpaid_months,
            "basic_total": b,
            "allowances_total": a,
            "deductions_total": d,
            "prev_due": prev,
            "total": tot,
            "paid": paid,
            "remaining": remaining,
            "months": []
        }
    months = []
    basic_total = allowances_total = deductions_total = prev_due = total = paid_total = 0.0
    unpaid_months = 0
    for r in rows:
        b = float(r.basic_salary or 0.0); a = float(r.allowances or 0.0); d = float(r.deductions or 0.0)
        prev = float(r.previous_salary_due or 0.0)
        tt = float(r.total_salary or (b + a - d + prev))
        try:
            rp = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount_paid), 0))
                       .filter(Payment.invoice_type == 'salary', Payment.invoice_id == r.id).scalar() or 0.0)
        except Exception:
            rp = 0.0
        rem = max(tt - rp, 0.0)
        status = 'paid' if rem <= 0.01 and tt > 0 else ('partial' if rp > 0 else 'due')
        if status != 'paid':
            unpaid_months += 1
        months.append({
            "year": int(r.year),
            "month": int(r.month),
            "basic": b,
            "allowances": a,
            "deductions": d,
            "prev_due": prev,
            "total": tt,
            "paid": rp,
            "remaining": rem,
            "status": status,
        })
        basic_total += b; allowances_total += a; deductions_total += d; prev_due += prev; total += tt; paid_total += rp
    return {
        "id": emp.id,
        "name": getattr(emp, 'full_name', '') or getattr(emp, 'employee_code', ''),
        "unpaid_months": unpaid_months,
        "basic_total": basic_total,
        "allowances_total": allowances_total,
        "deductions_total": deductions_total,
        "prev_due": prev_due,
        "total": total,
        "paid": paid_total,
        "remaining": max(total - paid_total, 0.0),
        "months": months
    }


def calc_grand_totals(employees):
    return {
        "basic": sum(e.get("basic_total", 0.0) for e in employees),
        "allowances": sum(e.get("allowances_total", 0.0) for e in employees),
        "deductions": sum(e.get("deductions_total", 0.0) for e in employees),
        "prev_due": sum(e.get("prev_due", 0.0) for e in employees),
        "total": sum(e.get("total", 0.0) for e in employees),
        "paid": sum(e.get("paid", 0.0) for e in employees),
        "remaining": sum(e.get("remaining", 0.0) for e in employees),
    }


@reports_bp.route("/payroll/report", methods=["GET"])
def payroll_report():
    if not Employee or not Salary or not Payment:
        flash('Payroll models not available', 'danger')
        return redirect(url_for('main.employees'))
    # period params
    y_from = request.args.get('year_from', type=int) or 2025
    m_from = request.args.get('month_from', type=int) or 1
    y_to = request.args.get('year_to', type=int) or 2025
    m_to = request.args.get('month_to', type=int) or 12

    # If print=1, show printable report; otherwise show selection UI
    if request.args.get('print', type=int) == 1:
        employees = prepare_employee_summary(Employee.query.order_by(Employee.full_name.asc()).all(), y_from, m_from, y_to, m_to)
        grand = calc_grand_totals(employees)
        return render_template("payroll-reports.html",
                               employees=employees,
                               grand=grand,
                               mode="all",
                               start_year=y_from, start_month=m_from,
                               end_year=y_to, end_month=m_to,
                               auto_print=True,
                               close_after_print=True,
                               report_title='🧾 Detailed Payroll Report / تقرير الرواتب التفصيلي')

    # Selection UI (lets the user pick employees then post to selected)
    all_employees = Employee.query.order_by(Employee.full_name.asc()).all()
    return render_template("payroll_report_select.html",
                           employees=all_employees,
                           start_year=y_from, start_month=m_from,
                           end_year=y_to, end_month=m_to)


@reports_bp.route("/payroll/report/employee/<int:emp_id>", methods=["GET"])
def payroll_report_employee(emp_id):
    if not Employee or not Salary or not Payment:
        flash('Payroll models not available', 'danger')
        return redirect(url_for('main.employees'))
    y_from = request.args.get('year_from', type=int) or 2025
    m_from = request.args.get('month_from', type=int) or 1
    y_to = request.args.get('year_to', type=int) or 2025
    m_to = request.args.get('month_to', type=int) or 12
    emp = Employee.query.get_or_404(emp_id)
    data = prepare_employee_detail(emp, y_from, m_from, y_to, m_to)
    return render_template("payroll-reports.html",
                           employees=[data],
                           grand=None,
                           mode="single",
                           start_year=y_from, start_month=m_from,
                           end_year=y_to, end_month=m_to,
                           auto_print=True,
                           close_after_print=True,
                           report_title='🧾 Detailed Payroll Report / تقرير الرواتب التفصيلي')


@reports_bp.route("/payroll/report/selected", methods=["POST"])
def payroll_report_selected():
    if not Employee or not Salary or not Payment:
        flash('Payroll models not available', 'danger')
        return redirect(url_for('main.employees'))
    ids_raw = (request.form.get("employee_ids") or '').strip()
    ids = []
    for i in (ids_raw.split(',') if ids_raw else []):
        try:
            ids.append(int(i.strip()))
        except Exception:
            continue
    y_from = request.form.get('year_from', type=int) or 2025
    m_from = request.form.get('month_from', type=int) or 1
    y_to = request.form.get('year_to', type=int) or 2025
    m_to = request.form.get('month_to', type=int) or 12
    if not ids:
        return redirect(url_for('reports.payroll_report', year_from=y_from, month_from=m_from, year_to=y_to, month_to=m_to))
    employees = Employee.query.filter(Employee.id.in_(ids)).order_by(Employee.full_name.asc()).all()
    employees = prepare_employee_summary(employees, y_from, m_from, y_to, m_to)
    grand = calc_grand_totals(employees)
    return render_template("payroll-reports.html",
                           employees=employees,
                           grand=grand,
                           mode="selected",
                           start_year=y_from, start_month=m_from,
                           end_year=y_to, end_month=m_to,
                           auto_print=True,
                           close_after_print=True,
                           report_title='🧾 Detailed Payroll Report / تقرير الرواتب التفصيلي')
