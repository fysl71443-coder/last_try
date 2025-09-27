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
print('DB path:', db_path)
print('\nPRAGMA table_info(employees):')
for row in cur.execute('PRAGMA table_info(employees)'):
    print(row)

print('\nSample rows (id, employee_code, active, work_hours, full_name):')
for row in cur.execute('SELECT id, employee_code, active, work_hours, full_name FROM employees ORDER BY id LIMIT 5'):
    print(row)

conn.close()
