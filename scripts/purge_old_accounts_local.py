#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
حذف الحسابات القديمة من قاعدة SQLite المحلية فقط.
يستخدم data.coa_new_tree كمرجع – يحذف أي حساب رمزه غير موجود في الشجرة الجديدة.
"""
import os
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
os.chdir(base_dir)

# إجبار SQLite المحلي فقط
instance_dir = os.path.join(base_dir, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, 'accounting_app.db')
os.environ.pop('DATABASE_URL', None)
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
os.environ['LOCAL_SQLITE_PATH'] = db_path

from app import create_app, db
from models import Account, LedgerEntry, JournalLine
from data.coa_new_tree import build_coa_dict

def main():
    app = create_app()
    with app.app_context():
        coa = build_coa_dict()
        new_codes = set(coa.keys())
        all_accounts = Account.query.all()
        old = [a for a in all_accounts if str(a.code or '').strip() not in new_codes]
        print(f'الحسابات في DB: {len(all_accounts)} | الشجرة الجديدة: {len(new_codes)} | قديمة للحذف: {len(old)}')
        if not old:
            print('لا توجد حسابات قديمة.')
            return
        for a in old:
            code = str(a.code or '').strip()
            le = LedgerEntry.query.filter_by(account_id=a.id).count()
            jl = JournalLine.query.filter_by(account_id=a.id).count()
            if le or jl:
                print(f'  تخطي {code}: {le} ledger, {jl} journal')
                continue
            db.session.delete(a)
            print(f'  حذف {code}')
        db.session.commit()
        print('تم.')

if __name__ == '__main__':
    main()
