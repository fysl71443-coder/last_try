import os, sys
os.environ.setdefault('USE_EVENTLET','0')

# Ensure project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app import app
from extensions import db
from sqlalchemy import inspect, text


def fix_draft_orders_table_no():
    insp = inspect(db.engine)
    if not insp.has_table('draft_orders'):
        print('draft_orders table not found, skipping')
        return
    cols = [c['name'] for c in insp.get_columns('draft_orders')]
    if 'table_no' in cols:
        print('Found legacy column draft_orders.table_no -> setting defaults and filling NULLs')
        try:
            # Try to set default ; SQLite may ignore for existing rows, but harmless
            try:
                db.session.execute(text("ALTER TABLE draft_orders ALTER COLUMN table_no SET DEFAULT 0"))
            except Exception:
                pass
            # Fill NULLs
            db.session.execute(text("UPDATE draft_orders SET table_no = 0 WHERE table_no IS NULL"))
            db.session.commit()
            print('Set table_no=0 where NULL')
        except Exception as e:
            print('Warning: could not update table_no defaults:', e)
            db.session.rollback()
    else:
        print('No legacy table_no column found; nothing to do')


def add_purchase_invoices_supplier_id():
    insp = inspect(db.engine)
    if not insp.has_table('purchase_invoices'):
        print('purchase_invoices table not found, skipping')
        return
    cols = [c['name'] for c in insp.get_columns('purchase_invoices')]
    if 'supplier_id' not in cols:
        print('Adding supplier_id to purchase_invoices')
        try:
            db.session.execute(text("ALTER TABLE purchase_invoices ADD COLUMN supplier_id INTEGER"))
            db.session.commit()
            print('Added supplier_id')
        except Exception as e:
            print('Failed to add supplier_id:', e)
            db.session.rollback()
    else:
        print('supplier_id already exists')


if __name__ == '__main__':
    with app.app_context():
        print('DB URI:', app.config.get('SQLALCHEMY_DATABASE_URI'))
        fix_draft_orders_table_no()
        add_purchase_invoices_supplier_id()
        # show final schemas
        insp = inspect(db.engine)
        for table in ['draft_orders','purchase_invoices']:
            if insp.has_table(table):
                cols = [c['name'] for c in insp.get_columns(table)]
                print(f"{table} columns:", cols)

