#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""إضافة أعمدة usage_group, is_control, allow_posting لجدول accounts وجدول account_usage_map. تشغيل مرة واحدة إذا ظهر خطأ no such column: accounts.usage_group"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from app import create_app
    from extensions import db
    from sqlalchemy import text
    app = create_app()
    with app.app_context():
        with db.engine.connect() as conn:
            for col, typ in [('usage_group', 'VARCHAR(30)'), ('is_control', 'INTEGER'), ('allow_posting', 'INTEGER')]:
                try:
                    conn.execute(text(f"ALTER TABLE accounts ADD COLUMN {col} {typ}"))
                    conn.commit()
                    print(f"Added column accounts.{col}")
                except Exception as e:
                    conn.rollback()
                    print(f"Column accounts.{col}: {e}")
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS account_usage_map (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        module VARCHAR(50) NOT NULL,
                        action VARCHAR(50) NOT NULL,
                        usage_group VARCHAR(30) NOT NULL,
                        function_key VARCHAR(50),
                        function_label_ar VARCHAR(120),
                        account_id INTEGER NOT NULL,
                        is_default INTEGER,
                        active INTEGER,
                        locked INTEGER,
                        FOREIGN KEY(account_id) REFERENCES accounts (id)
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_account_usage_map_module ON account_usage_map (module)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_account_usage_map_usage_group ON account_usage_map (usage_group)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_account_usage_map_account_id ON account_usage_map (account_id)"))
                conn.commit()
                print("Created table account_usage_map")
            except Exception as e:
                conn.rollback()
                print(f"account_usage_map: {e}")
            for col, typ in [('function_key', 'VARCHAR(50)'), ('function_label_ar', 'VARCHAR(120)'), ('locked', 'INTEGER')]:
                try:
                    conn.execute(text(f"ALTER TABLE account_usage_map ADD COLUMN {col} {typ}"))
                    conn.commit()
                    print(f"Added column account_usage_map.{col}")
                except Exception as e2:
                    conn.rollback()
                    print(f"Column account_usage_map.{col}: {e2}")
    print("Done.")

if __name__ == '__main__':
    main()
