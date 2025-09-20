#!/usr/bin/env python3
"""
Create admin user immediately
"""
import os
os.environ['USE_EVENTLET'] = '0'

from app import app, db
from extensions import bcrypt
from models import User

def create_admin():
    with app.app_context():
        try:
            # Delete any existing admin
            existing = User.query.filter_by(username='admin').all()
            for user in existing:
                db.session.delete(user)
            
            # Create new admin
            admin = User(
                username='admin',
                email='admin@restaurant.com',
                role='admin',
                active=True
            )
            
            # Set password directly
            password_hash = bcrypt.generate_password_hash('admin').decode('utf-8')
            admin.password_hash = password_hash
            
            db.session.add(admin)
            db.session.commit()
            
            # Test password
            test = bcrypt.check_password_hash(admin.password_hash, 'admin')
            print(f"✅ Admin created! Password test: {test}")
            print("Username: admin")
            print("Password: admin")
            
        except Exception as e:
            print(f"Error: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_admin()
