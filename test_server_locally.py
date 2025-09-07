#!/usr/bin/env python3
"""
Test the Flask server locally by making HTTP requests
"""

import sys
import os
import time
import threading
import requests
from app import app

def start_server():
    """Start Flask server in a separate thread"""
    try:
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Server error: {e}")

def test_server():
    """Test server endpoints"""
    base_url = 'http://127.0.0.1:5000'
    
    # Wait for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(3)
    
    # Test endpoints
    endpoints = [
        ('/', 'Home page'),
        ('/sales', 'Sales branch selection'),
        ('/sales/china_town', 'China Town POS'),
        ('/sales/palace_india', 'Palace India POS'),
        ('/settings', 'Settings page'),
    ]
    
    print("🔍 Testing endpoints...")
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5, allow_redirects=False)
            status = response.status_code
            
            if status in [200, 302]:  # 200 = OK, 302 = Redirect (login required)
                print(f"✅ {description}: {status}")
            else:
                print(f"❌ {description}: {status}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {description}: Connection failed")
        except Exception as e:
            print(f"❌ {description}: {e}")
    
    print("\n🎯 Server test completed!")
    print("📍 You can now access the system at:")
    print(f"   🏠 Main page: {base_url}")
    print(f"   🏮 China Town POS: {base_url}/sales/china_town")
    print(f"   🏛️ Palace India POS: {base_url}/sales/palace_india")
    print(f"   ⚙️ Settings: {base_url}/settings")

if __name__ == '__main__':
    print("🚀 Starting local server test...")
    
    # Start server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Test the server
    test_server()
    
    print("\n" + "="*60)
    print("🎉 Server is running! Press Ctrl+C to stop.")
    print("="*60)
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
        sys.exit(0)
