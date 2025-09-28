#!/usr/bin/env python3

import sqlite3
import os

def fix_table_names():
    """Fix table names to match the models"""
    
    db_path = 'accounting_app.db'
    if not os.path.exists(db_path):
        print("Database not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔧 Fixing table names to match models...")
    
    # Check current tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%table_section%'")
    tables = cursor.fetchall()
    print(f"Current table section tables: {[table[0] for table in tables]}")
    
    # Rename tables to match models
    try:
        # Rename table_section to table_sections
        if any('table_section' == table[0] for table in tables):
            print("Renaming table_section to table_sections...")
            cursor.execute("ALTER TABLE table_section RENAME TO table_sections")
        
        # Rename table_section_assignment to table_section_assignments  
        if any('table_section_assignment' == table[0] for table in tables):
            print("Renaming table_section_assignment to table_section_assignments...")
            cursor.execute("ALTER TABLE table_section_assignment RENAME TO table_section_assignments")
        
        conn.commit()
        print("✅ Table names fixed successfully!")
        
        # Verify
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%table_section%'")
        tables = cursor.fetchall()
        print(f"Updated table section tables: {[table[0] for table in tables]}")
        
    except Exception as e:
        print(f"❌ Error fixing table names: {e}")
        conn.rollback()
    
    conn.close()

if __name__ == "__main__":
    fix_table_names()

