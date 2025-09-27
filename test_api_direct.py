#!/usr/bin/env python3

import requests
import json

def test_api_direct():
    """Test the API endpoint directly"""
    
    session = requests.Session()
    
    # Login
    login_data = {'username': 'admin', 'password': 'admin123'}
    session.post("http://127.0.0.1:5000/login", data=login_data)
    
    print("🔍 Testing API endpoint directly...")
    
    # Test data
    test_data = {
        "sections": [
            {
                "id": "section_1",
                "name": "Test Section",
                "rows": [
                    {
                        "id": "row_1",
                        "tables": [
                            {"id": "table_1", "number": 1, "seats": 4},
                            {"id": "table_2", "number": 2, "seats": 4}
                        ]
                    }
                ]
            }
        ]
    }
    
    # Try to save
    print("📝 Attempting to save layout...")
    response = session.post(
        "http://127.0.0.1:5000/api/table-layout/china_town",
        json=test_data,
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response text: {response.text}")
    
    if response.status_code == 200:
        print("✅ Save successful")
        
        # Try to load
        print("\n📖 Attempting to load layout...")
        load_response = session.get("http://127.0.0.1:5000/api/table-layout/china_town")
        print(f"Load response status: {load_response.status_code}")
        print(f"Load response text: {load_response.text}")
        
        if load_response.status_code == 200:
            try:
                data = load_response.json()
                print(f"Loaded data: {json.dumps(data, indent=2, ensure_ascii=False)}")
            except:
                print("Could not parse JSON response")
    
    # Check database directly
    print("\n🗄️ Checking database...")
    import sqlite3
    conn = sqlite3.connect('accounting_app.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM table_sections WHERE branch_code = 'china_town'")
    count = cursor.fetchone()[0]
    print(f"Table sections count: {count}")
    
    if count > 0:
        cursor.execute("SELECT * FROM table_sections WHERE branch_code = 'china_town'")
        sections = cursor.fetchall()
        print("Sections in database:")
        for section in sections:
            print(f"  {section}")
    
    conn.close()

if __name__ == "__main__":
    test_api_direct()
