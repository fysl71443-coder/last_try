#!/usr/bin/env python3

import requests
import json
import time
import os

# Determine the correct SQLite path (matches app configuration)
DEFAULT_SQLITE_PATH = os.path.join('instance', 'accounting_app.db')
LOCAL_DB_PATH = os.getenv('LOCAL_SQLITE_PATH', DEFAULT_SQLITE_PATH)

# Configuration
BASE_URL = "http://127.0.0.1:5000"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """Login and get session"""
    session = requests.Session()

    # Ensure a fresh session each run and simulate browser redirect
    session.headers.update({'User-Agent': 'TableLayoutTest/1.0'})
    # follow redirects to landing page -> login
    response = session.get(f"{BASE_URL}/", allow_redirects=True)
    print(f"Login page status: {response.status_code}")
    if response.history:
        print("  Redirect history:", ' -> '.join(str(r.status_code) for r in response.history))

    # obtain CSRF token from login form if present
    csrf_token = None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        token_input = soup.find('input', {'name': 'csrf_token'})
        if token_input:
            csrf_token = token_input.get('value')
            print("  ✓ CSRF token extracted")
    except Exception as e:
        print(f"  ⚠️ Failed to parse CSRF token: {e}")

    login_data = {
        'username': USERNAME,
        'password': PASSWORD,
    }
    if csrf_token:
        login_data['csrf_token'] = csrf_token

    response = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=False)
    print(f"Login response status: {response.status_code}")
    if response.status_code == 302:
        redirect_target = response.headers.get('Location')
        print(f"  Redirecting to: {redirect_target}")
        # follow redirect to confirm session
        session.get(f"{BASE_URL}{redirect_target}")
    elif response.status_code != 200:
        print("❌ Login failed")
        return None

    # Verify session cookie set
    if not session.cookies:
        print("❌ Session cookies missing after login")
        return None

    print("✅ Login successful")
    return session

def create_test_sections(session, branch_code):
    """Create test sections for a branch"""
    print(f"\n🔧 Creating test sections for {branch_code}")
    
    # Test data - create 2 sections with different layouts
    test_sections = {
        "sections": [
            {
                "id": "section_1",
                "name": "القسم الأول",
                "rows": [
                    {
                        "id": "row_1",
                        "tables": [
                            {"id": "table_1", "number": 1, "seats": 4},
                            {"id": "table_2", "number": 2, "seats": 4},
                            {"id": "table_3", "number": 3, "seats": 4}
                        ]
                    },
                    {
                        "id": "row_2", 
                        "tables": [
                            {"id": "table_4", "number": 4, "seats": 4},
                            {"id": "table_5", "number": 5, "seats": 4}
                        ]
                    }
                ]
            },
            {
                "id": "section_2",
                "name": "القسم الثاني",
                "rows": [
                    {
                        "id": "row_3",
                        "tables": [
                            {"id": "table_6", "number": 6, "seats": 6},
                            {"id": "table_7", "number": 7, "seats": 6},
                            {"id": "table_8", "number": 8, "seats": 6},
                            {"id": "table_9", "number": 9, "seats": 6}
                        ]
                    }
                ]
            }
        ]
    }
    
    # Save layout
    response = session.post(
        f"{BASE_URL}/api/table-layout/{branch_code}",
        json=test_sections,
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"Save layout response status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Layout saved successfully")
        try:
            result = response.json()
            print(f"Response: {result}")
        except:
            print("Response is not JSON")
    else:
        print(f"❌ Failed to save layout: {response.text}")
    
    return response.status_code == 200

def load_layout(session, branch_code):
    """Load and verify the saved layout"""
    print(f"\n📖 Loading layout for {branch_code}")
    
    response = session.get(f"{BASE_URL}/api/table-layout/{branch_code}")
    print(f"Load layout response status: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print("✅ Layout loaded successfully")
            print(f"Sections count: {len(data.get('sections', []))}")
            
            for i, section in enumerate(data.get('sections', []), 1):
                print(f"  Section {i}: {section.get('name', 'Unnamed')}")
                print(f"    Rows: {len(section.get('rows', []))}")
                total_tables = sum(len(row.get('tables', [])) for row in section.get('rows', []))
                print(f"    Total tables: {total_tables}")
            
            return data
        except Exception as e:
            print(f"❌ Error parsing response: {e}")
            return None
    else:
        print(f"❌ Failed to load layout: {response.text}")
        return None

def test_tables_page(session, branch_code):
    """Test that sections appear on tables page"""
    print(f"\n🪑 Testing tables page for {branch_code}")
    
    response = session.get(f"{BASE_URL}/sales/{branch_code}/tables")
    print(f"Tables page response status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Tables page loaded successfully")

        content = response.text
        keywords = ["القسم الأول", "القسم الثاني", "Test Section"]
        found = any(kw in content for kw in keywords)
        if found:
            print("✅ Sections found in tables page!")
        else:
            print("❌ Sections NOT found in tables page content")
            # Save content for inspection
            out_path = f"tables_page_{branch_code}.html"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved tables page content to {out_path} for debugging")
        return found
    else:
        print(f"❌ Failed to load tables page: {response.text}")
        return False

def main():
    """Run the complete test"""
    print("🚀 Starting Table Sections Test")
    print("=" * 50)
    
    # Login
    session = login()
    if not session:
        print("❌ Cannot proceed without login")
        return
    
    # Test both branches
    branches = ['china_town', 'place_india']
    
    for branch in branches:
        print(f"\n{'='*20} TESTING {branch.upper()} {'='*20}")
        
        # Create sections
        if create_test_sections(session, branch):
            time.sleep(1)
            
            layout_data = load_layout(session, branch)
            if layout_data:
                result = test_tables_page(session, branch)
                if not result:
                    print("❌ Sections not visible on tables page; aborting test.")
                    return
        
        print(f"\n{'='*50}")
    
    print("\n🎉 Test completed!")

    print("\n🗄️ Checking database...")
    import sqlite3
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM table_sections WHERE branch_code = 'china_town'")
    count = cursor.fetchone()[0]
    print(f"Table sections count: {count}")

    if count > 0:
        cursor.execute("SELECT branch_code, name, sort_order FROM table_sections WHERE branch_code = 'china_town'")
        sections = cursor.fetchall()
        print("Sections in database:")
        for section in sections:
            print(f"  {section}")

    conn.close()

if __name__ == "__main__":
    main()
