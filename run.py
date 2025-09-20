#!/usr/bin/env python3
"""
Simple Flask Server Runner
"""
import os
import sys

def main():
    try:
        print("🔧 Starting Restaurant Management System...")
        
        # Set environment
        os.environ['FLASK_ENV'] = 'development'
        
        # Import app
        from app import app
        
        print("✅ App imported successfully")
        print("🚀 Server starting on http://127.0.0.1:5000")
        print("🔑 Login: admin / admin")
        print("⏹️  Press Ctrl+C to stop")
        print("-" * 50)
        
        # Run server
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=False,
            use_reloader=False
        )
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    main()
