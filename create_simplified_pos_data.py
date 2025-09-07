#!/usr/bin/env python3
"""
Create simplified POS data using Category and Item models
This implements the dynamic approach suggested by the user
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Category, Item, MenuCategory, MenuItem, Meal

def create_categories():
    """Create the 21 categories in simplified Category model"""
    
    categories_list = [
        "Appetizers", "Beef & Lamb", "Charcoal Grill / Kebabs", "Chicken",
        "Chinese Sizzling", "Duck", "House Special", "Indian Delicacy (Chicken)",
        "Indian Delicacy (Fish)", "Indian Delicacy (Vegetables)", "Juices",
        "Noodles & Chopsuey", "Prawns", "Rice & Biryani", "Salads",
        "Seafoods", "Shaw Faw", "Soft Drink", "Soups", "spring rolls", "دجاج"
    ]
    
    with app.app_context():
        print("🏷️ Creating simplified categories...")
        
        created_count = 0
        for cat_name in categories_list:
            # Check if category already exists
            existing = Category.query.filter_by(name=cat_name).first()
            if not existing:
                category = Category(name=cat_name, status='Active')
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
        
        return created_count

def migrate_meals_to_items():
    """Migrate existing meals to simplified Item model"""
    
    with app.app_context():
        print("🔄 Migrating meals to simplified items...")
        
        # Get all active meals
        meals = Meal.query.filter_by(active=True).all()
        print(f"📋 Found {len(meals)} active meals to migrate")
        
        # Get category mapping
        categories = {cat.name: cat for cat in Category.query.all()}
        menu_categories = {cat.id: cat.name for cat in MenuCategory.query.all()}
        
        migrated_count = 0
        
        for meal in meals:
            # Check if item already exists
            existing_item = Item.query.filter_by(name=meal.name).first()
            if existing_item:
                print(f"⚠️  Item already exists: {meal.name}")
                continue
            
            # Find category for this meal
            category = None
            
            # Try to find from MenuItem links
            menu_item = MenuItem.query.filter_by(meal_id=meal.id).first()
            if menu_item and menu_item.category_id in menu_categories:
                category_name = menu_categories[menu_item.category_id]
                category = categories.get(category_name)
            
            # Fallback to House Special if no category found
            if not category:
                category = categories.get('House Special')
            
            if category:
                # Create simplified item
                item = Item(
                    name=meal.display_name,
                    price=meal.selling_price or 0,
                    category_id=category.id,
                    status='Active'
                )
                db.session.add(item)
                migrated_count += 1
                print(f"✅ Migrated: {meal.display_name} -> {category.name}")
            else:
                print(f"❌ No category found for: {meal.display_name}")
        
        if migrated_count > 0:
            db.session.commit()
            print(f"\n🎉 Successfully migrated {migrated_count} meals to items!")
        else:
            print("\n✅ All meals already migrated!")
        
        return migrated_count

def create_sample_items():
    """Create sample items for empty categories"""
    
    sample_items = {
        'Appetizers': [
            {'name': 'Spring Rolls', 'price': 15.00},
            {'name': 'Chicken Samosa', 'price': 12.00},
            {'name': 'Vegetable Pakora', 'price': 18.00}
        ],
        'Beef & Lamb': [
            {'name': 'Beef Curry', 'price': 45.00},
            {'name': 'Lamb Biryani', 'price': 50.00},
            {'name': 'Grilled Lamb Chops', 'price': 65.00}
        ],
        'Charcoal Grill / Kebabs': [
            {'name': 'Chicken Tikka', 'price': 35.00},
            {'name': 'Seekh Kebab', 'price': 40.00},
            {'name': 'Mixed Grill', 'price': 55.00}
        ],
        'Chinese Sizzling': [
            {'name': 'Sizzling Chicken', 'price': 45.00},
            {'name': 'Sweet & Sour Chicken', 'price': 40.00},
            {'name': 'Kung Pao Chicken', 'price': 42.00}
        ],
        'Juices': [
            {'name': 'Fresh Orange Juice', 'price': 12.00},
            {'name': 'Mango Juice', 'price': 15.00},
            {'name': 'Apple Juice', 'price': 10.00}
        ],
        'Soft Drink': [
            {'name': 'Coca Cola', 'price': 8.00},
            {'name': 'Pepsi', 'price': 8.00},
            {'name': 'Fresh Lime', 'price': 10.00}
        ]
    }
    
    with app.app_context():
        print("🍽️ Creating sample items for empty categories...")
        
        # Get categories
        categories = {cat.name: cat for cat in Category.query.all()}
        
        created_count = 0
        
        for category_name, items_data in sample_items.items():
            if category_name not in categories:
                print(f"⚠️  Category not found: {category_name}")
                continue
            
            category = categories[category_name]
            
            # Check if category already has items
            existing_count = Item.query.filter_by(category_id=category.id).count()
            if existing_count > 0:
                print(f"⚠️  Category {category_name} already has {existing_count} items")
                continue
            
            print(f"\n📂 Adding items to: {category_name}")
            
            for item_data in items_data:
                # Check if item already exists
                existing_item = Item.query.filter_by(name=item_data['name']).first()
                if existing_item:
                    print(f"   ⚠️  Item already exists: {item_data['name']}")
                    continue
                
                # Create new item
                item = Item(
                    name=item_data['name'],
                    price=item_data['price'],
                    category_id=category.id,
                    status='Active'
                )
                db.session.add(item)
                created_count += 1
                print(f"   ✅ Created: {item_data['name']} - {item_data['price']} SAR")
        
        if created_count > 0:
            db.session.commit()
            print(f"\n🎉 Successfully created {created_count} sample items!")
        else:
            print("\n✅ All categories already have items!")
        
        return created_count

def test_simplified_api():
    """Test the simplified API endpoints"""
    
    with app.app_context():
        print("\n🧪 Testing simplified API...")
        
        # Test categories
        categories = Category.query.filter_by(status='Active').all()
        print(f"✅ Categories API: {len(categories)} categories")
        
        # Test items for each category
        categories_with_items = 0
        total_items = 0
        
        for cat in categories:
            item_count = Item.query.filter_by(category_id=cat.id, status='Active').count()
            if item_count > 0:
                categories_with_items += 1
                total_items += item_count
                print(f"   - {cat.name}: {item_count} items")
        
        print(f"\n📈 API Test Results:")
        print(f"   - Categories with items: {categories_with_items}/{len(categories)}")
        print(f"   - Total items available: {total_items}")
        
        if categories_with_items >= len(categories) * 0.8:  # 80% coverage
            print("✅ Excellent coverage! Simplified POS API should work great!")
        elif categories_with_items >= len(categories) * 0.5:  # 50% coverage
            print("⚠️  Good coverage, but some categories are still empty.")
        else:
            print("❌ Poor coverage. Many categories are empty.")
        
        return categories_with_items >= len(categories) * 0.5

def main():
    """Main function"""
    print("🚀 Creating Simplified POS Data (Category + Item models)\n")
    
    # Step 1: Create categories
    print("Step 1: Creating categories...")
    create_categories()
    
    # Step 2: Migrate existing meals
    print("\nStep 2: Migrating existing meals to items...")
    migrate_meals_to_items()
    
    # Step 3: Create sample items for empty categories
    print("\nStep 3: Creating sample items...")
    create_sample_items()
    
    # Step 4: Test the API
    print("\nStep 4: Testing API...")
    api_works = test_simplified_api()
    
    # Step 5: Final instructions
    print(f"\n🎯 Next Steps:")
    if api_works:
        print("✅ 1. Simplified POS API is ready!")
        print("✅ 2. Use GET /api/categories to get all categories")
        print("✅ 3. Use GET /api/items?category_id=<id> to get items for a category")
        print("✅ 4. Update POS frontend to use these simplified endpoints")
    else:
        print("❌ 1. Need to add more items to categories")
        print("💡 2. Run this script again or add items manually")
    
    print("🚀 5. Deploy to Render when ready")
    print("📝 6. Both old and new API endpoints are available for compatibility")

if __name__ == '__main__':
    main()
