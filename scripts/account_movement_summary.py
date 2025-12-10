import os
import sqlite3
from datetime import date

def main():
    db = os.path.join('instance', 'accounting_app.db')
    exists = os.path.exists(db)
    print(f"DB: {db} exists={exists}")
    if not exists:
        raise SystemExit("database file not found")
    con = sqlite3.connect(db)
    try:
        cur = con.cursor()
        start = '2025-10-01'
        end = date.today().isoformat()
        cur.execute(
            """
            SELECT a.code,
                   a.name,
                   COUNT(jl.id) AS lines,
                   COALESCE(SUM(jl.debit),0) AS debit,
                   COALESCE(SUM(jl.credit),0) AS credit
            FROM accounts a
            LEFT JOIN journal_lines jl
              ON jl.account_id = a.id
             AND jl.line_date BETWEEN ? AND ?
            GROUP BY a.id
            ORDER BY a.code
            """,
            (start, end),
        )
        rows = cur.fetchall()
        nonzero = [r for r in rows if (r[2] or 0) > 0 and (((r[3] or 0) != 0.0) or ((r[4] or 0) != 0.0))]
        print(f"ROWS={len(rows)} NONZERO={len(nonzero)}")
        for r in nonzero[:120]:
            print(f"{r[0]}\t{r[1]}\tlines={r[2]}\tdebit={float(r[3] or 0):.2f}\tcredit={float(r[4] or 0):.2f}")

        print("SPECIAL")
        cur.execute(
            """
            SELECT a.code,
                   a.name,
                   COALESCE(SUM(jl.debit),0) AS debit,
                   COALESCE(SUM(jl.credit),0) AS credit,
                   COUNT(jl.id) AS lines
            FROM accounts a
            LEFT JOIN journal_lines jl
              ON jl.account_id = a.id
             AND jl.line_date BETWEEN ? AND ?
            WHERE a.code IN ('4013','4014','1130','1140')
            GROUP BY a.id
            ORDER BY a.code
            """,
            (start, end),
        )
        spec = cur.fetchall()
        for r in spec:
            print(f"{r[0]} {r[1]} debit={float(r[2] or 0):.2f} credit={float(r[3] or 0):.2f} lines={int(r[4] or 0)}")
    finally:
        try:
            con.close()
        except Exception:
            pass

if __name__ == '__main__':
    main()

