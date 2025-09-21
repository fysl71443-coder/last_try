import os, sys, importlib

# Force local SQLite DB to avoid touching remote production DB
os.environ.setdefault('DATABASE_URL', 'sqlite:///local.db')
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

