#!/usr/bin/env python3
"""
Simple server starter
"""
import os
import sys

# Set Flask app
os.environ['FLASK_APP'] = 'app.py'
os.environ['FLASK_ENV'] = 'development'

try:
    print("🚀 Starting server...")
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
