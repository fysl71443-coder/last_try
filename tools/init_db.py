"""
Initialize the local SQLite database in instance/local.db by importing the app
and creating all tables via SQLAlchemy's create_all().
Run: python tools/init_db.py
"""
import os, pathlib

instance_dir = pathlib.Path(os.path.join(os.path.dirname(__file__), '..', 'instance')).resolve()
instance_dir.mkdir(parents=True, exist_ok=True)
db_file = instance_dir.joinpath('local.db').resolve()
os.environ['DATABASE_URL'] = f"sqlite:///{db_file.as_posix()}"

# Import app factory and create tables
import importlib
pkg = importlib.import_module('app')
app = pkg.create_app()

with app.app_context():
    from extensions import db
    print('Creating tables...')
    db.create_all()
    print('Done.')
