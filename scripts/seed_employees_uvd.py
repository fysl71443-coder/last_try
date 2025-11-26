import os, sys
import random
from datetime import date, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db
from models import Employee, EmployeeSalaryDefault, Salary, Account, JournalEntry, JournalLine


def ensure_account(code: str, name: str):
    try:
        acc = Account.query.filter_by(code=code).first()
        if not acc:
            acc = Account(code=code, name=name, type='asset')
            db.session.add(acc)
            db.session.commit()
        return acc
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def seed_employees():
    depts = ['kitchen', 'hall', 'admin']
    statuses = ['active', 'on_leave', 'inactive']

    # Create 15 employees with mixed attributes
    created = []
    import time
    base_ts = int(time.time())
    for i in range(1, 16):
        full_name = f"موظف تجريبي {i:02d}"
        national_id = f"{base_ts}{i:04d}"
        dept = random.choice(depts)
        pos = {'kitchen':'شيف','hall':'طاولات','admin':'إداري'}.get(dept, 'إداري')
        phone = f"055{random.randint(1000000,9999999)}"
        email = f"emp{i:02d}@example.com"
        hire_dt = date.today() - timedelta(days=random.randint(30, 900))
        status = random.choice(statuses)
        base_salary = random.choice([2500, 3000, 3500, 4000])
        allowances = random.choice([0, 250, 500])
        deductions = random.choice([0, 100, 200])

        e = Employee(full_name=full_name,
                     national_id=national_id,
                     department=dept,
                     position=pos,
                     phone=phone,
                     email=email,
                     hire_date=hire_dt)
        db.session.add(e)
        db.session.flush()

        d = EmployeeSalaryDefault(employee_id=e.id,
                                  base_salary=base_salary,
                                  allowances=allowances,
                                  deductions=deductions)
        db.session.add(d)
        created.append((e, d))

    db.session.commit()
    return created


def seed_advances_for(employees):
    adv_acc = ensure_account('1030', 'سلف موظفين')
    if not adv_acc:
        return
    for e, _ in employees:
        # Create one or two advances per employee
        for k in range(random.choice([1,2])):
            je = JournalEntry(entry_number=f"ADV{random.randint(100000,999999)}",
                              date=date.today() - timedelta(days=random.randint(1,60)),
                              description=f"سلفة للموظف {e.full_name}",
                              status='posted')
            db.session.add(je)
            db.session.flush()

            amt = random.choice([200, 350, 500])
            jl_debit = JournalLine(journal_id=je.id,
                                   line_no=1,
                                   account_id=adv_acc.id,
                                   employee_id=e.id,
                                   line_date=je.date,
                                   description='منح سلفة',
                                   debit=amt,
                                   credit=0.0)
            jl_credit = JournalLine(journal_id=je.id,
                                    line_no=2,
                                    account_id=adv_acc.id,
                                    employee_id=e.id,
                                    line_date=je.date,
                                    description='سداد جزء',
                                    debit=0.0,
                                    credit=random.choice([0.0, amt/2]))
            db.session.add(jl_debit)
            db.session.add(jl_credit)
    db.session.commit()


def seed_salaries_for(employees):
    today = date.today()
    y, m = today.year, today.month
    for e, d in employees:
        # Current month salary
        total = (d.base_salary or 0) + (d.allowances or 0) - (d.deductions or 0) + random.choice([0, 150, 300])
        s = Salary(employee_id=e.id,
                   year=y,
                   month=m,
                   basic_salary=d.base_salary or 0,
                   allowances=d.allowances or 0,
                   deductions=d.deductions or 0,
                   previous_salary_due=max(0, total - ((d.base_salary or 0) + (d.allowances or 0) - (d.deductions or 0))),
                   total_salary=total,
                   status=random.choice(['due','partial','paid']))
        db.session.add(s)
    db.session.commit()


def main():
    os.environ.setdefault('DATABASE_URL', 'sqlite:///local.db')
    app = create_app()
    with app.app_context():
        db.create_all()
        emps = seed_employees()
        seed_advances_for(emps)
        seed_salaries_for(emps)
        print(f"✅ Seeded {len(emps)} employees with advances and salaries.")


if __name__ == '__main__':
    main()
