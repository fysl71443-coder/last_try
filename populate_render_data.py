#!/usr/bin/env python3
"""
Populate Render database with categories and items
"""

import os
import psycopg2
from urllib.parse import urlparse

def connect_to_render_db():
    """Connect to Render PostgreSQL database"""
    database_url = "postgresql://china_town_system_user:password@dpg-ct8ej5pu0jms73e8kcog-a.oregon-postgres.render.com/china_town_system"
    
    try:
        parsed = urlparse(database_url)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        
        print("✅ Connected to Render database successfully!")
        return conn
    
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return None

def create_categories(conn):
    """Create categories in Render database"""
    categories_data = [
        "Appetizers", "Beef & Lamb", "Charcoal Grill / Kebabs", "Chicken",
        "Chinese Sizzling", "Duck", "House Special", "Indian Delicacy (Chicken)",
        "Indian Delicacy (Fish)", "Indian Delicacy (Vegetables)", "Juices",
        "Noodles & Chopsuey", "Prawns", "Rice & Biryani", "Salads",
        "Seafoods", "Shaw Faw", "Soft Drink", "Soups", "spring rolls", "دجاج"
    ]
    
    try:
        cursor = conn.cursor()
        
        print("📂 Creating categories...")
        created_count = 0
        
        for cat_name in categories_data:
            # Check if category already exists
            cursor.execute("SELECT id FROM categories WHERE name = %s", (cat_name,))
            existing = cursor.fetchone()
            
            if not existing:
                cursor.execute("""
                    INSERT INTO categories (name, status, created_at) 
                    VALUES (%s, 'Active', NOW())
                """, (cat_name,))
                created_count += 1
                print(f"   ✅ Created: {cat_name}")
            else:
                print(f"   ⚠️  Already exists: {cat_name}")
        
        conn.commit()
        cursor.close()
        
        print(f"📊 Created {created_count} new categories")
        return created_count
    
    except Exception as e:
        print(f"❌ Error creating categories: {e}")
        conn.rollback()
        return 0

def create_items(conn):
    """Create items in Render database"""
    
    # Sample items for each category
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
    
    try:
        cursor = conn.cursor()
        
        print("🍽️ Creating items...")
        created_count = 0
        
        # Get category IDs
        cursor.execute("SELECT id, name FROM categories")
        categories = {name: cat_id for cat_id, name in cursor.fetchall()}
        
        for item_data in items_data:
            category_name = item_data["category"]
            
            if category_name not in categories:
                print(f"   ⚠️  Category not found: {category_name}")
                continue
            
            category_id = categories[category_name]
            
            # Check if item already exists
            cursor.execute("SELECT id FROM items WHERE name = %s", (item_data["name"],))
            existing = cursor.fetchone()
            
            if not existing:
                cursor.execute("""
                    INSERT INTO items (name, price, category_id, status, created_at) 
                    VALUES (%s, %s, %s, 'Active', NOW())
                """, (item_data["name"], item_data["price"], category_id))
                created_count += 1
                print(f"   ✅ Created: {item_data['name']} - ${item_data['price']} ({category_name})")
            else:
                print(f"   ⚠️  Already exists: {item_data['name']}")
        
        conn.commit()
        cursor.close()
        
        print(f"📊 Created {created_count} new items")
        return created_count
    
    except Exception as e:
        print(f"❌ Error creating items: {e}")
        conn.rollback()
        return 0

def verify_data(conn):
    """Verify the data was created correctly"""
    try:
        cursor = conn.cursor()
        
        # Count categories
        cursor.execute("SELECT COUNT(*) FROM categories WHERE status = 'Active'")
        cat_count = cursor.fetchone()[0]
        
        # Count items
        cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'Active'")
        item_count = cursor.fetchone()[0]
        
        # Count categories with items
        cursor.execute("""
            SELECT COUNT(DISTINCT category_id) 
            FROM items 
            WHERE status = 'Active'
        """)
        cats_with_items = cursor.fetchone()[0]
        
        cursor.close()
        
        print(f"\n📊 Verification Results:")
        print(f"   Categories: {cat_count}")
        print(f"   Items: {item_count}")
        print(f"   Categories with items: {cats_with_items}")
        
        if cats_with_items > 0:
            print("   ✅ Data ready for POS API!")
        else:
            print("   ❌ No items found")
        
        return cats_with_items > 0
    
    except Exception as e:
        print(f"❌ Error verifying data: {e}")
        return False

def main():
    print("🚀 Populating Render Database...")
    print("=" * 50)
    
    # Connect to database
    conn = connect_to_render_db()
    if not conn:
        return
    
    try:
        # Create categories
        cat_count = create_categories(conn)
        
        # Create items
        item_count = create_items(conn)
        
        # Verify data
        success = verify_data(conn)
        
        if success:
            print("\n🎉 Database populated successfully!")
            print("🌐 API endpoints should now work:")
            print("   - GET /api/categories")
            print("   - GET /api/items?category_id=1")
        else:
            print("\n❌ Database population failed")
    
    finally:
        conn.close()
        print("\n✅ Database connection closed")

if __name__ == '__main__':
    main()
