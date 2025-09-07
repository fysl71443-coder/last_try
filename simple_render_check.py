#!/usr/bin/env python3
"""
Simple check for Render API
"""

import requests
import json

def check_render_api():
    BASE_URL = 'https://restaurant-system-fnbm.onrender.com'
    
    print('🚀 Checking Render API...')
    print('=' * 50)
    
    try:
        # Test connection
        print('🔗 Testing connection...')
        response = requests.get(f'{BASE_URL}/', timeout=15)
        print(f'✅ Server available - Status: {response.status_code}')
        
        # Get categories
        print('📋 Getting categories...')
        categories_response = requests.get(f'{BASE_URL}/api/categories', timeout=15)
        
        if categories_response.status_code == 200:
            categories = categories_response.json()
            print(f'✅ Found {len(categories)} categories')
            
            for i, cat in enumerate(categories[:5], 1):
                cat_name = cat.get('name', 'Unknown')
                cat_id = cat.get('id', 'Unknown')
                print(f'{i}. {cat_name} (ID: {cat_id})')
                
                # Get items for this category
                items_url = f'{BASE_URL}/api/items?category_id={cat_id}'
                items_response = requests.get(items_url, timeout=10)
                
                if items_response.status_code == 200:
                    items = items_response.json()
                    print(f'   📊 {len(items)} items')
                    
                    for item in items[:2]:  # Show first 2 items
                        item_name = item.get('name', 'Unknown')
                        item_price = item.get('price', 0)
                        print(f'      • {item_name} - {item_price} SAR')
                else:
                    print(f'   ❌ Failed to get items - Status: {items_response.status_code}')
            
            if len(categories) > 5:
                print(f'... and {len(categories) - 5} more categories')
                
        elif categories_response.status_code == 401:
            print('❌ Login required to access API')
        else:
            print(f'❌ Failed to get categories - Status: {categories_response.status_code}')
            print(f'Response: {categories_response.text[:200]}')
    
    except Exception as e:
        print(f'❌ Error: {e}')
    
    print('✅ Check completed')

if __name__ == '__main__':
    check_render_api()
