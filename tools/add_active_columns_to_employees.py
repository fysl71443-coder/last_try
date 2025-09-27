import os
import sqlite3

def add_missing_columns(db_path: str):
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get existing columns
    cur.execute("PRAGMA table_info(employees)")
    cols = [row[1] for row in cur.fetchall()]

    # Add 'active'
    if "active" not in cols:
        print("➡️ Adding 'active' column...")
        cur.execute("ALTER TABLE employees ADD COLUMN active INTEGER DEFAULT 1")
        conn.commit()
        print("✅ Column 'active' added.")
    else:
        print("ℹ️ Column 'active' already exists.")

    # Add 'work_hours'
    if "work_hours" not in cols:
        print("➡️ Adding 'work_hours' column...")
        cur.execute("ALTER TABLE employees ADD COLUMN work_hours INTEGER DEFAULT 0")
        conn.commit()
        print("✅ Column 'work_hours' added.")
    else:
        print("ℹ️ Column 'work_hours' already exists.")

    # Add 'employee_code'
    if "employee_code" not in cols:
        print("➡️ Adding 'employee_code' column...")
        cur.execute("ALTER TABLE employees ADD COLUMN employee_code TEXT UNIQUE")
        conn.commit()
        print("✅ Column 'employee_code' added.")
    else:
        print("ℹ️ Column 'employee_code' already exists.")

    conn.close()


if __name__ == "__main__":
    # Get database path from environment variable
    db_url = os.getenv("DATABASE_URL", "sqlite:///local.db")
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        add_missing_columns(db_path)
    else:
        print(f"❌ Unsupported DATABASE_URL: {db_url}")
