#!/usr/bin/env python3
"""
Test local API to verify it works before testing Render
"""

import sys
sys.path.append('.')

from app import app
from models import Category, Item

def test_local_data():
    """Test local database directly"""
    with app.app_context():
        print('🏠 Testing Local Database:')
        print('=' * 40)
        
        # Get categories
        categories = Category.query.filter_by(status='Active').all()
        print(f'✅ Categories: {len(categories)}')
        
        total_items = 0
        for i, cat in enumerate(categories[:10], 1):  # Show first 10
            items = Item.query.filter_by(category_id=cat.id, status='Active').all()
            total_items += len(items)
            
            print(f'{i:2d}. {cat.name} (ID: {cat.id})')
            print(f'    Items: {len(items)}')
            
            for item in items[:2]:  # Show first 2 items
                print(f'      • {item.name} - {item.price} SAR')
            
            if len(items) > 2:
                print(f'      ... and {len(items) - 2} more items')
        
        if len(categories) > 10:
            print(f'... and {len(categories) - 10} more categories')
        
        print(f'\n📊 Summary:')
        print(f'   Total Categories: {len(categories)}')
        print(f'   Total Items: {total_items}')
        
        if total_items > 0:
            print('   🎯 Status: Ready for POS!')
        else:
            print('   ⚠️  Status: Need to add items')

def test_api_routes():
    """Test API routes directly"""
    with app.app_context():
        print('\n🔗 Testing API Routes:')
        print('=' * 40)
        
        # Test categories route
        try:
            from models import Category
            categories = Category.query.filter_by(status='Active').all()
            categories_json = [cat.to_dict() for cat in categories]
            print(f'✅ /api/categories would return {len(categories_json)} categories')
            
            # Test items route for first category
            if categories:
                first_cat = categories[0]
                from models import Item
                items = Item.query.filter_by(category_id=first_cat.id, status='Active').all()
                items_json = [item.to_dict() for item in items]
                print(f'✅ /api/items?category_id={first_cat.id} would return {len(items_json)} items')
            
        except Exception as e:
            print(f'❌ API route test failed: {e}')

def generate_curl_commands():
    """Generate curl commands for testing"""
    print('\n🌐 Curl Commands for Testing:')
    print('=' * 40)
    
    print('# Test Render API:')
    print('curl -X GET "https://restaurant-system-fnbm.onrender.com/api/categories"')
    print('curl -X GET "https://restaurant-system-fnbm.onrender.com/api/items?category_id=1"')
    
    print('\n# Test Local API:')
    print('curl -X GET "http://localhost:5000/api/categories"')
    print('curl -X GET "http://localhost:5000/api/items?category_id=1"')

def main():
    print('🚀 Local API Test')
    print('=' * 50)
    
    test_local_data()
    test_api_routes()
    generate_curl_commands()
    
    print('\n✅ Local test completed!')
    print('\n💡 Next steps:')
    print('   1. Start local server: python app.py')
    print('   2. Test local API with curl commands above')
    print('   3. Test Render API with curl commands above')

if __name__ == '__main__':
    main()
