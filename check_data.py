#!/usr/bin/env python3
"""
Check current data status
"""

import sys
sys.path.append('.')

from app import app
from models import Category, Item

def check_data():
    with app.app_context():
        print('📊 Current Data Status:')
        
        categories = Category.query.filter_by(status='Active').all()
        print(f'✅ Categories: {len(categories)}')
        
        total_items = 0
        categories_with_items = 0
        
        for cat in categories:
            items = Item.query.filter_by(category_id=cat.id, status='Active').all()
            if items:
                print(f'   - {cat.name}: {len(items)} items')
                total_items += len(items)
                categories_with_items += 1
        
        print(f'✅ Total Items: {total_items}')
        print(f'✅ Categories with items: {categories_with_items}/{len(categories)}')
        
        if categories_with_items > 0:
            print('🎯 System is ready! Categories will show in POS.')
        else:
            print('⚠️  No items found. Need to add items to categories.')

if __name__ == '__main__':
    check_data()
