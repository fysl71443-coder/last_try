#!/usr/bin/env python3
"""
Add sample meals for each category to test POS system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Meal, MenuCategory, MenuItem, User

def create_sample_meals():
    """Create sample meals for each category"""
    
    # Sample meals for each category
    sample_meals = {
        'Appetizers': [
            {'name': 'Spring Rolls', 'name_ar': 'سبرينغ رولز', 'price': 15.00},
            {'name': 'Chicken Samosa', 'name_ar': 'سمبوسة دجاج', 'price': 12.00},
            {'name': 'Vegetable Pakora', 'name_ar': 'باكورا خضار', 'price': 18.00}
        ],
        'Beef & Lamb': [
            {'name': 'Beef Curry', 'name_ar': 'كاري لحم', 'price': 45.00},
            {'name': 'Lamb Biryani', 'name_ar': 'برياني لحم', 'price': 50.00},
            {'name': 'Grilled Lamb Chops', 'name_ar': 'ريش لحم مشوي', 'price': 65.00}
        ],
        'Charcoal Grill / Kebabs': [
            {'name': 'Chicken Tikka', 'name_ar': 'تكا دجاج', 'price': 35.00},
            {'name': 'Seekh Kebab', 'name_ar': 'سيخ كباب', 'price': 40.00},
            {'name': 'Mixed Grill', 'name_ar': 'مشاوي مشكلة', 'price': 55.00}
        ],
        'Chicken': [
            {'name': 'Butter Chicken', 'name_ar': 'دجاج بالزبدة', 'price': 38.00},
            {'name': 'Chicken Karahi', 'name_ar': 'دجاج كراهي', 'price': 42.00}
        ],
        'Chinese Sizzling': [
            {'name': 'Sizzling Chicken', 'name_ar': 'دجاج سيزلنغ', 'price': 45.00},
            {'name': 'Sweet & Sour Chicken', 'name_ar': 'دجاج حلو وحامض', 'price': 40.00},
            {'name': 'Kung Pao Chicken', 'name_ar': 'كونغ باو دجاج', 'price': 42.00}
        ],
        'Duck': [
            {'name': 'Roasted Duck', 'name_ar': 'بط محمر', 'price': 60.00},
            {'name': 'Duck Curry', 'name_ar': 'كاري بط', 'price': 55.00}
        ],
        'Indian Delicacy (Chicken)': [
            {'name': 'Chicken Tandoori', 'name_ar': 'دجاج تندوري', 'price': 40.00},
            {'name': 'Chicken Masala', 'name_ar': 'دجاج مسالا', 'price': 38.00}
        ],
        'Indian Delicacy (Fish)': [
            {'name': 'Fish Curry', 'name_ar': 'كاري سمك', 'price': 45.00},
            {'name': 'Fish Tikka', 'name_ar': 'تكا سمك', 'price': 48.00}
        ],
        'Indian Delicacy (Vegetables)': [
            {'name': 'Paneer Masala', 'name_ar': 'بانير مسالا', 'price': 32.00},
            {'name': 'Dal Makhani', 'name_ar': 'دال مخاني', 'price': 28.00}
        ],
        'Juices': [
            {'name': 'Fresh Orange Juice', 'name_ar': 'عصير برتقال طازج', 'price': 12.00},
            {'name': 'Mango Juice', 'name_ar': 'عصير مانجو', 'price': 15.00}
        ],
        'Noodles & Chopsuey': [
            {'name': 'Chicken Chow Mein', 'name_ar': 'تشاو مين دجاج', 'price': 35.00},
            {'name': 'Vegetable Chopsuey', 'name_ar': 'تشوب سوي خضار', 'price': 30.00}
        ],
        'Prawns': [
            {'name': 'Prawn Curry', 'name_ar': 'كاري جمبري', 'price': 50.00},
            {'name': 'Grilled Prawns', 'name_ar': 'جمبري مشوي', 'price': 55.00}
        ],
        'Rice & Biryani': [
            {'name': 'Vegetable Biryani', 'name_ar': 'برياني خضار', 'price': 32.00},
            {'name': 'Fried Rice', 'name_ar': 'أرز مقلي', 'price': 25.00}
        ],
        'Salads': [
            {'name': 'Greek Salad', 'name_ar': 'سلطة يونانية', 'price': 22.00},
            {'name': 'Caesar Salad', 'name_ar': 'سلطة قيصر', 'price': 25.00}
        ],
        'Seafoods': [
            {'name': 'Grilled Fish', 'name_ar': 'سمك مشوي', 'price': 48.00},
            {'name': 'Seafood Platter', 'name_ar': 'طبق مأكولات بحرية', 'price': 75.00}
        ],
        'Soft Drink': [
            {'name': 'Coca Cola', 'name_ar': 'كوكا كولا', 'price': 8.00},
            {'name': 'Fresh Lime', 'name_ar': 'ليمون طازج', 'price': 10.00}
        ],
        'Soups': [
            {'name': 'Chicken Soup', 'name_ar': 'شوربة دجاج', 'price': 18.00},
            {'name': 'Hot & Sour Soup', 'name_ar': 'شوربة حارة وحامضة', 'price': 20.00}
        ],
        'spring rolls': [
            {'name': 'Vegetable Spring Rolls', 'name_ar': 'سبرينغ رولز خضار', 'price': 16.00}
        ],
        'دجاج': [
            {'name': 'دجاج مشوي', 'name_ar': 'دجاج مشوي', 'price': 35.00},
            {'name': 'دجاج محشي', 'name_ar': 'دجاج محشي', 'price': 45.00}
        ]
    }
    
    with app.app_context():
        print("🍽️ Creating sample meals for categories...")
        
        # Get admin user
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            print("❌ No admin user found. Creating one...")
            admin_user = User(username='admin', email='admin@example.com', role='admin', active=True)
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
        
        # Get all categories
        categories = {cat.name: cat for cat in MenuCategory.query.all()}
        
        created_meals = 0
        created_links = 0
        
        for category_name, meals_data in sample_meals.items():
            if category_name not in categories:
                print(f"⚠️  Category not found: {category_name}")
                continue
            
            category = categories[category_name]
            print(f"\n📂 Processing category: {category_name}")
            
            for meal_data in meals_data:
                # Check if meal already exists
                existing_meal = Meal.query.filter_by(name=meal_data['name']).first()
                if existing_meal:
                    print(f"   ⚠️  Meal already exists: {meal_data['name']}")
                    continue
                
                # Create new meal
                meal = Meal(
                    name=meal_data['name'],
                    name_ar=meal_data['name_ar'],
                    description=f"Delicious {meal_data['name']}",
                    category=category_name,
                    total_cost=meal_data['price'] * 0.6,  # 60% cost ratio
                    profit_margin_percent=40.0,
                    selling_price=meal_data['price'],
                    active=True,
                    user_id=admin_user.id
                )
                db.session.add(meal)
                db.session.flush()  # Get the meal ID
                
                # Create menu item link
                menu_item = MenuItem(
                    category_id=category.id,
                    meal_id=meal.id,
                    price_override=None,
                    display_order=None
                )
                db.session.add(menu_item)
                
                created_meals += 1
                created_links += 1
                print(f"   ✅ Created: {meal_data['name']} - {meal_data['price']} SAR")
        
        # Commit all changes
        if created_meals > 0:
            db.session.commit()
            print(f"\n🎉 Successfully created {created_meals} meals and {created_links} category links!")
        else:
            print("\n✅ All sample meals already exist!")
        
        return created_meals

def test_categories_coverage():
    """Test how many categories now have meals"""
    
    with app.app_context():
        print("\n📊 Testing category coverage...")
        
        categories = MenuCategory.query.all()
        categories_with_meals = 0
        total_meals = 0
        
        for category in categories:
            meal_count = MenuItem.query.filter_by(category_id=category.id).count()
            if meal_count > 0:
                categories_with_meals += 1
                total_meals += meal_count
                print(f"   ✅ {category.name}: {meal_count} meals")
            else:
                print(f"   ❌ {category.name}: 0 meals")
        
        print(f"\n📈 Coverage Summary:")
        print(f"   - Categories with meals: {categories_with_meals}/{len(categories)}")
        print(f"   - Coverage percentage: {(categories_with_meals/len(categories)*100):.1f}%")
        print(f"   - Total meals available: {total_meals}")
        
        if categories_with_meals >= len(categories) * 0.8:  # 80% coverage
            print("✅ Excellent coverage! POS system should work great!")
        elif categories_with_meals >= len(categories) * 0.5:  # 50% coverage
            print("⚠️  Good coverage, but some categories are still empty.")
        else:
            print("❌ Poor coverage. Many categories are empty.")

def main():
    """Main function"""
    print("🚀 Adding Sample Meals for POS Categories\n")
    
    # Step 1: Create sample meals
    created_count = create_sample_meals()
    
    # Step 2: Test coverage
    test_categories_coverage()
    
    # Step 3: Final instructions
    print(f"\n🎯 Next Steps:")
    print("✅ 1. Test POS system at http://localhost:5000/sales/china_town")
    print("✅ 2. Click on different categories to see their meals")
    print("✅ 3. Add items to cart and test checkout process")
    print("🚀 4. Deploy to Render when satisfied with local testing")
    print("📝 5. Use /menu interface to add more real meals and organize categories")

if __name__ == '__main__':
    main()
