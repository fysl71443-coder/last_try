import os, sys
import tempfile
import pytest

# Ensure project root in path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db

@pytest.fixture(scope='session')
def test_app():
    # Configure app for testing with isolated SQLite temp DB
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    fd, db_path = tempfile.mkstemp(prefix='test_db_', suffix='.sqlite')
    os.close(fd)
    uri = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    # Avoid pool with SQLite for tests
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'echo': False,
        'connect_args': {'check_same_thread': False}
    }

    with app.app_context():
        db.drop_all()
        db.create_all()
    try:
        yield app
    finally:
        try:
            os.remove(db_path)
        except Exception:
            pass

@pytest.fixture()
def client(test_app):
    return test_app.test_client()

