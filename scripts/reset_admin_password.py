#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
إعادة تعيين كلمة مرور admin إلى admin123 (للاستخدام المحلي فقط).
يُعطّل أيضاً 2FA للمستخدم admin لتسجيل الدخول بدون رمز التحقق.
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

# نفس DB التطبيق
instance_dir = os.path.join(base_dir, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, 'accounting_app.db')
os.environ.pop('DATABASE_URL', None)
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
os.environ.setdefault('LOCAL_SQLITE_PATH', db_path)
os.environ.setdefault('SECRET_KEY', 'dev')

from app import create_app, db
from models import User

PASSWORD = 'admin123'


def main():
    app = create_app()
    with app.app_context():
        admin = User.query.filter(User.username.ilike('admin')).first()
        if not admin:
            admin = User(username='admin', email='admin@example.com', role='admin', active=True)
            admin.set_password(PASSWORD)
            db.session.add(admin)
            db.session.commit()
            print('تم إنشاء مستخدم admin وكلمة المرور: admin123')
        else:
            admin.set_password(PASSWORD)
            if hasattr(admin, 'twofa_enabled'):
                admin.twofa_enabled = False
            if hasattr(admin, 'twofa_secret'):
                admin.twofa_secret = None
            db.session.commit()
            print('تم تعيين كلمة مرور admin إلى: admin123 (وتم تعطيل 2FA)')
        print('سجّل الدخول بـ: admin / admin123')


if __name__ == '__main__':
    main()
