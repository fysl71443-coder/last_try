#!/usr/bin/env python3
"""
Test script for the new POS system
Tests all the new functionality including:
- Branch-specific settings
- Draft invoice printing
- Payment processing
- Void password verification
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Settings, MenuCategory, MenuItem
import json

def test_database_setup():
    """Test that the database has the new branch-specific settings"""
    print("🔍 Testing database setup...")
    
    with app.app_context():
        settings = Settings.query.first()
        if not settings:
            print("❌ No settings found in database")
            return False
        
        # Check if new columns exist
        required_fields = [
            'china_town_void_password',
            'china_town_vat_rate', 
            'china_town_discount_rate',
            'place_india_void_password',
            'place_india_vat_rate',
            'place_india_discount_rate'
        ]
        
        for field in required_fields:
            if not hasattr(settings, field):
                print(f"❌ Missing field: {field}")
                return False
            print(f"✅ Field exists: {field} = {getattr(settings, field)}")
        
        print("✅ Database setup is correct")
        return True

def test_routes():
    """Test that all new routes are accessible"""
    print("\n🔍 Testing routes...")
    
    with app.test_client() as client:
        routes_to_test = [
            ('/sales', 'Sales branch selection'),
            ('/sales/china_town', 'China Town POS'),
            ('/sales/palace_india', 'Palace India POS'),
            ('/settings', 'Settings page'),
        ]
        
        for route, description in routes_to_test:
            response = client.get(route)
            if response.status_code in [200, 302]:  # 302 is redirect (login required)
                print(f"✅ {description}: {response.status_code}")
            else:
                print(f"❌ {description}: {response.status_code}")
                return False
        
        print("✅ All routes are accessible")
        return True

def test_api_endpoints():
    """Test API endpoints structure"""
    print("\n🔍 Testing API endpoints...")

    with app.test_client() as client:
        api_routes = [
            '/api/pos/china_town/categories',
            '/api/pos/palace_india/categories',
            '/api/pos/china_town/categories/1/items',
            '/api/pos/china_town/customers/search?q=test',
            '/api/pos/china_town/print_draft',
            '/api/pos/china_town/process_payment',
            '/api/pos/china_town/verify_void_password',
        ]

        for route in api_routes:
            if 'categories' in route and not 'items' in route:
                response = client.get(route)
            elif 'search' in route:
                response = client.get(route)
            elif 'items' in route:
                response = client.get(route)
            else:
                response = client.post(route)

            # API routes should return 302 (redirect to login) or 400/500 (missing data)
            if response.status_code in [302, 400, 500]:
                print(f"✅ API endpoint exists: {route}")
            else:
                print(f"❌ API endpoint issue: {route} - {response.status_code}")
                return False

        print("✅ All API endpoints are accessible")
        return True

def test_helper_functions():
    """Test helper functions for invoice generation"""
    print("\n🔍 Testing helper functions...")
    
    try:
        from app import generate_draft_invoice_html, generate_final_invoice_html
        
        # Test data
        test_data = {
            'items': [
                {'id': 1, 'name': 'Test Item', 'price': 10.0, 'quantity': 2}
            ],
            'table_number': '5',
            'customer_phone': '1234567890',
            'customer_discount': 10.0
        }
        
        # Test draft invoice generation
        draft_html = generate_draft_invoice_html('china_town', test_data)
        if 'UNPAID' in draft_html and 'Table #5' in draft_html:
            print("✅ Draft invoice generation works")
        else:
            print("❌ Draft invoice generation failed")
            return False
        
        # Test final invoice generation
        final_html = generate_final_invoice_html('china_town', test_data, 'TEST-001')
        if 'PAID' in final_html and 'Invoice #TEST-001' in final_html:
            print("✅ Final invoice generation works")
        else:
            print("❌ Final invoice generation failed")
            return False
        
        print("✅ Helper functions work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Helper function test failed: {e}")
        return False

def test_template_files():
    """Test that all template files exist"""
    print("\n🔍 Testing template files...")
    
    template_files = [
        'templates/china_town_sales.html',
        'templates/palace_india_sales.html', 
        'templates/sales_branches.html',
        'templates/sales_redirect.html',
        'templates/settings.html'
    ]
    
    for template in template_files:
        if os.path.exists(template):
            print(f"✅ Template exists: {template}")
        else:
            print(f"❌ Template missing: {template}")
            return False
    
    print("✅ All template files exist")
    return True

def run_all_tests():
    """Run all tests"""
    print("🚀 Starting POS System Tests\n")
    
    tests = [
        test_database_setup,
        test_routes,
        test_api_endpoints,
        test_helper_functions,
        test_template_files
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test failed: {test.__name__}")
        except Exception as e:
            print(f"❌ Test error in {test.__name__}: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The new POS system is ready to use.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
