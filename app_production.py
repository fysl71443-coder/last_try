#!/usr/bin/env python3
"""
Production entry point that completely avoids eventlet
"""
import os
import sys

# CRITICAL: Set environment variables BEFORE any imports
os.environ.setdefault('USE_EVENTLET', '0')
os.environ.setdefault('FLASK_ENV', 'production')

# Block eventlet completely in production
def block_eventlet():
    """Block eventlet imports to prevent conflicts"""
    import sys
    
    class EventletBlocker:
        def find_spec(self, name, path, target=None):
            if name.startswith('eventlet'):
                print(f"🚫 Blocked eventlet import: {name}")
                raise ImportError(f"eventlet import blocked in production: {name}")
            return None
    
    # Install the blocker
    sys.meta_path.insert(0, EventletBlocker())
    
    # Also remove from sys.modules if already imported
    eventlet_modules = [mod for mod in sys.modules.keys() if mod.startswith('eventlet')]
    for mod in eventlet_modules:
        print(f"🗑️ Removing eventlet module: {mod}")
        del sys.modules[mod]

# Apply eventlet blocking
block_eventlet()

# Now import the main app (this will also register all routes)
from app import app as main_app

# Use the main app instance (which has all routes registered)
app = main_app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
