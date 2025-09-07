#!/usr/bin/env python3
"""
Simple test for Render API - no authentication required
"""

import requests
import json

def test_render_api():
    BASE_URL = 'https://restaurant-system-fnbm.onrender.com'
    
    print('🌐 Testing Render API...')
    print('=' * 40)
    
    try:
        # Test main page first
        print('🔗 Testing main page...')
        response = requests.get(f'{BASE_URL}/', timeout=10)
        print(f'   Status: {response.status_code}')
        
        if response.status_code != 200:
            print('   ❌ Main page not accessible')
            return
        
        # Test categories API
        print('📂 Testing categories API...')
        categories_url = f'{BASE_URL}/api/categories'
        response = requests.get(categories_url, timeout=15)
        
        print(f'   Status: {response.status_code}')
        
        if response.status_code == 200:
            try:
                categories = response.json()
                print(f'   ✅ Found {len(categories)} categories')
                
                # Show first few categories
                for i, cat in enumerate(categories[:5], 1):
                    print(f'      {i}. {cat.get("name", "Unknown")} (ID: {cat.get("id", "?")})')
                
                if len(categories) > 5:
                    print(f'      ... and {len(categories) - 5} more')
                
                # Test items API with first category
                if categories:
                    first_cat_id = categories[0].get('id')
                    print(f'\n🍽️ Testing items API for category {first_cat_id}...')
                    
                    items_url = f'{BASE_URL}/api/items?category_id={first_cat_id}'
                    items_response = requests.get(items_url, timeout=10)
                    
                    print(f'   Status: {items_response.status_code}')
                    
                    if items_response.status_code == 200:
                        try:
                            items = items_response.json()
                            print(f'   ✅ Found {len(items)} items')
                            
                            for item in items[:3]:
                                name = item.get('name', 'Unknown')
                                price = item.get('price', 0)
                                print(f'      • {name} - {price} SAR')
                        
                        except json.JSONDecodeError:
                            print('   ❌ Invalid JSON response for items')
                    else:
                        print(f'   ❌ Items API failed: {items_response.text[:100]}')
                
            except json.JSONDecodeError:
                print('   ❌ Invalid JSON response for categories')
                print(f'   Response: {response.text[:200]}')
        
        elif response.status_code == 401:
            print('   ❌ Authentication required')
            print('   💡 API requires login - need to add auth headers')
        
        elif response.status_code == 404:
            print('   ❌ API endpoint not found')
            print('   💡 Check if routes are properly configured')
        
        else:
            print(f'   ❌ API failed with status {response.status_code}')
            print(f'   Response: {response.text[:200]}')
    
    except requests.exceptions.Timeout:
        print('   ❌ Request timed out')
        print('   💡 Render server might be sleeping - try again')
    
    except requests.exceptions.ConnectionError:
        print('   ❌ Connection failed')
        print('   💡 Check if Render app is running')
    
    except Exception as e:
        print(f'   ❌ Unexpected error: {e}')

def generate_test_commands():
    """Generate manual test commands"""
    print('\n🛠️ Manual Testing Commands:')
    print('=' * 40)
    
    print('# Test with curl:')
    print('curl -X GET "https://restaurant-system-fnbm.onrender.com/api/categories"')
    print('curl -X GET "https://restaurant-system-fnbm.onrender.com/api/items?category_id=1"')
    
    print('\n# Test in browser:')
    print('https://restaurant-system-fnbm.onrender.com/api/categories')
    print('https://restaurant-system-fnbm.onrender.com/api/items?category_id=1')
    
    print('\n# Test POS interface:')
    print('https://restaurant-system-fnbm.onrender.com/sales/china_town')

def main():
    print('🚀 Render API Test')
    print('=' * 50)
    
    test_render_api()
    generate_test_commands()
    
    print('\n✅ Test completed!')

if __name__ == '__main__':
    main()
