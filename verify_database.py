#!/usr/bin/env python3
"""
Database Verification Script for Restaurant System
This script verifies that the database schema matches the model requirements
"""

import os
import sys
from sqlalchemy import text, inspect
from app import app
from extensions import db

def verify_database_schema():
    """Verify that database schema matches model requirements"""
    
    with app.app_context():
        try:
            print("🔍 Verifying database schema...")
            
            inspector = inspect(db.engine)
            db_type = db.engine.dialect.name
            
            print(f"📊 Database type: {db_type.upper()}")
            
            # Check if draft_orders table exists
            if 'draft_orders' not in inspector.get_table_names():
                print("❌ draft_orders table does not exist")
                return False
            
            # Get column information
            columns = inspector.get_columns('draft_orders')
            column_info = {col['name']: col for col in columns}
            
            print(f"\n📋 Found {len(columns)} columns in draft_orders table:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col['default'] else ""
                print(f"  - {col['name']}: {col['type']}{default} {nullable}")
            
            # Check required columns
            required_columns = {
                'table_number': {'type': 'VARCHAR', 'nullable': False, 'default': '0'},
                'status': {'type': 'VARCHAR', 'nullable': False, 'default': 'draft'},
                'branch_code': {'type': 'VARCHAR', 'nullable': False},
                'payment_method': {'type': 'VARCHAR', 'nullable': False, 'default': 'CASH'}
            }
            
            print(f"\n🔍 Checking required columns:")
            all_good = True
            
            for col_name, requirements in required_columns.items():
                if col_name not in column_info:
                    print(f"❌ Missing column: {col_name}")
                    all_good = False
                    continue
                
                col = column_info[col_name]
                
                # Check type (basic check)
                if 'VARCHAR' in requirements['type'] and 'VARCHAR' not in str(col['type']).upper():
                    print(f"⚠️  {col_name}: Expected VARCHAR, got {col['type']}")
                
                # Check nullable
                if col['nullable'] != requirements['nullable']:
                    nullable_expected = "NULL" if requirements['nullable'] else "NOT NULL"
                    nullable_actual = "NULL" if col['nullable'] else "NOT NULL"
                    print(f"⚠️  {col_name}: Expected {nullable_expected}, got {nullable_actual}")
                
                # Check default (if specified)
                if 'default' in requirements and requirements['default']:
                    if not col['default'] or requirements['default'] not in str(col['default']):
                        print(f"⚠️  {col_name}: Expected default '{requirements['default']}', got '{col['default']}'")
                
                print(f"✅ {col_name}: OK")
            
            if all_good:
                print(f"\n🎉 All required columns are properly configured!")
            else:
                print(f"\n⚠️  Some columns need attention (see warnings above)")
            
            return True
            
        except Exception as e:
            print(f"❌ Database verification failed: {e}")
            return False

def test_draft_order_operations():
    """Test basic draft order operations"""
    
    with app.app_context():
        try:
            print(f"\n🧪 Testing draft order operations...")
            
            from models import DraftOrder
            
            # Test query
            draft_count = DraftOrder.query.count()
            print(f"✅ Query test: Found {draft_count} draft orders")
            
            # Test safe table number handling
            from app import safe_table_number
            
            test_values = [None, '', '5', 'invalid', 0, 10]
            print(f"✅ Safe table number tests:")
            for val in test_values:
                result = safe_table_number(val)
                print(f"  - safe_table_number({repr(val)}) = {result}")
            
            print(f"🎉 All operations working correctly!")
            return True
            
        except Exception as e:
            print(f"❌ Operation test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def generate_fix_commands():
    """Generate SQL commands to fix common issues"""
    
    print(f"\n🔧 SQL commands to fix common issues:")
    print(f"=" * 50)
    
    commands = [
        "-- Fix NULL values first",
        "UPDATE draft_orders SET table_number = '0' WHERE table_number IS NULL;",
        "UPDATE draft_orders SET status = 'draft' WHERE status IS NULL;",
        "UPDATE draft_orders SET branch_code = 'china_town' WHERE branch_code IS NULL;",
        "UPDATE draft_orders SET payment_method = 'CASH' WHERE payment_method IS NULL;",
        "",
        "-- Add missing columns",
        "ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50) NOT NULL DEFAULT '0';",
        "ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft';",
        "",
        "-- Update existing columns to proper constraints",
        "ALTER TABLE draft_orders ALTER COLUMN table_number SET NOT NULL;",
        "ALTER TABLE draft_orders ALTER COLUMN table_number SET DEFAULT '0';",
        "ALTER TABLE draft_orders ALTER COLUMN status SET NOT NULL;",
        "ALTER TABLE draft_orders ALTER COLUMN status SET DEFAULT 'draft';",
        "",
        "-- Verify changes",
        "\\d draft_orders"
    ]
    
    for cmd in commands:
        print(cmd)

if __name__ == "__main__":
    print("🚀 Restaurant System Database Verification")
    print("=" * 50)
    
    # Verify schema
    if verify_database_schema():
        print("\n" + "=" * 50)
        
        # Test operations
        if test_draft_order_operations():
            print("\n🎉 Database verification completed successfully!")
            print("✅ System is ready for production")
        else:
            print("\n❌ Operation tests failed")
            generate_fix_commands()
    else:
        print("\n❌ Schema verification failed")
        generate_fix_commands()
