import argparse
import os
import re
from decimal import Decimal
from datetime import date
from sqlalchemy import create_engine, text

MASK_RE = re.compile(r"://([^:]+):([^@]+)@")

def mask_url(url: str) -> str:
    return MASK_RE.sub(lambda m: f"://{m.group(1)}:***@", url)


def fetch_one(conn, sql, **params):
    r = conn.execute(text(sql), params).mappings().first()
    return dict(r) if r else None


def fetch_all(conn, sql, **params):
    rs = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rs]


def main():
    p = argparse.ArgumentParser(description="Check settings and run transactional sales invoice smoke test (rollback)")
    p.add_argument('--url', default=os.environ.get('DB_URL'))
    args = p.parse_args()
    if not args.url:
        print('ERROR: provide --url or DB_URL env')
        raise SystemExit(2)

    db_url = args.url
    print('Connecting to:', mask_url(db_url))
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        # Show key settings
        print('\n[Settings] latest row:')
        st = fetch_one(conn, "SELECT id, company_name, currency, currency_image, printer_type, receipt_logo_height, receipt_footer_text FROM settings ORDER BY id DESC LIMIT 1")
        if st:
            for k, v in st.items():
                print(f" - {k}: {v}")
        else:
            print(' - No rows in settings')

        # Ensure currency image present or at least currency value
        has_currency_img = bool(st and st.get('currency_image'))
        print(f"Currency image present: {has_currency_img}")

        # Inspect target tables
        print('\n[Schema] Columns')
        for t in ('sales_invoices','sales_invoice_items'):
            cols = fetch_all(conn, """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:t
                ORDER BY ordinal_position
            """, t=t)
            print(f" - {t}:")
            for c in cols:
                print(f"    {c['column_name']} ({c['data_type']}) null={c['is_nullable']}")

        # Transactional smoke test (will rollback)
        print('\n[Smoke] Creating a test sales invoice inside a rollback-only transaction...')
        try:
            # ensure we are not in an implicit transaction from previous reads
            try:
                conn.rollback()
            except Exception:
                pass
            trans = conn.begin()
            inv_no = f"INV-SMOKE-{int(os.getpid())}"
            subtotal = Decimal('20.00')
            tax_amount = Decimal('0.00')
            discount_amount = Decimal('0.00')
            grand = subtotal + tax_amount - discount_amount

            inv = fetch_one(conn, """
                INSERT INTO sales_invoices (
                  invoice_number, date, payment_method, branch, table_number,
                  customer_name, total_before_tax, tax_amount, discount_amount,
                  total_after_tax_discount, status, created_at, user_id
                ) VALUES (
                  :invoice_number, :date, :payment_method, :branch, :table_number,
                  :customer_name, :total_before_tax, :tax_amount, :discount_amount,
                  :total_after, :status, NOW(), :user_id
                ) RETURNING id
            """,
            invoice_number=inv_no,
            date=date.today(),
            payment_method='CASH',
            branch='china_town',
            table_number=1,
            customer_name='DB Smoke Test',
            total_before_tax=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total_after=grand,
            status='unpaid',
            user_id=1)
            inv_id = inv['id'] if inv else None
            if not inv_id:
                raise RuntimeError('Failed to insert sales_invoices row')

            # Insert one item
            conn.execute(text("""
                INSERT INTO sales_invoice_items (
                  invoice_id, product_name, quantity, price_before_tax, tax, discount, total_price
                ) VALUES (:invoice_id, :product_name, :quantity, :price_before_tax, :tax, :discount, :total_price)
            """),
            dict(invoice_id=inv_id, product_name='Test Item A', quantity=Decimal('2'), price_before_tax=Decimal('10.00'), tax=Decimal('0.00'), discount=Decimal('0.00'), total_price=Decimal('20.00')))

            # Verify
            check = fetch_one(conn, "SELECT COUNT(*) AS c FROM sales_invoice_items WHERE invoice_id=:i", i=inv_id)
            print(f"Inserted invoice id={inv_id}, items={check['c'] if check else 0}, total={grand}")

            print('Rolling back the test transaction (no data will persist).')
            trans.rollback()
        except Exception as e:
            print('ERROR during smoke test, rolling back:', e)
            try: trans.rollback()
            except Exception: pass
            raise SystemExit(5)

    print('\nOK: Settings inspected and transactional sales smoke test succeeded.')

if __name__ == '__main__':
    main()

