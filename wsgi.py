#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""
import os
import sys

# CRITICAL: Set environment variables BEFORE any imports
os.environ.setdefault('USE_EVENTLET', '0')
os.environ.setdefault('FLASK_ENV', 'production')

# Prevent eventlet from being imported
if 'eventlet' in sys.modules:
    print("WARNING: eventlet was already imported!")

# Block eventlet imports
class EventletBlocker:
    def find_spec(self, name, path, target=None):
        if name.startswith('eventlet'):
            raise ImportError(f"eventlet import blocked: {name}")
        return None

# Install the blocker (only in production)
if os.getenv('USE_EVENTLET', '1') == '0':
    sys.meta_path.insert(0, EventletBlocker())

from app import create_app

# Create the application instance
application = create_app()

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
