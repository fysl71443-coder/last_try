#!/usr/bin/env python3
"""
Create admin user for login
"""
import os
import sys

# Disable eventlet for this script
os.environ['USE_EVENTLET'] = '0'

from app import app
from extensions import db, bcrypt
from models import User
import os
try:
    from config import Config
    app.config.from_object(Config)
except Exception:
    pass
# Fallback to existing SQLite DB if URI not set
if not app.config.get('SQLALCHEMY_DATABASE_URI'):
    db_file = os.path.join(os.path.dirname(__file__), 'instance', 'accounting_app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_file.replace('\\', '/')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Ensure the SQLAlchemy instance is bound to this app
try:
    db.init_app(app)
except Exception:
    pass

def create_admin_user():
    """Create or update admin user"""
    with app.app_context():
        try:
            # Ensure tables exist (safe if already created)
            try:
                db.create_all()
            except Exception as ce:
                print(f"(warn) create_all failed or skipped: {ce}")

            # Check if admin user exists
            admin = User.query.filter_by(username='admin').first()

            if admin:
                print("✅ Admin user already exists")
                # Update password to ensure it works
                admin.set_password('admin', bcrypt)
                db.session.commit()
                print("✅ Admin password updated to 'admin'")
            else:
                # Create new admin user
                admin = User(
                    username='admin',
                    email='admin@restaurant.com',
                    role='admin',
                    active=True
                )
                admin.set_password('admin', bcrypt)
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin user created with password 'admin'")

            # Test password verification
            test_result = admin.check_password('admin', bcrypt)
            print(f"Password verification test: {test_result}")

            print(f"Admin user ID: {admin.id}")
            print("Login credentials:")
            print("Username: admin")
            print("Password: admin")

            # Also create a simple user for testing
            simple_user = User.query.filter_by(username='user').first()
            if not simple_user:
                simple_user = User(
                    username='user',
                    email='user@restaurant.com',
                    role='user',
                    active=True
                )
                simple_user.set_password('user', bcrypt)
                db.session.add(simple_user)
                db.session.commit()
                print("✅ Simple user created: username=user, password=user")

        except Exception as e:
            print(f"❌ Error: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_admin_user()
