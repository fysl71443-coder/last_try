from app import app, db
from models import ExpenseInvoice, ExpenseInvoiceItem, User
from datetime import datetime, timedelta
from decimal import Decimal
import random

def create_sample_expenses():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            print('Admin user not found. Please create admin user first.')
            return
        
        # Sample expense categories and descriptions
        expense_items = [
            # Utilities
            {'description': 'Electricity Bill / فاتورة الكهرباء', 'price_range': (200, 800), 'quantity': 1},
            {'description': 'Water Bill / فاتورة المياه', 'price_range': (50, 200), 'quantity': 1},
            {'description': 'Gas Bill / فاتورة الغاز', 'price_range': (100, 300), 'quantity': 1},
            {'description': 'Internet & Phone / الإنترنت والهاتف', 'price_range': (150, 400), 'quantity': 1},
            
            # Rent and Property
            {'description': 'Restaurant Rent / إيجار المطعم', 'price_range': (2000, 5000), 'quantity': 1},
            {'description': 'Storage Rent / إيجار المخزن', 'price_range': (500, 1500), 'quantity': 1},
            {'description': 'Property Maintenance / صيانة العقار', 'price_range': (200, 1000), 'quantity': 1},
            
            # Equipment and Supplies
            {'description': 'Kitchen Equipment Maintenance / صيانة معدات المطبخ', 'price_range': (100, 800), 'quantity': 1},
            {'description': 'Cleaning Supplies / مواد التنظيف', 'price_range': (50, 200), 'quantity': 1},
            {'description': 'Office Supplies / لوازم المكتب', 'price_range': (30, 150), 'quantity': 1},
            {'description': 'Disposable Items / أدوات يمكن التخلص منها', 'price_range': (100, 400), 'quantity': 1},
            
            # Marketing and Advertising
            {'description': 'Social Media Advertising / إعلانات وسائل التواصل', 'price_range': (200, 1000), 'quantity': 1},
            {'description': 'Print Advertising / إعلانات مطبوعة', 'price_range': (100, 500), 'quantity': 1},
            {'description': 'Website Maintenance / صيانة الموقع', 'price_range': (50, 300), 'quantity': 1},
            
            # Transportation and Delivery
            {'description': 'Fuel Costs / تكاليف الوقود', 'price_range': (100, 500), 'quantity': 1},
            {'description': 'Vehicle Maintenance / صيانة المركبات', 'price_range': (200, 800), 'quantity': 1},
            {'description': 'Delivery Service / خدمة التوصيل', 'price_range': (300, 1200), 'quantity': 1},
            
            # Professional Services
            {'description': 'Accounting Services / خدمات المحاسبة', 'price_range': (300, 1000), 'quantity': 1},
            {'description': 'Legal Consultation / استشارة قانونية', 'price_range': (200, 800), 'quantity': 1},
            {'description': 'Insurance Premium / قسط التأمين', 'price_range': (500, 2000), 'quantity': 1},
            
            # Miscellaneous
            {'description': 'Bank Fees / رسوم البنك', 'price_range': (20, 100), 'quantity': 1},
            {'description': 'License Renewal / تجديد الرخصة', 'price_range': (100, 500), 'quantity': 1},
            {'description': 'Staff Training / تدريب الموظفين', 'price_range': (200, 1000), 'quantity': 1},
        ]
        
        payment_methods = ['MADA','BANK','CASH','VISA','MASTERCARD','AKS','GCC','آجل']

        # Create sample expense invoices
        sample_invoices = []
        
        for i in range(1, 16):  # Create 15 expense invoices
            # Random invoice data
            payment_method = random.choice(payment_methods)
            invoice_date = datetime.now().date() - timedelta(days=random.randint(0, 90))
            
            # Create invoice
            invoice = ExpenseInvoice(
                invoice_number=f'EXP-2024-{i:03d}',
                date=invoice_date,
                payment_method=payment_method,
                total_before_tax=0,  # Will be calculated
                tax_amount=0,  # Will be calculated
                discount_amount=0,  # Will be calculated
                total_after_tax_discount=0,  # Will be calculated
                status='paid',  # Most expenses are paid immediately
                user_id=admin_user.id
            )
            
            db.session.add(invoice)
            db.session.flush()  # Get the invoice ID
            
            # Add 1-4 items per invoice
            num_items = random.randint(1, 4)
            selected_items = random.sample(expense_items, min(num_items, len(expense_items)))
            
            total_before_tax = 0
            total_tax = 0
            total_discount = 0
            
            for item_data in selected_items:
                # Random price within range
                min_price, max_price = item_data['price_range']
                price = round(random.uniform(min_price, max_price), 2)
                quantity = item_data['quantity']
                
                # Random tax (0-15%)
                tax = round(price * quantity * random.uniform(0, 0.15), 2)
                
                # Random discount (0-10% of total)
                discount = round((price * quantity) * random.uniform(0, 0.1), 2)
                
                # Calculate total
                item_before_tax = price * quantity
                item_total = item_before_tax + tax - discount
                
                # Create expense item
                item = ExpenseInvoiceItem(
                    invoice_id=invoice.id,
                    description=item_data['description'],
                    quantity=Decimal(str(quantity)),
                    price_before_tax=Decimal(str(price)),
                    tax=Decimal(str(tax)),
                    discount=Decimal(str(discount)),
                    total_price=Decimal(str(item_total))
                )
                
                db.session.add(item)
                
                # Update invoice totals
                total_before_tax += item_before_tax
                total_tax += tax
                total_discount += discount
            
            # Update invoice totals
            invoice.total_before_tax = Decimal(str(total_before_tax))
            invoice.tax_amount = Decimal(str(total_tax))
            invoice.discount_amount = Decimal(str(total_discount))
            invoice.total_after_tax_discount = Decimal(str(total_before_tax + total_tax - total_discount))
            
            sample_invoices.append(invoice)
        
        db.session.commit()
        
        print(f'Created {len(sample_invoices)} sample expense invoices successfully!')
        
        # Print summary by payment method
        payment_summary = {}
        for invoice in sample_invoices:
            method = invoice.payment_method
            if method not in payment_summary:
                payment_summary[method] = {'count': 0, 'total': 0}
            payment_summary[method]['count'] += 1
            payment_summary[method]['total'] += float(invoice.total_after_tax_discount)
        
        print('\nExpense summary by payment method:')
        for method, data in payment_summary.items():
            print(f'- {method}: {data["count"]} invoices, ${data["total"]:.2f}')
        
        # Print total expenses
        total_expenses = sum(float(inv.total_after_tax_discount) for inv in sample_invoices)
        print(f'\nTotal expenses: ${total_expenses:.2f}')
        
        # Print sample expense categories
        print('\nSample expense categories created:')
        categories = set()
        for invoice in sample_invoices:
            for item in invoice.items:
                category = item.description.split(' /')[0]  # Get English part
                categories.add(category)
        
        for category in sorted(list(categories))[:10]:  # Show first 10
            print(f'- {category}')
        
        if len(categories) > 10:
            print(f'... and {len(categories) - 10} more categories')

if __name__ == '__main__':
    create_sample_expenses()
