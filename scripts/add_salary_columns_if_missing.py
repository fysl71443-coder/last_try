#!/usr/bin/env python3
"""Add extra, absence, incentive columns to salaries table if missing (fix for payroll run)."""
import os
import sys

_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _base)
os.chdir(_base)

_instance = os.path.join(_base, 'instance')
_db_path = os.getenv('LOCAL_SQLITE_PATH') or os.path.join(_instance, 'accounting_app.db')

def main():
    import sqlite3
    if not os.path.exists(_db_path):
        print('DB not found:', _db_path)
        return 1
    conn = sqlite3.connect(_db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(salaries)")
    cols = [row[1] for row in cur.fetchall()]
    added = []
    for name, sql in [
        ('extra', 'ALTER TABLE salaries ADD COLUMN extra NUMERIC(12,2) DEFAULT 0'),
        ('absence', 'ALTER TABLE salaries ADD COLUMN absence NUMERIC(12,2) DEFAULT 0'),
        ('incentive', 'ALTER TABLE salaries ADD COLUMN incentive NUMERIC(12,2) DEFAULT 0'),
    ]:
        if name not in cols:
            try:
                cur.execute(sql)
                added.append(name)
            except Exception as e:
                print('Error adding', name, ':', e)
    conn.commit()
    conn.close()
    if added:
        print('Added columns to salaries:', ', '.join(added))
    else:
        print('salaries table already has extra, absence, incentive.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
