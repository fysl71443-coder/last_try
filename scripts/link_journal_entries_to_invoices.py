#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربط القيود المنشورة غير المربوطة بالفواتير (JournalEntry + JournalLine).
يُحدد القيد من الوصف أو رقم القيد (Sales/Purchase/Expense + رقم الفاتورة) ويُحدّث invoice_id و invoice_type.

تشغيل من جذر المشروع:
  python scripts/link_journal_entries_to_invoices.py
  python scripts/link_journal_entries_to_invoices.py --dry-run   # عرض فقط دون تحديث
"""
import os
import re
import sys
import argparse

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


def extract_invoice_number_from_entry(entry_number: str, description: str) -> tuple:
    """
    استخراج رقم الفاتورة ونوعها من رقم القيد أو الوصف.
    Returns (invoice_number or None, invoice_type: 'sales'|'purchase'|'expense'|None).
    """
    entry_number = (entry_number or '').strip()
    description = (description or '').strip()
    # JE-SAL-INV-xxx, JE-PUR-INV-PUR-2026-0001, JE-EXP-TEST-EXP-001
    for prefix, inv_type in [('JE-SAL-', 'sales'), ('JE-PUR-', 'purchase'), ('JE-EXP-', 'expense')]:
        if entry_number.startswith(prefix):
            num = entry_number[len(prefix):].strip()
            if num:
                return (num, inv_type)
    # Description: "Sales INV-xxx", "Purchase INV-PUR-2026-0001", "Expense INV-EXP-001"
    for prefix, inv_type in [('Sales ', 'sales'), ('Purchase ', 'purchase'), ('Expense ', 'expense')]:
        if description.startswith(prefix):
            num = description[len(prefix):].strip()
            if num:
                return (num, inv_type)
    return (None, None)


def main():
    parser = argparse.ArgumentParser(description='Link posted journal entries to invoices')
    parser.add_argument('--dry-run', action='store_true', help='Only report, do not update DB')
    parser.add_argument('--backfill', action='store_true', help='After linking, run backfill to create missing JEs for invoices')
    args = parser.parse_args()

    from sqlalchemy import or_
    from app import create_app
    from extensions import db
    from models import JournalEntry, JournalLine, SalesInvoice, PurchaseInvoice, ExpenseInvoice

    app = create_app()
    with app.app_context():
        # قيود منشورة بدون ربط فاتورة (أو ربط قديم فارغ)
        q = JournalEntry.query.filter(JournalEntry.status == 'posted')
        q = q.filter(
            or_(
                JournalEntry.invoice_id.is_(None),
                JournalEntry.invoice_type.is_(None),
                JournalEntry.invoice_type == '',
            )
        )
        entries = q.order_by(JournalEntry.id.asc()).all()
        linked_entries = 0
        linked_lines = 0
        skipped = 0
        errors = []

        for je in entries:
            entry_no = getattr(je, 'entry_number', '') or ''
            desc = getattr(je, 'description', '') or ''
            inv_number, inv_type = extract_invoice_number_from_entry(entry_no, desc)
            if not inv_number or not inv_type:
                skipped += 1
                continue
            inv_id = None
            if inv_type == 'sales':
                inv = SalesInvoice.query.filter_by(invoice_number=inv_number).first()
            elif inv_type == 'purchase':
                inv = PurchaseInvoice.query.filter_by(invoice_number=inv_number).first()
            elif inv_type == 'expense':
                inv = ExpenseInvoice.query.filter_by(invoice_number=inv_number).first()
            else:
                inv = None
            if not inv:
                errors.append(f"JE {entry_no}: invoice not found for {inv_type} {inv_number}")
                continue
            inv_id = inv.id
            if args.dry_run:
                print(f"[DRY-RUN] Would link JE {je.id} ({entry_no}) -> {inv_type} id={inv_id} ({inv_number})")
                linked_entries += 1
                lines = JournalLine.query.filter_by(journal_id=je.id).all()
                linked_lines += len(lines)
                continue
            je.invoice_id = inv_id
            je.invoice_type = inv_type
            for line in JournalLine.query.filter_by(journal_id=je.id).all():
                line.invoice_id = inv_id
                line.invoice_type = inv_type
                linked_lines += 1
            linked_entries += 1

        if not args.dry_run and (linked_entries > 0 or linked_lines > 0):
            try:
                db.session.commit()
                print(f"Linked {linked_entries} journal entries and {linked_lines} lines to invoices.")
            except Exception as e:
                db.session.rollback()
                print("Error committing:", e)
                sys.exit(1)
        elif args.dry_run:
            print(f"Would link {linked_entries} entries and {linked_lines} lines. Run without --dry-run to apply.")
        if errors:
            print("Warnings (invoice not found):", len(errors))
            for e in errors[:20]:
                print(" ", e)
            if len(errors) > 20:
                print(" ... and", len(errors) - 20, "more")
        print("Skipped (no pattern):", skipped)

        if args.backfill and not args.dry_run:
            print("Running backfill for missing journal entries...")
            try:
                from routes.journal import create_missing_journal_entries
                created, errs = create_missing_journal_entries()
                db.session.commit()
                print(f"Backfill: created {len(created)} entries, errors {len(errs)}")
                for e in errs[:10]:
                    print(" ", e)
            except Exception as e:
                db.session.rollback()
                print("Backfill failed:", e)

    print("Done.")


if __name__ == '__main__':
    main()
