import os
from app import app, db

# Ensure we don't trigger eventlet paths while importing
os.environ.setdefault('USE_EVENTLET', '0')


def ensure_schema():
    with app.app_context():
        print('URI:', app.config.get('SQLALCHEMY_DATABASE_URI'))
        conn = db.engine.raw_connection()
        cur = conn.cursor()

        # Show attached DBs for this connection
        cur.execute("PRAGMA database_list")
        print('DBS:', cur.fetchall())

        # Create tables if not exist (idempotent)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS menu_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(120) NOT NULL,
                branch VARCHAR(50),
                display_order INTEGER NOT NULL DEFAULT 0,
                image_url VARCHAR(300)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS menu_section_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                meal_id INTEGER NOT NULL,
                display_order INTEGER NOT NULL DEFAULT 0,
                price_override NUMERIC(12,2),
                FOREIGN KEY(section_id) REFERENCES menu_sections(id)
            )
            """
        )
        conn.commit()

        # Check and add missing columns
        def cols(table):
            cur.execute(f"PRAGMA table_info({table})")
            return [r[1] for r in cur.fetchall()]

        cur.execute("PRAGMA table_info(menu_sections)")
        ms = [r[1] for r in cur.fetchall()]
        print('menu_sections BEFORE:', ms)
        if 'image_url' not in ms:
            cur.execute("ALTER TABLE menu_sections ADD COLUMN image_url VARCHAR(300)")
            conn.commit()
            print('image_url added')

        cur.execute("PRAGMA table_info(menu_section_items)")
        msi = [r[1] for r in cur.fetchall()]
        print('menu_section_items BEFORE:', msi)
        if 'price_override' not in msi:
            cur.execute("ALTER TABLE menu_section_items ADD COLUMN price_override NUMERIC(12,2)")
            conn.commit()
            print('price_override added')

        # After
        cur.execute("PRAGMA table_info(menu_sections)")
        print('menu_sections AFTER:', [r[1] for r in cur.fetchall()])
        cur.execute("PRAGMA table_info(menu_section_items)")
        print('menu_section_items AFTER:', [r[1] for r in cur.fetchall()])

        cur.close()
        conn.close()


if __name__ == '__main__':
    ensure_schema()

