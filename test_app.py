#!/usr/bin/env python3
"""
Test App - Check for Flask issues
"""
import sys
import traceback

def test_import():
    """Test importing the app"""
    try:
        print("🔍 Testing app import...")
        import app
        print("✅ App imported successfully!")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        print("📋 Full traceback:")
        traceback.print_exc()
        return False

def test_flask_creation():
    """Test Flask app creation"""
    try:
        print("🔍 Testing Flask app creation...")
        from flask import Flask
        test_app = Flask(__name__)
        print("✅ Flask app created successfully!")
        return True
    except Exception as e:
        print(f"❌ Flask creation failed: {e}")
        return False

def test_database():
    """Test database connection"""
    try:
        print("🔍 Testing database...")
        import sqlite3
        conn = sqlite3.connect('restaurant.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"✅ Database connected! Found {len(tables)} tables")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Restaurant System Diagnostics")
    print("=" * 50)
    
    # Test Python version
    print(f"🐍 Python version: {sys.version}")
    
    # Test Flask
    if not test_flask_creation():
        return 1
    
    # Test database
    if not test_database():
        return 1
    
    # Test app import
    if not test_import():
        return 1
    
    print("\n🎉 All tests passed! The app should work now.")
    print("💡 Try running: python app.py")
    return 0

if __name__ == '__main__':
    exit(main())
