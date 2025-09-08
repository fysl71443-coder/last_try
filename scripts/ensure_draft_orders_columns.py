import os
import sys
os.environ.setdefault('USE_EVENTLET', '0')

# Ensure parent directory is on sys.path so `import app` works when running from scripts/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app import app
from extensions import db
from sqlalchemy import inspect, text


def add_column_if_missing(table: str, column: str, ddl: str) -> bool:
    insp = inspect(db.engine)
    if not insp.has_table(table):
        print(f"❌ Table '{table}' not found")
        return False
    cols = [c['name'] for c in insp.get_columns(table)]
    print(f"🔎 Existing columns in {table}: {cols}")
    if column in cols:
        print(f"✅ Column '{column}' already exists in '{table}'")
        return False
    try:
        print(f"➕ Adding column '{column}' to '{table}' ...")
        db.session.execute(text(ddl))
        db.session.commit()
        print(f"✅ Added '{column}' to '{table}'")
        return True
    except Exception as e:
        print(f"❌ Failed to add '{column}' to '{table}': {e}")
        db.session.rollback()
        return False


if __name__ == '__main__':
    with app.app_context():
        db_type = db.engine.dialect.name
        print(f"🔌 DB: {db_type} | URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

        changed = False
        if db_type == 'sqlite':
            changed |= add_column_if_missing('draft_orders', 'table_number',
                                             "ALTER TABLE draft_orders ADD COLUMN table_number VARCHAR(50) DEFAULT '0'")
            changed |= add_column_if_missing('draft_orders', 'status',
                                             "ALTER TABLE draft_orders ADD COLUMN status VARCHAR(20) DEFAULT 'draft'")
            changed |= add_column_if_missing('draft_orders', 'branch_code',
                                             "ALTER TABLE draft_orders ADD COLUMN branch_code VARCHAR(50) DEFAULT 'china_town'")
        else:
            changed |= add_column_if_missing('draft_orders', 'table_number',
                                             "ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0'")
            changed |= add_column_if_missing('draft_orders', 'status',
                                             "ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft'")
            changed |= add_column_if_missing('draft_orders', 'branch_code',
                                             "ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50) NOT NULL DEFAULT 'china_town'")

        insp = inspect(db.engine)
        if insp.has_table('draft_orders'):
            final_cols = [c['name'] for c in insp.get_columns('draft_orders')]
            print('📋 Final draft_orders columns:', final_cols)
        else:
            print("⚠️ 'draft_orders' table does not exist")

