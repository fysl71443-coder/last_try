import os, sys, importlib

import pathlib

# Force local SQLite DB to avoid touching remote production DB
# Use instance/local.db for a clearer, created directory
instance_dir = pathlib.Path(os.path.join(os.path.dirname(__file__), '..', 'instance')).resolve()
instance_dir.mkdir(parents=True, exist_ok=True)
db_file = instance_dir.joinpath('local.db').resolve()
# Use POSIX style path for SQLAlchemy sqlite URI to avoid backslash escaping issues on Windows
os.environ.setdefault('DATABASE_URL', f"sqlite:///{db_file.as_posix()}")
os.environ.setdefault('SECRET_KEY', 'dev')

# Ensure repository root is on sys.path and import the real package 'app'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

pkg = importlib.import_module('app')
app = pkg.create_app()

if __name__ == '__main__':
    # Bind to 127.0.0.1:5001
    app.run(host='127.0.0.1', port=5001, debug=True)

