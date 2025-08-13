import random
import string
import time
from datetime import datetime, timedelta
import argparse
import os, sys, json
# Ensure project root is on sys.path when running from scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from app import app, db
from models import SalesInvoice, SalesInvoiceItem, Meal

PAYMENT_METHODS = ['CASH','MADA','BANK','VISA','MASTERCARD','AKS','GCC','آجل']
BRANCHES = ['place_india', 'china_town']
LOG_PATH = os.path.join(ROOT, 'instance', 'load_test.log')
SUM_PATH = os.path.join(ROOT, 'instance', 'load_test_summary.json')

def log(msg):
    print(msg, flush=True)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def unique_suffix(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))


def run_load(total_invoices:int=2000, items_per_invoice:int=3):
    created = 0
    start = time.time()
    with app.app_context():
        # Try to get some meal names; fallback to generic
        meal_names = [m.display_name for m in Meal.query.limit(50).all()] or [
            'Test Item A','Test Item B','Test Item C','Test Item D']
        log(f"using_meals={len(meal_names)}")

        batch = 0
        for i in range(total_invoices):
            branch = BRANCHES[i % len(BRANCHES)]
            pm = PAYMENT_METHODS[i % len(PAYMENT_METHODS)]
            now = datetime.utcnow()
            inv_no = f"SAL-LOAD-{now.strftime('%Y%m%d%H%M%S')}-{unique_suffix(6)}-{i:06d}"

            inv = SalesInvoice(
                invoice_number=inv_no,
                date=(now.date() - timedelta(days=random.randint(0, 10))),
                payment_method=pm,
                branch=branch,
                customer_name=None,
                total_before_tax=0,
                tax_amount=0,
                discount_amount=0,
                total_after_tax_discount=0,
                status='paid' if pm != 'آجل' else 'unpaid',
                user_id=1
            )
            db.session.add(inv)
            db.session.flush()

            total_bt = 0.0
            total_tax = 0.0
            total_disc = 0.0
            for j in range(items_per_invoice):
                name = random.choice(meal_names)
                qty = round(random.uniform(1, 5), 2)
                price = round(random.uniform(10, 60), 2)
                tax = round(price * 0.15, 2)
                disc = round(price * 0.05, 2)
                total_line = (price + tax - disc) * qty
                db.session.add(SalesInvoiceItem(
                    invoice_id=inv.id,
                    product_name=name,
                    quantity=qty,
                    price_before_tax=price,
                    tax=tax,
                    discount=disc,
                    total_price=total_line
                ))
                total_bt += price * qty
                total_tax += tax * qty
                total_disc += disc * qty

            inv.total_before_tax = round(total_bt, 2)
            inv.tax_amount = round(total_tax, 2)
            inv.discount_amount = round(total_disc, 2)
            inv.total_after_tax_discount = round(total_bt + total_tax - total_disc, 2)

            created += 1
            batch += 1
            if created % 100 == 0:
                log(f"progress_created={created}")
            if batch >= 200:
                db.session.commit()
                batch = 0
        if batch:
            db.session.commit()
    dur = time.time() - start
    summary = {
        'created_invoices': created,
        'items_per_invoice': items_per_invoice,
        'duration_sec': round(dur, 2),
        'invoices_per_sec': round(created/dur, 2) if dur > 0 else None,
        'items_per_sec': round((created*items_per_invoice)/dur, 2) if dur > 0 else None,
    }
    log(summary)
    try:
        with open(SUM_PATH, 'w', encoding='utf-8') as f:
            json.dump(summary, f)
    except Exception:
        pass


def cleanup():
    removed_inv = removed_items = 0
    with app.app_context():
        q = SalesInvoice.query.filter(SalesInvoice.invoice_number.like('SAL-LOAD-%')).all()
        for inv in q:
            cnt = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).delete()
            removed_items += cnt
            db.session.delete(inv)
        db.session.commit()
        removed_inv = len(q)
    summary = {
        'cleanup_removed_invoices': removed_inv,
        'cleanup_removed_items': removed_items
    }
    log(summary)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['run','cleanup'], help='run: create load; cleanup: delete test data')
    ap.add_argument('--invoices', type=int, default=2000)
    ap.add_argument('--items', type=int, default=3)
    args = ap.parse_args()

    if args.mode == 'run':
        run_load(total_invoices=args.invoices, items_per_invoice=args.items)
    else:
        cleanup()

