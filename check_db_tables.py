#!/usr/bin/env python3

import sqlite3
import os

def check_db_tables():
    """Check database tables and their structure"""
    
    db_path = 'accounting_app.db'
    if not os.path.exists(db_path):
        print("Database not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔍 Checking database tables...")
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    print(f"All tables: {[table[0] for table in tables]}")
    
    # Check table_sections structure
    if any('table_sections' == table[0] for table in tables):
        print("\n📋 table_sections structure:")
        cursor.execute("PRAGMA table_info(table_sections)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
    
    # Check table_section_assignments structure
    if any('table_section_assignments' == table[0] for table in tables):
        print("\n📋 table_section_assignments structure:")
        cursor.execute("PRAGMA table_info(table_section_assignments)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
    
    # Check if there's any data
    cursor.execute("SELECT COUNT(*) FROM table_sections")
    sections_count = cursor.fetchone()[0]
    print(f"\nSections count: {sections_count}")
    
    cursor.execute("SELECT COUNT(*) FROM table_section_assignments")
    assignments_count = cursor.fetchone()[0]
    print(f"Assignments count: {assignments_count}")
    
    if sections_count > 0:
        cursor.execute("SELECT * FROM table_sections")
        sections = cursor.fetchall()
        print("\nSections data:")
        for section in sections:
            print(f"  {section}")
    
    conn.close()

if __name__ == "__main__":
    check_db_tables()

















