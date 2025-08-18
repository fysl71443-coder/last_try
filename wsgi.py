#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""
import os

# Set environment variable to avoid eventlet issues in production
os.environ.setdefault('USE_EVENTLET', '0')

from app import create_app

# Create the application instance
application = create_app()

if __name__ == "__main__":
    application.run()
