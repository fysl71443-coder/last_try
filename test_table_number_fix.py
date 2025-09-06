#!/usr/bin/env python3
"""
Test script to verify table_number type compatibility fixes
"""

import os
import sys
from flask import Flask
from sqlalchemy import text

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_table_number_queries():
    """Test that table_number queries work with mixed data types"""
    
    try:
        from app import app, db
        from models import DraftOrder, Table
        
        with app.app_context():
            print("🧪 Testing table_number query compatibility...")
            
            # Test 1: DraftOrder queries with string table_number
            print("\n1. Testing DraftOrder queries...")
            try:
                # This should work now - comparing VARCHAR with string
                draft_count = DraftOrder.query.filter_by(
                    branch_code='china_town',
                    table_number='1',  # String value
                    status='draft'
                ).count()
                print(f"✅ DraftOrder query with string table_number: {draft_count} results")
            except Exception as e:
                print(f"❌ DraftOrder query failed: {e}")
                return False
            
            # Test 2: Table queries with integer table_number
            print("\n2. Testing Table queries...")
            try:
                # This should work - comparing INTEGER with integer
                table_count = Table.query.filter_by(
                    branch_code='china_town',
                    table_number=1  # Integer value
                ).count()
                print(f"✅ Table query with integer table_number: {table_count} results")
            except Exception as e:
                print(f"❌ Table query failed: {e}")
                return False
            
            # Test 3: Safe table number conversion
            print("\n3. Testing safe_table_number function...")
            try:
                from app import safe_table_number
                
                test_cases = [
                    ('1', 1),
                    ('5', 5),
                    ('invalid', 0),
                    (None, 0),
                    (10, 10),
                    ('', 0)
                ]
                
                for input_val, expected in test_cases:
                    result = safe_table_number(input_val)
                    if result == expected:
                        print(f"✅ safe_table_number({repr(input_val)}) = {result}")
                    else:
                        print(f"❌ safe_table_number({repr(input_val)}) = {result}, expected {expected}")
                        return False
                        
            except Exception as e:
                print(f"❌ safe_table_number test failed: {e}")
                return False
            
            # Test 4: Check database schema
            print("\n4. Checking database schema...")
            try:
                with db.engine.connect() as conn:
                    # Check DraftOrder table_number column type
                    result = conn.execute(text("""
                        SELECT data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'draft_orders' 
                        AND column_name = 'table_number'
                    """))
                    draft_type = result.fetchone()
                    if draft_type:
                        print(f"✅ DraftOrder.table_number type: {draft_type[0]}")
                    
                    # Check Table table_number column type
                    result = conn.execute(text("""
                        SELECT data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'tables' 
                        AND column_name = 'table_number'
                    """))
                    table_type = result.fetchone()
                    if table_type:
                        print(f"✅ Table.table_number type: {table_type[0]}")
                        
            except Exception as e:
                print(f"❌ Schema check failed: {e}")
                return False
            
            print("\n🎉 All tests passed! table_number compatibility is fixed.")
            return True
            
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🔧 Table Number Compatibility Test")
    print("=" * 50)
    
    success = test_table_number_queries()
    
    if success:
        print("\n✅ SUCCESS: All table_number queries should work now!")
        print("\nNext steps:")
        print("1. Deploy the updated code to Render")
        print("2. Test the sales pages in your browser")
        print("3. Try creating and managing draft orders")
    else:
        print("\n❌ FAILED: Some issues remain")
        print("Check the error messages above for details")
    
    sys.exit(0 if success else 1)
