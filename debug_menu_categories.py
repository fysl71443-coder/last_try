#!/usr/bin/env python3
"""
Debug script to check menu categories and items state
"""

import os
import sys
from flask import Flask
from extensions import db
from models import MenuCategory, MenuItem, Meal

def create_debug_app():
    """Create minimal Flask app for debugging"""
    app = Flask(__name__)
    
    # Load configuration
    from config import Config
    app.config.from_object(Config)
    
    # Initialize database
    db.init_app(app)
    
    return app

def check_menu_state():
    """Check the current state of menu categories and items"""
    app = create_debug_app()
    
    with app.app_context():
        print("🔍 Checking Menu Categories and Items...")
        print("=" * 50)
        
        try:
            # Check MenuCategory table
            categories = MenuCategory.query.all()
            print(f"📂 Found {len(categories)} menu categories:")
            for cat in categories:
                print(f"  - ID: {cat.id}, Name: '{cat.name}', Active: {cat.active}")
            
            if not categories:
                print("⚠️  No menu categories found!")
                print("💡 Creating default categories...")
                
                defaults = [
                    'Appetizers','Soups','Salads','House Special','Prawns','Seafoods',
                    'Chinese Sizzling','Shaw Faw','Chicken','Beef & Lamb','Rice & Biryani',
                    'Noodles & Chopsuey','Charcoal Grill / Kebabs','Indian Delicacy (Chicken)',
                    'Indian Delicacy (Fish)','Indian Delicacy (Vegetables)','Juices','Soft Drink'
                ]
                
                for name in defaults:
                    cat = MenuCategory(name=name, active=True)
                    db.session.add(cat)
                
                db.session.commit()
                print(f"✅ Created {len(defaults)} default categories")
                
                # Re-fetch categories
                categories = MenuCategory.query.all()
            
            print("\n" + "=" * 50)
            
            # Check MenuItem table
            menu_items = MenuItem.query.all()
            print(f"🍽️  Found {len(menu_items)} menu items:")
            for item in menu_items:
                meal_name = item.meal.display_name if item.meal else 'N/A'
                cat_name = item.category.name if item.category else 'N/A'
                print(f"  - ID: {item.id}, Category: '{cat_name}', Meal: '{meal_name}'")
            
            if not menu_items:
                print("⚠️  No menu items found!")
                print("💡 You need to link meals to categories in the /menu admin page")
            
            print("\n" + "=" * 50)
            
            # Check Meals table
            meals = Meal.query.filter_by(active=True).all()
            print(f"🥘 Found {len(meals)} active meals:")
            for meal in meals[:10]:  # Show first 10
                print(f"  - ID: {meal.id}, Name: '{meal.display_name}', Price: {meal.selling_price}")
            if len(meals) > 10:
                print(f"  ... and {len(meals) - 10} more meals")
            
            if not meals:
                print("⚠️  No active meals found!")
                print("💡 You need to create meals in the /meals admin page")
            
            print("\n" + "=" * 50)
            
            # Create category mapping
            cat_map = {c.name: c.id for c in categories if c.active}
            print(f"🗺️  Category mapping (CAT_MAP):")
            for name, cat_id in cat_map.items():
                item_count = MenuItem.query.filter_by(category_id=cat_id).count()
                print(f"  - '{name}' -> ID: {cat_id} ({item_count} items)")
            
            print("\n" + "=" * 50)
            print("✅ Menu state check complete!")
            
            return {
                'categories_count': len(categories),
                'menu_items_count': len(menu_items),
                'meals_count': len(meals),
                'cat_map': cat_map
            }
            
        except Exception as e:
            print(f"❌ Error checking menu state: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == '__main__':
    result = check_menu_state()
    if result:
        print(f"\n📊 Summary:")
        print(f"   Categories: {result['categories_count']}")
        print(f"   Menu Items: {result['menu_items_count']}")
        print(f"   Active Meals: {result['meals_count']}")
        print(f"   Category Map: {len(result['cat_map'])} entries")
