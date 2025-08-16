import sqlite3, os

DB_PATH = os.path.join(os.getcwd(), 'accounting_app.db')
print('Using DB:', DB_PATH)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

def table_exists(name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def cols(table):
    return [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]

# 1) إنشاء الجداول إن لم تكن موجودة
cur.execute("""
CREATE TABLE IF NOT EXISTS menu_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(120) NOT NULL,
    branch VARCHAR(50),
    display_order INTEGER NOT NULL DEFAULT 0,
    image_url VARCHAR(300)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS menu_section_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL,
    meal_id INTEGER NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    price_override NUMERIC(12,2),
    FOREIGN KEY(section_id) REFERENCES menu_sections(id)
)
""")

# 2) إضافة الأعمدة الناقصة فقط إن كانت غير موجودة
ms_cols = cols('menu_sections')
if 'image_url' not in ms_cols:
    cur.execute("ALTER TABLE menu_sections ADD COLUMN image_url VARCHAR(300)")

msi_cols = cols('menu_section_items')
if 'price_override' not in msi_cols:
    cur.execute("ALTER TABLE menu_section_items ADD COLUMN price_override NUMERIC(12,2)")
if 'image_url' not in msi_cols:
    cur.execute("ALTER TABLE menu_section_items ADD COLUMN image_url VARCHAR(300)")


con.commit()

# طباعة ملخص
print('tables:', [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")])
print('menu_sections columns:', cols('menu_sections'))
print('menu_section_items columns:', cols('menu_section_items'))

con.close()
print('DB fix complete.')
