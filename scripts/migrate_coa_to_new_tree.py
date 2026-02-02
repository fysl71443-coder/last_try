#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
سكريبت لنقل الحسابات من الشجرة القديمة للشجرة الجديدة
- فحص الحسابات الموجودة
- نقل البيانات من الحسابات القديمة للجديدة
- حذف الحسابات القديمة
- التأكد من وجود جميع الحسابات الجديدة
"""

import os
import sys
from decimal import Decimal

# إصلاح مشكلة الترميز في Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# إضافة المسار الجذر للمشروع
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app import create_app, db
from models import Account, LedgerEntry, JournalLine
from data.coa_new_tree import build_coa_dict, leaf_coa_dict, OLD_TO_NEW_MAP, NEW_COA_TREE

def get_all_new_codes():
    """الحصول على جميع رموز الحسابات الجديدة من الشجرة."""
    coa = build_coa_dict()
    return set(coa.keys())

def get_old_codes_in_db():
    """الحصول على رموز الحسابات القديمة الموجودة في قاعدة البيانات."""
    all_codes = get_all_new_codes()
    all_accounts = Account.query.all()
    old_codes = []
    for acc in all_accounts:
        code = str(acc.code or '').strip()
        if code and code not in all_codes:
            old_codes.append(code)
    return old_codes

def migrate_ledger_entries(old_code, new_code):
    """نقل إدخالات دفتر الأستاذ من الحساب القديم للجديد."""
    old_acc = Account.query.filter_by(code=old_code).first()
    new_acc = Account.query.filter_by(code=new_code).first()
    
    if not old_acc or not new_acc:
        return 0
    
    # نقل LedgerEntry
    count = 0
    entries = LedgerEntry.query.filter_by(account_id=old_acc.id).all()
    for entry in entries:
        entry.account_id = new_acc.id
        count += 1
    
    return count

def migrate_journal_lines(old_code, new_code):
    """نقل سطور القيود من الحساب القديم للجديد."""
    old_acc = Account.query.filter_by(code=old_code).first()
    new_acc = Account.query.filter_by(code=new_code).first()
    
    if not old_acc or not new_acc:
        return 0
    
    # نقل JournalLine
    count = 0
    lines = JournalLine.query.filter_by(account_id=old_acc.id).all()
    for line in lines:
        line.account_id = new_acc.id
        count += 1
    
    return count

def ensure_new_accounts():
    """التأكد من وجود جميع الحسابات الجديدة في قاعدة البيانات."""
    coa = build_coa_dict()
    created = 0
    updated = 0
    
    for code, info in coa.items():
        acc = Account.query.filter_by(code=code).first()
        if not acc:
            # إنشاء حساب جديد
            acc = Account(
                code=code,
                name=info.get('name', ''),
                type=info.get('type', 'EXPENSE')
            )
            # إضافة name_ar و name_en إذا كانت موجودة في النموذج
            if hasattr(Account, 'name_ar'):
                acc.name_ar = info.get('name_ar', info.get('name', ''))
            if hasattr(Account, 'name_en'):
                acc.name_en = info.get('name_en', '')
            if hasattr(Account, 'active'):
                acc.active = True
            db.session.add(acc)
            created += 1
        else:
            # تحديث بيانات الحساب الموجود
            updated_fields = False
            if acc.name != info.get('name', ''):
                acc.name = info.get('name', '')
                updated_fields = True
            if hasattr(acc, 'name_ar'):
                new_name_ar = info.get('name_ar', info.get('name', ''))
                if getattr(acc, 'name_ar', None) != new_name_ar:
                    acc.name_ar = new_name_ar
                    updated_fields = True
            if hasattr(acc, 'name_en'):
                new_name_en = info.get('name_en', '')
                if getattr(acc, 'name_en', None) != new_name_en:
                    acc.name_en = new_name_en
                    updated_fields = True
            if acc.type != info.get('type', 'EXPENSE'):
                acc.type = info.get('type', 'EXPENSE')
                updated_fields = True
            if hasattr(acc, 'active') and not getattr(acc, 'active', True):
                acc.active = True
                updated_fields = True
            if updated_fields:
                updated += 1
    
    db.session.commit()
    return created, updated

def delete_old_accounts():
    """حذف الحسابات القديمة بعد التأكد من نقل جميع البيانات."""
    old_codes = get_old_codes_in_db()
    deleted = 0
    
    for old_code in old_codes:
        acc = Account.query.filter_by(code=old_code).first()
        if acc:
            # التحقق من عدم وجود إدخالات مرتبطة
            ledger_count = LedgerEntry.query.filter_by(account_id=acc.id).count()
            journal_count = JournalLine.query.filter_by(account_id=acc.id).count()
            
            if ledger_count == 0 and journal_count == 0:
                db.session.delete(acc)
                deleted += 1
            else:
                print(f"⚠️  تحذير: الحساب {old_code} ({acc.name}) لا يزال لديه {ledger_count} إدخال دفتر و {journal_count} سطر قيد")
    
    db.session.commit()
    return deleted

def main():
    """الدالة الرئيسية للهجرة."""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("بدء هجرة شجرة الحسابات إلى الشجرة الجديدة")
        print("=" * 60)
        
        # 1. فحص الحسابات الموجودة
        print("\n1. فحص الحسابات الموجودة...")
        all_accounts = Account.query.all()
        print(f"   عدد الحسابات الموجودة: {len(all_accounts)}")
        
        new_codes = get_all_new_codes()
        print(f"   عدد الحسابات المطلوبة (الشجرة الجديدة): {len(new_codes)}")
        
        old_codes = get_old_codes_in_db()
        print(f"   عدد الحسابات القديمة: {len(old_codes)}")
        if old_codes:
            print(f"   الحسابات القديمة: {', '.join(sorted(old_codes)[:20])}{'...' if len(old_codes) > 20 else ''}")
        
        # 2. التأكد من وجود جميع الحسابات الجديدة
        print("\n2. التأكد من وجود جميع الحسابات الجديدة...")
        created, updated = ensure_new_accounts()
        print(f"   ✅ تم إنشاء {created} حساب جديد")
        print(f"   ✅ تم تحديث {updated} حساب موجود")
        
        # 3. نقل البيانات من الحسابات القديمة للجديدة
        print("\n3. نقل البيانات من الحسابات القديمة للجديدة...")
        total_ledger_moved = 0
        total_journal_moved = 0
        
        for old_code in old_codes:
            if old_code in OLD_TO_NEW_MAP:
                new_code = OLD_TO_NEW_MAP[old_code]
                ledger_count = migrate_ledger_entries(old_code, new_code)
                journal_count = migrate_journal_lines(old_code, new_code)
                
                if ledger_count > 0 or journal_count > 0:
                    print(f"   ✅ {old_code} → {new_code}: {ledger_count} إدخال دفتر، {journal_count} سطر قيد")
                    total_ledger_moved += ledger_count
                    total_journal_moved += journal_count
            else:
                print(f"   ⚠️  الحساب {old_code} غير موجود في خريطة التحويل")
        
        if total_ledger_moved > 0 or total_journal_moved > 0:
            db.session.commit()
            print(f"   ✅ تم نقل {total_ledger_moved} إدخال دفتر و {total_journal_moved} سطر قيد")
        else:
            print("   ℹ️  لا توجد بيانات للنقل")
        
        # 4. حذف الحسابات القديمة
        print("\n4. حذف الحسابات القديمة...")
        deleted = delete_old_accounts()
        print(f"   ✅ تم حذف {deleted} حساب قديم")
        
        # 5. التحقق النهائي
        print("\n5. التحقق النهائي...")
        final_accounts = Account.query.all()
        final_codes = {str(acc.code) for acc in final_accounts}
        missing_codes = new_codes - final_codes
        
        if missing_codes:
            print(f"   ⚠️  الحسابات المفقودة: {', '.join(sorted(missing_codes))}")
        else:
            print(f"   ✅ جميع الحسابات الجديدة موجودة ({len(final_codes)} حساب)")
        
        # 6. التحقق من الربط
        print("\n6. التحقق من الربط...")
        orphaned_ledger = db.session.query(LedgerEntry).filter(
            ~LedgerEntry.account_id.in_(db.session.query(Account.id))
        ).count()
        orphaned_journal = db.session.query(JournalLine).filter(
            ~JournalLine.account_id.in_(db.session.query(Account.id))
        ).count()
        
        if orphaned_ledger > 0:
            print(f"   ⚠️  يوجد {orphaned_ledger} إدخال دفتر بدون حساب مرتبط")
        else:
            print(f"   ✅ جميع إدخالات دفتر الأستاذ مرتبطة")
        
        if orphaned_journal > 0:
            print(f"   ⚠️  يوجد {orphaned_journal} سطر قيد بدون حساب مرتبط")
        else:
            print(f"   ✅ جميع سطور القيود مرتبطة")
        
        print("\n" + "=" * 60)
        print("✅ اكتملت الهجرة بنجاح!")
        print("=" * 60)

if __name__ == '__main__':
    main()
