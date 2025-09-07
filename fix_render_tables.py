#!/usr/bin/env python3
"""
Direct fix for Render database - create tables and populate data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def create_tables_and_data():
    """Create categories and items tables with data"""
    with app.app_context():
        try:
            print("🔧 Creating categories and items tables...")
            
            # Create categories table
            db.engine.execute(text("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    status VARCHAR(50) DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create items table
            db.engine.execute(text("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    price NUMERIC(10,2) NOT NULL,
                    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                    status VARCHAR(50) DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            print("✅ Tables created successfully")
            
            # Check if data already exists
            result = db.engine.execute(text("SELECT COUNT(*) FROM categories"))
            count = result.fetchone()[0]
            
            if count > 0:
                print(f"⚠️ Categories already exist ({count} found)")
                return
            
            print("📊 Inserting sample data...")
            
            # Insert categories
            categories = [
                "Appetizers", "Beef & Lamb", "Charcoal Grill / Kebabs", "Chicken",
                "Chinese Sizzling", "Duck", "House Special", "Indian Delicacy (Chicken)",
                "Indian Delicacy (Fish)", "Indian Delicacy (Vegetables)", "Juices",
                "Noodles & Chopsuey", "Prawns", "Rice & Biryani", "Salads",
                "Seafoods", "Shaw Faw", "Soft Drink", "Soups", "spring rolls", "دجاج"
            ]
            
            for cat_name in categories:
                db.engine.execute(text(
                    "INSERT INTO categories (name, status, created_at) VALUES (:name, 'Active', CURRENT_TIMESTAMP)"
                ), {"name": cat_name})
            
            # Insert items
            items_data = [
                # Appetizers (category_id = 1)
                ("Spring Rolls", 15.00, 1),
                ("Chicken Samosa", 12.00, 1),
                ("Vegetable Pakora", 18.00, 1),
                
                # Beef & Lamb (category_id = 2)
                ("Beef Curry", 45.00, 2),
                ("Lamb Biryani", 50.00, 2),
                ("Grilled Lamb Chops", 65.00, 2),
                
                # Charcoal Grill / Kebabs (category_id = 3)
                ("Chicken Tikka", 35.00, 3),
                ("Seekh Kebab", 40.00, 3),
                ("Mixed Grill", 55.00, 3),
                
                # Chicken (category_id = 4)
                ("Butter Chicken", 38.00, 4),
                ("Chicken Curry", 35.00, 4),
                ("Chicken Biryani", 42.00, 4),
                
                # Chinese Sizzling (category_id = 5)
                ("Sizzling Chicken", 45.00, 5),
                ("Sweet & Sour Chicken", 40.00, 5),
                ("Kung Pao Chicken", 42.00, 5),
                
                # House Special (category_id = 7)
                ("Chef's Special Platter", 60.00, 7),
                ("Mixed Seafood Special", 75.00, 7),
                ("Vegetarian Delight", 35.00, 7),
                
                # Juices (category_id = 11)
                ("Fresh Orange Juice", 12.00, 11),
                ("Mango Juice", 15.00, 11),
                ("Apple Juice", 10.00, 11),
                ("Mixed Fruit Juice", 18.00, 11),
                
                # Rice & Biryani (category_id = 14)
                ("Plain Rice", 15.00, 14),
                ("Vegetable Biryani", 35.00, 14),
                ("Mutton Biryani", 55.00, 14),
                
                # Soft Drink (category_id = 18)
                ("Coca Cola", 8.00, 18),
                ("Pepsi", 8.00, 18),
                ("Fresh Lime", 10.00, 18),
            ]
            
            for item_name, price, cat_id in items_data:
                db.engine.execute(text(
                    "INSERT INTO items (name, price, category_id, status, created_at) VALUES (:name, :price, :cat_id, 'Active', CURRENT_TIMESTAMP)"
                ), {"name": item_name, "price": price, "cat_id": cat_id})
            
            print(f"✅ Inserted {len(categories)} categories and {len(items_data)} items")
            
            # Verify data
            cat_result = db.engine.execute(text("SELECT COUNT(*) FROM categories"))
            item_result = db.engine.execute(text("SELECT COUNT(*) FROM items"))
            
            cat_count = cat_result.fetchone()[0]
            item_count = item_result.fetchone()[0]
            
            print(f"📊 Verification:")
            print(f"   Categories: {cat_count}")
            print(f"   Items: {item_count}")
            
            if cat_count > 0 and item_count > 0:
                print("🎉 SUCCESS! POS system is now ready!")
                print("🌐 API endpoints should work:")
                print("   - GET /api/categories")
                print("   - GET /api/items?category_id=1")
            else:
                print("❌ Something went wrong")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

def test_api_locally():
    """Test the API endpoints locally"""
    with app.app_context():
        try:
            from models import Category, Item
            
            print("\n🧪 Testing API locally...")
            
            # Test categories
            categories = Category.query.filter_by(status='Active').all()
            print(f"✅ Categories API would return: {len(categories)} categories")
            
            if categories:
                # Test items for first category
                first_cat = categories[0]
                items = Item.query.filter_by(category_id=first_cat.id, status='Active').all()
                print(f"✅ Items API would return: {len(items)} items for '{first_cat.name}'")
                
                # Show sample data
                print(f"\n📋 Sample data:")
                for i, cat in enumerate(categories[:5], 1):
                    cat_items = Item.query.filter_by(category_id=cat.id, status='Active').all()
                    print(f"   {i}. {cat.name} ({len(cat_items)} items)")
                    for item in cat_items[:2]:
                        print(f"      • {item.name} - {item.price} SAR")
            
        except Exception as e:
            print(f"❌ API test failed: {e}")

if __name__ == "__main__":
    print("🚀 Fixing Render Database...")
    print("=" * 50)
    
    create_tables_and_data()
    test_api_locally()
    
    print("\n✅ Fix completed!")
    print("\n💡 Next steps:")
    print("1. Deploy this script to Render")
    print("2. Run it once to create tables and data")
    print("3. Test POS interface")
