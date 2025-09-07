#!/usr/bin/env python3
"""
Debug login functionality
"""
import os
import sys

# Set environment
os.environ.setdefault('USE_EVENTLET', '0')

def debug_login():
    """Debug login functionality step by step"""
    print("🔍 Debugging login functionality...")
    
    try:
        print("1. Importing app...")
        from app import app
        print("✅ App imported")
        
        print("2. Importing models...")
        from models import User, db
        print("✅ Models imported")
        
        print("3. Importing bcrypt...")
        from extensions import bcrypt
        print("✅ Bcrypt imported")
        
        print("4. Testing app context...")
        with app.app_context():
            print("✅ App context working")
            
            print("5. Creating tables...")
            db.create_all()
            print("✅ Tables created")
            
            print("6. Checking admin user...")
            admin = User.query.filter_by(username='admin').first()
            if admin:
                print(f"✅ Admin user found: {admin.username}")
            else:
                print("❌ Admin user not found, creating...")
                admin = User(
                    username='admin',
                    email='admin@restaurant.com',
                    role='admin',
                    active=True
                )
                admin.set_password('admin123', bcrypt)
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin user created")
            
            print("7. Testing password verification...")
            if bcrypt.check_password_hash(admin.password_hash, 'admin123'):
                print("✅ Password verification works")
            else:
                print("❌ Password verification failed")
        
        print("8. Testing login route...")
        with app.test_client() as client:
            response = client.get('/login')
            print(f"GET /login: {response.status_code}")
            
            response = client.post('/login', data={
                'username': 'admin',
                'password': 'admin123'
            })
            print(f"POST /login: {response.status_code}")
        
        print("✅ All debug steps completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Debug error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    debug_login()
