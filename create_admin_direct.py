#!/usr/bin/env python3
"""
Create admin user directly in database
"""
import os
import sqlite3

def create_admin_direct():
    """Create admin user directly in SQLite database"""
    try:
        # Connect to database
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        
        # Delete existing admin users
        cursor.execute("DELETE FROM users WHERE username = 'admin'")
        
        # Create admin user with bcrypt hash for 'admin'
        # This is bcrypt hash of 'admin' with salt
        password_hash = '$2b$12$LQv3c1yqBwEHFl4E0s3wVeaVStP/.HqOFiukjCdDXA4L/KmxnSXxC'
        
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, active, language_pref)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('admin', 'admin@restaurant.com', password_hash, 'admin', 1, 'en'))
        
        conn.commit()
        conn.close()
        
        print("✅ Admin user created successfully!")
        print("Username: admin")
        print("Password: admin")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    create_admin_direct()
