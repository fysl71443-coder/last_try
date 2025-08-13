from app import app, db
from models import SalesInvoice, SalesInvoiceItem, User
from datetime import datetime, timedelta
import random

def create_sample_sales():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            print('Admin user not found. Please create admin user first.')
            return
        
        # Sample data
        customers = [
            'أحمد محمد علي', 'فاطمة حسن', 'محمد عبدالله', 'عائشة سالم',
            'Ahmed Mohamed Ali', 'Fatima Hassan', 'Mohammed Abdullah', 'Aisha Salem'
        ]
        
        products = [
            'أرز بسمتي', 'شاي أحمر', 'سكر أبيض', 'زيت طبخ', 'دقيق أبيض',
            'Basmati Rice', 'Black Tea', 'White Sugar', 'Cooking Oil', 'White Flour',
            'توابل مشكلة', 'عدس أحمر', 'حمص', 'فول', 'برغل',
            'Mixed Spices', 'Red Lentils', 'Chickpeas', 'Fava Beans', 'Bulgur'
        ]
        
        payment_methods = ['cash', 'card', 'bank_transfer', 'check']
        branches = ['place_india', 'china_town']
        
        # Create sample sales invoices
        sample_invoices = []
        
        for i in range(1, 16):  # Create 15 sales invoices
            # Random invoice data
            branch = random.choice(branches)
            customer = random.choice(customers)
            payment_method = random.choice(payment_methods)
            invoice_date = datetime.now().date() - timedelta(days=random.randint(0, 30))
            
            # Calculate totals
            total_before_tax = 0
            total_tax = 0
            total_discount = 0
            
            # Create invoice
            invoice = SalesInvoice(
                invoice_number=f'SAL-2024-{i:03d}',
                date=invoice_date,
                payment_method=payment_method,
                branch=branch,
                customer_name=customer,
                total_before_tax=0,  # Will be calculated
                tax_amount=0,  # Will be calculated
                discount_amount=0,  # Will be calculated
                total_after_tax_discount=0,  # Will be calculated
                status=random.choice(['unpaid', 'paid', 'partial']),
                user_id=admin_user.id
            )
            
            db.session.add(invoice)
            db.session.flush()  # Get the invoice ID
            
            # Add 2-5 items per invoice
            num_items = random.randint(2, 5)
            for j in range(num_items):
                product = random.choice(products)
                quantity = round(random.uniform(1, 10), 2)
                price_before_tax = round(random.uniform(5, 50), 2)
                tax = round(price_before_tax * 0.15, 2)  # 15% tax
                discount = round(random.uniform(0, price_before_tax * 0.1), 2)  # Up to 10% discount
                
                item_total = (price_before_tax + tax - discount) * quantity
                
                item = SalesInvoiceItem(
                    invoice_id=invoice.id,
                    product_name=product,
                    quantity=quantity,
                    price_before_tax=price_before_tax,
                    tax=tax,
                    discount=discount,
                    total_price=item_total
                )
                
                db.session.add(item)
                
                # Update invoice totals
                total_before_tax += price_before_tax * quantity
                total_tax += tax * quantity
                total_discount += discount * quantity
            
            # Update invoice totals
            invoice.total_before_tax = round(total_before_tax, 2)
            invoice.tax_amount = round(total_tax, 2)
            invoice.discount_amount = round(total_discount, 2)
            invoice.total_after_tax_discount = round(total_before_tax + total_tax - total_discount, 2)
            
            sample_invoices.append(invoice)
        
        db.session.commit()
        
        print(f'Created {len(sample_invoices)} sample sales invoices successfully!')
        
        # Print summary by branch
        place_india_count = len([inv for inv in sample_invoices if inv.branch == 'place_india'])
        china_town_count = len([inv for inv in sample_invoices if inv.branch == 'china_town'])
        
        print(f'- Place India: {place_india_count} invoices')
        print(f'- China Town: {china_town_count} invoices')
        
        # Print summary by status
        paid_count = len([inv for inv in sample_invoices if inv.status == 'paid'])
        unpaid_count = len([inv for inv in sample_invoices if inv.status == 'unpaid'])
        partial_count = len([inv for inv in sample_invoices if inv.status == 'partial'])
        
        print(f'- Paid: {paid_count} invoices')
        print(f'- Unpaid: {unpaid_count} invoices')
        print(f'- Partial: {partial_count} invoices')

if __name__ == '__main__':
    create_sample_sales()
