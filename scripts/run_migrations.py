import os
import traceback
from sqlalchemy import inspect

try:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from app import app, db
    from flask_migrate import upgrade, stamp
except Exception as e:
    print('IMPORT_ERROR:', e)
    traceback.print_exc()
    raise

if __name__ == '__main__':
    # Ensure instance dir exists
    os.makedirs('instance', exist_ok=True)
    with app.app_context():
        try:
            print('Stamping base...')
            stamp('base')
        except Exception as e:
            print('stamp_base_error:', e)
        try:
            print('Upgrading to heads...')
            upgrade('heads')
        except Exception as e:
            print('upgrade_error:', e)
            traceback.print_exc()
            raise
        insp = inspect(db.engine)
        print('tables:', insp.get_table_names())
        print('has_dining_tables:', insp.has_table('dining_tables'))
        print('migrations_applied_ok')

