#!/usr/bin/env python3

import requests
import json

def debug_tables_page():
    """Debug why sections don't appear on tables page"""
    
    session = requests.Session()
    
    # Login
    login_data = {'username': 'admin', 'password': 'admin123'}
    session.post("http://127.0.0.1:5000/login", data=login_data)
    
    print("🔍 Debugging tables page...")
    
    # Get tables page for china_town
    response = session.get("http://127.0.0.1:5000/sales/china_town/tables")
    print(f"Tables page status: {response.status_code}")
    
    # Check if we can access the API directly
    api_response = session.get("http://127.0.0.1:5000/api/tables/china_town")
    print(f"API tables status: {api_response.status_code}")
    
    if api_response.status_code == 200:
        try:
            api_data = api_response.json()
            print(f"API returned {len(api_data.get('tables', []))} tables")
        except:
            print("API response is not JSON")
    
    # Check the actual template content
    content = response.text
    
    # Look for key indicators
    print("\n📋 Analyzing page content:")
    print(f"Contains 'grouped_tables': {'grouped_tables' in content}")
    print(f"Contains 'sections': {'sections' in content}")
    print(f"Contains 'القسم الأول': {'القسم الأول' in content}")
    print(f"Contains 'Table 1': {'Table 1' in content}")
    
    # Save content to file for inspection
    with open('tables_page_content.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("\n💾 Page content saved to tables_page_content.html")
    
    # Check what the sales_tables route is actually returning
    print("\n🔍 Checking route data...")
    
    # Let's also check the database directly
    import sqlite3
    conn = sqlite3.connect('accounting_app.db')
    cursor = conn.cursor()
    
    print("\n🗄️ Database check:")
    cursor.execute("SELECT COUNT(*) FROM table_section WHERE branch_code = 'china_town'")
    sections_count = cursor.fetchone()[0]
    print(f"Table sections in DB: {sections_count}")
    
    cursor.execute("SELECT COUNT(*) FROM table_section_assignment WHERE branch_code = 'china_town'")
    assignments_count = cursor.fetchone()[0]
    print(f"Table assignments in DB: {assignments_count}")
    
    if sections_count > 0:
        cursor.execute("SELECT id, name, sort_order FROM table_section WHERE branch_code = 'china_town'")
        sections = cursor.fetchall()
        print("Sections in DB:")
        for section in sections:
            print(f"  ID: {section[0]}, Name: {section[1]}, Sort: {section[2]}")
    
    if assignments_count > 0:
        cursor.execute("SELECT table_number, section_id FROM table_section_assignment WHERE branch_code = 'china_town' LIMIT 5")
        assignments = cursor.fetchall()
        print("Sample assignments in DB:")
        for assignment in assignments:
            print(f"  Table: {assignment[0]} -> Section: {assignment[1]}")
    
    conn.close()

if __name__ == "__main__":
    debug_tables_page()












