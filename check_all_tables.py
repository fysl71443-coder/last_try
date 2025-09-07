#!/usr/bin/env python3
"""
Check all tables that might contain product/meal data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Product, Meal, MenuCategory, MenuItem

def check_all_tables():
    """Check all tables for product/meal data"""
    with app.app_context():
        print("🔍 Checking All Tables for Product/Meal Data\n")
        
        # Check Product table
        try:
            products = Product.query.all()
            active_products = Product.query.filter_by(active=True).all()
            print(f"📦 Products Table: {len(products)} total ({len(active_products)} active)")
            
            if len(products) > 0:
                print("   First 5 products:")
                for product in products[:5]:
                    status = "✅" if product.active else "❌"
                    print(f"      {status} {product.display_name}: {product.price_before_tax} SAR (category: {product.category})")
                
                # Group by category
                product_categories = {}
                for product in products:
                    cat = product.category or "No Category"
                    if cat not in product_categories:
                        product_categories[cat] = 0
                    product_categories[cat] += 1
                
                print("   Products by category:")
                for cat, count in sorted(product_categories.items()):
                    print(f"      📂 {cat}: {count} products")
        except Exception as e:
            print(f"❌ Error checking Products table: {e}")
        
        print()
        
        # Check Meal table
        try:
            meals = Meal.query.all()
            active_meals = Meal.query.filter_by(active=True).all()
            print(f"🥘 Meals Table: {len(meals)} total ({len(active_meals)} active)")
            
            if len(meals) > 0:
                print("   First 5 meals:")
                for meal in meals[:5]:
                    status = "✅" if meal.active else "❌"
                    print(f"      {status} {meal.display_name}: {meal.selling_price} SAR (category: {meal.category})")
        except Exception as e:
            print(f"❌ Error checking Meals table: {e}")
        
        print()
        
        # Check MenuCategory table
        try:
            categories = MenuCategory.query.all()
            active_categories = MenuCategory.query.filter_by(active=True).all()
            print(f"📋 MenuCategory Table: {len(categories)} total ({len(active_categories)} active)")
            
            if len(categories) > 0:
                print("   Categories:")
                for cat in categories:
                    status = "✅" if cat.active else "❌"
                    print(f"      {status} {cat.name}")
        except Exception as e:
            print(f"❌ Error checking MenuCategory table: {e}")
        
        print()
        
        # Check MenuItem table
        try:
            menu_items = MenuItem.query.all()
            print(f"🍽️ MenuItem Table: {len(menu_items)} items")
            
            if len(menu_items) > 0:
                print("   First 5 menu items:")
                for item in menu_items[:5]:
                    meal_name = item.meal.display_name if item.meal else "No Meal"
                    cat_name = item.category.name if item.category else "No Category"
                    price = item.price_override if item.price_override else (item.meal.selling_price if item.meal else 0)
                    print(f"      - {meal_name} in {cat_name}: {price} SAR")
        except Exception as e:
            print(f"❌ Error checking MenuItem table: {e}")
        
        print("\n" + "="*60)
        print("📊 Summary:")
        
        try:
            product_count = Product.query.count()
            meal_count = Meal.query.count()
            category_count = MenuCategory.query.count()
            menu_item_count = MenuItem.query.count()
            
            print(f"   📦 Products: {product_count}")
            print(f"   🥘 Meals: {meal_count}")
            print(f"   📋 Categories: {category_count}")
            print(f"   🍽️ Menu Items: {menu_item_count}")
            
            total_items = product_count + meal_count
            print(f"\n🎯 Total Items Available: {total_items}")
            
            if total_items >= 200:
                print(f"   ✅ Found {total_items} items! This might be where your 204 items are.")
            elif product_count > 0:
                print(f"   💡 Found {product_count} products in Product table.")
                print("   These might need to be converted to Meals and linked to MenuItems.")
            else:
                print("   ⚠️ No significant data found. You might need to import your menu data.")
                
        except Exception as e:
            print(f"❌ Error getting summary: {e}")

if __name__ == '__main__':
    check_all_tables()
