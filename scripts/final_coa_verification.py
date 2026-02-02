#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""التحقق النهائي من ربط شجرة الحسابات الجديدة بالنظام"""

import os
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app import create_app, db
from models import Account, LedgerEntry, JournalLine
from data.coa_new_tree import build_coa_dict, leaf_coa_dict

def main():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("التحقق النهائي من ربط شجرة الحسابات الجديدة")
        print("=" * 60)
        
        # 1. التحقق من الحسابات في قاعدة البيانات
        print("\n1. التحقق من الحسابات في قاعدة البيانات...")
        coa = build_coa_dict()
        all_accounts = Account.query.all()
        db_codes = {str(a.code) for a in all_accounts}
        new_codes = set(coa.keys())
        
        missing = new_codes - db_codes
        old = db_codes - new_codes
        
        if missing:
            print(f"   ❌ الحسابات المفقودة ({len(missing)}): {', '.join(sorted(missing)[:10])}")
        else:
            print(f"   ✅ جميع الحسابات الجديدة موجودة ({len(new_codes)} حساب)")
        
        if old:
            print(f"   ❌ الحسابات القديمة ({len(old)}): {', '.join(sorted(old)[:10])}")
        else:
            print(f"   ✅ لا توجد حسابات قديمة")
        
        # 2. التحقق من الربط في LedgerEntry
        print("\n2. التحقق من الربط في دفتر الأستاذ...")
        all_ledger = LedgerEntry.query.all()
        orphaned_ledger = []
        for entry in all_ledger:
            acc = Account.query.get(entry.account_id)
            if not acc or str(acc.code) not in new_codes:
                orphaned_ledger.append(entry.id)
        
        if orphaned_ledger:
            print(f"   ❌ يوجد {len(orphaned_ledger)} إدخال غير مرتبط")
        else:
            print(f"   ✅ جميع إدخالات دفتر الأستاذ مرتبطة بالحسابات الجديدة ({len(all_ledger)} إدخال)")
        
        # 3. التحقق من الربط في JournalLine
        print("\n3. التحقق من الربط في القيود...")
        all_journal = JournalLine.query.all()
        orphaned_journal = []
        for line in all_journal:
            acc = Account.query.get(line.account_id)
            if not acc or str(acc.code) not in new_codes:
                orphaned_journal.append(line.id)
        
        if orphaned_journal:
            print(f"   ❌ يوجد {len(orphaned_journal)} سطر غير مرتبط")
        else:
            print(f"   ✅ جميع سطور القيود مرتبطة بالحسابات الجديدة ({len(all_journal)} سطر)")
        
        # 4. التحقق من CHART_OF_ACCOUNTS
        print("\n4. التحقق من CHART_OF_ACCOUNTS في النظام...")
        try:
            from app.routes import CHART_OF_ACCOUNTS
            chart_codes = set(CHART_OF_ACCOUNTS.keys())
            if chart_codes == new_codes:
                print(f"   ✅ CHART_OF_ACCOUNTS يطابق الشجرة الجديدة ({len(chart_codes)} حساب)")
            else:
                diff = new_codes - chart_codes
                extra = chart_codes - new_codes
                if diff:
                    print(f"   ⚠️  حسابات مفقودة في CHART_OF_ACCOUNTS: {', '.join(sorted(diff)[:10])}")
                if extra:
                    print(f"   ⚠️  حسابات إضافية في CHART_OF_ACCOUNTS: {', '.join(sorted(extra)[:10])}")
        except Exception as e:
            print(f"   ❌ خطأ في فحص CHART_OF_ACCOUNTS: {e}")
        
        # 5. ملخص نهائي
        print("\n" + "=" * 60)
        if not missing and not old and not orphaned_ledger and not orphaned_journal:
            print("✅ النظام مرتبط بشكل كامل بشجرة الحسابات الجديدة!")
        else:
            print("⚠️  يوجد بعض المشاكل - راجع التفاصيل أعلاه")
        print("=" * 60)

if __name__ == '__main__':
    main()
