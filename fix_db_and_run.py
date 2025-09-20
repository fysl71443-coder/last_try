#!/usr/bin/env python3
"""
Fix database schema and run server
This script handles all database migration issues and starts the server
"""
import os
import sys
import sqlite3
from pathlib import Path

def remove_db_files():
    """Remove existing database files"""
    db_files = [
        'app.db',
        'accounting_app.db', 
        'instance/accounting_app.db',
        'instance/accounting_app.db.bak'
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
                print(f"✅ Removed {db_file}")
            except Exception as e:
                print(f"⚠️ Could not remove {db_file}: {e}")

def create_fresh_db():
    """Create fresh database with all tables"""
    print("🔄 Creating fresh database...")
    
    # Disable eventlet for database operations
    os.environ['USE_EVENTLET'] = '0'
    
    try:
        # Import app after setting environment
        from app import create_app, db
        
        app = create_app()
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database tables created")
            
            # Create sample data
            try:
                from app import create_sample_data
                create_sample_data()
                print("✅ Sample data created")
            except Exception as e:
                print(f"⚠️ Sample data creation failed: {e}")
                # Continue anyway
                
    except Exception as e:
        print(f"❌ Database creation failed: {e}")
        return False
        
    return True

def run_server():
    """Run the Flask server"""
    print("🚀 Starting server...")
    
    # Enable eventlet for server
    os.environ['USE_EVENTLET'] = '1'
    os.environ['PORT'] = '5000'
    
    try:
        # Import and run app
        from app import create_app
        
        app = create_app()
        
        # Try with eventlet first
        try:
            import eventlet
            eventlet.monkey_patch()
            from flask_socketio import SocketIO
            
            socketio = SocketIO(app, cors_allowed_origins="*")
            print("✅ Server starting with SocketIO on http://127.0.0.1:5000")
            socketio.run(app, host='0.0.0.0', port=5000, debug=True)
            
        except Exception as e:
            print(f"⚠️ SocketIO failed: {e}")
            print("🔄 Falling back to standard Flask server...")
            app.run(host='0.0.0.0', port=5000, debug=True)
            
    except Exception as e:
        print(f"❌ Server start failed: {e}")
        return False
        
    return True

def main():
    """Main execution"""
    print("🔧 Database Fix & Server Start Script")
    print("=" * 40)
    
    # Step 1: Remove old databases
    print("Step 1: Cleaning old databases...")
    remove_db_files()
    
    # Step 2: Create fresh database
    print("\nStep 2: Creating fresh database...")
    if not create_fresh_db():
        print("❌ Database creation failed. Exiting.")
        sys.exit(1)
    
    # Step 3: Run server
    print("\nStep 3: Starting server...")
    run_server()

if __name__ == '__main__':
    main()
