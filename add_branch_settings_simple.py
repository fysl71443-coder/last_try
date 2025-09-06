#!/usr/bin/env python3
"""Simple migration to add branch-specific settings columns"""

import sqlite3
import os

def add_branch_settings():
    """Add branch-specific settings columns to Settings table"""
    db_paths = ['accounting_app.db', 'instance/accounting_app.db']

    for db_path in db_paths:
        if not os.path.exists(db_path):
            continue

        print(f"Processing database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        process_database(cursor, conn)
        conn.close()

def process_database(cursor, conn):
    
    try:
        # Check if settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if not cursor.fetchone():
            # Create settings table
            cursor.execute("""
                CREATE TABLE settings (
                    id INTEGER PRIMARY KEY,
                    company_name VARCHAR(200),
                    tax_number VARCHAR(50),
                    address VARCHAR(300),
                    phone VARCHAR(50),
                    email VARCHAR(100),
                    vat_rate DECIMAL(5,2) DEFAULT 15.00,
                    place_india_label VARCHAR(100) DEFAULT 'Place India',
                    china_town_label VARCHAR(100) DEFAULT 'China Town',
                    currency VARCHAR(10) DEFAULT 'SAR',
                    default_theme VARCHAR(10) DEFAULT 'light',
                    china_town_void_password VARCHAR(50) DEFAULT '1991',
                    china_town_vat_rate DECIMAL(5,2) DEFAULT 15.00,
                    china_town_discount_rate DECIMAL(5,2) DEFAULT 0.00,
                    place_india_void_password VARCHAR(50) DEFAULT '1991',
                    place_india_vat_rate DECIMAL(5,2) DEFAULT 15.00,
                    place_india_discount_rate DECIMAL(5,2) DEFAULT 0.00,
                    receipt_paper_width VARCHAR(4) DEFAULT '80',
                    receipt_margin_top_mm INTEGER DEFAULT 5,
                    receipt_margin_bottom_mm INTEGER DEFAULT 5,
                    receipt_margin_left_mm INTEGER DEFAULT 3,
                    receipt_margin_right_mm INTEGER DEFAULT 3,
                    receipt_font_size INTEGER DEFAULT 12,
                    receipt_show_logo BOOLEAN DEFAULT 1,
                    receipt_show_tax_number BOOLEAN DEFAULT 1,
                    receipt_footer_text VARCHAR(300) DEFAULT '',
                    logo_url VARCHAR(300) DEFAULT '/static/chinese-logo.svg'
                )
            """)
            print("Created settings table with branch-specific columns")

            # Insert initial record
            cursor.execute("""
                INSERT INTO settings (company_name, china_town_void_password, place_india_void_password)
                VALUES ('Restaurant', '1991', '1991')
            """)
            print("Created initial settings record")

        else:
            # Check if columns already exist
            cursor.execute("PRAGMA table_info(settings)")
            columns = [row[1] for row in cursor.fetchall()]
        
            # Add China Town settings columns
            if 'china_town_void_password' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN china_town_void_password VARCHAR(50) DEFAULT "1991"')
                print("Added china_town_void_password column")

            if 'china_town_vat_rate' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN china_town_vat_rate DECIMAL(5,2) DEFAULT 15.00')
                print("Added china_town_vat_rate column")

            if 'china_town_discount_rate' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN china_town_discount_rate DECIMAL(5,2) DEFAULT 0.00')
                print("Added china_town_discount_rate column")

            # Add Palace India settings columns
            if 'place_india_void_password' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN place_india_void_password VARCHAR(50) DEFAULT "1991"')
                print("Added place_india_void_password column")

            if 'place_india_vat_rate' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN place_india_vat_rate DECIMAL(5,2) DEFAULT 15.00')
                print("Added place_india_vat_rate column")

            if 'place_india_discount_rate' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN place_india_discount_rate DECIMAL(5,2) DEFAULT 0.00')
                print("Added place_india_discount_rate column")

            # Add other missing columns
            if 'logo_url' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN logo_url VARCHAR(300) DEFAULT "/static/chinese-logo.svg"')
                print("Added logo_url column")

            if 'receipt_paper_width' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_paper_width VARCHAR(4) DEFAULT "80"')
                print("Added receipt_paper_width column")

            if 'receipt_margin_top_mm' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_margin_top_mm INTEGER DEFAULT 5')
                print("Added receipt_margin_top_mm column")

            if 'receipt_margin_bottom_mm' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_margin_bottom_mm INTEGER DEFAULT 5')
                print("Added receipt_margin_bottom_mm column")

            if 'receipt_margin_left_mm' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_margin_left_mm INTEGER DEFAULT 3')
                print("Added receipt_margin_left_mm column")

            if 'receipt_margin_right_mm' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_margin_right_mm INTEGER DEFAULT 3')
                print("Added receipt_margin_right_mm column")

            if 'receipt_font_size' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_font_size INTEGER DEFAULT 12')
                print("Added receipt_font_size column")

            if 'receipt_show_logo' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_show_logo BOOLEAN DEFAULT 1')
                print("Added receipt_show_logo column")

            if 'receipt_show_tax_number' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_show_tax_number BOOLEAN DEFAULT 1')
                print("Added receipt_show_tax_number column")

            if 'receipt_footer_text' not in columns:
                cursor.execute('ALTER TABLE settings ADD COLUMN receipt_footer_text VARCHAR(300) DEFAULT ""')
                print("Added receipt_footer_text column")

            # Initialize settings if they don't exist
            cursor.execute("SELECT COUNT(*) FROM settings")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO settings (company_name, china_town_void_password, place_india_void_password)
                    VALUES ('Restaurant', '1991', '1991')
                """)
                print("Created initial settings record")
        
        conn.commit()
        print("Branch settings migration completed successfully")

    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise

if __name__ == '__main__':
    add_branch_settings()
