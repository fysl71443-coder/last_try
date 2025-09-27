#!/usr/bin/env python3
"""
China Town - Place India Management System
Simple launcher script
"""

from app import create_app

if __name__ == '__main__':
    app = create_app()
    print("🚀 Starting China Town Management System...")
    print("📊 Admin Dashboard: http://localhost:5000/dashboard")
    print("🔐 Login: http://localhost:5000/login")
    print("👤 Default Admin: admin / admin123")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

