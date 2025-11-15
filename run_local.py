#!/usr/bin/env python3
"""
Local Server Runner - Restaurant Management System
Ensures the server runs on localhost (127.0.0.1) for local access
"""
import os
import subprocess
import time
import sys

PORT = 5000

def kill_existing_processes():
    """Kill any Python processes using the specified port (Windows only)"""
    try:
        print(f"🔄 Checking for existing processes on port {PORT}...")
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
        lines = result.stdout.splitlines()
        pids_to_kill = []
        for line in lines:
            if f":{PORT}" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit():
                    pids_to_kill.append(pid)
        if pids_to_kill:
            for pid in pids_to_kill:
                print(f"⚠️  Killing process with PID {pid}...")
                subprocess.run(['taskkill', '/PID', pid, '/F'], shell=True)
            time.sleep(2)
            print("✅ Port cleared")
        else:
            print(f"✅ Port {PORT} is available")
    except Exception as e:
        print(f"⚠️  Could not check/clear port: {e}")

def main():
    print(f"📍 Working directory: {os.getcwd()}")
    
    if not os.path.exists('app.py'):
        print("❌ app.py not found in current directory")
        print("💡 Make sure you're in the correct project folder")
        return 1
    
    print("✅ app.py found")

    if not os.path.exists('restaurant.db'):
        print("⚠️  restaurant.db not found - will be created automatically")
    else:
        print("✅ restaurant.db found")
    
    # Kill any process using the port
    kill_existing_processes()
    
    # Set environment variables
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '0'
    os.environ['PORT'] = str(PORT)
    
    print("🚀 Starting server...")
    print(f"🌐 Server will be available at: http://127.0.0.1:{PORT}")
    print("🔑 Login credentials: admin / admin123")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        import app  # استيراد app.py
        # شغّل كائن Flask الرئيسي مباشرة
        app.app.run(
            host='127.0.0.1',
            port=PORT,
            debug=True,
            use_reloader=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped by user")
        return 0
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all required packages are installed:")
        print("   pip install flask flask-login flask-sqlalchemy flask-migrate flask-wtf")
        return 1
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
