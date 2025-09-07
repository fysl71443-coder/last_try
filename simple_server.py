#!/usr/bin/env python3
"""
Simple server to test the API
"""

import sys
sys.path.append('.')

from app import app

if __name__ == '__main__':
    print("Starting simple server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
