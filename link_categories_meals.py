#!/usr/bin/env python3
"""
Link existing meals to menu categories based on their category field
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Meal, MenuCategory, MenuItem

def create_categories_from_list():
    """Create the 21 categories from the provided list"""
    categories_list = [
        "Appetizers",
        "Beef & Lamb", 
        "Charcoal Grill / Kebabs",
        "Chicken",
        "Chinese Sizzling",
        "Duck",
        "House Special",
        "Indian Delicacy (Chicken)",
        "Indian Delicacy (Fish)",
        "Indian Delicacy (Vegetables)",
        "Juices",
        "Noodles & Chopsuey",
        "Prawns",
        "Rice & Biryani",
        "Salads",
        "Seafoods",
        "Shaw Faw",
        "Soft Drink",
        "Soups",
        "spring rolls",
        "دجاج"
    ]
    
    created_count = 0
    for cat_name in categories_list:
        # Check if category already exists
        existing = MenuCategory.query.filter_by(name=cat_name).first()
        if not existing:
            category = MenuCategory(name=cat_name, active=True)
            db.session.add(category)
            created_count += 1
            print(f"✅ Created category: {cat_name}")
        else:
            print(f"⚠️  Category already exists: {cat_name}")
    
    if created_count > 0:
        db.session.commit()
        print(f"\n🎉 Created {created_count} new categories!")
    else:
        print("\n✅ All categories already exist!")

def link_meals_to_categories():
    """Link existing meals to categories based on their category field"""
    
    # Category mapping - map meal.category to MenuCategory names
    category_mapping = {
        # Common mappings
        'chicken': 'Chicken',
        'beef': 'Beef & Lamb',
        'lamb': 'Beef & Lamb',
        'rice': 'Rice & Biryani',
        'biryani': 'Rice & Biryani',
        'appetizer': 'Appetizers',
        'appetizers': 'Appetizers',
        'soup': 'Soups',
        'soups': 'Soups',
        'salad': 'Salads',
        'salads': 'Salads',
        'juice': 'Juices',
        'juices': 'Juices',
        'drink': 'Soft Drink',
        'drinks': 'Soft Drink',
        'soft drink': 'Soft Drink',
        'noodles': 'Noodles & Chopsuey',
        'chopsuey': 'Noodles & Chopsuey',
        'prawns': 'Prawns',
        'prawn': 'Prawns',
        'seafood': 'Seafoods',
        'seafoods': 'Seafoods',
        'duck': 'Duck',
        'kebab': 'Charcoal Grill / Kebabs',
        'kebabs': 'Charcoal Grill / Kebabs',
        'grill': 'Charcoal Grill / Kebabs',
        'chinese': 'Chinese Sizzling',
        'sizzling': 'Chinese Sizzling',
        'indian': 'Indian Delicacy (Chicken)',
        'spring roll': 'spring rolls',
        'spring rolls': 'spring rolls',
        'دجاج': 'دجاج',
        'house special': 'House Special',
        'special': 'House Special'
    }
    
    # Get all meals
    meals = Meal.query.filter_by(active=True).all()
    print(f"📋 Found {len(meals)} active meals")
    
    # Get all categories
    categories = {cat.name.lower(): cat for cat in MenuCategory.query.all()}
    print(f"📋 Found {len(categories)} categories")
    
    linked_count = 0
    unlinked_meals = []
    
    for meal in meals:
        # Check if meal is already linked
        existing_link = MenuItem.query.filter_by(meal_id=meal.id).first()
        if existing_link:
            print(f"⚠️  Meal already linked: {meal.display_name}")
            continue
        
        # Try to find matching category
        category = None
        meal_category = (meal.category or '').lower().strip()
        
        if meal_category:
            # Direct match
            if meal_category in categories:
                category = categories[meal_category]
            # Mapping match
            elif meal_category in category_mapping:
                mapped_name = category_mapping[meal_category].lower()
                if mapped_name in categories:
                    category = categories[mapped_name]
            # Partial match
            else:
                for cat_key, cat_obj in categories.items():
                    if meal_category in cat_key or cat_key in meal_category:
                        category = cat_obj
                        break
        
        # If no category found, try to guess from meal name
        if not category:
            meal_name = meal.name.lower()
            for keyword, cat_name in category_mapping.items():
                if keyword in meal_name:
                    mapped_name = cat_name.lower()
                    if mapped_name in categories:
                        category = categories[mapped_name]
                        break
        
        # Link meal to category
        if category:
            menu_item = MenuItem(
                category_id=category.id,
                meal_id=meal.id,
                price_override=None,  # Use meal's selling_price
                display_order=None
            )
            db.session.add(menu_item)
            linked_count += 1
            print(f"✅ Linked: {meal.display_name} -> {category.name}")
        else:
            unlinked_meals.append(meal)
            print(f"❌ No category found for: {meal.display_name} (category: '{meal.category}')")
    
    # Commit changes
    if linked_count > 0:
        db.session.commit()
        print(f"\n🎉 Successfully linked {linked_count} meals to categories!")
    
    # Show unlinked meals
    if unlinked_meals:
        print(f"\n⚠️  {len(unlinked_meals)} meals could not be linked:")
        for meal in unlinked_meals:
            print(f"   - {meal.display_name} (category: '{meal.category}')")
        
        # Ask user to manually assign these to a default category
        print(f"\n💡 You can manually assign these meals to categories using the admin interface.")

def main():
    """Main function"""
    with app.app_context():
        print("🔗 Linking Categories and Meals\n")
        
        # Step 1: Create categories
        print("Step 1: Creating categories...")
        create_categories_from_list()
        
        print("\nStep 2: Linking meals to categories...")
        link_meals_to_categories()
        
        # Step 3: Show summary
        print("\n📊 Final Summary:")
        categories = MenuCategory.query.all()
        menu_items = MenuItem.query.all()
        meals = Meal.query.filter_by(active=True).all()
        
        print(f"   - Total categories: {len(categories)}")
        print(f"   - Total active meals: {len(meals)}")
        print(f"   - Total linked items: {len(menu_items)}")
        print(f"   - Unlinked meals: {len(meals) - len(menu_items)}")
        
        print("\n✅ Process completed!")

if __name__ == '__main__':
    main()
