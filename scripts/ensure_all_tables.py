import os
import sys
from contextlib import suppress

from sqlalchemy import inspect

# Ensure project root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from app import create_app
    from extensions import db
except Exception as e:
    print(f"ERROR: Failed to import app context: {e}")
    sys.exit(1)


def main():
    app = create_app()
    with app.app_context():
        engine = db.engine
        insp = inspect(engine)
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        print(f"Using DB: {uri}")

        before = set(insp.get_table_names())
        print(f"Existing tables before: {len(before)}")

        # Create all missing tables based on SQLAlchemy models
        db.create_all()

        # Re-inspect after creation
        insp = inspect(engine)
        after = set(insp.get_table_names())
        created = sorted(list(after - before))
        print(f"Newly created tables: {created}")
        print(f"Total tables after: {len(after)}")

        # Optional: ensure default settings row exists
        with suppress(Exception):
            from models import Settings  # noqa: F401
            if db.session.execute(db.text("SELECT COUNT(*) FROM settings")).scalar() == 0:
                db.session.execute(db.text("INSERT INTO settings (company_name) VALUES ('')"))
                db.session.commit()
                print("Inserted default settings row")

    return 0


if __name__ == "__main__":
    sys.exit(main())


