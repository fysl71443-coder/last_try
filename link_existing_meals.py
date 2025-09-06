#!/usr/bin/env python3
"""
Link existing meals to menu categories based on their category field
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Meal, MenuCategory, MenuItem

def link_existing_meals():
    """Link existing meals to menu categories"""
    with app.app_context():
        print("🔗 Linking Existing Meals to Menu Categories\n")
        
        # Get all active meals
        meals = Meal.query.filter_by(active=True).all()
        print(f"Found {len(meals)} active meals")
        
        # Get all categories
        categories = MenuCategory.query.filter_by(active=True).all()
        category_map = {cat.name.lower(): cat for cat in categories}
        
        print(f"Found {len(categories)} categories")
        print("Available categories:", list(category_map.keys()))
        
        # Category mapping for existing meals
        category_mapping = {
            'main course': 'chicken',  # Map to closest category
            'side dish': 'rice & biryani',
            'دجاج': 'chicken',
            'general': 'house special'
        }
        
        linked_count = 0
        
        for meal in meals:
            meal_category = (meal.category or '').lower()
            
            # Try direct match first
            target_category = None
            if meal_category in category_map:
                target_category = category_map[meal_category]
            elif meal_category in category_mapping:
                mapped_name = category_mapping[meal_category].lower()
                target_category = category_map.get(mapped_name)
            else:
                # Default to House Special
                target_category = category_map.get('house special')
            
            if target_category:
                # Check if already linked
                existing = MenuItem.query.filter_by(
                    category_id=target_category.id,
                    meal_id=meal.id
                ).first()
                
                if not existing:
                    menu_item = MenuItem(
                        category_id=target_category.id,
                        meal_id=meal.id,
                        display_order=linked_count + 1
                    )
                    db.session.add(menu_item)
                    linked_count += 1
                    print(f"✅ Linked '{meal.display_name}' to '{target_category.name}'")
                else:
                    print(f"⚠️ '{meal.display_name}' already linked to '{target_category.name}'")
            else:
                print(f"❌ Could not find category for '{meal.display_name}' (category: {meal.category})")
        
        if linked_count > 0:
            try:
                db.session.commit()
                print(f"\n🎉 Successfully linked {linked_count} meals to categories!")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error saving changes: {e}")
        else:
            print("\n⚠️ No new meals were linked.")
        
        # Show final status
        total_menu_items = MenuItem.query.count()
        print(f"\n📊 Total MenuItems now: {total_menu_items}")
        
        # Show items by category
        print("\n📋 Menu Items by Category:")
        for category in categories:
            items = MenuItem.query.filter_by(category_id=category.id).all()
            if items:
                print(f"   📂 {category.name}: {len(items)} items")
                for item in items:
                    meal_name = item.meal.display_name if item.meal else "No Meal"
                    price = item.price_override if item.price_override else (item.meal.selling_price if item.meal else 0)
                    print(f"      - {meal_name}: {price} SAR")

if __name__ == '__main__':
    link_existing_meals()
