#!/usr/bin/env python
"""
Update existing purchase journal entries that have 0.00 amounts.
Recalculates totals from purchase_invoice_items and updates JournalEntry
and JournalLine so the journal displays correct amounts.
Run once: python scripts/fix_purchase_journal_zero_amounts.py
Or from flask shell: from scripts.fix_purchase_journal_zero_amounts import main; main()
"""
from __future__ import print_function
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from app import create_app
    from extensions import db
    from models import JournalEntry, JournalLine, PurchaseInvoice, Account

    app = create_app()
    with app.app_context():
        # Purchase JEs with zero totals
        zero_jes = JournalEntry.query.filter(
            JournalEntry.invoice_type == 'purchase',
            JournalEntry.total_debit == 0,
            JournalEntry.total_credit == 0,
        ).all()
        if not zero_jes:
            print("No purchase journal entries with zero amounts found.")
            return
        updated = 0
        for je in zero_jes:
            inv_id = je.invoice_id
            if not inv_id:
                continue
            inv = PurchaseInvoice.query.get(inv_id)
            if not inv:
                continue
            total_before, tax_amt, total_inc_tax = inv.get_effective_totals()
            if total_inc_tax == 0:
                continue
            # Update entry totals
            je.total_debit = total_inc_tax
            je.total_credit = total_inc_tax
            # Update lines by account code
            ap_credit_set = False
            for line in sorted(je.lines, key=lambda x: x.line_no):
                code = (line.account.code or '').strip() if line.account else ''
                if code == '1161':
                    line.debit = total_before
                    line.credit = 0
                elif code == '1170':
                    line.debit = tax_amt
                    line.credit = 0
                elif code in ('2111', '2110'):
                    if not ap_credit_set:
                        line.debit = 0
                        line.credit = total_inc_tax
                        ap_credit_set = True
                    else:
                        line.debit = total_inc_tax
                        line.credit = 0
                elif code in ('1111', '1112', '1121', '1122', '1123'):
                    line.debit = 0
                    line.credit = total_inc_tax
            updated += 1
        try:
            db.session.commit()
            print("Updated {} purchase journal entry(ies) with amounts from items.".format(updated))
        except Exception as e:
            db.session.rollback()
            print("Error:", e)

if __name__ == '__main__':
    main()
