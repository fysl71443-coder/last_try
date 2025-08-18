#!/usr/bin/env python3
"""
Direct database fix script - run this on the server
"""

import os
import sys
import logging

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_database():
    try:
        from app import app, db
        from sqlalchemy import text
        
        with app.app_context():
            print("🔧 Starting database fix...")
            
            # 1. Check and add table_no column to sales_invoices
            try:
                result = db.engine.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'sales_invoices' 
                    AND column_name = 'table_no'
                """))
                
                if not result.fetchone():
                    print("➕ Adding table_no column to sales_invoices...")
                    db.engine.execute(text("ALTER TABLE sales_invoices ADD COLUMN table_no INTEGER"))
                    print("✅ table_no column added successfully")
                else:
                    print("✅ table_no column already exists")
            except Exception as e:
                print(f"⚠️ Error with table_no column: {e}")
            
            # 2. Create tables table if missing
            try:
                print("➕ Creating/verifying tables table...")
                db.engine.execute(text("""
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
                print("✅ tables table created/verified")
            except Exception as e:
                print(f"⚠️ Error with tables table: {e}")
            
            # 3. Create draft_orders table if missing
            try:
                print("➕ Creating/verifying draft_orders table...")
                db.engine.execute(text("""
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
                print("✅ draft_orders table created/verified")
            except Exception as e:
                print(f"⚠️ Error with draft_orders table: {e}")
            
            # 4. Create draft_order_items table if missing
            try:
                print("➕ Creating/verifying draft_order_items table...")
                db.engine.execute(text("""
                    CREATE TABLE IF NOT EXISTS draft_order_items (
                        id SERIAL PRIMARY KEY,
                        draft_order_id INTEGER NOT NULL,
                        meal_id INTEGER,
                        product_name VARCHAR(200) NOT NULL,
                        quantity NUMERIC(10,2) NOT NULL,
                        price_before_tax NUMERIC(12,2) NOT NULL,
                        tax NUMERIC(12,2) NOT NULL DEFAULT 0,
                        discount NUMERIC(12,2) NOT NULL DEFAULT 0,
                        total_price NUMERIC(12,2) NOT NULL
                    )
                """))
                print("✅ draft_order_items table created/verified")
            except Exception as e:
                print(f"⚠️ Error with draft_order_items table: {e}")
            
            # 5. Add foreign key constraints if they don't exist
            try:
                print("➕ Adding foreign key constraints...")
                db.engine.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.table_constraints 
                            WHERE constraint_name = 'draft_order_items_draft_order_id_fkey'
                        ) THEN
                            ALTER TABLE draft_order_items 
                            ADD CONSTRAINT draft_order_items_draft_order_id_fkey 
                            FOREIGN KEY (draft_order_id) REFERENCES draft_orders(id) ON DELETE CASCADE;
                        END IF;
                    END $$;
                """))
                print("✅ Foreign key constraints added/verified")
            except Exception as e:
                print(f"⚠️ Error with foreign keys: {e}")
            
            # 6. Commit all changes
            try:
                db.session.commit()
                print("✅ All changes committed to database")
            except Exception as e:
                print(f"⚠️ Error committing changes: {e}")
                db.session.rollback()
            
            print("🎉 Database fix completed successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Database fix failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fix_database()
    if success:
        print("\n✅ Database is now ready! You can restart the application.")
    else:
        print("\n❌ Fix failed. Check the error messages above.")
    sys.exit(0 if success else 1)
