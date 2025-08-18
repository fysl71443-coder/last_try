#!/usr/bin/env python3
"""
Quick migration to add table_no column to sales_invoices table
Run this on the server to fix the missing column error
"""

import os
import sys
from sqlalchemy import create_engine, text

def add_table_no_column():
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not found")
        return False
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Check if column already exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sales_invoices' 
                AND column_name = 'table_no'
            """))
            
            if result.fetchone():
                print("Column 'table_no' already exists in sales_invoices table")
                return True
            
            # Add the column
            print("Adding table_no column to sales_invoices table...")
            conn.execute(text("ALTER TABLE sales_invoices ADD COLUMN table_no INTEGER"))
            conn.commit()
            print("✅ Successfully added table_no column")
            
            # Also create tables table if it doesn't exist
            print("Creating tables table if it doesn't exist...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tables (
                    id SERIAL PRIMARY KEY,
                    branch_code VARCHAR(20) NOT NULL,
                    table_number INTEGER NOT NULL,
                    status VARCHAR(20) DEFAULT 'available',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(branch_code, table_number)
                )
            """))
            conn.commit()
            print("✅ Tables table created/verified")

            # Create draft_orders table
            print("Creating draft_orders table if it doesn't exist...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS draft_orders (
                    id SERIAL PRIMARY KEY,
                    branch_code VARCHAR(20) NOT NULL,
                    table_no INTEGER NOT NULL,
                    customer_name VARCHAR(100),
                    customer_phone VARCHAR(30),
                    payment_method VARCHAR(20) DEFAULT 'CASH',
                    status VARCHAR(20) DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER NOT NULL
                )
            """))
            conn.commit()
            print("✅ Draft orders table created/verified")

            # Create draft_order_items table
            print("Creating draft_order_items table if it doesn't exist...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS draft_order_items (
                    id SERIAL PRIMARY KEY,
                    draft_order_id INTEGER NOT NULL,
                    meal_id INTEGER,
                    product_name VARCHAR(200) NOT NULL,
                    quantity NUMERIC(10,2) NOT NULL,
                    price_before_tax NUMERIC(12,2) NOT NULL,
                    tax NUMERIC(12,2) NOT NULL DEFAULT 0,
                    discount NUMERIC(12,2) NOT NULL DEFAULT 0,
                    total_price NUMERIC(12,2) NOT NULL,
                    FOREIGN KEY (draft_order_id) REFERENCES draft_orders(id) ON DELETE CASCADE
                )
            """))
            conn.commit()
            print("✅ Draft order items table created/verified")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    success = add_table_no_column()
    sys.exit(0 if success else 1)
