#!/usr/bin/env python3
"""
Check existing menu data in the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import MenuCategory, MenuItem, Meal

def check_menu_data():
    """Check what menu data exists in the database"""
    with app.app_context():
        print("🔍 Checking Menu Data in Database\n")
        
        # Check MenuCategory
        categories = MenuCategory.query.all()
        print(f"📋 Menu Categories: {len(categories)}")
        for cat in categories:
            print(f"   - {cat.id}: {cat.name} (active: {cat.active})")
        
        print()
        
        # Check MenuItem
        menu_items = MenuItem.query.all()
        print(f"🍽️ Menu Items: {len(menu_items)}")
        
        # Group by category
        items_by_category = {}
        for item in menu_items:
            cat_name = item.category.name if item.category else "No Category"
            if cat_name not in items_by_category:
                items_by_category[cat_name] = []
            items_by_category[cat_name].append(item)
        
        for cat_name, items in items_by_category.items():
            print(f"   📂 {cat_name}: {len(items)} items")
            for item in items[:3]:  # Show first 3 items
                meal_name = item.meal.display_name if item.meal else "No Meal"
                price = item.price_override if item.price_override else (item.meal.selling_price if item.meal else 0)
                print(f"      - {meal_name}: {price} SAR")
            if len(items) > 3:
                print(f"      ... and {len(items) - 3} more")
        
        print()
        
        # Check Meals
        meals = Meal.query.filter_by(active=True).all()
        print(f"🥘 Active Meals: {len(meals)}")
        
        # Group meals by category
        meals_by_category = {}
        for meal in meals:
            cat_name = meal.category or "No Category"
            if cat_name not in meals_by_category:
                meals_by_category[cat_name] = []
            meals_by_category[cat_name].append(meal)
        
        for cat_name, meals_list in meals_by_category.items():
            print(f"   📂 {cat_name}: {len(meals_list)} meals")
            for meal in meals_list[:3]:  # Show first 3 meals
                print(f"      - {meal.display_name}: {meal.selling_price} SAR")
            if len(meals_list) > 3:
                print(f"      ... and {len(meals_list) - 3} more")
        
        print("\n" + "="*60)
        
        # Check if MenuItems are properly linked to Meals
        print("🔗 Checking MenuItem to Meal relationships:")
        linked_items = MenuItem.query.filter(MenuItem.meal_id.isnot(None)).count()
        total_items = MenuItem.query.count()
        print(f"   Linked MenuItems: {linked_items}/{total_items}")
        
        # Check if there are meals not in menu items
        meal_ids_in_menu = {item.meal_id for item in MenuItem.query.all() if item.meal_id}
        all_meal_ids = {meal.id for meal in Meal.query.filter_by(active=True).all()}
        unlinked_meals = all_meal_ids - meal_ids_in_menu
        
        print(f"   Meals not in MenuItems: {len(unlinked_meals)}")
        if unlinked_meals:
            print("   First 5 unlinked meals:")
            unlinked_meal_objects = Meal.query.filter(Meal.id.in_(list(unlinked_meals)[:5])).all()
            for meal in unlinked_meal_objects:
                print(f"      - {meal.display_name} (category: {meal.category})")

if __name__ == '__main__':
    check_menu_data()
