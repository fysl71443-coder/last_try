#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
إجبار شجرة الحسابات الجديدة فقط في SQLite المحلي.
- يستخدم نفس مسار DB كما في التطبيق (config).
- يضمن وجود كل حسابات الشجرة الجديدة.
- ينقل JournalLine و LedgerEntry من الحسابات القديمة → الجديدة حسب OLD_TO_NEW_MAP.
- يحذف كل الحسابات القديمة.
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

# إجبار SQLite المحلي – نفس منطق config
os.environ.pop('DATABASE_URL', None)
instance_dir = os.path.join(base_dir, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, 'accounting_app.db')
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
os.environ['LOCAL_SQLITE_PATH'] = db_path

from app import create_app, db
from models import Account, LedgerEntry, JournalLine
from data.coa_new_tree import build_coa_dict, OLD_TO_NEW_MAP, NEW_COA_TREE


def new_codes_set():
    return set(build_coa_dict().keys())


def ensure_new_accounts():
    coa = build_coa_dict()
    created = 0
    updated = 0
    for code, info in coa.items():
        acc = Account.query.filter_by(code=code).first()
        if not acc:
            acc = Account(code=code, name=info.get('name', ''), type=info.get('type', 'EXPENSE'))
            if hasattr(Account, 'name_ar'):
                acc.name_ar = info.get('name_ar', info.get('name', ''))
            if hasattr(Account, 'name_en'):
                acc.name_en = info.get('name_en', '')
            if hasattr(Account, 'active'):
                acc.active = True
            db.session.add(acc)
            created += 1
        else:
            changed = False
            if acc.name != info.get('name', ''):
                acc.name = info.get('name', '')
                changed = True
            if hasattr(acc, 'name_ar') and getattr(acc, 'name_ar', None) != info.get('name_ar', info.get('name', '')):
                acc.name_ar = info.get('name_ar', info.get('name', ''))
                changed = True
            if hasattr(acc, 'name_en') and getattr(acc, 'name_en', None) != info.get('name_en', ''):
                acc.name_en = info.get('name_en', '')
                changed = True
            if acc.type != info.get('type', 'EXPENSE'):
                acc.type = info.get('type', 'EXPENSE')
                changed = True
            if hasattr(acc, 'active') and not getattr(acc, 'active', True):
                acc.active = True
                changed = True
            if changed:
                updated += 1
    db.session.commit()
    return created, updated


def migrate_to_new(old_code: str, new_code: str):
    old_acc = Account.query.filter_by(code=old_code).first()
    new_acc = Account.query.filter_by(code=new_code).first()
    if not old_acc or not new_acc:
        return 0, 0
    n_ledger = LedgerEntry.query.filter_by(account_id=old_acc.id).update({'account_id': new_acc.id})
    n_journal = JournalLine.query.filter_by(account_id=old_acc.id).update({'account_id': new_acc.id})
    return n_ledger or 0, n_journal or 0


def delete_old_accounts(new_codes: set):
    old = [a for a in Account.query.all() if str(a.code or '').strip() not in new_codes]
    deleted = 0
    for a in old:
        code = str(a.code or '').strip()
        le = LedgerEntry.query.filter_by(account_id=a.id).count()
        jl = JournalLine.query.filter_by(account_id=a.id).count()
        if le or jl:
            print(f"  تخطي {code}: {le} ledger, {jl} journal – انقل البيانات أولاً via OLD_TO_NEW_MAP")
            continue
        db.session.delete(a)
        deleted += 1
    db.session.commit()
    return deleted


def main():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("إجبار الشجرة الجديدة فقط في SQLite")
        print("=" * 60)
        print(f"DB: {db_path}")

        new_codes = new_codes_set()
        all_acc = Account.query.all()
        old_codes = [str(a.code or '').strip() for a in all_acc if str(a.code or '').strip() not in new_codes]
        print(f"\nحسابات في DB: {len(all_acc)} | شجرة جديدة: {len(new_codes)} | قديمة: {len(old_codes)}")

        print("\n1. ضمان وجود الحسابات الجديدة...")
        created, updated = ensure_new_accounts()
        print(f"   إنشاء: {created} | تحديث: {updated}")

        print("\n2. نقل البيانات قديم → جديد (OLD_TO_NEW_MAP)...")
        total_ledger, total_journal = 0, 0
        for old_code in old_codes:
            if old_code not in OLD_TO_NEW_MAP:
                continue
            new_code = OLD_TO_NEW_MAP[old_code]
            nle, njl = migrate_to_new(old_code, new_code)
            if nle or njl:
                print(f"   {old_code} → {new_code}: {nle} ledger, {njl} journal")
                total_ledger += nle
                total_journal += njl
        if total_ledger or total_journal:
            db.session.commit()
        print(f"   إجمالي منقول: {total_ledger} ledger, {total_journal} journal")

        print("\n3. حذف الحسابات القديمة (بدون حركات)...")
        deleted = delete_old_accounts(new_codes)
        print(f"   محذوف: {deleted}")

        # إعادة جرد القديمة بعد الحذف (قد يتبقى من لديهم حركات ولم يُنقلوا)
        remaining_old = [a for a in Account.query.all() if str(a.code or '').strip() not in new_codes]
        print(f"\n4. التحقق: حسابات قديمة متبقية: {len(remaining_old)}")
        if remaining_old:
            for a in remaining_old[:30]:
                le = LedgerEntry.query.filter_by(account_id=a.id).count()
                jl = JournalLine.query.filter_by(account_id=a.id).count()
                print(f"   {a.code} ({a.name}): {le} ledger, {jl} journal")
            if len(remaining_old) > 30:
                print(f"   ... و {len(remaining_old) - 30} أخرى")

        final = Account.query.all()
        final_set = {str(a.code) for a in final}
        missing = new_codes - final_set
        if missing:
            print(f"\n   حسابات مطلوبة ناقصة: {sorted(missing)}")
        else:
            print(f"\n   جميع الحسابات الجديدة موجودة ({len(final)} حساب).")

        print("\n" + "=" * 60)
        print("تم.")
        print("=" * 60)


if __name__ == '__main__':
    main()
