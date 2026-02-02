#!/usr/bin/env python3
"""Add missing columns to settings table."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('USE_EVENTLET', '0')
os.environ.setdefault('DISABLE_SOCKETIO', '1')
db_path = os.path.join(ROOT, 'instance', 'accounting_app.db')
os.environ.setdefault('LOCAL_SQLITE_PATH', db_path)
os.environ.setdefault('DATABASE_URL', 'sqlite:///' + db_path.replace('\\', '/'))

def main():
    from sqlalchemy import text
    from app import create_app
    from extensions import db
    from models import Settings

    app = create_app()
    with app.app_context():
        with db.engine.connect() as conn:
            ri = conn.execute(text("PRAGMA table_info(settings)")).fetchall()
            existing = {str(r[1]).lower() for r in ri}
        print("Existing settings columns:", len(existing))

        added = []
        with db.engine.connect() as conn:
            for col in Settings.__table__.c:
                c = col.key
                if c.lower() in existing:
                    continue
                t = type(col.type).__name__
                if "Int" in t or "Bool" in t:
                    sqltyp = "INTEGER"
                elif "Numeric" in t or "Float" in t or "Real" in t:
                    sqltyp = "REAL"
                else:
                    sqltyp = "TEXT"
                try:
                    sql = "ALTER TABLE settings ADD COLUMN %s %s" % (c, sqltyp)
                    conn.execute(text(sql))
                    conn.commit()
                    added.append(c)
                except Exception as e:
                    print("ALTER failed for", c, ":", e)

        print("Added columns:", added or "(none)")

if __name__ == "__main__":
    main()
