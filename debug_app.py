#!/usr/bin/env python3
"""
Debug Application Script
========================
Script to test and debug the Flask application.
"""

import os
import sys
import traceback

# Set environment to avoid eventlet issues
os.environ.setdefault('USE_EVENTLET', '0')

def test_app_creation():
    """Test creating the Flask app"""
    try:
        print("🔧 Testing app creation...")
        from app import create_app
        app = create_app()
        print("✅ App created successfully")
        return app
    except Exception as e:
        print(f"❌ App creation failed: {e}")
        traceback.print_exc()
        return None

def test_extensions():
    """Test extensions import and initialization"""
    try:
        print("🔧 Testing extensions...")
        from extensions import db, bcrypt, migrate, login_manager, babel, csrf
        print("✅ Extensions imported successfully")
        
        # Test that they are initialized
        print(f"  - db: {type(db)}")
        print(f"  - bcrypt: {type(bcrypt)}")
        print(f"  - migrate: {type(migrate)}")
        print(f"  - login_manager: {type(login_manager)}")
        print(f"  - babel: {type(babel)}")
        print(f"  - csrf: {type(csrf)}")
        
        return True
    except Exception as e:
        print(f"❌ Extensions test failed: {e}")
        traceback.print_exc()
        return False

def test_models():
    """Test models import"""
    try:
        print("🔧 Testing models...")
        from models import User, SalesInvoice, Product, Meal
        print("✅ Models imported successfully")
        return True
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        traceback.print_exc()
        return False

def test_dashboard_route():
    """Test dashboard route specifically"""
    try:
        print("🔧 Testing dashboard route...")
        from app import create_app
        app = create_app()
        
        with app.test_client() as client:
            # Test without login (should redirect)
            response = client.get('/dashboard')
            print(f"  - Dashboard without login: {response.status_code}")
            
            # Test if route exists
            with app.app_context():
                from flask import url_for
                dashboard_url = url_for('dashboard')
                print(f"  - Dashboard URL: {dashboard_url}")
        
        print("✅ Dashboard route test completed")
        return True
    except Exception as e:
        print(f"❌ Dashboard route test failed: {e}")
        traceback.print_exc()
        return False

def test_template_rendering():
    """Test template rendering"""
    try:
        print("🔧 Testing template rendering...")
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from flask import render_template_string
            # Test simple template
            result = render_template_string("Hello {{ name }}", name="World")
            print(f"  - Simple template: {result}")
            
            # Test if dashboard template exists
            import os
            template_path = os.path.join('templates', 'dashboard.html')
            if os.path.exists(template_path):
                print(f"  - Dashboard template exists: {template_path}")
            else:
                print(f"  - Dashboard template missing: {template_path}")
        
        print("✅ Template rendering test completed")
        return True
    except Exception as e:
        print(f"❌ Template rendering test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🚀 Flask Application Debug Script")
    print("=" * 40)
    
    tests = [
        test_extensions,
        test_models,
        test_app_creation,
        test_dashboard_route,
        test_template_rendering
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
            print()
    
    print("📋 Summary:")
    passed_count = sum(1 for r in results if r is True)
    print(f"  - Tests passed: {passed_count}/{len(results)}")

    if all(r is True for r in results):
        print("✅ All tests passed! The app should work correctly.")
    else:
        print("❌ Some tests failed. Check the errors above.")

if __name__ == '__main__':
    main()
