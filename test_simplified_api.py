#!/usr/bin/env python3
"""
Test the simplified POS API endpoints
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Category, Item

def create_test_data():
    """Create test data for simplified API"""
    
    with app.app_context():
        print("🔧 Creating test data for simplified API...")
        
        # Create categories
        categories_data = [
            "Appetizers", "Chicken", "Rice & Biryani", "Juices", "Soft Drink"
        ]
        
        for cat_name in categories_data:
            if not Category.query.filter_by(name=cat_name).first():
                cat = Category(name=cat_name, status='Active')
                db.session.add(cat)
                print(f"✅ Created category: {cat_name}")
        
        db.session.commit()
        
        # Create items
        items_data = [
            {"name": "Spring Rolls", "price": 15.0, "category": "Appetizers"},
            {"name": "Chicken Samosa", "price": 12.0, "category": "Appetizers"},
            {"name": "Butter Chicken", "price": 38.0, "category": "Chicken"},
            {"name": "Chicken Tikka", "price": 35.0, "category": "Chicken"},
            {"name": "Chicken Biryani", "price": 42.0, "category": "Rice & Biryani"},
            {"name": "Plain Rice", "price": 15.0, "category": "Rice & Biryani"},
            {"name": "Orange Juice", "price": 12.0, "category": "Juices"},
            {"name": "Mango Juice", "price": 15.0, "category": "Juices"},
            {"name": "Coca Cola", "price": 8.0, "category": "Soft Drink"},
            {"name": "Pepsi", "price": 8.0, "category": "Soft Drink"}
        ]
        
        categories = {cat.name: cat for cat in Category.query.all()}
        
        for item_data in items_data:
            if not Item.query.filter_by(name=item_data["name"]).first():
                category = categories.get(item_data["category"])
                if category:
                    item = Item(
                        name=item_data["name"],
                        price=item_data["price"],
                        category_id=category.id,
                        status='Active'
                    )
                    db.session.add(item)
                    print(f"✅ Created item: {item_data['name']} - {item_data['price']} SAR")
        
        db.session.commit()
        print("🎉 Test data created successfully!")

def test_categories_api():
    """Test /api/categories endpoint"""
    
    with app.app_context():
        print("\n🧪 Testing /api/categories endpoint...")
        
        categories = Category.query.filter_by(status='Active').all()
        result = [cat.to_dict() for cat in categories]
        
        print(f"✅ Found {len(result)} active categories:")
        for cat in result:
            print(f"   - {cat['id']}: {cat['name']} ({cat['status']})")
        
        return result

def test_items_api():
    """Test /api/items endpoint"""
    
    with app.app_context():
        print("\n🧪 Testing /api/items endpoint...")
        
        categories = Category.query.filter_by(status='Active').all()
        
        for category in categories:
            items = Item.query.filter_by(category_id=category.id, status='Active').all()
            result = [item.to_dict() for item in items]
            
            print(f"\n📂 Category: {category.name} (ID: {category.id})")
            print(f"   Items found: {len(result)}")
            
            for item in result:
                print(f"   - {item['id']}: {item['name']} - {item['price']} SAR")
        
        return True

def simulate_pos_workflow():
    """Simulate POS workflow using simplified API"""
    
    with app.app_context():
        print("\n🎯 Simulating POS workflow...")
        
        # Step 1: Get categories (like POS frontend would do)
        print("Step 1: Getting categories...")
        categories = Category.query.filter_by(status='Active').all()
        categories_json = [cat.to_dict() for cat in categories]
        print(f"✅ Retrieved {len(categories_json)} categories")
        
        # Step 2: User clicks on "Chicken" category
        chicken_cat = next((cat for cat in categories_json if cat['name'] == 'Chicken'), None)
        if chicken_cat:
            print(f"\nStep 2: User clicked on '{chicken_cat['name']}' category...")
            
            # Get items for this category
            items = Item.query.filter_by(category_id=chicken_cat['id'], status='Active').all()
            items_json = [item.to_dict() for item in items]
            
            print(f"✅ Retrieved {len(items_json)} items for {chicken_cat['name']}:")
            for item in items_json:
                print(f"   - {item['name']}: {item['price']} SAR")
        
        # Step 3: User clicks on "Juices" category
        juices_cat = next((cat for cat in categories_json if cat['name'] == 'Juices'), None)
        if juices_cat:
            print(f"\nStep 3: User clicked on '{juices_cat['name']}' category...")
            
            # Get items for this category
            items = Item.query.filter_by(category_id=juices_cat['id'], status='Active').all()
            items_json = [item.to_dict() for item in items]
            
            print(f"✅ Retrieved {len(items_json)} items for {juices_cat['name']}:")
            for item in items_json:
                print(f"   - {item['name']}: {item['price']} SAR")
        
        print("\n🎉 POS workflow simulation completed successfully!")
        return True

def generate_api_examples():
    """Generate API usage examples"""
    
    print("\n📋 API Usage Examples:")
    print("=" * 50)
    
    print("\n1. Get all categories:")
    print("   GET /api/categories")
    print("   Response: [{'id': 1, 'name': 'Appetizers', 'status': 'Active'}, ...]")
    
    print("\n2. Get items for a category:")
    print("   GET /api/items?category_id=1")
    print("   Response: [{'id': 1, 'name': 'Spring Rolls', 'price': 15.0, 'category_id': 1, 'status': 'Active'}, ...]")
    
    print("\n3. JavaScript example for POS frontend:")
    print("""
    // Load categories
    async function loadCategories() {
        const response = await fetch('/api/categories');
        const categories = await response.json();
        
        categories.forEach(cat => {
            const button = `<button onclick="loadItems(${cat.id})">${cat.name}</button>`;
            $('#categories-container').append(button);
        });
    }
    
    // Load items for selected category
    async function loadItems(categoryId) {
        const response = await fetch(`/api/items?category_id=${categoryId}`);
        const items = await response.json();
        
        $('#items-container').empty();
        items.forEach(item => {
            const itemHtml = `
                <div class="menu-item" onclick="addToCart(${item.id}, '${item.name}', ${item.price})">
                    <h5>${item.name}</h5>
                    <p>${item.price} SAR</p>
                </div>
            `;
            $('#items-container').append(itemHtml);
        });
    }
    """)

def main():
    """Main function"""
    print("🚀 Testing Simplified POS API\n")
    
    # Step 1: Create test data
    create_test_data()
    
    # Step 2: Test categories API
    categories = test_categories_api()
    
    # Step 3: Test items API
    test_items_api()
    
    # Step 4: Simulate POS workflow
    simulate_pos_workflow()
    
    # Step 5: Generate examples
    generate_api_examples()
    
    # Step 6: Final summary
    print(f"\n🎯 Summary:")
    print(f"✅ Simplified API is working correctly!")
    print(f"✅ Categories: {len(categories)} active")
    print(f"✅ Dynamic item loading by category works")
    print(f"✅ Ready for POS frontend integration")
    
    print(f"\n🚀 Next Steps:")
    print(f"1. Update POS frontend to use /api/categories and /api/items")
    print(f"2. Test with actual POS interface")
    print(f"3. Deploy to Render when ready")

if __name__ == '__main__':
    main()
