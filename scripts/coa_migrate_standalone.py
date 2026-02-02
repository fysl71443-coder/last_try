# -*- coding: utf-8 -*-
"""
هجرة شجرة الحسابات دون تحميل تطبيق Flask. اتصال مباشر بـ SQLite.
"""
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ.setdefault("USE_EVENTLET", "0")
os.environ.setdefault("DISABLE_SOCKETIO", "1")
instance_dir = os.path.join(ROOT, "instance")
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, "local.db").replace("\\", "/")
# استخدم SQLite المحلي إلا إذا طُلِب صراحة استخدام DATABASE_URL (مثلاً لـ PostgreSQL)
use_env_db = os.environ.get("COA_MIGRATE_USE_ENV_DB", "").strip().lower() in ("1", "true", "yes")
db_url = os.environ.get("DATABASE_URL") if use_env_db else ("sqlite:///" + db_path)

def main():
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    from data.coa_new_tree import NEW_COA_TREE, OLD_TO_NEW_MAP, LEAF_CODES

    # 1) Ensure extended columns
    is_pg = "postgresql" in db_url or "postgres" in db_url
    def get_columns():
        try:
            if is_pg:
                r = session.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'accounts'"
                ))
                return [row[0] for row in r.fetchall()]
            r = session.execute(text("PRAGMA table_info(accounts)"))
            return [row[1] for row in r.fetchall()]
        except Exception as e:
            print("get_columns:", e)
            session.rollback()
            return []
    try:
        session.rollback()
    except Exception:
        pass
    cols = get_columns()
    for col, defn in [
        ("name_ar", "VARCHAR(200)"),
        ("name_en", "VARCHAR(200)"),
        ("level", "INTEGER"),
        ("parent_account_code", "VARCHAR(20)"),
        ("allow_opening_balance", "BOOLEAN DEFAULT TRUE" if is_pg else "BOOLEAN DEFAULT 1"),
        ("active", "BOOLEAN DEFAULT TRUE" if is_pg else "BOOLEAN DEFAULT 1"),
    ]:
        try:
            if col not in cols:
                session.execute(text(f"ALTER TABLE accounts ADD COLUMN {col} {defn}"))
                session.commit()
                cols.append(col)
        except Exception as e:
            session.rollback()
    try:
        session.commit()
    except Exception:
        session.rollback()

    # 2) Insert new accounts
    created = 0
    for row in NEW_COA_TREE:
        code, name_ar, name_en, atype, parent_code, level = row
        r = session.execute(text("SELECT id FROM accounts WHERE code = :c"), {"c": code})
        existing = r.fetchone()
        allow = 1 if code in LEAF_CODES else 0
        if existing:
            try:
                session.execute(text("""
                    UPDATE accounts SET name=:n, type=:t, name_ar=:na, name_en=:ne,
                    parent_account_code=:p, level=:l, allow_opening_balance=:a, active=1
                    WHERE code=:c
                """), {"n": name_ar, "t": atype, "na": name_ar, "ne": name_en, "p": parent_code, "l": level, "a": allow, "c": code})
            except Exception:
                pass
            continue
        try:
            session.execute(text("""
                INSERT INTO accounts (code, name, type, name_ar, name_en, parent_account_code, level, allow_opening_balance, active)
                VALUES (:c, :n, :t, :na, :ne, :p, :l, :a, 1)
            """), {"c": code, "n": name_ar, "t": atype, "na": name_ar, "ne": name_en, "p": parent_code, "l": level, "a": allow})
            created += 1
        except Exception as e:
            print("Insert", code, ":", e)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print("Commit (accounts) failed:", e)
        return
    print("Accounts added/updated:", created)

    # 3) Build id map
    id_map = {}
    for old_code, new_code in OLD_TO_NEW_MAP.items():
        old_code = str(old_code).strip()
        new_code = str(new_code).strip()
        if old_code == new_code:
            continue
        o = session.execute(text("SELECT id FROM accounts WHERE code = :c"), {"c": old_code}).fetchone()
        n = session.execute(text("SELECT id FROM accounts WHERE code = :c"), {"c": new_code}).fetchone()
        if o and n and o[0] != n[0]:
            id_map[o[0]] = n[0]
    print("Old->New id map size:", len(id_map))

    # 4) Migrate journal_lines
    jl = 0
    for old_id, new_id in id_map.items():
        r = session.execute(text("UPDATE journal_lines SET account_id = :n WHERE account_id = :o"), {"n": new_id, "o": old_id})
        jl += r.rowcount
    print("JournalLine updated:", jl)

    # 5) Migrate ledger_entries
    le = 0
    for old_id, new_id in id_map.items():
        r = session.execute(text("UPDATE ledger_entries SET account_id = :n WHERE account_id = :o"), {"n": new_id, "o": old_id})
        le += r.rowcount
    print("LedgerEntry updated:", le)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print("Commit (migrate) failed:", e)
        return
    print("Done. No accounts deleted.")
    session.close()

if __name__ == "__main__":
    main()
