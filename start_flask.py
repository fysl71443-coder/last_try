#!/usr/bin/env python3
"""
Flask Server Starter - Simple and Direct
"""
import os
import sys

def main():
    print("🔧 Starting Flask server...")
    
    try:
        # Import Flask app
        from app import app
        
        print("✅ Flask app imported successfully")
        print("🚀 Starting server on http://127.0.0.1:5000")
        print("🔑 Login: admin / admin")
        print("⏹️  Press Ctrl+C to stop")
        
        # Start server
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=False,
            threaded=True
        )
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    main()
