#!/usr/bin/env python3
"""
Quick fix for login - create working admin user
"""
import os
import sys

# Disable eventlet
os.environ['USE_EVENTLET'] = '0'

def main():
    print("🔧 Quick Login Fix")
    print("=" * 30)
    
    try:
        # Import with error handling
        print("Importing modules...")
        from app import app, db
        from extensions import bcrypt
        from models import User
        print("✅ Modules imported")
        
        with app.app_context():
            print("Creating/updating admin user...")
            
            # Remove any existing admin users
            existing_admins = User.query.filter_by(username='admin').all()
            for admin in existing_admins:
                db.session.delete(admin)
            
            # Create fresh admin user
            admin = User()
            admin.username = 'admin'
            admin.email = 'admin@restaurant.com'
            admin.role = 'admin'
            admin.active = True
            
            # Set password using bcrypt directly
            password_hash = bcrypt.generate_password_hash('admin').decode('utf-8')
            admin.password_hash = password_hash
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Admin user created successfully")
            
            # Test the password
            test_result = bcrypt.check_password_hash(admin.password_hash, 'admin')
            print(f"Password test result: {test_result}")
            
            if test_result:
                print("🎉 SUCCESS! Login credentials:")
                print("Username: admin")
                print("Password: admin")
            else:
                print("❌ Password test failed")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
