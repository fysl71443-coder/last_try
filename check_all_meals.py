#!/usr/bin/env python3
"""
Check all meals in the database including inactive ones
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Meal

def check_all_meals():
    """Check all meals in the database"""
    with app.app_context():
        print("🔍 Checking All Meals in Database\n")
        
        # Check all meals (active and inactive)
        all_meals = Meal.query.all()
        active_meals = Meal.query.filter_by(active=True).all()
        inactive_meals = Meal.query.filter_by(active=False).all()
        
        print(f"🥘 Total Meals: {len(all_meals)}")
        print(f"   ✅ Active: {len(active_meals)}")
        print(f"   ❌ Inactive: {len(inactive_meals)}")
        
        print("\n📊 Meals by Category:")
        
        # Group all meals by category
        meals_by_category = {}
        for meal in all_meals:
            cat_name = meal.category or "No Category"
            if cat_name not in meals_by_category:
                meals_by_category[cat_name] = {'active': 0, 'inactive': 0, 'meals': []}
            
            if meal.active:
                meals_by_category[cat_name]['active'] += 1
            else:
                meals_by_category[cat_name]['inactive'] += 1
            
            meals_by_category[cat_name]['meals'].append(meal)
        
        for cat_name, data in sorted(meals_by_category.items()):
            total = data['active'] + data['inactive']
            print(f"   📂 {cat_name}: {total} meals (✅{data['active']} ❌{data['inactive']})")
            
            # Show first few meals
            for meal in data['meals'][:3]:
                status = "✅" if meal.active else "❌"
                print(f"      {status} {meal.display_name}: {meal.selling_price} SAR")
            
            if len(data['meals']) > 3:
                print(f"      ... and {len(data['meals']) - 3} more")
        
        print(f"\n📈 Summary:")
        print(f"   Total categories with meals: {len(meals_by_category)}")
        print(f"   Total meals: {len(all_meals)}")
        
        if len(all_meals) > 50:
            print(f"\n🎯 It looks like you have {len(all_meals)} meals!")
            print("   The issue is that these meals are not linked to MenuItems.")
            print("   We need to create MenuItem entries to link meals to categories.")

if __name__ == '__main__':
    check_all_meals()
