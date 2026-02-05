#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أمر التشغيل الموحد — وضع المطور مع قاعدة بيانات SQLite ثابتة.
البيانات تُحفظ في instance/accounting_app.db ولا تُفقد.

الاستخدام: python run_dev.py
"""
import os
import sys
import subprocess

# ─── إعداد قاعدة البيانات قبل أي استيراد للتطبيق ───
_base = os.path.dirname(os.path.abspath(__file__))
os.chdir(_base)
_instance = os.path.join(_base, 'instance')
os.makedirs(_instance, exist_ok=True)
_db_file = os.path.abspath(os.path.join(_instance, 'accounting_app.db'))

os.environ['LOCAL_SQLITE_PATH'] = _db_file
os.environ['DATABASE_URL'] = 'sqlite:///' + _db_file.replace('\\', '/')
os.environ.setdefault('ENV', 'development')
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('FLASK_DEBUG', '1')
os.environ.setdefault('PYTHONUNBUFFERED', '1')


def _kill_port_5000():
    """إيقاف أي عملية تستخدم المنفذ 5000 (Windows)."""
    try:
        out = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            shell=True,
            timeout=5,
        )
        if out.returncode != 0:
            return
        for line in (out.stdout or '').splitlines():
            if ':5000' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5 and parts[-1].isdigit():
                    pid = parts[-1]
                    subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True, shell=True, timeout=3)
                    break
    except Exception:
        pass


def main():
    # تجنب UnicodeEncodeError على ويندوز عند طباعة العربية
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    _kill_port_5000()
    print("=" * 60)
    print("  تشغيل النظام — وضع المطور (قاعدة بيانات SQLite ثابتة)")
    print("=" * 60)
    print("  قاعدة البيانات:", _db_file)
    print("  التأكد: الملف موجود" if os.path.isfile(_db_file) else "  (سيتم إنشاء الملف عند أول تشغيل)")
    print("  الخادم:  http://127.0.0.1:5000")
    print("  إيقاف:   Ctrl+C")
    print("=" * 60)

    from app import create_app
    app = create_app()

    with app.app_context():
        try:
            from extensions import db
            from models import User
            if User.query.count() == 0:
                admin = User(username='admin', email='admin@example.com', role='admin', active=True)
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("  تم إنشاء مستخدم افتراضي: admin / admin123")
        except Exception as e:
            print("  ملاحظة:", e)

    # use_reloader=False يمنع انهيار الخادم على Windows (عملية مزدوجة)
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)


if __name__ == '__main__':
    main()
