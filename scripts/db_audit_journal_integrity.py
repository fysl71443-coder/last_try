# -*- coding: utf-8 -*-
"""
تدقيق تطابق قاعدة البيانات مع النظام – مصدر الحقيقة: قيود اليومية المنشورة فقط.

يفحص:
1. تطابق شجرة الحسابات (COA) بين data/coa_new_tree والقاعدة (accounts).
2. صلاحية كل قيد مرحل: مجموع المدين = مجموع الدائن، ومطابقة total_debit/total_credit.
3. قيود تشير لفواتير/رواتب غير موجودة (مرجع مكسور).
4. فواتير مبيعات/مشتريات/مصروفات ليس لها قيد مرتبط (بيانات بلا قيد).
5. إحصاء LedgerEntry (تراثي – المصدر الوحيد يجب أن يكون JournalLine).

تشغيل: من جذر المشروع
  set PYTHONPATH=.
  python scripts/db_audit_journal_integrity.py

  أو مع تطبيق create_app:
  python -c "import sys; sys.path.insert(0,'.'); from scripts.db_audit_journal_integrity import run; run()"
"""
import os
import sys
from decimal import Decimal

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def run():
    from app import create_app
    from extensions import db
    from sqlalchemy import func, text

    app = create_app()
    report = []

    with app.app_context():
        # --- 1. شجرة الحسابات: تطابق COA مع accounts ---
        report.append("=== 1. Chart of Accounts (COA) vs DB (accounts) ===")
        try:
            from data.coa_new_tree import build_coa_dict, LEAF_CODES
            from models import Account

            coa = build_coa_dict()
            coa_codes = set(coa.keys())
            db_accounts = {str(a.code): a for a in Account.query.all()}
            db_codes = set(db_accounts.keys())

            missing_in_db = sorted(coa_codes - db_codes)
            extra_in_db = sorted(db_codes - coa_codes)

            if missing_in_db:
                report.append(f"  WARN: COA codes in tree but not in DB ({len(missing_in_db)}): {missing_in_db[:20]}{'...' if len(missing_in_db) > 20 else ''}")
                report.append("  Action: run seed_chart_of_accounts or import COA from UI.")
            else:
                report.append("  OK: All COA codes exist in DB.")

            if extra_in_db:
                report.append(f"  Note: Accounts in DB not in current tree ({len(extra_in_db)}): {extra_in_db[:15]}{'...' if len(extra_in_db) > 15 else ''}")

            leaf_missing = sorted(LEAF_CODES - db_codes) if hasattr(LEAF_CODES, '__iter__') and not isinstance(LEAF_CODES, dict) else []
            if leaf_missing:
                report.append(f"  WARN: Leaf (posting) codes missing in DB: {leaf_missing[:15]}...")
        except Exception as e:
            report.append(f"  Error checking COA: {e}")

        # --- 2. صلاحية قيود اليومية المنشورة ---
        report.append("")
        report.append("=== 2. Journal entries validity (status=posted) ===")
        try:
            from models import JournalEntry, JournalLine

            posted = JournalEntry.query.filter_by(status='posted').all()
            invalid = []
            for je in posted:
                lines = JournalLine.query.filter_by(journal_id=je.id).all()
                sum_d = sum(float(l.debit or 0) for l in lines)
                sum_c = sum(float(l.credit or 0) for l in lines)
                td = float(je.total_debit or 0)
                tc = float(je.total_credit or 0)
                if round(sum_d, 2) != round(sum_c, 2):
                    invalid.append((je.entry_number, f"sum_debit={sum_d} != sum_credit={sum_c}"))
                elif round(td, 2) != round(tc, 2):
                    invalid.append((je.entry_number, f"total_debit={td} != total_credit={tc}"))
                elif round(sum_d, 2) != round(td, 2):
                    invalid.append((je.entry_number, f"lines_sum={sum_d} != total_debit={td}"))

            if invalid:
                report.append(f"  WARN: Unbalanced journal entries ({len(invalid)}):")
                for num, msg in invalid[:20]:
                    report.append(f"    - {num}: {msg}")
                if len(invalid) > 20:
                    report.append(f"    ... and {len(invalid) - 20} more.")
            else:
                report.append(f"  OK: All posted entries ({len(posted)}) are balanced.")
        except Exception as e:
            report.append(f"  Error checking entries: {e}")

        # --- 3. قيود تشير لفواتير/رواتب غير موجودة ---
        report.append("")
        report.append("=== 3. Entries with broken invoice/salary reference ===")
        try:
            from models import JournalEntry, SalesInvoice, PurchaseInvoice, ExpenseInvoice, Salary

            broken = []
            for je in JournalEntry.query.filter(JournalEntry.status == 'posted').filter(
                (JournalEntry.invoice_id.isnot(None)) | (JournalEntry.salary_id.isnot(None))
            ).all():
                if je.invoice_id and je.invoice_type:
                    if je.invoice_type == 'sales' and not db.session.get(SalesInvoice, je.invoice_id):
                        broken.append((je.entry_number, f"invoice_type=sales invoice_id={je.invoice_id} missing"))
                    elif je.invoice_type == 'purchase' and not db.session.get(PurchaseInvoice, je.invoice_id):
                        broken.append((je.entry_number, f"invoice_type=purchase invoice_id={je.invoice_id} missing"))
                    elif je.invoice_type == 'expense' and not db.session.get(ExpenseInvoice, je.invoice_id):
                        broken.append((je.entry_number, f"invoice_type=expense invoice_id={je.invoice_id} missing"))
                if je.salary_id and not db.session.get(Salary, je.salary_id):
                    broken.append((je.entry_number, f"salary_id={je.salary_id} missing"))

            if broken:
                report.append(f"  WARN: Entries with broken reference ({len(broken)}):")
                for num, msg in broken[:15]:
                    report.append(f"    - {num}: {msg}")
            else:
                report.append("  OK: No entries with broken reference.")
        except Exception as e:
            report.append(f"  Error: {e}")

        # --- 4. فواتير بدون قيد مرتبط ---
        report.append("")
        report.append("=== 4. Invoices without linked journal (invoice_id + invoice_type) ===")
        try:
            from models import JournalEntry, SalesInvoice, PurchaseInvoice, ExpenseInvoice

            # فواتير مبيعات بدون قيد (نبحث بالـ invoice_id + invoice_type في journal_entries)
            sales_without_je = []
            for inv in SalesInvoice.query.limit(5000).all():
                exists = JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type='sales', status='posted').first()
                if not exists:
                    sales_without_je.append((inv.invoice_number, inv.id))
            if sales_without_je:
                report.append(f"  Sales without linked journal: {len(sales_without_je)} (sample: {sales_without_je[:5]})")

            purch_without_je = []
            for inv in PurchaseInvoice.query.limit(5000).all():
                exists = JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type='purchase', status='posted').first()
                if not exists:
                    purch_without_je.append((inv.invoice_number, inv.id))
            if purch_without_je:
                report.append(f"  Purchases without linked journal: {len(purch_without_je)} (sample: {purch_without_je[:5]})")

            exp_without_je = []
            for inv in ExpenseInvoice.query.limit(5000).all():
                exists = JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type='expense', status='posted').first()
                if not exists:
                    exp_without_je.append((inv.invoice_number, inv.id))
            if exp_without_je:
                report.append(f"  Expenses without linked journal: {len(exp_without_je)} (sample: {exp_without_je[:5]})")

            if not sales_without_je and not purch_without_je and not exp_without_je:
                report.append("  OK: All listed invoices have a linked journal (or no invoices).")
            else:
                report.append("  Action: use backfill or 'Post from invoices' to create journal entries for unposted invoices.")
        except Exception as e:
            report.append(f"  خطأ: {e}")

        # --- 5. LedgerEntry (تراثي) ---
        report.append("")
        report.append("=== 5. LedgerEntry (legacy; single source of truth: JournalLine) ===")
        try:
            from models import LedgerEntry, JournalLine, JournalEntry

            n_ledger = db.session.query(func.count(LedgerEntry.id)).scalar() or 0
            n_journal_lines = db.session.query(func.count(JournalLine.id)).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalEntry.status == 'posted').scalar() or 0
            report.append(f"  LedgerEntry rows: {n_ledger}")
            report.append(f"  Posted JournalLine rows: {n_journal_lines}")
            if n_ledger > 0 and n_journal_lines == 0:
                report.append("  WARN: LedgerEntry exists but no posted journal lines; reports using JournalLine will be empty.")
        except Exception as e:
            report.append(f"  خطأ: {e}")

        # --- 6. Report totals vs posted journal lines ---
        report.append("")
        report.append("=== 6. Report totals vs posted journal lines ===")
        try:
            from models import JournalEntry, JournalLine
            q = db.session.query(
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalEntry.status == 'posted')
            row = q.first()
            total_d = float(row[0] or 0)
            total_c = float(row[1] or 0)
            diff = round(abs(total_d - total_c), 2)
            if diff > 0.01:
                report.append(f"  WARN: Posted journal lines sum: debit={total_d:.2f}, credit={total_c:.2f}; diff={diff:.2f} (should be 0).")
            else:
                report.append(f"  OK: Posted journal lines balanced (debit={total_d:.2f}, credit={total_c:.2f}).")
        except Exception as e:
            report.append(f"  Error: {e}")

        # --- 7. أعمدة مطلوبة في الجداول الرئيسية ---
        report.append("")
        report.append("=== 7. Required columns (sample) ===")
        try:
            from sqlalchemy import inspect
            insp = inspect(db.engine)
            for table, required in [
                ('journal_entries', ['entry_number', 'date', 'status', 'total_debit', 'total_credit', 'invoice_id', 'invoice_type']),
                ('journal_lines', ['journal_id', 'account_id', 'debit', 'credit', 'line_date']),
                ('accounts', ['code', 'name', 'type']),
                ('sales_invoices', ['invoice_number', 'date', 'branch']),
            ]:
                if table not in insp.get_table_names():
                    report.append(f"  Table missing: {table}")
                    continue
                cols = {c['name'] for c in insp.get_columns(table)}
                missing = [c for c in required if c not in cols]
                if missing:
                    report.append(f"  {table}: missing columns: {missing}")
                else:
                    report.append(f"  {table}: OK")
        except Exception as e:
            report.append(f"  خطأ: {e}")

    for line in report:
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode('ascii', 'replace').decode('ascii'))
    return report

if __name__ == '__main__':
    run()
