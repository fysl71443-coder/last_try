#!/usr/bin/env python3
"""
Simple database fix using raw SQL
"""

import sqlite3
import os

def fix_database():
    db_path = 'accounting_app.db'
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return False
    
    print("🔧 Fixing database with raw SQL...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing columns: {columns}")
        
        # Add missing columns
        missing_columns = [
            ("china_town_logo_url", "VARCHAR(300)"),
            ("place_india_logo_url", "VARCHAR(300)"),
        ]
        
        for col_name, col_type in missing_columns:
            if col_name not in columns:
                print(f"Adding column: {col_name}")
                cursor.execute(f"ALTER TABLE settings ADD COLUMN {col_name} {col_type}")
            else:
                print(f"Column {col_name} already exists")
        
        conn.commit()
        conn.close()
        
        print("✅ Database fixed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    fix_database()
