#!/usr/bin/env python
"""
Backfill purchase_invoices.total_after_tax_discount (and related totals) from
purchase_invoice_items when the header total is 0. Fixes invoices that show
$0.00 on Render because the header was never updated (e.g. created via API
or items saved in a different flow).
Run once on production: flask shell < scripts/backfill_purchase_invoice_totals.py
Or: python -c "
from app import create_app
from extensions import db
from models import PurchaseInvoice, PurchaseInvoiceItem
from sqlalchemy import func
app = create_app()
with app.app_context():
    rows = db.session.query(PurchaseInvoiceItem.invoice_id,
        func.sum(PurchaseInvoiceItem.total_price).label('st'),
        func.sum(PurchaseInvoiceItem.tax).label('tax'),
        func.sum(PurchaseInvoiceItem.discount).label('disc')).filter(
        PurchaseInvoiceItem.invoice_id.in_(
            db.session.query(PurchaseInvoice.id).filter(
                (PurchaseInvoice.total_after_tax_discount == 0) | (PurchaseInvoice.total_after_tax_discount.is_(None))
            )
        )).group_by(PurchaseInvoiceItem.invoice_id).all()
    for inv_id, st, tax, disc in rows:
        inv = PurchaseInvoice.query.get(inv_id)
        if inv and (float(inv.total_after_tax_discount or 0) == 0):
            total = float(st or 0)
            tax_f = float(tax or 0)
            disc_f = float(disc or 0)
            inv.total_before_tax = total - tax_f
            inv.tax_amount = tax_f
            inv.discount_amount = disc_f
            inv.total_after_tax_discount = total
    db.session.commit()
    print('Done')
"
"""
from __future__ import print_function
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from app import create_app
    from extensions import db
    from models import PurchaseInvoice, PurchaseInvoiceItem
    from sqlalchemy import func

    app = create_app()
    with app.app_context():
        # Invoices with header total 0 or NULL
        zero_ids = [r[0] for r in db.session.query(PurchaseInvoice.id).filter(
            (PurchaseInvoice.total_after_tax_discount == 0) | (PurchaseInvoice.total_after_tax_discount.is_(None))
        ).all()]
        if not zero_ids:
            print("No purchase invoices with zero total found.")
            return
        # Sum total_price, tax, discount per invoice from items
        rows = (db.session.query(
            PurchaseInvoiceItem.invoice_id,
            func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0).label('st'),
            func.coalesce(func.sum(PurchaseInvoiceItem.tax), 0).label('tax'),
            func.coalesce(func.sum(PurchaseInvoiceItem.discount), 0).label('disc'),
        ).filter(PurchaseInvoiceItem.invoice_id.in_(zero_ids))
         .group_by(PurchaseInvoiceItem.invoice_id).all())
        updated = 0
        for inv_id, st, tax, disc in rows:
            inv = PurchaseInvoice.query.get(inv_id)
            if not inv:
                continue
            total = float(st or 0)
            if total == 0:
                continue
            tax_f = float(tax or 0)
            disc_f = float(disc or 0)
            inv.total_before_tax = max(0, total - tax_f)
            inv.tax_amount = tax_f
            inv.discount_amount = disc_f
            inv.total_after_tax_discount = total
            updated += 1
        db.session.commit()
        print("Updated {} purchase invoice(s) with totals from items.".format(updated))

if __name__ == '__main__':
    main()
