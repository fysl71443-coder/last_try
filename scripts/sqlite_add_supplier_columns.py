import os
import sys

# Ensure project root on sys.path
ROOT = os.path.abspath('.')
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from extensions import db
from sqlalchemy import text


def column_exists_sqlite(table_name: str, column_name: str) -> bool:
    result = db.session.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    for row in result:
        if str(row.get('name')).lower() == column_name.lower():
            return True
    return False


def add_column_if_missing_sqlite(table: str, column: str, ddl: str) -> bool:
    if column_exists_sqlite(table, column):
        return False
    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    return True


app = create_app()
with app.app_context():
    dialect = db.engine.dialect.name
    if dialect != 'sqlite':
        print(f"Not a SQLite database; skipping (dialect: {dialect})")
        sys.exit(0)

    changed = False
    # Suppliers extra columns
    changed |= add_column_if_missing_sqlite('suppliers', 'cr_number', 'VARCHAR(50)')
    changed |= add_column_if_missing_sqlite('suppliers', 'iban', 'VARCHAR(50)')
    changed |= add_column_if_missing_sqlite('suppliers', 'payment_method', "VARCHAR(50) DEFAULT 'CASH'")

    # Normalize defaults if needed
    try:
        db.session.execute(text("UPDATE suppliers SET payment_method='CASH' WHERE payment_method IS NULL OR TRIM(payment_method)=''"))
    except Exception:
        pass

    if changed:
        db.session.commit()
        print('Suppliers table updated.')
    else:
        db.session.rollback()
        print('No changes needed.')



