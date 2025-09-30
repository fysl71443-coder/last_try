import os
import sys

# Ensure project root on sys.path
ROOT = os.path.abspath('.')
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from extensions import db
from sqlalchemy import text


def ensure_sqlite():
    def column_exists_sqlite(table_name: str, column_name: str) -> bool:
        result = db.session.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
        for row in result:
            if str(row.get('name')).lower() == column_name.lower():
                return True
        return False

    changed = False
    if not column_exists_sqlite('suppliers', 'cr_number'):
        db.session.execute(text("ALTER TABLE suppliers ADD COLUMN cr_number VARCHAR(50)"))
        changed = True
    if not column_exists_sqlite('suppliers', 'iban'):
        db.session.execute(text("ALTER TABLE suppliers ADD COLUMN iban VARCHAR(50)"))
        changed = True
    if not column_exists_sqlite('suppliers', 'payment_method'):
        db.session.execute(text("ALTER TABLE suppliers ADD COLUMN payment_method VARCHAR(50) DEFAULT 'CASH'"))
        changed = True
    if changed:
        db.session.execute(text("UPDATE suppliers SET payment_method='CASH' WHERE payment_method IS NULL OR TRIM(payment_method)=''"))
        db.session.commit()
        print('SQLite: suppliers columns ensured.')
    else:
        db.session.rollback()
        print('SQLite: no changes needed.')


def ensure_postgres():
    # Use IF NOT EXISTS to be idempotent
    db.session.execute(text("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS cr_number VARCHAR(50)"))
    db.session.execute(text("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS iban VARCHAR(50)"))
    db.session.execute(text("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'CASH'"))
    # Normalize existing rows
    db.session.execute(text("UPDATE suppliers SET payment_method='CASH' WHERE payment_method IS NULL OR payment_method=''"))
    db.session.commit()
    print('PostgreSQL: suppliers columns ensured.')


def main():
    app = create_app()
    with app.app_context():
        dialect = db.engine.dialect.name
        if dialect == 'sqlite':
            ensure_sqlite()
        elif dialect in ('postgresql', 'postgres'):
            ensure_postgres()
        else:
            print(f"Unsupported dialect: {dialect}")


if __name__ == '__main__':
    main()



