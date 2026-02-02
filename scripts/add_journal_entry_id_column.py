#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
إضافة عمود journal_entry_id إلى sales_invoices إذا لم يكن موجوداً.
يستخدم نفس SQLite كما في التطبيق.
"""
import os
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
os.chdir(base_dir)

instance_dir = os.path.join(base_dir, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, 'accounting_app.db')
os.environ.pop('DATABASE_URL', None)
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
os.environ.setdefault('LOCAL_SQLITE_PATH', db_path)
os.environ.setdefault('SECRET_KEY', 'dev')

import sqlite3


def main():
    print(f"DB: {db_path}")
    if not os.path.isfile(db_path):
        print("Database file not found.")
        return 1
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(sales_invoices)")
        cols = [r[1] for r in cur.fetchall()]
        if 'journal_entry_id' in cols:
            print("Column journal_entry_id already exists.")
            return 0
        cur.execute("ALTER TABLE sales_invoices ADD COLUMN journal_entry_id INTEGER")
        conn.commit()
        print("Added column journal_entry_id to sales_invoices.")
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
