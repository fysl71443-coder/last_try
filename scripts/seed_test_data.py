#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إنشاء فواتير وعمليات اختبارية حقيقية لكل الشاشات داخل النظام.
يُنشئ: مبيعات، مشتريات، مصروفات، رواتب، ثم يقيد القيود اليومية (backfill).

تشغيل: من جذر المشروع
  python scripts/seed_test_data.py
  python scripts/seed_test_data.py --more   # إضافة دفعة جديدة ببادئة TEST2- حتى مع وجود TEST-*

إعادة التشغيل بدون --more تتخطى الفواتير ذات الأرقام الموجودة (TEST-SAL-001 ...).
"""
import os
import sys
import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('ENV', 'development')
os.environ.setdefault('USE_EVENTLET', '0')
instance_dir = os.path.join(ROOT, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.abspath(os.path.join(instance_dir, 'accounting_app.db'))
os.environ['LOCAL_SQLITE_PATH'] = db_path
os.environ['DATABASE_URL'] = 'sqlite:///' + db_path.replace('\\', '/')


def _d(x):
    return Decimal(str(x))


def main():
    parser = argparse.ArgumentParser(description="Seed test invoices and journal entries")
    parser.add_argument("--more", action="store_true", help="Add another batch with prefix TEST2- even if TEST-* exist")
    args = parser.parse_args()
    prefix = "TEST2" if args.more else "TEST"

    from app import create_app
    from extensions import db
    from models import (
        User, FiscalYear, Account,
        Customer, Supplier, RawMaterial, Employee, EmployeeSalaryDefault,
        SalesInvoice, SalesInvoiceItem,
        PurchaseInvoice, PurchaseInvoiceItem,
        ExpenseInvoice, ExpenseInvoiceItem,
        Salary,
        get_saudi_now,
    )

    app = create_app()
    with app.app_context():
        db.create_all()

        # --- 1) سنة مالية مفتوحة ---
        today = get_saudi_now().date()
        year = today.year
        if not FiscalYear.query.filter(FiscalYear.year == year).first():
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            fy = FiscalYear(year=year, year_name=str(year), start_date=start, end_date=end, status='open')
            db.session.add(fy)
            db.session.commit()
            print(f"Created fiscal year {year} (open)")
        else:
            print(f"Fiscal year {year} already exists")

        # --- 2) مستخدم ---
        user = User.query.filter_by(username='admin').first()
        if not user:
            from create_user import create_admin_user
            create_admin_user()
            user = User.query.filter_by(username='admin').first()
        if not user:
            user = User(username='admin', email='admin@example.com', role='admin', active=True)
            user.set_password('admin123')
            db.session.add(user)
            db.session.commit()
            print("Created admin user")
        user_id = user.id

        # --- 3) دليل الحسابات (مطلوب للقيود) ---
        try:
            from routes.journal import _ensure_journal_link_columns, _ensure_accounts
            _ensure_journal_link_columns()
            _ensure_accounts()
            print("COA / journal columns ensured")
        except Exception as e:
            print("COA ensure:", e)

        # --- 4) عملاء، موردون، مواد خام، موظفون ---
        customers = []
        for name, ctype in [('عميل نقدي 1', 'cash'), ('عميل آجل 1', 'credit'), ('KEETA', 'cash'), ('HUNGER', 'cash')]:
            c = Customer.query.filter_by(name=name).first()
            if not c:
                c = Customer(name=name, customer_type=ctype, active=True)
                db.session.add(c)
                db.session.flush()
            customers.append(c)
        suppliers = []
        for name in ['مورد خضار', 'مورد لحوم', 'مورد مشروبات']:
            s = Supplier.query.filter_by(name=name).first()
            if not s:
                s = Supplier(name=name, active=True)
                db.session.add(s)
                db.session.flush()
            suppliers.append(s)
        materials = []
        for name, unit, cost in [('طماطم', 'kg', 8.5), ('أرز', 'kg', 6), ('دجاج', 'kg', 25), ('زيت', 'liter', 18), ('بهارات', 'kg', 40)]:
            r = RawMaterial.query.filter_by(name=name).first()
            if not r:
                r = RawMaterial(name=name, unit=unit, cost_per_unit=_d(cost), stock_quantity=_d(0), active=True)
                db.session.add(r)
                db.session.flush()
            materials.append(r)
        employees = []
        for code, full_name, nid in [('EMP001', 'أحمد محمد', '1000000001'), ('EMP002', 'سارة علي', '1000000002')]:
            e = Employee.query.filter_by(employee_code=code).first()
            if not e:
                e = Employee(employee_code=code, full_name=full_name, national_id=nid, status='active', active=True)
                db.session.add(e)
                db.session.flush()
            employees.append(e)
        db.session.commit()

        # --- 5) فواتير مبيعات + بنود ---
        base_date = today - timedelta(days=30)
        sales_inv_numbers = []
        for i in range(8):
            inv_no = f"{prefix}-SAL-{i+1:03d}"
            if SalesInvoice.query.filter_by(invoice_number=inv_no).first():
                continue
            branch = 'china_town' if i % 2 == 0 else 'place_india'
            pay = 'CREDIT' if i % 3 == 0 else 'CASH'
            cust_name = 'KEETA' if i % 5 == 0 else ('HUNGER' if i % 7 == 0 else (customers[i % len(customers)].name if customers else 'عميل'))
            inv_date = base_date + timedelta(days=i * 3)
            total_bt = _d(100 + i * 50)
            tax = _d(15)
            disc = _d(5) if i % 2 == 0 else _d(0)
            total_at = total_bt + tax - disc
            inv = SalesInvoice(
                invoice_number=inv_no,
                date=inv_date,
                payment_method=pay,
                branch=branch,
                table_number=(i % 5) + 1,
                customer_name=cust_name,
                total_before_tax=total_bt,
                tax_amount=tax,
                discount_amount=disc,
                total_after_tax_discount=total_at,
                status='paid',
                user_id=user_id,
            )
            db.session.add(inv)
            db.session.flush()
            # بنود
            for j, (pname, qty, price) in enumerate([('وجبة أ', 2, 25.0), ('مشروب', 1, 10.0)]):
                if j == 1 and i % 4 == 0:
                    continue
                line_tax = _d(price * 0.15 * float(qty))
                line_total = _d(price * qty) + line_tax
                db.session.add(SalesInvoiceItem(
                    invoice_id=inv.id,
                    product_name=pname,
                    quantity=_d(qty),
                    price_before_tax=_d(price),
                    tax=line_tax,
                    discount=_d(0),
                    total_price=line_total,
                ))
            sales_inv_numbers.append(inv_no)
        db.session.commit()
        print("Sales invoices:", len(sales_inv_numbers), sales_inv_numbers[:5], "...")

        # --- 6) فواتير مشتريات + بنود ---
        pur_inv_numbers = []
        for i in range(5):
            inv_no = f"{prefix}-PUR-{i+1:03d}"
            if PurchaseInvoice.query.filter_by(invoice_number=inv_no).first():
                continue
            inv_date = base_date + timedelta(days=i * 4)
            rm = materials[i % len(materials)]
            qty = _d(10 + i * 5)
            price = rm.cost_per_unit
            total_bt = qty * price
            tax = total_bt * _d("0.15")
            total_at = total_bt + tax
            inv = PurchaseInvoice(
                invoice_number=inv_no,
                date=inv_date,
                supplier_name=suppliers[i % len(suppliers)].name,
                supplier_id=suppliers[i % len(suppliers)].id,
                payment_method='CASH' if i % 2 == 0 else 'BANK',
                total_before_tax=total_bt,
                tax_amount=tax,
                discount_amount=_d(0),
                total_after_tax_discount=total_at,
                status='paid',
                user_id=user_id,
            )
            db.session.add(inv)
            db.session.flush()
            db.session.add(PurchaseInvoiceItem(
                invoice_id=inv.id,
                raw_material_id=rm.id,
                raw_material_name=rm.name,
                quantity=qty,
                price_before_tax=price,
                tax=tax,
                discount=_d(0),
                total_price=total_at,
            ))
            pur_inv_numbers.append(inv_no)
        db.session.commit()
        print("Purchase invoices:", len(pur_inv_numbers), pur_inv_numbers[:3], "...")

        # --- 7) فواتير مصروفات + بنود ---
        exp_inv_numbers = []
        for i in range(5):
            inv_no = f"{prefix}-EXP-{i+1:03d}"
            if ExpenseInvoice.query.filter_by(invoice_number=inv_no).first():
                continue
            inv_date = base_date + timedelta(days=i * 5)
            total_bt = _d(200 + i * 100)
            tax = total_bt * _d("0.15")
            total_at = total_bt + tax
            inv = ExpenseInvoice(
                invoice_number=inv_no,
                date=inv_date,
                payment_method='CASH' if i % 2 == 0 else 'BANK',
                total_before_tax=total_bt,
                tax_amount=tax,
                discount_amount=_d(0),
                total_after_tax_discount=total_at,
                status='paid',
                user_id=user_id,
            )
            db.session.add(inv)
            db.session.flush()
            db.session.add(ExpenseInvoiceItem(
                invoice_id=inv.id,
                description=f"مصروف اختبار {i+1}",
                account_code='5230',
                quantity=_d(1),
                price_before_tax=total_bt,
                tax=tax,
                discount=_d(0),
                total_price=total_at,
            ))
            exp_inv_numbers.append(inv_no)
        db.session.commit()
        print("Expense invoices:", len(exp_inv_numbers), exp_inv_numbers[:3], "...")

        # --- 8) رواتب (شهر واحد لكل موظف) ---
        sal_created = 0
        for emp in employees[:2]:
            yr, mo = today.year, today.month
            if Salary.query.filter_by(employee_id=emp.id, year=yr, month=mo).first():
                continue
            basic = _d(3000)
            total = basic + _d(200) - _d(0)
            sal = Salary(employee_id=emp.id, year=yr, month=mo, basic_salary=basic, extra=_d(0), absence=_d(0),
                        incentive=_d(200), allowances=_d(0), deductions=_d(0), previous_salary_due=_d(0),
                        total_salary=total, status='paid')
            db.session.add(sal)
            sal_created += 1
        if sal_created:
            db.session.commit()
            print("Salaries created:", sal_created)

        # --- 9) قيود اليومية (backfill) ---
        try:
            from routes.journal import create_missing_journal_entries
            created, errors = create_missing_journal_entries()
            db.session.commit()
            print("Journal backfill: created", len(created), "entries; errors", len(errors))
            if errors:
                for e in errors[:10]:
                    print("  -", e)
        except Exception as e:
            db.session.rollback()
            print("Journal backfill failed:", e)
            import traceback
            traceback.print_exc()

    print("Done. You can open: Sales, Purchases, Expenses, Payroll, Financials (Trial Balance, Income, Cash Flow), Reports.")


if __name__ == '__main__':
    main()
