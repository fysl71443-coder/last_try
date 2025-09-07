#!/usr/bin/env python3
"""
Check Render database directly using SQL commands
"""

import os
import psycopg2
from urllib.parse import urlparse

def connect_to_render_db():
    """Connect to Render PostgreSQL database"""
    # Render database URL format: postgresql://user:password@host:port/database
    database_url = "postgresql://china_town_system_user:password@dpg-ct8ej5pu0jms73e8kcog-a.oregon-postgres.render.com/china_town_system"
    
    try:
        # Parse the URL
        parsed = urlparse(database_url)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password
        )
        
        print("✅ Connected to Render database successfully!")
        return conn
    
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return None

def check_tables(conn):
    """Check what tables exist"""
    try:
        cursor = conn.cursor()
        
        # List all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"\n📋 Tables found ({len(tables)}):")
        for table in tables:
            print(f"   - {table[0]}")
        
        cursor.close()
        return [table[0] for table in tables]
    
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return []

def check_categories(conn):
    """Check categories table"""
    try:
        cursor = conn.cursor()
        
        # Check if categories table exists and get data
        cursor.execute("SELECT id, name, status FROM categories ORDER BY id;")
        categories = cursor.fetchall()
        
        print(f"\n📂 Categories table ({len(categories)} rows):")
        for cat in categories:
            print(f"   {cat[0]:2d}. {cat[1]} ({cat[2]})")
        
        cursor.close()
        return categories
    
    except Exception as e:
        print(f"❌ Error checking categories: {e}")
        return []

def check_items(conn):
    """Check items table"""
    try:
        cursor = conn.cursor()
        
        # Check if items table exists and get data
        cursor.execute("SELECT id, name, price, category_id, status FROM items ORDER BY category_id, id;")
        items = cursor.fetchall()
        
        print(f"\n🍽️ Items table ({len(items)} rows):")
        
        # Group by category
        current_category = None
        for item in items:
            if item[3] != current_category:
                current_category = item[3]
                print(f"\n   Category {current_category}:")
            
            print(f"      {item[0]:2d}. {item[1]} - ${item[2]} ({item[4]})")
        
        cursor.close()
        return items
    
    except Exception as e:
        print(f"❌ Error checking items: {e}")
        return []

def check_api_readiness(categories, items):
    """Check if data is ready for API"""
    print(f"\n🎯 API Readiness Check:")
    print(f"   Categories: {len(categories)}")
    print(f"   Items: {len(items)}")
    
    # Count items per category
    category_items = {}
    for item in items:
        cat_id = item[3]
        if cat_id not in category_items:
            category_items[cat_id] = 0
        category_items[cat_id] += 1
    
    categories_with_items = len(category_items)
    print(f"   Categories with items: {categories_with_items}")
    
    if categories_with_items > 0:
        print("   ✅ Ready for POS system!")
    else:
        print("   ❌ Need to add items to categories")
    
    return categories_with_items > 0

def main():
    print("🔍 Checking Render Database...")
    print("=" * 50)
    
    # Connect to database
    conn = connect_to_render_db()
    if not conn:
        return
    
    try:
        # Check tables
        tables = check_tables(conn)
        
        # Check categories
        categories = []
        if 'categories' in tables:
            categories = check_categories(conn)
        else:
            print("❌ Categories table not found!")
        
        # Check items
        items = []
        if 'items' in tables:
            items = check_items(conn)
        else:
            print("❌ Items table not found!")
        
        # Check API readiness
        check_api_readiness(categories, items)
        
    finally:
        conn.close()
        print("\n✅ Database connection closed")

if __name__ == '__main__':
    main()
