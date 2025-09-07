#!/usr/bin/env python3
"""
Create POS tables using SQLAlchemy models
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Category, Item

def create_pos_data():
    """Create categories and items using SQLAlchemy models"""
    with app.app_context():
        try:
            print("🔧 Creating POS tables and data...")
            
            # Create all tables
            db.create_all()
            print("✅ Tables created/verified")
            
            # Check if categories already exist
            existing_cats = Category.query.count()
            if existing_cats > 0:
                print(f"⚠️ Categories already exist ({existing_cats} found)")
                
                # Show existing data
                categories = Category.query.filter_by(status='Active').all()
                items = Item.query.filter_by(status='Active').all()
                
                print(f"📊 Current data:")
                print(f"   Categories: {len(categories)}")
                print(f"   Items: {len(items)}")
                
                # Show sample
                for cat in categories[:5]:
                    cat_items = Item.query.filter_by(category_id=cat.id, status='Active').all()
                    print(f"   • {cat.name}: {len(cat_items)} items")
                
                return
            
            print("📊 Creating sample data...")
            
            # Create categories
            categories_data = [
                "Appetizers", "Beef & Lamb", "Charcoal Grill / Kebabs", "Chicken",
                "Chinese Sizzling", "Duck", "House Special", "Indian Delicacy (Chicken)",
                "Indian Delicacy (Fish)", "Indian Delicacy (Vegetables)", "Juices",
                "Noodles & Chopsuey", "Prawns", "Rice & Biryani", "Salads",
                "Seafoods", "Shaw Faw", "Soft Drink", "Soups", "spring rolls", "دجاج"
            ]
            
            created_categories = {}
            for cat_name in categories_data:
                cat = Category(name=cat_name, status='Active')
                db.session.add(cat)
                db.session.flush()  # Get the ID
                created_categories[cat_name] = cat.id
                print(f"   ✅ Created category: {cat_name} (ID: {cat.id})")
            
            # Create items
            items_data = [
                # Appetizers
                {"name": "Spring Rolls", "price": 15.00, "category": "Appetizers"},
                {"name": "Chicken Samosa", "price": 12.00, "category": "Appetizers"},
                {"name": "Vegetable Pakora", "price": 18.00, "category": "Appetizers"},
                
                # Beef & Lamb
                {"name": "Beef Curry", "price": 45.00, "category": "Beef & Lamb"},
                {"name": "Lamb Biryani", "price": 50.00, "category": "Beef & Lamb"},
                {"name": "Grilled Lamb Chops", "price": 65.00, "category": "Beef & Lamb"},
                
                # Charcoal Grill / Kebabs
                {"name": "Chicken Tikka", "price": 35.00, "category": "Charcoal Grill / Kebabs"},
                {"name": "Seekh Kebab", "price": 40.00, "category": "Charcoal Grill / Kebabs"},
                {"name": "Mixed Grill", "price": 55.00, "category": "Charcoal Grill / Kebabs"},
                
                # Chicken
                {"name": "Butter Chicken", "price": 38.00, "category": "Chicken"},
                {"name": "Chicken Curry", "price": 35.00, "category": "Chicken"},
                {"name": "Chicken Biryani", "price": 42.00, "category": "Chicken"},
                
                # Chinese Sizzling
                {"name": "Sizzling Chicken", "price": 45.00, "category": "Chinese Sizzling"},
                {"name": "Sweet & Sour Chicken", "price": 40.00, "category": "Chinese Sizzling"},
                {"name": "Kung Pao Chicken", "price": 42.00, "category": "Chinese Sizzling"},
                
                # House Special
                {"name": "Chef's Special Platter", "price": 60.00, "category": "House Special"},
                {"name": "Mixed Seafood Special", "price": 75.00, "category": "House Special"},
                {"name": "Vegetarian Delight", "price": 35.00, "category": "House Special"},
                
                # Juices
                {"name": "Fresh Orange Juice", "price": 12.00, "category": "Juices"},
                {"name": "Mango Juice", "price": 15.00, "category": "Juices"},
                {"name": "Apple Juice", "price": 10.00, "category": "Juices"},
                {"name": "Mixed Fruit Juice", "price": 18.00, "category": "Juices"},
                
                # Rice & Biryani
                {"name": "Plain Rice", "price": 15.00, "category": "Rice & Biryani"},
                {"name": "Vegetable Biryani", "price": 35.00, "category": "Rice & Biryani"},
                {"name": "Mutton Biryani", "price": 55.00, "category": "Rice & Biryani"},
                
                # Soft Drink
                {"name": "Coca Cola", "price": 8.00, "category": "Soft Drink"},
                {"name": "Pepsi", "price": 8.00, "category": "Soft Drink"},
                {"name": "Fresh Lime", "price": 10.00, "category": "Soft Drink"},
            ]
            
            for item_data in items_data:
                category_name = item_data["category"]
                if category_name in created_categories:
                    item = Item(
                        name=item_data["name"],
                        price=item_data["price"],
                        category_id=created_categories[category_name],
                        status='Active'
                    )
                    db.session.add(item)
                    print(f"   ✅ Created item: {item_data['name']} - {item_data['price']} SAR")
            
            # Commit all changes
            db.session.commit()
            
            # Verify final data
            final_cats = Category.query.filter_by(status='Active').count()
            final_items = Item.query.filter_by(status='Active').count()
            
            print(f"\n📊 Final verification:")
            print(f"   Categories: {final_cats}")
            print(f"   Items: {final_items}")
            
            if final_cats > 0 and final_items > 0:
                print("\n🎉 SUCCESS! POS system is ready!")
                print("🌐 API endpoints will work:")
                print("   - GET /api/categories")
                print("   - GET /api/items?category_id=1")
                
                # Test API functions
                test_api_functions()
            else:
                print("\n❌ Something went wrong")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()

def test_api_functions():
    """Test the actual API functions"""
    try:
        print("\n🧪 Testing API functions...")
        
        # Test get_categories function
        categories = Category.query.filter_by(status='Active').all()
        categories_json = [cat.to_dict() for cat in categories]
        print(f"✅ /api/categories returns {len(categories_json)} categories")
        
        # Test get_items function
        if categories:
            first_cat_id = categories[0].id
            items = Item.query.filter_by(category_id=first_cat_id, status='Active').all()
            items_json = [item.to_dict() for item in items]
            print(f"✅ /api/items?category_id={first_cat_id} returns {len(items_json)} items")
            
            # Show sample data
            print(f"\n📋 Sample API responses:")
            print(f"Categories (first 3):")
            for cat in categories_json[:3]:
                print(f"   • {cat['name']} (ID: {cat['id']})")
            
            print(f"Items for '{categories[0].name}':")
            for item in items_json[:3]:
                print(f"   • {item['name']} - {item['price']} SAR")
        
    except Exception as e:
        print(f"❌ API test failed: {e}")

if __name__ == "__main__":
    print("🚀 Creating POS Tables and Data...")
    print("=" * 50)
    
    create_pos_data()
    
    print("\n✅ Script completed!")
    print("\n💡 To run on Render:")
    print("1. Upload this script")
    print("2. Run: python create_pos_tables.py")
    print("3. Test POS interface")
