#!/usr/bin/env python3
"""
Test the API endpoints directly without running the server
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import MenuCategory, MenuItem, Meal

def test_categories_api():
    """Test the categories API directly"""
    with app.app_context():
        print("🔍 Testing Categories API\n")
        
        # Test the logic that the API uses
        try:
            # Get active categories
            categories = MenuCategory.query.filter_by(active=True).order_by(MenuCategory.name.asc()).all()
            print(f"✅ Found {len(categories)} active categories")
            
            result = []
            for cat in categories:
                result.append({
                    'id': cat.id,
                    'name': cat.name
                })
                print(f"   - {cat.id}: {cat.name}")
            
            print(f"\n📋 API would return: {len(result)} categories")
            
            # Test items for first category
            if categories:
                first_cat = categories[0]
                print(f"\n🔍 Testing items for '{first_cat.name}' (ID: {first_cat.id})")
                
                items = MenuItem.query.filter_by(category_id=first_cat.id).order_by(MenuItem.display_order.asc().nulls_last()).all()
                print(f"✅ Found {len(items)} items in this category")
                
                for item in items:
                    if item.meal:
                        price = float(item.price_override) if item.price_override is not None else float(item.meal.selling_price or 0)
                        print(f"   - {item.meal.display_name}: {price} SAR")
                    else:
                        print(f"   - Item {item.id}: No meal linked")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing categories API: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_with_flask_client():
    """Test using Flask test client"""
    print("\n🔍 Testing with Flask Test Client\n")
    
    with app.test_client() as client:
        # Test categories endpoint
        response = client.get('/api/pos/china_town/categories')
        print(f"Categories API status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.get_json()
            print(f"✅ Categories API returned {len(data)} categories")
            for cat in data:
                print(f"   - {cat['id']}: {cat['name']}")
        elif response.status_code == 302:
            print("⚠️ API redirected (login required)")
        else:
            print(f"❌ API error: {response.status_code}")
            print(response.get_data(as_text=True))

if __name__ == '__main__':
    print("🚀 Testing API Endpoints Directly\n")
    
    # Test database logic
    success1 = test_categories_api()
    
    # Test Flask client
    test_with_flask_client()
    
    if success1:
        print("\n✅ Database logic works correctly")
        print("💡 The issue might be with authentication or server startup")
        print("\n🔧 Try these solutions:")
        print("1. Make sure you're logged in to the system")
        print("2. Check browser console for JavaScript errors")
        print("3. Try accessing the API directly: http://127.0.0.1:5000/api/pos/china_town/categories")
    else:
        print("\n❌ There's an issue with the database logic")
