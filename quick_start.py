#!/usr/bin/env python3
"""
Quick Start - Restaurant System
"""
import os
import sys

def main():
    print("🔧 Restaurant Management System")
    print("📍 Current directory:", os.getcwd())
    print("🐍 Python version:", sys.version)
    
    # Check if app.py exists
    if os.path.exists('app.py'):
        print("✅ app.py found")
        
        # Try to import and run
        try:
            print("🚀 Starting server...")
            exec(open('app.py').read())
        except Exception as e:
            print(f"❌ Error: {e}")
            print("🔧 Creating simple server instead...")
            
            # Create simple server
            from flask import Flask
            app = Flask(__name__)
            
            @app.route('/')
            def home():
                return '''
                <h1>🍽️ Restaurant System</h1>
                <p>✅ Server is running on http://127.0.0.1:5000</p>
                <p>🔧 Main app.py has issues, running simple version</p>
                '''
            
            app.run(host='127.0.0.1', port=5000, debug=False)
    else:
        print("❌ app.py not found")

if __name__ == '__main__':
    main()
