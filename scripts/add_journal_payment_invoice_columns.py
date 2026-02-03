#!/usr/bin/env python3
"""إضافة أعمدة ربط القيد بالدفعة/الفاتورة — تشغيل مرة واحدة إذا لم تُنفَّذ الهجرة.
مصدر الحقيقة: قيود اليومية المنشورة فقط.
"""
import os
import sys

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base)
os.chdir(base)

def main():
    from app import create_app
    from extensions import db
    app = create_app()
    with app.app_context():
        conn = db.engine.raw_connection()
        cur = conn.cursor()
        try:
            # journal_entries.payment_method
            cur.execute("PRAGMA table_info(journal_entries)")
            je_cols = [r[1] for r in cur.fetchall()]
            if 'payment_method' not in je_cols:
                cur.execute("ALTER TABLE journal_entries ADD COLUMN payment_method VARCHAR(20)")
                print("Added journal_entries.payment_method")
            # journal_lines.invoice_id, invoice_type
            cur.execute("PRAGMA table_info(journal_lines)")
            jl_cols = [r[1] for r in cur.fetchall()]
            if 'invoice_id' not in jl_cols:
                cur.execute("ALTER TABLE journal_lines ADD COLUMN invoice_id INTEGER")
                print("Added journal_lines.invoice_id")
            if 'invoice_type' not in jl_cols:
                cur.execute("ALTER TABLE journal_lines ADD COLUMN invoice_type VARCHAR(20)")
                print("Added journal_lines.invoice_type")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_journal_lines_invoice_id ON journal_lines (invoice_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_journal_lines_invoice_type ON journal_lines (invoice_type)")
            conn.commit()
            print("Done. Journal payment/invoice columns are in place.")
        except Exception as e:
            conn.rollback()
            print("Error:", e)
            raise
        finally:
            conn.close()

if __name__ == "__main__":
    main()
