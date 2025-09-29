import os, sqlite3

db_path = os.path.join('instance', 'accounting_app.db')
os.makedirs('instance', exist_ok=True)
print('DB path:', os.path.abspath(db_path))

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY AUTOINCREMENT)")
cur.execute("PRAGMA table_info(settings)")
existing = {row[1] for row in cur.fetchall()}
print('Existing columns:', len(existing))

def add(col, coldef):
    if col in existing:
        print('Exists:', col)
        return 0
    try:
        cur.execute(f"ALTER TABLE settings ADD COLUMN {col} {coldef}")
        print('Added:', col)
        return 1
    except Exception as e:
        print('Failed to add', col, 'error:', e)
        return 0

added = 0
added += add('china_town_phone1', 'VARCHAR(50)')
added += add('china_town_phone2', 'VARCHAR(50)')
added += add('place_india_phone1', 'VARCHAR(50)')
added += add('place_india_phone2', 'VARCHAR(50)')

conn.commit()
conn.close()
print('Done. Added', added, 'column(s).')
