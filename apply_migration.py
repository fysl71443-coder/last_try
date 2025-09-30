#!/usr/bin/env python3
"""
Database Migration Script for Restaurant System
This script applies necessary database schema changes for both SQLite and PostgreSQL
"""

import os
import sys
from sqlalchemy import text, inspect
from app import create_app
from extensions import db

def get_database_type():
    """Detect database type"""
    return db.engine.dialect.name

def apply_migration():
    """Apply database migration for both SQLite and PostgreSQL compatibility"""

    app = create_app()
    with app.app_context():
        try:
            db_type = get_database_type()
            print(f"🔄 Starting database migration for {db_type.upper()}...")

            # Use SQLAlchemy's create_all() which works for both SQLite and PostgreSQL
            print("📝 Creating/updating all tables using SQLAlchemy models...")
            db.create_all()
            print("✅ All tables created/updated successfully")

            # Apply database-specific optimizations
            if db_type == 'postgresql':
                print("🔧 Applying PostgreSQL-specific optimizations...")
                try:
                    # Create indexes for better performance
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_draft_orders_branch_status ON draft_orders(branch_code, status)"))
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_tables_branch ON tables(branch_code)"))
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_draft_order_items_order_id ON draft_order_items(draft_order_id)"))
                    db.session.commit()
                    print("✅ PostgreSQL indexes created")
                except Exception as e:
                    print(f"⚠️ Index creation failed (may already exist): {e}")
                    db.session.rollback()

            elif db_type == 'sqlite':
                print("🔧 Applying SQLite-specific optimizations...")
                try:
                    # Create indexes for better performance (SQLite syntax)
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_draft_orders_branch_status ON draft_orders(branch_code, status)"))
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_tables_branch ON tables(branch_code)"))
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_draft_order_items_order_id ON draft_order_items(draft_order_id)"))
                    db.session.commit()
                    print("✅ SQLite indexes created")
                except Exception as e:
                    print(f"⚠️ Index creation failed (may already exist): {e}")
                    db.session.rollback()

            print("🎯 Migration completed successfully!")
            return True

        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            return False

def verify_columns():
    """Verify that critical columns exist using SQLAlchemy inspector"""

    app = create_app()
    with app.app_context():
        try:
            print("\n🔍 Verifying critical columns...")

            inspector = inspect(db.engine)

            # Check draft_orders table
            if 'draft_orders' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('draft_orders')]
                required_columns = ['table_number', 'status', 'branch_code']

                missing_columns = [col for col in required_columns if col not in columns]

                if missing_columns:
                    print(f"❌ Missing columns in draft_orders: {missing_columns}")
                    return False
                else:
                    print("✅ All required columns exist in draft_orders")
                    print(f"📋 draft_orders columns: {columns}")
            else:
                print("❌ draft_orders table does not exist")
                return False

            # Check tables table
            if 'tables' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('tables')]
                print(f"📋 tables columns: {columns}")

            return True

        except Exception as e:
            print(f"❌ Column verification failed: {e}")
            return False

def test_sales_functionality():
    """Test that sales functionality works after migration"""

    app = create_app()
    with app.app_context():
        try:
            print("\n🧪 Testing sales functionality...")
            
            # Test DraftOrder query
            from models import DraftOrder
            draft_orders = DraftOrder.query.filter_by(status='draft').limit(5).all()
            print(f"✅ DraftOrder query successful, found {len(draft_orders)} draft orders")
            
            # Test Table query
            from models import Table
            tables = Table.query.limit(5).all()
            print(f"✅ Table query successful, found {len(tables)} tables")
            
            print("🎉 Sales functionality test passed!")
            return True
            
        except Exception as e:
            print(f"❌ Sales functionality test failed: {e}")
            return False

if __name__ == "__main__":
    print("🚀 Restaurant System Database Migration")
    print("=" * 50)

    # Apply migration
    if apply_migration():
        print("\n" + "=" * 50)

        # Verify columns
        if verify_columns():
            print("\n" + "=" * 50)

            # Test functionality
            if test_sales_functionality():
                print("\n🎉 Migration and testing completed successfully!")
                print("✅ System is ready for production deployment")
                sys.exit(0)
            else:
                print("\n❌ Migration succeeded but functionality test failed")
                sys.exit(1)
        else:
            print("\n❌ Column verification failed")
            sys.exit(1)
    else:
        print("\n❌ Migration failed")
        sys.exit(1)
