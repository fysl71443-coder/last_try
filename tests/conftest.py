import os
import sys
import tempfile
import warnings

import pytest

# Ensure project root in path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# عدم إظهار تحذيرات من المكتبات لتحقيق نتيجة 100% بدون تحذيرات
warnings.filterwarnings("ignore", category=DeprecationWarning, module="flask_babel")
warnings.filterwarnings("ignore", message=".*Query\\.get\\(\\)*")
warnings.filterwarnings("ignore", message=".*locked_cached_property.*")
try:
    from sqlalchemy.exc import LegacyAPIWarning
    warnings.filterwarnings("ignore", category=LegacyAPIWarning)
except ImportError:
    pass

from app import app, db


def pytest_configure(config):
    """تسجيل فلتر التحذيرات في pytest لضمان 0 تحذيرات."""
    config.addinivalue_line("filterwarnings", "ignore::DeprecationWarning:flask_babel.*")
    config.addinivalue_line("filterwarnings", "ignore::sqlalchemy.exc.LegacyAPIWarning")


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

