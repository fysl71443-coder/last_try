#!/usr/bin/env python3
"""
Start the Flask development server for testing the new POS system
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app
    
    print("🚀 Starting China Town & Palace India POS System")
    print("📍 Server will be available at: http://127.0.0.1:5000")
    print("🔐 Default login credentials:")
    print("   Username: admin")
    print("   Password: admin")
    print("\n🏮 China Town POS: http://127.0.0.1:5000/sales/china_town")
    print("🏛️ Palace India POS: http://127.0.0.1:5000/sales/palace_india")
    print("⚙️ Settings: http://127.0.0.1:5000/settings")
    print("\n" + "="*60)
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Start the Flask development server
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader to avoid issues
    )
    
except ImportError as e:
    print(f"❌ Error importing Flask app: {e}")
    print("Make sure all dependencies are installed:")
    print("pip install flask flask-sqlalchemy flask-login flask-wtf")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Error starting server: {e}")
    sys.exit(1)
