#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نسخة احتياطية يدوية لملف SQLite.
يقرأ المسار من config (instance/accounting_app.db أو LOCAL_SQLITE_PATH)
وينسخ الملف إلى backup/db_backup_YYYYMMDD_HHMMSS.sqlite.

تشغيل: python scripts/backup_sqlite_db.py
"""
import os
import sys
import shutil
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def main():
    try:
        from config import LOCAL_SQLITE_PATH_FOR_SCRIPTS
        db_path = LOCAL_SQLITE_PATH_FOR_SCRIPTS
    except Exception:
        db_path = os.path.join(ROOT, 'instance', 'accounting_app.db')

    if not os.path.isfile(db_path):
        print(f"❌ ملف قاعدة البيانات غير موجود: {db_path}")
        return 1

    backup_dir = os.path.join(ROOT, 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'db_backup_{stamp}.sqlite')
    shutil.copy2(db_path, backup_path)
    print(f"✅ تم النسخ الاحتياطي: {backup_path}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
