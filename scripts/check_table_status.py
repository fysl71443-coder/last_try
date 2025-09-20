import argparse
import sys
from typing import List, Tuple


def normalize_branch_candidates(branch: str) -> List[str]:
    b = (branch or '').strip()
    bl = b.lower().replace('-', '_')
    cand = {bl, bl.replace(' ', '_'), bl.replace('_', ' ')}
    if 'india' in bl:
        cand |= {'place_india', 'palace_india', 'place india', 'palace india', 'india place'}
    if 'china' in bl:
        cand |= {'china_town', 'china town', 'china'}
    return sorted({c.lower() for c in cand})


def sqlite_check(db_path: str, branch: str, table_no: int) -> Tuple[str, int]:
    import sqlite3
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        # Prepare branch candidates
        bcands = normalize_branch_candidates(branch)
        placeholders = ','.join(['?'] * len(bcands))
        # Detect columns presence
        def has_column(table: str, col: str) -> bool:
            cur.execute(f"PRAGMA table_info('{table}')")
            return any(row[1].lower() == col.lower() for row in cur.fetchall())

        # 1) tables.status (cast to text to compare reliably)
        table_status = None
        if has_column('tables', 'status') and has_column('tables', 'branch_code') and has_column('tables', 'table_number'):
            q1 = f"""
            SELECT status FROM tables
            WHERE lower(branch_code) IN ({placeholders})
              AND CAST(table_number AS TEXT) = ?
            LIMIT 1
            """
            cur.execute(q1, (*bcands, str(table_no)))
            row = cur.fetchone()
            table_status = row[0] if row else None

        # 2) draft_orders count (handle table_number string and legacy table_no int)
        draft_count = 0
        if has_column('draft_orders', 'branch_code') and has_column('draft_orders', 'status'):
            has_tblno = has_column('draft_orders', 'table_no')
            has_tblnum = has_column('draft_orders', 'table_number')
            if has_tblnum and has_tblno:
                q2 = f"""
                SELECT COUNT(*) FROM draft_orders
                WHERE lower(branch_code) IN ({placeholders})
                  AND status = 'draft'
                  AND (CAST(table_number AS TEXT) = ? OR table_no = ?)
                """
                cur.execute(q2, (*bcands, str(table_no), int(table_no)))
            elif has_tblnum:
                q2 = f"""
                SELECT COUNT(*) FROM draft_orders
                WHERE lower(branch_code) IN ({placeholders})
                  AND status = 'draft'
                  AND CAST(table_number AS TEXT) = ?
                """
                cur.execute(q2, (*bcands, str(table_no)))
            elif has_tblno:
                q2 = f"""
                SELECT COUNT(*) FROM draft_orders
                WHERE lower(branch_code) IN ({placeholders})
                  AND status = 'draft'
                  AND table_no = ?
                """
                cur.execute(q2, (*bcands, int(table_no)))
            else:
                draft_count = 0
            if cur.description is not None:
                row = cur.fetchone()
                draft_count = int(row[0]) if row else 0

        return table_status, draft_count
    finally:
        con.close()


def mysql_check(host: str, user: str, password: str, database: str, branch: str, table_no: int) -> Tuple[str, int]:
    import mysql.connector as m
    con = m.connect(host=host, user=user, password=password, database=database)
    cur = con.cursor()
    try:
        bcands = normalize_branch_candidates(branch)
        placeholders = ','.join(['%s'] * len(bcands))

        def has_column(table: str, col: str) -> bool:
            cur.execute(
                """
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
                LIMIT 1
                """,
                (database, table, col),
            )
            return cur.fetchone() is not None

        # 1) tables.status
        table_status = None
        if has_column('tables', 'status') and has_column('tables', 'branch_code') and has_column('tables', 'table_number'):
            q1 = f"""
            SELECT status FROM tables
            WHERE lower(branch_code) IN ({placeholders})
              AND CAST(table_number AS CHAR) = %s
            LIMIT 1
            """
            cur.execute(q1, (*bcands, str(table_no)))
            row = cur.fetchone()
            table_status = row[0] if row else None

        # 2) draft_orders count
        draft_count = 0
        if has_column('draft_orders', 'status') and has_column('draft_orders', 'branch_code'):
            has_tblno = has_column('draft_orders', 'table_no')
            has_tblnum = has_column('draft_orders', 'table_number')
            if has_tblnum and has_tblno:
                q2 = f"""
                SELECT COUNT(*) FROM draft_orders
                WHERE lower(branch_code) IN ({placeholders})
                  AND status='draft'
                  AND (CAST(table_number AS CHAR) = %s OR table_no = %s)
                """
                cur.execute(q2, (*bcands, str(table_no), int(table_no)))
            elif has_tblnum:
                q2 = f"""
                SELECT COUNT(*) FROM draft_orders
                WHERE lower(branch_code) IN ({placeholders})
                  AND status='draft'
                  AND CAST(table_number AS CHAR) = %s
                """
                cur.execute(q2, (*bcands, str(table_no)))
            elif has_tblno:
                q2 = f"""
                SELECT COUNT(*) FROM draft_orders
                WHERE lower(branch_code) IN ({placeholders})
                  AND status='draft'
                  AND table_no = %s
                """
                cur.execute(q2, (*bcands, int(table_no)))
            row = cur.fetchone()
            draft_count = int(row[0]) if row else 0

        return table_status, draft_count
    finally:
        try:
            cur.close()
        except Exception:
            pass
        con.close()


def main():
    p = argparse.ArgumentParser(description='Check table status and draft count')
    p.add_argument('--engine', choices=['sqlite', 'mysql'], default='sqlite')
    p.add_argument('--db', default='instance/app.db', help='SQLite path or ignored for MySQL')
    p.add_argument('--branch', default='china_town')
    p.add_argument('--table', type=int, default=1)
    # MySQL params
    p.add_argument('--host', default='localhost')
    p.add_argument('--user', default='root')
    p.add_argument('--password', default='password')
    p.add_argument('--database', default='app')
    args = p.parse_args()

    if args.engine == 'sqlite':
        ts, dc = sqlite_check(args.db, args.branch, args.table)
    else:
        ts, dc = mysql_check(args.host, args.user, args.password, args.database, args.branch, args.table)

    print(f"\n📊 Result for branch={args.branch} table={args.table}")
    print(f"- tables.status = {ts if ts is not None else 'NOT FOUND'}")
    print(f"- draft_orders.count(draft) = {dc}")
    if ts and isinstance(ts, str) and ts.lower() == 'available' and dc == 0:
        print("✅ GREEN: table is available")
        sys.exit(0)
    else:
        print("❌ RED: table is occupied (either status or drafts)")
        sys.exit(1)


if __name__ == '__main__':
    main()

