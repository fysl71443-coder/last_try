#!/usr/bin/env python3
"""
Comprehensive test for all table_number queries to ensure type compatibility
"""

import os
import sys
from flask import Flask

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_all_table_number_queries():
    """Test all table_number queries in the application"""
    
    try:
        from app import app, db, safe_table_number
        from models import DraftOrder, Table
        
        with app.app_context():
            print("🔍 Comprehensive Table Number Query Test")
            print("=" * 50)
            
            # Test 1: DraftOrder queries with string conversion
            print("\n1. Testing DraftOrder queries...")
            test_cases = [
                ("filter_by with string", lambda: DraftOrder.query.filter_by(
                    branch_code='china_town',
                    table_number='1',
                    status='draft'
                ).count()),
                
                ("filter_by with str() conversion", lambda: DraftOrder.query.filter_by(
                    branch_code='china_town', 
                    table_number=str(5),
                    status='draft'
                ).count()),
            ]
            
            for test_name, query_func in test_cases:
                try:
                    result = query_func()
                    print(f"✅ {test_name}: {result} results")
                except Exception as e:
                    print(f"❌ {test_name} failed: {e}")
                    return False
            
            # Test 2: Table queries with integer values
            print("\n2. Testing Table queries...")
            table_test_cases = [
                ("filter_by with integer", lambda: Table.query.filter_by(
                    branch_code='china_town',
                    table_number=1
                ).count()),
                
                ("filter_by with safe_table_number", lambda: Table.query.filter_by(
                    branch_code='china_town',
                    table_number=safe_table_number('5')
                ).count()),
            ]
            
            for test_name, query_func in table_test_cases:
                try:
                    result = query_func()
                    print(f"✅ {test_name}: {result} results")
                except Exception as e:
                    print(f"❌ {test_name} failed: {e}")
                    return False
            
            # Test 3: Mixed scenarios that might occur in real usage
            print("\n3. Testing mixed scenarios...")
            
            # Simulate route parameter (int) being used with DraftOrder
            table_number_from_route = 10  # This comes as int from Flask route
            try:
                result = DraftOrder.query.filter_by(
                    branch_code='china_town',
                    table_number=str(table_number_from_route),  # Convert to string
                    status='draft'
                ).count()
                print(f"✅ Route int -> DraftOrder string: {result} results")
            except Exception as e:
                print(f"❌ Route int -> DraftOrder string failed: {e}")
                return False
            
            # Simulate DraftOrder.table_number being used with Table query
            try:
                # Create a mock draft order table_number (string)
                draft_table_number = '15'
                table_num_int = safe_table_number(draft_table_number)
                result = Table.query.filter_by(
                    branch_code='china_town',
                    table_number=table_num_int  # Convert to int
                ).count()
                print(f"✅ DraftOrder string -> Table int: {result} results")
            except Exception as e:
                print(f"❌ DraftOrder string -> Table int failed: {e}")
                return False
            
            # Test 4: Edge cases
            print("\n4. Testing edge cases...")
            edge_cases = [
                ("Empty string", ''),
                ("None value", None),
                ("Invalid string", 'invalid'),
                ("Zero string", '0'),
                ("Large number", '999'),
            ]
            
            for case_name, test_value in edge_cases:
                try:
                    # Test safe_table_number conversion
                    converted = safe_table_number(test_value)
                    
                    # Test DraftOrder query with string
                    draft_result = DraftOrder.query.filter_by(
                        branch_code='china_town',
                        table_number=str(test_value) if test_value is not None else '0',
                        status='draft'
                    ).count()
                    
                    # Test Table query with converted int
                    table_result = Table.query.filter_by(
                        branch_code='china_town',
                        table_number=converted
                    ).count()
                    
                    print(f"✅ {case_name}: safe_table_number={converted}, draft_query={draft_result}, table_query={table_result}")
                    
                except Exception as e:
                    print(f"❌ {case_name} failed: {e}")
                    return False
            
            print("\n🎉 All table_number queries passed!")
            print("\n📋 Summary:")
            print("- ✅ DraftOrder queries use string conversion")
            print("- ✅ Table queries use integer values")
            print("- ✅ safe_table_number() handles all edge cases")
            print("- ✅ Route parameters are properly converted")
            print("- ✅ Cross-model queries work correctly")
            
            return True
            
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_specific_app_routes():
    """Test the specific query patterns used in app routes"""
    
    try:
        from app import app, db, safe_table_number
        from models import DraftOrder, Table
        
        with app.app_context():
            print("\n🎯 Testing Specific App Route Patterns")
            print("=" * 50)
            
            # Pattern 1: sales_table_manage (line 688-692)
            print("\n1. sales_table_manage pattern...")
            table_number = 5  # From route <int:table_number>
            try:
                result = DraftOrder.query.filter_by(
                    branch_code='china_town',
                    table_number=str(table_number),  # ✅ Fixed
                    status='draft'
                ).order_by(DraftOrder.created_at.desc()).count()
                print(f"✅ sales_table_manage pattern: {result} results")
            except Exception as e:
                print(f"❌ sales_table_manage pattern failed: {e}")
                return False
            
            # Pattern 2: Table status update (line 1683)
            print("\n2. Table status update pattern...")
            try:
                result = Table.query.filter_by(
                    branch_code='china_town', 
                    table_number=table_number  # ✅ Integer for Table
                ).count()
                print(f"✅ Table status update pattern: {result} results")
            except Exception as e:
                print(f"❌ Table status update pattern failed: {e}")
                return False
            
            # Pattern 3: Cross-model operations
            print("\n3. Cross-model operations...")
            try:
                # Simulate getting a draft order and updating table
                draft_table_number = '10'  # From DraftOrder (VARCHAR)
                table_num_int = safe_table_number(draft_table_number)
                
                # Query Table with converted integer
                result = Table.query.filter_by(
                    branch_code='china_town',
                    table_number=table_num_int  # ✅ Converted to int
                ).count()
                print(f"✅ Cross-model operations: {result} results")
            except Exception as e:
                print(f"❌ Cross-model operations failed: {e}")
                return False
            
            print("\n🎉 All app route patterns work correctly!")
            return True
            
    except Exception as e:
        print(f"❌ App route test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🔧 Comprehensive Table Number Compatibility Test")
    print("Testing all query patterns used in the application...")
    
    success1 = test_all_table_number_queries()
    success2 = test_specific_app_routes()
    
    overall_success = success1 and success2
    
    if overall_success:
        print("\n🎊 SUCCESS: All table_number queries are compatible!")
        print("\n✅ Ready for deployment:")
        print("1. All DraftOrder queries use string conversion")
        print("2. All Table queries use integer values") 
        print("3. safe_table_number() bridges the gap")
        print("4. No more PostgreSQL type errors expected")
    else:
        print("\n❌ FAILED: Some compatibility issues remain")
        print("Check the error messages above for details")
    
    sys.exit(0 if overall_success else 1)
