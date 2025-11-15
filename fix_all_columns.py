#!/usr/bin/env python3
"""
Add all missing columns to settings table
"""

import sqlite3
import os

def fix_all_columns():
    db_path = 'accounting_app.db'
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return False
    
    print("🔧 Adding all missing columns...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # All missing columns based on the error
        missing_columns = [
            ("printer_type", "VARCHAR(20) DEFAULT 'thermal'"),
            ("currency_image", "VARCHAR(300)"),
            ("footer_message", "VARCHAR(300) DEFAULT 'THANK YOU FOR VISIT'"),
            ("china_town_void_password", "VARCHAR(50) DEFAULT '1991'"),
            ("china_town_vat_rate", "NUMERIC(5,2) DEFAULT 15.00"),
            ("china_town_discount_rate", "NUMERIC(5,2) DEFAULT 0.00"),
            ("place_india_void_password", "VARCHAR(50) DEFAULT '1991'"),
            ("place_india_vat_rate", "NUMERIC(5,2) DEFAULT 15.00"),
            ("place_india_discount_rate", "NUMERIC(5,2) DEFAULT 0.00"),
            ("receipt_paper_width", "VARCHAR(4) DEFAULT '80'"),
            ("receipt_margin_top_mm", "INTEGER DEFAULT 5"),
            ("receipt_margin_bottom_mm", "INTEGER DEFAULT 5"),
            ("receipt_margin_left_mm", "INTEGER DEFAULT 3"),
            ("receipt_margin_right_mm", "INTEGER DEFAULT 3"),
            ("receipt_font_size", "INTEGER DEFAULT 12"),
            ("receipt_logo_height", "INTEGER DEFAULT 72"),
            ("receipt_show_logo", "BOOLEAN DEFAULT 1"),
            ("receipt_show_tax_number", "BOOLEAN DEFAULT 1"),
            ("receipt_footer_text", "VARCHAR(300) DEFAULT 'THANK YOU FOR VISIT'"),
            ("receipt_extra_bottom_mm", "INTEGER DEFAULT 15"),
            ("logo_url", "VARCHAR(300) DEFAULT '/static/chinese-logo.svg'"),
            ("china_town_logo_url", "VARCHAR(300)"),
            ("place_india_logo_url", "VARCHAR(300)"),
        ]
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(settings)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing columns: {len(existing_columns)}")
        
        added_count = 0
        for col_name, col_def in missing_columns:
            if col_name not in existing_columns:
                print(f"Adding: {col_name}")
                cursor.execute(f"ALTER TABLE settings ADD COLUMN {col_name} {col_def}")
                added_count += 1
            else:
                print(f"Exists: {col_name}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Added {added_count} columns successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    fix_all_columns()
