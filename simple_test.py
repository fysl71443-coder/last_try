#!/usr/bin/env python3
"""
Very simple Flask test to verify template works
"""
from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

# Mock data
class MockItem:
    def __init__(self, product_name, quantity, price_before_tax, total_price):
        self.product_name = product_name
        self.quantity = quantity
        self.price_before_tax = price_before_tax
        self.total_price = total_price

class MockDraft:
    def __init__(self, id, items):
        self.id = id
        self.created_at = datetime.now()
        self.items = items
        self.total_amount = sum(float(item.total_price) for item in items)

@app.route('/')
def test():
    # Create test data
    items = [
        MockItem('Chicken Biryani', 2, 25.00, 50.00),
        MockItem('Naan Bread', 3, 5.00, 15.00)
    ]
    
    drafts = [MockDraft(1, items)]
    
    return render_template('sales_table_manage.html',
                         branch_code='china_town',
                         branch_label='China Town',
                         table_number=1,
                         draft_orders=drafts)

if __name__ == '__main__':
    print("Testing template...")
    try:
        app.run(host='127.0.0.1', port=5002, debug=False)
    except Exception as e:
        print(f"Error: {e}")
