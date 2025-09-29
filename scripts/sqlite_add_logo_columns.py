import os
import sys
import sqlite3

# Ensure project root import path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from extensions import db


def ensure_logo_columns(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        cur.execute("PRAGMA table_info(settings)")
        existing = {row[1] for row in cur.fetchall()}

        def add(col: str, coldef: str) -> None:
            if col in existing:
                print(f"Exists: {col}")
                return
            try:
                cur.execute(f"ALTER TABLE settings ADD COLUMN {col} {coldef}")
                print(f"Added: {col}")
            except Exception as e:
                print(f"Failed to add {col}: {e}")

        add("china_town_logo_url", "VARCHAR(300)")
        add("place_india_logo_url", "VARCHAR(300)")
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    app = create_app()
    with app.app_context():
        engine = db.engine
        if engine.dialect.name != "sqlite":
            print("Not a SQLite database; skipping (dialect:", engine.dialect.name, ")")
            return 0
        db_path = engine.url.database or os.path.join("instance", "accounting_app.db")
        print("SQLite DB:", os.path.abspath(db_path))
        ensure_logo_columns(db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


