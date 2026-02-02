# -*- coding: utf-8 -*-
"""
استبدال شجرة الحسابات بالشجرة المعتمدة (data/coa_new_tree).
- إضافة الحسابات الجديدة فقط (بدون حذف).
- نقل حركات journal_lines و ledger_entries من الحسابات القديمة إلى الجديدة حسب خريطة old→new.
- عدم حذف أي حساب (لا فقدان بيانات).
"""
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# بيئة التطبيق
os.environ.setdefault("USE_EVENTLET", "0")
os.environ.setdefault("DISABLE_SOCKETIO", "1")
instance_dir = os.path.join(ROOT, "instance")
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, "local.db").replace("\\", "/")
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///" + db_path

def main():
    from app import create_app, db
    from models import Account, JournalLine, LedgerEntry

    app = create_app()
    with app.app_context():
        from data.coa_new_tree import NEW_COA_TREE, OLD_TO_NEW_MAP, LEAF_CODES

        # 1) Ensure extended columns on accounts
        try:
            from app.routes import ensure_account_extended_columns
            ensure_account_extended_columns()
        except Exception as e:
            print("ensure_account_extended_columns:", e)

        # 2) Add new accounts (skip if code exists)
        created = 0
        for row in NEW_COA_TREE:
            code, name_ar, name_en, atype, parent_code, level = row
            a = db.session.query(Account).filter(Account.code == code).first()
            if a:
                # تحديث اسم/نوع فقط إن وُجد
                try:
                    a.name = name_ar
                    if hasattr(a, "name_ar"):
                        a.name_ar = name_ar
                    if hasattr(a, "name_en"):
                        a.name_en = name_en
                    if hasattr(a, "type"):
                        a.type = atype
                    if hasattr(a, "parent_account_code"):
                        a.parent_account_code = parent_code
                    if hasattr(a, "level"):
                        a.level = level
                    if hasattr(a, "allow_opening_balance"):
                        a.allow_opening_balance = code in LEAF_CODES
                    if hasattr(a, "active"):
                        a.active = True
                except Exception:
                    pass
                continue
            a = Account(code=code, name=name_ar, type=atype)
            try:
                if hasattr(a, "name_ar"):
                    a.name_ar = name_ar
                if hasattr(a, "name_en"):
                    a.name_en = name_en
                if hasattr(a, "parent_account_code"):
                    a.parent_account_code = parent_code
                if hasattr(a, "level"):
                    a.level = level
                if hasattr(a, "allow_opening_balance"):
                    a.allow_opening_balance = code in LEAF_CODES
                if hasattr(a, "active"):
                    a.active = True
            except Exception:
                pass
            db.session.add(a)
            created += 1

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Commit (add accounts) failed:", e)
            return

        print("Accounts added/updated:", created)

        # 3) Build old account_id -> new account_id map
        id_map = {}
        for old_code, new_code in OLD_TO_NEW_MAP.items():
            old_code = str(old_code).strip()
            new_code = str(new_code).strip()
            if old_code == new_code:
                continue
            old_acc = db.session.query(Account).filter(Account.code == old_code).first()
            new_acc = db.session.query(Account).filter(Account.code == new_code).first()
            if old_acc and new_acc and old_acc.id != new_acc.id:
                id_map[old_acc.id] = new_acc.id

        print("Old->New account id map size:", len(id_map))

        # 4) Migrate JournalLine
        jl_updated = 0
        for line in db.session.query(JournalLine).all():
            aid = line.account_id
            if aid in id_map:
                line.account_id = id_map[aid]
                jl_updated += 1
        print("JournalLine rows updated:", jl_updated)

        # 5) Migrate LedgerEntry
        le_updated = 0
        for entry in db.session.query(LedgerEntry).all():
            aid = entry.account_id
            if aid in id_map:
                entry.account_id = id_map[aid]
                le_updated += 1
        print("LedgerEntry rows updated:", le_updated)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Commit (migrate JL/LE) failed:", e)
            return

        print("Done. No accounts deleted.")

if __name__ == "__main__":
    main()
