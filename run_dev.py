#!/usr/bin/env python3
"""
Development server with SocketIO support
Requires: pip install -r requirements-dev.txt
"""
import os
import sys

# Set development environment
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('USE_EVENTLET', '1')

try:
    # Import eventlet and monkey patch first
    import eventlet
    eventlet.monkey_patch()
    print("✅ Eventlet monkey patching applied for development")
except ImportError:
    print("❌ Eventlet not found. Install with: pip install -r requirements-dev.txt")
    sys.exit(1)

from flask_socketio import SocketIO
from app import create_app

def run_dev_server():
    """Run the development server with SocketIO"""
    # Create the app with development config
    app = create_app('development')

    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Run with SocketIO
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.getenv('PORT', 8000)),
        debug=True
    )

if __name__ == '__main__':
    run_dev_server()
