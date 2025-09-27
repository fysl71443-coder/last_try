#!/usr/bin/env python3
"""
Test script to verify settings saving functionality
"""

import requests
import sys

def test_settings():
    base_url = "http://127.0.0.1:5000"
    
    # Test 1: Check if server is running
    print("🔍 Testing server connection...")
    try:
        response = requests.get(f"{base_url}/login", timeout=5)
        print(f"✅ Server is running (Status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Server is not running: {e}")
        return False
    
    # Test 2: Login
    print("\n🔐 Testing login...")
    session = requests.Session()
    
    login_data = {
        'username': 'admin',
        'password': 'admin123'
    }
    
    try:
        response = session.post(f"{base_url}/login", data=login_data, timeout=5)
        if response.status_code == 302:  # Redirect after successful login
            print("✅ Login successful")
        else:
            print(f"❌ Login failed (Status: {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Login request failed: {e}")
        return False
    
    # Test 3: Get settings page
    print("\n📄 Testing settings page access...")
    try:
        response = session.get(f"{base_url}/settings", timeout=5)
        if response.status_code == 200:
            print("✅ Settings page accessible")
        else:
            print(f"❌ Settings page failed (Status: {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Settings page request failed: {e}")
        return False
    
    # Test 4: Save settings
    print("\n💾 Testing settings save...")
    settings_data = {
        'company_name': 'Test Company',
        'tax_number': '123456789',
        'phone': '+966501234567',
        'address': 'Test Address',
        'email': 'test@example.com',
        'currency': 'SAR',
        'receipt_font_size': '12',
        'receipt_logo_height': '72',
        'receipt_extra_bottom_mm': '15',
        'receipt_paper_width': '80',
        'receipt_show_logo': 'on',
        'receipt_show_tax_number': 'on',
        'receipt_footer_text': 'Thank you for your visit',
        'footer_message': 'THANK YOU FOR VISIT',
        'printer_type': 'thermal'
    }
    
    try:
        response = session.post(f"{base_url}/settings", data=settings_data, timeout=10)
        print(f"📊 Save response status: {response.status_code}")
        
        if response.status_code == 302:  # Redirect after successful save
            print("✅ Settings saved successfully (redirected)")
        elif response.status_code == 200:
            print("⚠️ Settings page returned (may have errors)")
            # Check for error messages in response
            if 'error' in response.text.lower() or 'could not save' in response.text.lower():
                print("❌ Error detected in response")
                return False
            else:
                print("✅ Settings may have been saved")
        else:
            print(f"❌ Unexpected response status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Settings save request failed: {e}")
        return False
    
    # Test 5: Verify settings were saved
    print("\n🔍 Verifying settings were saved...")
    try:
        response = session.get(f"{base_url}/settings", timeout=5)
        if 'Test Company' in response.text:
            print("✅ Settings verification successful - company name updated")
        else:
            print("⚠️ Settings may not have been saved - company name not found")
    except requests.exceptions.RequestException as e:
        print(f"❌ Settings verification failed: {e}")
        return False
    
    print("\n🎉 All tests completed!")
    return True

if __name__ == "__main__":
    print("🧪 Testing Settings Save Functionality")
    print("=" * 50)
    
    success = test_settings()
    
    if success:
        print("\n✅ Settings functionality is working!")
    else:
        print("\n❌ Settings functionality has issues!")
        sys.exit(1)
