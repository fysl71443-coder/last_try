import os
import sys
import importlib.util
from typing import Optional

# Ensure repo root on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Load app package explicitly by path to avoid clash with top-level app.py
APP_INIT_PATH = os.path.join(REPO_ROOT, 'app', '__init__.py')
MODELS_PATH = os.path.join(REPO_ROOT, 'app', 'models.py')

spec_app = importlib.util.spec_from_file_location('app_pkg', APP_INIT_PATH)
app_pkg = importlib.util.module_from_spec(spec_app)
spec_app.loader.exec_module(app_pkg)  # type: ignore

# Expose as 'app' for any internal imports "from app import ..."
sys.modules.setdefault('app', app_pkg)

# Load models
spec_models = importlib.util.spec_from_file_location('app_models', MODELS_PATH)
app_models = importlib.util.module_from_spec(spec_models)
spec_models.loader.exec_module(app_models)  # type: ignore

# Also expose under package name if referenced
sys.modules.setdefault('app.models', app_models)

create_app = getattr(app_pkg, 'create_app')
db = getattr(app_pkg, 'db')

User = getattr(app_models, 'User')


def check_admin(password: str) -> str:
    app = create_app()
    with app.app_context():
        admin: Optional[User] = User.query.filter_by(username='admin').first()
        if not admin:
            return 'missing'
        try:
            return 'exists-valid' if admin.check_password(password) else 'exists-invalid'
        except Exception:
            return 'exists-unknown'


def ensure_admin(new_password: str, reset_if_exists: bool = False) -> str:
    app = create_app()
    with app.app_context():
        admin: Optional[User] = User.query.filter_by(username='admin').first()
        if admin:
            if reset_if_exists:
                admin.set_password(new_password)
                db.session.commit()
                return 'updated'
            else:
                return 'exists'
        else:
            admin = User(username='admin')
            admin.set_password(new_password)
            db.session.add(admin)
            db.session.commit()
            return 'created'


def main():
    # Usage:
    #   python scripts/ensure_admin_user.py --check [password]
    #   python scripts/ensure_admin_user.py [password] [--reset]
    args = sys.argv[1:]
    if not args:
        args = ['--check', 'admin123']

    if args[0] == '--check':
        pw = args[1] if len(args) > 1 else 'admin123'
        status = check_admin(pw)
        print(f"Check: {status}")
        return

    pw = args[0] if args and not args[0].startswith('-') else 'admin123'
    reset = ('--reset' in args)
    result = ensure_admin(pw, reset_if_exists=reset)
    print(f"Result: {result}")


if __name__ == '__main__':
    main()

