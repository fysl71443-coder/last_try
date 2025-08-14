import os
from app import app, db
from sqlalchemy import inspect

if __name__ == '__main__':
    os.makedirs('instance', exist_ok=True)
    with app.app_context():
        insp = inspect(db.engine)
        before = set(insp.get_table_names())
        db.create_all()
        insp = inspect(db.engine)
        after = set(insp.get_table_names())
        print('created_tables:', sorted(list(after - before)))
        print('ok')

