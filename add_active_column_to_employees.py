"""
Simple migration helper: add `active` column to employees table for SQLite.
Run: python add_active_column_to_employees.py

This will detect if the column exists, and if not, run ALTER TABLE employees ADD COLUMN active INTEGER DEFAULT 1
"""
import sqlite3
import os
from sqlalchemy import create_engine, inspect

# Try to retrieve DATABASE_URL from environment or fallback to sqlite.db
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE') or 'sqlite:///app.db'

if DATABASE_URL.startswith('sqlite:///'):
    path = DATABASE_URL.replace('sqlite:///', '')
    if not os.path.exists(path):
        print('Database file not found:', path)
        print('No action taken.')
        raise SystemExit(1)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    # Check if column exists
    cur.execute("PRAGMA table_info(employees);")
    cols = [r[1] for r in cur.fetchall()]
    if 'active' in cols:
        print('Column `active` already exists in employees table.')
    else:
        print('Adding column `active` to employees table...')
        cur.execute("ALTER TABLE employees ADD COLUMN active INTEGER DEFAULT 1;")
        conn.commit()
        print('Done.')
    conn.close()
else:
    print('This helper only supports SQLite local DB (sqlite:///path).')
    print('DATABASE_URL:', DATABASE_URL)
    raise SystemExit(1)
