#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة فهارس لدعم استعلامات GL (JournalLine + LedgerEntry) وتقارير نهاية الفترة.
تشغيل مرة واحدة أو عبر آلية migration.

الفهارس:
- journal_lines: line_date (استعلامات asof)، (account_id, line_date)، (journal_id, line_date)
- ledger_entries: account_id (تجميع حسب الحساب)
"""
from __future__ import annotations

import os
import sys

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)

    from app import create_app
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        from app import db
        conn = db.engine.connect()
        indexes_jl = [
            ("ix_journal_lines_line_date", "journal_lines", "line_date"),
            ("ix_journal_lines_account_id_line_date", "journal_lines", "account_id, line_date"),
            ("ix_journal_lines_journal_id_line_date", "journal_lines", "journal_id, line_date"),
        ]
        indexes_le = [
            ("ix_ledger_entries_account_id", "ledger_entries", "account_id"),
        ]
        created = []
        for name, table, cols in indexes_jl + indexes_le:
            try:
                if db.engine.dialect.name == "sqlite":
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})"))
                else:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})"))
                conn.commit()
                created.append(name)
            except Exception as e:
                print(f"Index {name}: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
        print("Created or existing indexes:", created)
        conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
