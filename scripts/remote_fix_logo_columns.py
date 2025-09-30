import os
import sys
import urllib.parse as up
import psycopg2

def ensure_columns(conn, table, targets):
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    existing = {row[0] for row in cur.fetchall()}
    added = 0
    for name, coltype in targets:
        if name in existing:
            print(f"Exists: {name}")
            continue
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
            print(f"Added: {name}")
            added += 1
        except Exception as e:
            print(f"Failed to add {name}: {e}")
    cur.close()
    return added

url = os.getenv('DATABASE_URL')
if not url:
    print('ERROR: DATABASE_URL not set')
    sys.exit(1)

parsed = up.urlparse(url)
print(f"Connecting to {parsed.scheme}://{parsed.hostname}:{parsed.port or ''}{parsed.path}")

conn = psycopg2.connect(url)
conn.autocommit = True
try:
    targets = [
        ("china_town_logo_url", "VARCHAR(300)"),
        ("place_india_logo_url", "VARCHAR(300)")
    ]
    added = ensure_columns(conn, 'settings', targets)
    print(f"Done. Added {added} column(s).")
finally:
    conn.close()
