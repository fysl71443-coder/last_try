#!/usr/bin/env python3
"""
Fix category-meal links for POS system
This script ensures all meals are properly linked to categories
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Meal, MenuCategory, MenuItem

def smart_category_mapping():
    """Smart mapping of meals to categories based on name and content"""
    
    # Enhanced category mapping with Arabic support
    category_mappings = {
        # Chicken dishes
        'chicken': ['Chicken', 'دجاج', 'Indian Delicacy (Chicken)'],
        'دجاج': ['Chicken', 'دجاج', 'Indian Delicacy (Chicken)'],
        'curry': ['Indian Delicacy (Chicken)', 'Chicken'],
        'tikka': ['Charcoal Grill / Kebabs', 'Indian Delicacy (Chicken)'],
        'tandoor': ['Charcoal Grill / Kebabs', 'Indian Delicacy (Chicken)'],
        
        # Rice and Biryani
        'rice': ['Rice & Biryani'],
        'biryani': ['Rice & Biryani'],
        'برياني': ['Rice & Biryani'],
        'أرز': ['Rice & Biryani'],
        'fried rice': ['Rice & Biryani', 'Chinese Sizzling'],
        
        # Beef and Lamb
        'beef': ['Beef & Lamb'],
        'lamb': ['Beef & Lamb'],
        'mutton': ['Beef & Lamb'],
        'لحم': ['Beef & Lamb'],
        
        # Seafood
        'fish': ['Indian Delicacy (Fish)', 'Seafoods'],
        'prawn': ['Prawns', 'Seafoods'],
        'shrimp': ['Prawns', 'Seafoods'],
        'crab': ['Seafoods'],
        'lobster': ['Seafoods'],
        'سمك': ['Indian Delicacy (Fish)', 'Seafoods'],
        
        # Chinese dishes
        'chinese': ['Chinese Sizzling'],
        'sizzling': ['Chinese Sizzling'],
        'chow mein': ['Noodles & Chopsuey'],
        'noodles': ['Noodles & Chopsuey'],
        'chopsuey': ['Noodles & Chopsuey'],
        'fried': ['Chinese Sizzling'],
        
        # Appetizers
        'starter': ['Appetizers'],
        'appetizer': ['Appetizers'],
        'spring roll': ['spring rolls', 'Appetizers'],
        'samosa': ['Appetizers'],
        'pakora': ['Appetizers'],
        
        # Soups
        'soup': ['Soups'],
        'شوربة': ['Soups'],
        
        # Salads
        'salad': ['Salads'],
        'سلطة': ['Salads'],
        
        # Drinks
        'juice': ['Juices'],
        'عصير': ['Juices'],
        'drink': ['Soft Drink'],
        'cola': ['Soft Drink'],
        'water': ['Soft Drink'],
        'tea': ['Soft Drink'],
        'coffee': ['Soft Drink'],
        
        # Vegetables
        'vegetable': ['Indian Delicacy (Vegetables)'],
        'veg': ['Indian Delicacy (Vegetables)'],
        'خضار': ['Indian Delicacy (Vegetables)'],
        'paneer': ['Indian Delicacy (Vegetables)'],
        
        # Kebabs and Grills
        'kebab': ['Charcoal Grill / Kebabs'],
        'grill': ['Charcoal Grill / Kebabs'],
        'bbq': ['Charcoal Grill / Kebabs'],
        'شواء': ['Charcoal Grill / Kebabs'],
        
        # Duck
        'duck': ['Duck'],
        'بط': ['Duck'],
        
        # Special dishes
        'special': ['House Special'],
        'signature': ['House Special'],
        'chef': ['House Special']
    }
    
    return category_mappings

def link_meals_intelligently():
    """Link meals to categories using intelligent mapping"""
    
    with app.app_context():
        print("🔗 Starting intelligent meal-category linking...")
        
        # Get all categories as a lookup dict
        categories = {cat.name: cat for cat in MenuCategory.query.all()}
        category_mappings = smart_category_mapping()
        
        # Get all active meals
        meals = Meal.query.filter_by(active=True).all()
        print(f"📋 Found {len(meals)} active meals")
        print(f"📋 Found {len(categories)} categories")
        
        linked_count = 0
        unlinked_meals = []
        
        for meal in meals:
            # Skip if already linked
            existing_link = MenuItem.query.filter_by(meal_id=meal.id).first()
            if existing_link:
                print(f"⚠️  Already linked: {meal.display_name}")
                continue
            
            # Try to find best category match
            best_category = None
            meal_text = f"{meal.name} {meal.name_ar or ''} {meal.category or ''}".lower()
            
            # Score each category based on keyword matches
            category_scores = {}
            
            for keyword, possible_cats in category_mappings.items():
                if keyword in meal_text:
                    for cat_name in possible_cats:
                        if cat_name in categories:
                            category_scores[cat_name] = category_scores.get(cat_name, 0) + 1
            
            # Choose category with highest score
            if category_scores:
                best_category_name = max(category_scores, key=category_scores.get)
                best_category = categories[best_category_name]
            
            # Fallback: try direct category match
            if not best_category and meal.category:
                meal_cat = meal.category.strip()
                # Try exact match
                for cat_name, cat_obj in categories.items():
                    if meal_cat.lower() == cat_name.lower():
                        best_category = cat_obj
                        break
                
                # Try partial match
                if not best_category:
                    for cat_name, cat_obj in categories.items():
                        if meal_cat.lower() in cat_name.lower() or cat_name.lower() in meal_cat.lower():
                            best_category = cat_obj
                            break
            
            # Final fallback: assign to House Special
            if not best_category:
                best_category = categories.get('House Special')
            
            # Create the link
            if best_category:
                menu_item = MenuItem(
                    category_id=best_category.id,
                    meal_id=meal.id,
                    price_override=None,  # Use meal's selling_price
                    display_order=None
                )
                db.session.add(menu_item)
                linked_count += 1
                print(f"✅ Linked: {meal.display_name} -> {best_category.name}")
            else:
                unlinked_meals.append(meal)
                print(f"❌ Could not link: {meal.display_name}")
        
        # Commit changes
        if linked_count > 0:
            db.session.commit()
            print(f"\n🎉 Successfully linked {linked_count} meals!")
        
        # Show summary
        total_categories = len(categories)
        total_meals = len(meals)
        total_links = MenuItem.query.count()
        
        print(f"\n📊 Final Summary:")
        print(f"   - Total categories: {total_categories}")
        print(f"   - Total active meals: {total_meals}")
        print(f"   - Total linked items: {total_links}")
        print(f"   - Newly linked: {linked_count}")
        print(f"   - Unlinked meals: {len(unlinked_meals)}")
        
        if unlinked_meals:
            print(f"\n⚠️  Unlinked meals:")
            for meal in unlinked_meals:
                print(f"   - {meal.display_name} (category: '{meal.category}')")
        
        return linked_count

def test_pos_api():
    """Test the POS API to ensure categories and items work"""
    
    with app.app_context():
        print("\n🧪 Testing POS API...")
        
        # Test categories
        categories = MenuCategory.query.filter_by(active=True).order_by(MenuCategory.name.asc()).all()
        print(f"✅ Categories API: {len(categories)} categories")
        
        # Test items for each category
        categories_with_items = 0
        total_items = 0
        
        for cat in categories:
            items = MenuItem.query.filter_by(category_id=cat.id).all()
            if items:
                categories_with_items += 1
                total_items += len(items)
                print(f"   - {cat.name}: {len(items)} items")
        
        print(f"\n📈 API Test Results:")
        print(f"   - Categories with items: {categories_with_items}/{len(categories)}")
        print(f"   - Total items available: {total_items}")
        
        if categories_with_items == 0:
            print("❌ No categories have items! POS will not work.")
            return False
        elif categories_with_items < len(categories) / 2:
            print("⚠️  Many categories are empty. Consider redistributing meals.")
        else:
            print("✅ POS API should work correctly!")
        
        return True

def main():
    """Main function"""
    print("🔧 Fixing Category-Meal Links for POS System\n")
    
    # Step 1: Link meals intelligently
    linked_count = link_meals_intelligently()
    
    # Step 2: Test the API
    api_works = test_pos_api()
    
    # Step 3: Final recommendations
    print(f"\n🎯 Next Steps:")
    if api_works:
        print("✅ 1. POS system should now work correctly")
        print("✅ 2. Categories will show their respective meals")
        print("✅ 3. Test the POS interface at /sales/china_town or /sales/palace_india")
    else:
        print("❌ 1. POS system needs more work")
        print("💡 2. Consider adding more meals or redistributing existing ones")
    
    print("🚀 3. Deploy to Render to see changes in production")
    print("📝 4. Use the admin interface at /menu to manually adjust categories if needed")

if __name__ == '__main__':
    main()
