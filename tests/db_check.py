import argparse
import os
import re
import sys
from contextlib import contextmanager

MASK_RE = re.compile(r"://([^:]+):([^@]+)@")

def mask_url(url: str) -> str:
    try:
        return MASK_RE.sub(lambda m: f"://{m.group(1)}:***@", url)
    except Exception:
        return url


def main():
    parser = argparse.ArgumentParser(description="Read-only DB connectivity and schema check")
    parser.add_argument("--url", dest="url", default=os.environ.get("DB_URL"), help="Database URL, e.g. postgresql://user:pass@host/db")
    args = parser.parse_args()
    db_url = args.url
    if not db_url:
        print("ERROR: No DB URL provided. Use --url or set DB_URL.")
        sys.exit(2)

    print("Connecting to:", mask_url(db_url))

    # Try SQLAlchemy first
    try:
        from sqlalchemy import create_engine, text
    except Exception as e:
        print("ERROR: SQLAlchemy not available:", e)
        sys.exit(3)

    try:
        engine = create_engine(db_url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    except Exception as e:
        print("ERROR: Failed to create engine. Possibly missing driver (psycopg2).", e)
        sys.exit(4)

    try:
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version();")).scalar()
            print("Server version:", ver)

            # List public tables
            rows = conn.execute(text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_type='BASE TABLE'
                ORDER BY table_name
            """)).fetchall()
            tables = [r[0] for r in rows]
            print("Found", len(tables), "tables:")
            for t in tables:
                print(" -", t)

            # Probe common tables if exist
            probe = [
                'users','sales_invoices','sales_invoice_items','product_catalog',
                'meals','meal_ingredients','raw_materials','purchase_invoices','settings'
            ]
            for t in probe:
                if t in tables:
                    cnt = conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                    print(f"Count {t}:", cnt.scalar())

            # Peek last 5 invoices if present
            if 'sales_invoices' in tables:
                rs = conn.execute(text("""
                    SELECT invoice_number, date, payment_method, total_after_tax_discount, status
                    FROM sales_invoices
                    ORDER BY id DESC
                    LIMIT 5
                """))
                print("Last 5 sales_invoices:")
                for row in rs:
                    print("  ", dict(row._mapping))

    except Exception as e:
        print("ERROR during DB checks:", e)
        sys.exit(5)

    print("OK: DB connectivity and basic checks passed.")

if __name__ == "__main__":
    main()

