#!/usr/bin/env python3
"""
ربط وتهيئة قاعدة SQLite المحلية ثم إنشاء المستخدم الافتراضي والبيانات الأولية.
تشغيل مرة واحدة قبل أول تشغيل للخادم إن لم تكن قد أنشأت الجداول من قبل.

  python scripts/ensure_local_db.py

أو من جذر المشروع:
  python -m scripts.ensure_local_db
"""
import os
import sys

# جذر المشروع = المجلد الذي فيه config.py
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('ENV', 'development')
os.environ.setdefault('USE_EVENTLET', '0')
instance_dir = os.path.join(ROOT, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.abspath(os.path.join(instance_dir, 'accounting_app.db'))
os.environ['LOCAL_SQLITE_PATH'] = db_path
os.environ['DATABASE_URL'] = 'sqlite:///' + db_path.replace('\\', '/')

def main():
    print('Database file:', db_path)
    try:
        from create_user import create_admin_user
        create_admin_user()
        print('Done. Start the server with: python run.py')
        return 0
    except Exception as e:
        print('Error:', e)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
