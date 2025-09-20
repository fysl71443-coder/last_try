#!/usr/bin/env python3
"""
Simple test server to verify the template fix
"""
import os
import sys
from flask import Flask, render_template, request

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
app.secret_key = 'test-key-123'

# Mock data for testing
BRANCH_CODES = {'china_town': 'China Town', 'palace_india': 'Palace India'}

class MockDraftOrder:
    def __init__(self, id, created_at, items):
        self.id = id
        self.created_at = created_at
        self.items = items
        self.total_amount = sum(float(item.total_price or 0) for item in items)

class MockDraftItem:
    def __init__(self, product_name, quantity, price_before_tax, total_price):
        self.product_name = product_name
        self.quantity = quantity
        self.price_before_tax = price_before_tax
        self.total_price = total_price

from datetime import datetime

@app.route('/')
def home():
    return '''
    <h1>🧪 Template Test Server</h1>
    <p>Testing the sales_table_manage.html template</p>
    <ul>
        <li><a href="/test/china_town/table/1/manage">Test China Town Table 1</a></li>
        <li><a href="/test/palace_india/table/2/manage">Test Palace India Table 2</a></li>
    </ul>
    '''

@app.route('/test/<branch_code>/table/<int:table_number>/manage')
def test_table_manage(branch_code, table_number):
    """Test the sales_table_manage template"""
    
    # Create mock draft orders
    mock_items = [
        MockDraftItem('Chicken Biryani', 2, 25.00, 50.00),
        MockDraftItem('Naan Bread', 3, 5.00, 15.00)
    ]
    
    draft_orders = [
        MockDraftOrder(1, datetime.now(), mock_items),
        MockDraftOrder(2, datetime.now(), [
            MockDraftItem('Beef Curry', 1, 30.00, 30.00)
        ])
    ]
    
    return render_template('sales_table_manage.html',
                         branch_code=branch_code,
                         branch_label=BRANCH_CODES.get(branch_code, branch_code),
                         table_number=table_number,
                         draft_orders=draft_orders)

@app.route('/test/<branch_code>/table/<int:table_number>/manage/empty')
def test_table_manage_empty(branch_code, table_number):
    """Test the template with no draft orders"""
    
    return render_template('sales_table_manage.html',
                         branch_code=branch_code,
                         branch_label=BRANCH_CODES.get(branch_code, branch_code),
                         table_number=table_number,
                         draft_orders=[])

if __name__ == '__main__':
    print("🚀 Starting Template Test Server...")
    print("🌐 Server URL: http://127.0.0.1:5000")
    print("🧪 Test the sales_table_manage.html template")
    print("⏹️  Press Ctrl+C to stop")
    
    app.run(host='127.0.0.1', port=5000, debug=True)
