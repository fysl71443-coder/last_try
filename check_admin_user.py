#!/usr/bin/env python3
"""
Check if admin user exists and create if needed
"""
import os
import sys

# Set environment for production-like testing
os.environ.setdefault('USE_EVENTLET', '0')
os.environ.setdefault('FLASK_ENV', 'production')

def check_admin_user():
    """Check if admin user exists and database is properly set up"""
    print("🔍 Checking admin user and database setup...")
    
    try:
        # Import with app context
        from app import app
        from models import User, db
        from extensions import bcrypt
        
        with app.app_context():
            print("✅ App context established")
            
            # Check if tables exist
            try:
                db.create_all()
                print("✅ Database tables created/verified")
            except Exception as e:
                print(f"❌ Error creating tables: {e}")
                return False
            
            # Check if admin user exists
            try:
                admin = User.query.filter_by(username='admin').first()
                if admin:
                    print("✅ Admin user exists")
                    print(f"   Username: {admin.username}")
                    print(f"   Active: {admin.active}")
                    print(f"   Role: {admin.role}")
                    
                    # Test password hash
                    try:
                        test_password = bcrypt.check_password_hash(admin.password_hash, 'admin123')
                        print(f"   Password test (admin123): {'✅ Valid' if test_password else '❌ Invalid'}")
                    except Exception as pwd_error:
                        print(f"   Password test error: {pwd_error}")
                    
                    return True
                else:
                    print("❌ Admin user does not exist")
                    
                    # Create admin user
                    try:
                        print("🔧 Creating admin user...")
                        admin_user = User(
                            username='admin',
                            email='admin@restaurant.com',
                            role='admin',
                            active=True
                        )
                        admin_user.set_password('admin123', bcrypt)
                        db.session.add(admin_user)
                        db.session.commit()
                        print("✅ Admin user created successfully!")
                        print("   Username: admin")
                        print("   Password: admin123")
                        return True
                    except Exception as create_error:
                        print(f"❌ Error creating admin user: {create_error}")
                        db.session.rollback()
                        return False
                        
            except Exception as query_error:
                print(f"❌ Error querying admin user: {query_error}")
                return False
                
    except Exception as e:
        print(f"❌ General error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_login_functionality():
    """Test login functionality"""
    print("\n🧪 Testing login functionality...")
    
    try:
        from app import app
        
        with app.test_client() as client:
            # Test GET login page
            response = client.get('/login')
            print(f"GET /login: {response.status_code}")
            
            # Test POST login with correct credentials
            response = client.post('/login', data={
                'username': 'admin',
                'password': 'admin123'
            }, follow_redirects=False)
            print(f"POST /login (correct): {response.status_code}")
            
            # Test POST login with wrong credentials
            response = client.post('/login', data={
                'username': 'admin',
                'password': 'wrong'
            }, follow_redirects=False)
            print(f"POST /login (wrong): {response.status_code}")
            
            return True
    except Exception as e:
        print(f"❌ Login test error: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Admin User Check & Database Verification")
    print("=" * 50)
    
    # Check admin user
    admin_ok = check_admin_user()
    
    # Test login
    login_ok = test_login_functionality()
    
    print("\n📋 Summary:")
    print(f"Admin user: {'✅ OK' if admin_ok else '❌ FAILED'}")
    print(f"Login test: {'✅ OK' if login_ok else '❌ FAILED'}")
    
    if admin_ok and login_ok:
        print("\n🎉 All checks passed! Ready for deployment.")
    else:
        print("\n⚠️ Some checks failed. Review the errors above.")

if __name__ == '__main__':
    main()
