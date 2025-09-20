#!/usr/bin/env python3
"""
Simple Flask server runner
"""
import os
import sys

def main():
    try:
        print("🔧 Setting up environment...")
        
        # Set environment variables
        os.environ['FLASK_APP'] = 'app.py'
        os.environ['FLASK_ENV'] = 'development'
        
        print("📦 Importing Flask app...")
        
        # Import the app
        from app import app
        
        print("🚀 Starting Flask server on http://127.0.0.1:5000")
        print("📱 Access the application at: http://127.0.0.1:5000")
        print("🔑 Login with: admin / admin")
        print("⏹️  Press Ctrl+C to stop the server")
        
        # Run the server
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True
        )
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure all required packages are installed")
        return 1
        
    except Exception as e:
        print(f"❌ Server Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
