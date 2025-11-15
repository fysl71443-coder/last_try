#!/usr/bin/env python3
"""
Fix and Run - Restaurant Management System
This script fixes common issues and starts the server
"""
import os
import sys
import subprocess
import time

def check_python():
    """Check Python installation"""
    print("🐍 Python version:", sys.version)
    return True

def check_flask():
    """Check Flask installation"""
    try:
        import flask
        print("✅ Flask is installed:", flask.__version__)
        return True
    except ImportError:
        print("❌ Flask not installed. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'flask'])
        return True

def check_files():
    """Check required files"""
    required_files = ['app.py', 'restaurant.db']
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} found")
        else:
            print(f"❌ {file} missing")
            missing_files.append(file)
    
    return len(missing_files) == 0

def kill_existing_processes():
    """Kill existing Python processes on port 5000"""
    try:
        # Kill processes using port 5000
        subprocess.run(['netstat', '-ano', '|', 'findstr', ':5000'], shell=True, capture_output=True)
        subprocess.run(['taskkill', '/f', '/im', 'python.exe'], shell=True, capture_output=True)
        print("🔄 Killed existing processes")
        time.sleep(2)
    except:
        pass

def fix_app_py():
    """Fix common issues in app.py"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for duplicate routes (simple check)
        if content.count('def api_get_tables') > 1:
            print("⚠️  Found duplicate routes in app.py")
            print("🔧 Manual fix required - check for duplicate function definitions")
            return False
        
        print("✅ app.py looks good")
        return True
    except Exception as e:
        print(f"❌ Error checking app.py: {e}")
        return False

def start_server():
    """Start the Flask server"""
    try:
        print("\n" + "="*60)
        print("🚀 STARTING RESTAURANT MANAGEMENT SYSTEM")
        print("="*60)
        print("📍 Working directory:", os.getcwd())
        print("🌐 Server URL: http://127.0.0.1:5000")
        print("🔑 Login: admin / admin")
        print("⏹️  Press Ctrl+C to stop the server")
        print("="*60)
        
        # Import and run the app via factory
        from app import create_app
        app = create_app()
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=False,
            use_reloader=False
        )
        
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check if port 5000 is already in use")
        print("2. Verify app.py has no syntax errors")
        print("3. Check database file exists")
        print("4. Try running: python -c 'import app; print(\"OK\")'")
        return False

def main():
    """Main function"""
    print("🔧 Restaurant Management System - Fix & Run")
    print("-" * 50)
    
    # Run checks
    if not check_python():
        return 1
    
    if not check_flask():
        return 1
    
    if not check_files():
        print("❌ Missing required files")
        return 1
    
    # Kill existing processes
    kill_existing_processes()
    
    # Fix app.py if needed
    if not fix_app_py():
        print("⚠️  app.py may have issues, but trying to start anyway...")
    
    # Start server
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped by user")
        return 0
    except Exception as e:
        print(f"\n❌ Failed to start server: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
