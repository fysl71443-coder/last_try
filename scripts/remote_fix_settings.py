import os
import sys
import urllib.parse as up
import psycopg2

url = os.getenv('DATABASE_URL')
if not url:
    print('ERROR: DATABASE_URL not set')
    sys.exit(1)

# Masked DSN for log
try:
    parsed = up.urlparse(url)
    safe_netloc = f"{parsed.username}:***@{parsed.hostname}:{parsed.port or ''}".rstrip(':')
    print(f"Connecting to {parsed.scheme}://{safe_netloc}{parsed.path}")
except Exception:
    print('Connecting to remote database')

conn = None
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    # Determine existing columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'settings'
    """)
    existing = {row[0] for row in cur.fetchall()}

    targets = [
        ("china_town_phone1", "VARCHAR(50)"),
        ("china_town_phone2", "VARCHAR(50)"),
        ("place_india_phone1", "VARCHAR(50)"),
        ("place_india_phone2", "VARCHAR(50)")
    ]

    added = 0
    for name, coltype in targets:
        if name in existing:
            print(f"Exists: {name}")
            continue
        try:
            cur.execute(f"ALTER TABLE settings ADD COLUMN {name} {coltype}")
            print(f"Added: {name}")
            added += 1
        except Exception as e:
            print(f"Failed to add {name}: {e}")

    print(f"Done. Added {added} column(s).")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    try:
        if conn: conn.close()
    except Exception:
        pass
