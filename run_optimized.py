#!/usr/bin/env python3
"""
Optimized Flask server runner with better performance settings
"""
import os
import sys
from app import create_app

# Set environment variables for better performance
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = '0'
os.environ['WERKZEUG_RUN_MAIN'] = 'true'

# Create app
app = create_app()

if __name__ == '__main__':
    # Optimized settings for better performance
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True,
        processes=1
    )
