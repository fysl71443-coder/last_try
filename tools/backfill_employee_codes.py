import os, sqlite3

db_url = os.getenv('DATABASE_URL', 'sqlite:///instance/local.db')
if not db_url.startswith('sqlite:///'):
    print('Unsupported DATABASE_URL:', db_url)
    raise SystemExit(1)

db_path = db_url.replace('sqlite:///', '')
if not os.path.exists(db_path):
    print('Database file not found:', db_path)
    raise SystemExit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    rows = cur.execute('SELECT id, employee_code FROM employees').fetchall()
except Exception as e:
    print('Error reading employees table:', e)
    conn.close()
    raise

cnt = 0
for eid, code in rows:
    cur_code = (code or '').strip()
    # if empty or not 4-digit padded, normalize
    if cur_code == '' or not (len(cur_code) == 4 and cur_code.isdigit()):
        new_code = f"{eid:04d}"
        try:
            cur.execute('UPDATE employees SET employee_code=? WHERE id=?', (new_code, eid))
            cnt += 1
        except Exception as ex:
            print('Failed to update', eid, ex)

conn.commit()
print('Backfill complete. Rows updated:', cnt)
conn.close()
