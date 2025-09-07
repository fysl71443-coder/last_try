#!/usr/bin/env python3
"""
Test Print Templates
Tests all print templates to ensure they work correctly
"""

import os
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@dataclass
class MockInvoice:
    """Mock invoice for testing"""
    id: int = 1001
    invoice_number: str = "INV-2024-001001"
    date: datetime = datetime.now()
    created_at: datetime = datetime.now()
    branch: str = "China Town"
    branch_code: str = "china_town"
    table_number: Optional[str] = "T-05"
    table_no: Optional[str] = "T-05"
    payment_method: str = "Cash"
    customer_name: str = "Ahmed Al-Rashid"
    customer_phone: str = "+966501234567"
    total_before_tax: float = 85.50
    tax_amount: float = 12.83
    discount_amount: float = 5.00
    total_after_tax_discount: float = 93.33
    subtotal: float = 85.50
    total_amount: float = 93.33
    status: str = "paid"

@dataclass
class MockItem:
    """Mock invoice item for testing"""
    product_name: str
    quantity: float
    unit_price: float
    price_before_tax: float
    total_price: float

@dataclass
class MockSettings:
    """Mock settings for testing"""
    company_name: str = "China Town & Palace India"
    logo_url: str = "/static/logo.svg"
    tax_number: str = "123456789012345"
    phone: str = "+966112345678"
    address: str = "King Fahd Road, Riyadh, Saudi Arabia"
    receipt_font_size: int = 12
    receipt_width: int = 320
    receipt_margin_top_mm: int = 2
    receipt_logo_height: int = 40
    receipt_extra_bottom_mm: int = 15
    receipt_show_logo: bool = True
    receipt_show_tax_number: bool = True

def create_test_data():
    """Create test data for templates"""
    
    # Create mock invoice
    invoice = MockInvoice()
    
    # Create mock items
    items = [
        MockItem(
            product_name="Chicken Biryani",
            quantity=2.0,
            unit_price=25.00,
            price_before_tax=25.00,
            total_price=50.00
        ),
        MockItem(
            product_name="Mutton Karahi",
            quantity=1.0,
            unit_price=35.50,
            price_before_tax=35.50,
            total_price=35.50
        ),
        MockItem(
            product_name="Naan Bread",
            quantity=4.0,
            unit_price=3.00,
            price_before_tax=3.00,
            total_price=12.00
        ),
        MockItem(
            product_name="Mango Lassi",
            quantity=2.0,
            unit_price=8.00,
            price_before_tax=8.00,
            total_price=16.00
        )
    ]
    
    # Create mock settings
    settings = MockSettings()
    
    return invoice, items, settings

def test_template_exists(template_path):
    """Test if template file exists"""
    full_path = os.path.join('templates', template_path)
    exists = os.path.exists(full_path)
    print(f"{'✅' if exists else '❌'} Template exists: {template_path}")
    return exists

def test_template_syntax(template_path):
    """Test template syntax by trying to read it"""
    try:
        full_path = os.path.join('templates', template_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Basic syntax checks
        checks = [
            ('HTML structure', '<html' in content and '</html>' in content),
            ('Head section', '<head>' in content and '</head>' in content),
            ('Body section', '<body>' in content and '</body>' in content),
            ('CSS styles', '<style>' in content or 'style=' in content),
            ('Jinja templates', '{{' in content and '}}' in content),
        ]
        
        all_passed = True
        for check_name, passed in checks:
            print(f"  {'✅' if passed else '❌'} {check_name}")
            if not passed:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ❌ Error reading template: {e}")
        return False

def test_template_features(template_path):
    """Test specific features in template"""
    try:
        full_path = os.path.join('templates', template_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        features = [
            ('Thank you message', 'THANK YOU FOR VISIT' in content),
            ('QR Code support', 'qr' in content.lower() or 'QRCode' in content),
            ('Print functionality', 'window.print()' in content),
            ('Responsive design', '@media print' in content),
            ('Multilingual support', '_(' in content),
            ('Company info', 'company_name' in content or 'settings' in content),
            ('Invoice details', 'invoice' in content and 'items' in content),
        ]
        
        feature_count = 0
        for feature_name, has_feature in features:
            if has_feature:
                feature_count += 1
                print(f"  ✅ {feature_name}")
            else:
                print(f"  ⚪ {feature_name}")
        
        print(f"  📊 Features: {feature_count}/{len(features)}")
        return feature_count >= len(features) // 2  # At least half features
        
    except Exception as e:
        print(f"  ❌ Error analyzing features: {e}")
        return False

def test_all_templates():
    """Test all print templates"""
    
    print("🔍 Testing Print Templates")
    print("=" * 50)
    
    templates = [
        'print/receipt.html',
        'sales_receipt.html', 
        'invoice_print.html',
        'unified_receipt.html',
        'payment.html'
    ]
    
    results = {}
    
    for template in templates:
        print(f"\n📄 Testing: {template}")
        print("-" * 30)
        
        # Test existence
        exists = test_template_exists(template)
        
        # Test syntax
        syntax_ok = test_template_syntax(template) if exists else False
        
        # Test features
        features_ok = test_template_features(template) if exists else False
        
        results[template] = {
            'exists': exists,
            'syntax': syntax_ok,
            'features': features_ok,
            'overall': exists and syntax_ok and features_ok
        }
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 50)
    
    total_templates = len(templates)
    passed_templates = sum(1 for r in results.values() if r['overall'])
    
    for template, result in results.items():
        status = "✅ PASS" if result['overall'] else "❌ FAIL"
        print(f"{status} {template}")
    
    print(f"\n🎯 Overall: {passed_templates}/{total_templates} templates passed")
    
    if passed_templates == total_templates:
        print("🎉 All templates are working correctly!")
        return True
    else:
        print("⚠️  Some templates need attention")
        return False

def test_print_helper():
    """Test print helper functionality"""
    print("\n🔧 Testing Print Helper")
    print("=" * 30)
    
    try:
        # Test import
        from print_helper import print_helper, get_available_templates
        print("✅ Print helper imported successfully")
        
        # Test available templates
        templates = get_available_templates()
        print(f"✅ Available templates: {len(templates)}")
        for template in templates:
            print(f"  - {template}")
        
        # Test configuration
        from templates.print_config import get_template_config
        for template_type in templates:
            config = get_template_config(template_type)
            print(f"✅ Config for {template_type}: {config['description']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Print helper test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Print Templates Test Suite")
    print("=" * 60)
    
    # Test templates
    templates_ok = test_all_templates()
    
    # Test helper
    helper_ok = test_print_helper()
    
    # Final result
    print("\n🏁 Final Results")
    print("=" * 30)
    
    if templates_ok and helper_ok:
        print("🎉 All tests passed! Print system is ready.")
        return 0
    else:
        print("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
