#!/usr/bin/env python3
"""
Test Server Script
==================
Quick test to verify the server starts correctly.
"""

import os
import sys
import threading
import time
import requests

# Set environment to avoid eventlet issues
os.environ.setdefault('USE_EVENTLET', '0')

def test_server():
    """Test that the server responds correctly"""
    try:
        # Wait a moment for server to start
        time.sleep(2)
        
        # Test basic routes
        base_url = "http://127.0.0.1:5000"
        
        print("🔧 Testing server routes...")
        
        # Test root redirect
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"  - Root (/): {response.status_code}")
        
        # Test login page
        response = requests.get(f"{base_url}/login", timeout=5)
        print(f"  - Login (/login): {response.status_code}")
        
        # Test dashboard (should redirect to login)
        response = requests.get(f"{base_url}/dashboard", timeout=5, allow_redirects=False)
        print(f"  - Dashboard (/dashboard): {response.status_code}")
        
        print("✅ Server is responding correctly!")
        
    except Exception as e:
        print(f"❌ Server test failed: {e}")

def run_test_server():
    """Run a simple test server"""
    try:
        from app import app
        
        print("🚀 Starting test server on http://127.0.0.1:5000")
        print("Press Ctrl+C to stop")
        
        # Start test client in a separate thread
        test_thread = threading.Thread(target=test_server)
        test_thread.daemon = True
        test_thread.start()
        
        # Run the Flask development server
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")

if __name__ == '__main__':
    run_test_server()
