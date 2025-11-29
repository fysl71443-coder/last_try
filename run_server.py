#!/usr/bin/env python3
"""
Simple script to run the Flask server and open browser
"""

import os
import sys
import time
import webbrowser
import threading

def open_browser():
    """Open browser after server starts"""
    time.sleep(2)  # Wait for server to start
    print("Opening browser...")
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    try:
        os.environ.setdefault('TZ', 'Asia/Riyadh')
        try:
            import time as _time
            if hasattr(_time, 'tzset'):
                _time.tzset()
        except Exception:
            pass
        from app import create_app
        app = create_app()

        print("Starting China Town & Palace India POS System")
        print("Server URL: http://127.0.0.1:5000")
        print("Default login: admin / admin")
        print("Press Ctrl+C to stop the server")
        print("="*60 + "\n")

        # Start browser in background
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

        # Start Flask server
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=True,
            use_reloader=True
        )

    except ImportError as e:
        print(f"Error importing Flask app: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
