#!/usr/bin/env python3
"""
Local Server Runner - Restaurant Management System
Ensures the server runs on localhost (127.0.0.1) for local access
"""
import os
import sys
import subprocess
import time

def kill_existing_processes():
    """Kill any existing Python processes on port 5000"""
    try:
        print("🔄 Checking for existing processes on port 5000...")
        # Check what's using port 5000
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
        if ':5000' in result.stdout:
            print("⚠️  Port 5000 is in use, attempting to free it...")
            subprocess.run(['taskkill', '/f', '/im', 'python.exe'], shell=True, capture_output=True)
            time.sleep(2)
            print("✅ Port cleared")
        else:
            print("✅ Port 5000 is available")
    except Exception as e:
        print(f"⚠️  Could not check/clear port: {e}")

def start_server():
    """Start the restaurant management system"""
    print("🍽️ Restaurant Management System")
    print("=" * 50)
    
    # Kill existing processes
    kill_existing_processes()
    
    # Set environment variables for local development
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '0'
    os.environ['PORT'] = '5000'
    
    print("🚀 Starting server...")
    print("🌐 Server will be available at: http://127.0.0.1:5000")
    print("🔑 Login credentials: admin / admin")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        # Import and run the Flask app
        from flask import Flask
        
        # Create a simple test to ensure Flask works
        test_app = Flask(__name__)
        
        @test_app.route('/test')
        def test():
            return "Flask is working!"
        
        print("✅ Flask is working, starting main application...")
        
        # Now import the main app
        import app
        
        # Force the app to run on localhost
        app.app.run(
            host='127.0.0.1',
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped by user")
        return 0
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all required packages are installed:")
        print("   pip install flask flask-sqlalchemy flask-migrate")
        return 1
    except Exception as e:
        print(f"❌ Server error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check if app.py exists in the current directory")
        print("2. Verify database file (restaurant.db) exists")
        print("3. Try running: python -c 'import flask; print(\"Flask OK\")'")
        return 1

def main():
    """Main function"""
    # Check current directory
    print(f"📍 Working directory: {os.getcwd()}")
    
    # Check if app.py exists
    if not os.path.exists('app.py'):
        print("❌ app.py not found in current directory")
        print("💡 Make sure you're in the correct project folder")
        return 1
    
    print("✅ app.py found")
    
    # Check if database exists
    if not os.path.exists('restaurant.db'):
        print("⚠️  restaurant.db not found - will be created automatically")
    else:
        print("✅ restaurant.db found")
    
    # Start the server
    return start_server()

if __name__ == '__main__':
    exit(main())
