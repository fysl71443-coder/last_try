#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""سكريبت للتحقق من تطابق شجرة الحسابات في قاعدة البيانات مع الشجرة الجديدة"""

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
from models import Account
from data.coa_new_tree import build_coa_dict

def main():
    app = create_app()
    with app.app_context():
        coa = build_coa_dict()
        db_accounts = Account.query.all()
        db_codes = {str(a.code) for a in db_accounts}
        new_codes = set(coa.keys())
        
        missing = new_codes - db_codes
        old = db_codes - new_codes
        
        print("=" * 60)
        print("التحقق من شجرة الحسابات")
        print("=" * 60)
        print(f"\nالحسابات الجديدة المطلوبة: {len(new_codes)}")
        print(f"الحسابات الموجودة في DB: {len(db_codes)}")
        print(f"الحسابات المفقودة: {len(missing)}")
        print(f"الحسابات القديمة: {len(old)}")
        
        if missing:
            print(f"\n⚠️  الحسابات المفقودة: {', '.join(sorted(missing))}")
        else:
            print("\n✅ جميع الحسابات الجديدة موجودة")
        
        if old:
            print(f"\n⚠️  الحسابات القديمة: {', '.join(sorted(old))}")
        else:
            print("\n✅ لا توجد حسابات قديمة")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
