#!/usr/bin/env python3
"""
Development server with SocketIO support
"""
import os

# Set development environment
os.environ.setdefault('FLASK_ENV', 'development')

# Import eventlet and monkey patch first
import eventlet
eventlet.monkey_patch()

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
