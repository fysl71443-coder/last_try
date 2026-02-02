#!/usr/bin/env python3
"""
Verify SQLite DB connection, list tables, and check required tables/columns.
Run from project root: python tools/check_db_tables.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ.setdefault('USE_EVENTLET', '0')
os.environ.setdefault('DISABLE_SOCKETIO', '1')
u = os.environ.get('DATABASE_URL') or ''
if 'postgres' in u.lower() or 'render.com' in u.lower():
    os.environ.pop('DATABASE_URL', None)
instance_dir = os.path.join(ROOT, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, 'accounting_app.db')
os.environ.setdefault('LOCAL_SQLITE_PATH', db_path)
os.environ.setdefault('DATABASE_URL', 'sqlite:///' + db_path.replace('\\', '/'))

def main():
    from sqlalchemy import text, inspect
    from app import create_app
    from extensions import db

    app = create_app()
    with app.app_context():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print('DB URI:', uri[:60] + '...' if len(uri) > 60 else uri)
        print('DB path:', db_path)
        print('Exists:', os.path.isfile(db_path))

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print('\nTables:', len(tables))
        for t in sorted(tables):
            print('  -', t)

        required = ['settings', 'accounts', 'users', 'journal_entries', 'journal_lines', 'app_kv']
        missing = [t for t in required if t not in tables]
        if missing:
            print('\nMissing tables:', missing)
        else:
            print('\nRequired tables OK')

        if 'settings' in tables:
            cols = [c['name'] for c in inspector.get_columns('settings')]
            print('\nSettings columns:', len(cols))
            for k in ['company_name', 'tax_number', 'vat_rate', 'logo_url']:
                print('    ', k, ':', 'OK' if k in cols else 'MISSING')
            try:
                from models import Settings
                n = Settings.query.count()
                print('    Settings rows:', n)
            except Exception as e:
                print('    Settings query error:', e)

        if 'app_kv' in tables:
            try:
                from app.models import AppKV
                n = AppKV.query.count()
                print('\napp_kv rows:', n)
            except Exception as e:
                print('\napp_kv query error:', e)

    print('\nDone.')

if __name__ == '__main__':
    main()
