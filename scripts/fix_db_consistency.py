import os, sys
os.environ.setdefault('USE_EVENTLET','0')

# Ensure project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app import create_app
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


def fix_settings_branding():
    insp = inspect(db.engine)
    if not insp.has_table('settings'):
        print('settings table not found, creating via db.create_all()')
        db.create_all()
        insp = inspect(db.engine)
        if not insp.has_table('settings'):
            print('Failed to create settings table')
            return
    # Ensure required columns exist
    cols = {c['name'] for c in insp.get_columns('settings')}
    def add(name: str, ddl: str):
        if name not in cols:
            try:
                db.session.execute(text(f"ALTER TABLE settings ADD COLUMN {ddl}"))
                db.session.commit()
                print(f"Added settings column: {name}")
                cols.add(name)
            except Exception as e:
                print(f"Failed to add settings column {name}: {e}")
                db.session.rollback()
    add('logo_url', "logo_url VARCHAR(300) DEFAULT '/static/chinese-logo.svg'")
    add('china_town_logo_url', "china_town_logo_url VARCHAR(300)")
    add('place_india_logo_url', "place_india_logo_url VARCHAR(300)")
    add('currency_image', "currency_image VARCHAR(300)")
    add('receipt_logo_height', "receipt_logo_height INTEGER DEFAULT 40")
    add('receipt_extra_bottom_mm', "receipt_extra_bottom_mm INTEGER DEFAULT 15")
    add('receipt_high_contrast', "receipt_high_contrast INTEGER DEFAULT 1")
    add('receipt_bold_totals', "receipt_bold_totals INTEGER DEFAULT 1")
    add('receipt_border_style', "receipt_border_style VARCHAR(10) DEFAULT 'solid'")
    add('receipt_font_bump', "receipt_font_bump INTEGER DEFAULT 1")
    add('china_town_phone1', "china_town_phone1 VARCHAR(50)")
    add('china_town_phone2', "china_town_phone2 VARCHAR(50)")
    add('place_india_phone1', "place_india_phone1 VARCHAR(50)")
    add('place_india_phone2', "place_india_phone2 VARCHAR(50)")
    add('receipt_show_logo', "receipt_show_logo INTEGER DEFAULT 1")
    add('receipt_show_tax_number', "receipt_show_tax_number INTEGER DEFAULT 1")

    # Ensure at least one settings row exists
    try:
        count = db.session.execute(text("SELECT COUNT(*) AS c FROM settings")).scalar()
        if (count or 0) == 0:
            db.session.execute(text("INSERT INTO settings (company_name) VALUES ('Restaurant')"))
            db.session.commit()
            print('Inserted default settings row')
    except Exception as e:
        print('Failed to ensure settings row:', e)
        db.session.rollback()

    # Update defaults where missing/blank
    try:
        db.session.execute(text("UPDATE settings SET company_name = COALESCE(NULLIF(company_name,''),'Restaurant')"))
        db.session.execute(text("UPDATE settings SET logo_url = COALESCE(NULLIF(logo_url,''), '/static/logo.svg')"))
        db.session.execute(text("UPDATE settings SET china_town_logo_url = COALESCE(NULLIF(china_town_logo_url,''), '/static/chinese-logo.svg')"))
        db.session.execute(text("UPDATE settings SET place_india_logo_url = COALESCE(NULLIF(place_india_logo_url,''), '/static/logo.svg')"))
        db.session.execute(text("UPDATE settings SET receipt_show_logo = COALESCE(receipt_show_logo, 1)"))
        db.session.commit()
        print('Updated settings branding defaults')
    except Exception as e:
        print('Failed to update settings branding:', e)
        db.session.rollback()


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print('DB URI:', app.config.get('SQLALCHEMY_DATABASE_URI'))
        fix_draft_orders_table_no()
        add_purchase_invoices_supplier_id()
        fix_settings_branding()
        # show final schemas
        insp = inspect(db.engine)
        for table in ['draft_orders','purchase_invoices','settings']:
            if insp.has_table(table):
                cols = [c['name'] for c in insp.get_columns(table)]
                print(f"{table} columns:", cols)

