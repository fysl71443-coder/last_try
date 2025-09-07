#!/usr/bin/env python3
"""
Test the API endpoints
"""

import requests
import time

def test_api():
    print("Testing API endpoints...")
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test categories endpoint
        print("\n1. Testing /api/categories")
        response = requests.get('http://localhost:5000/api/categories')
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Categories found: {len(data)}")
            for cat in data[:5]:  # Show first 5
                print(f"  - {cat['id']}: {cat['name']}")
        else:
            print(f"Response: {response.text[:200]}")
        
        # Test items endpoint
        if response.status_code == 200 and data:
            print(f"\n2. Testing /api/items?category_id={data[0]['id']}")
            items_response = requests.get(f"http://localhost:5000/api/items?category_id={data[0]['id']}")
            print(f"Status: {items_response.status_code}")
            
            if items_response.status_code == 200:
                items_data = items_response.json()
                print(f"Items found: {len(items_data)}")
                for item in items_data[:3]:  # Show first 3
                    print(f"  - {item['id']}: {item['name']} - {item['price']} SAR")
            else:
                print(f"Response: {items_response.text[:200]}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_api()
