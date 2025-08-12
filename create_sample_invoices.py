from app import app, db
from models import Invoice, User
from datetime import datetime, timedelta
import random

def create_sample_invoices():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            print('Admin user not found. Please create admin user first.')
            return
        
        # Sample data
        customers = [
            'شركة الأمل للتجارة', 'مؤسسة النور', 'شركة الفجر المحدودة',
            'Al-Amal Trading Co.', 'Noor Corporation', 'Fajr Limited'
        ]
        
        suppliers = [
            'مورد المواد الخام', 'شركة التوريدات الذهبية', 'مؤسسة الإمداد',
            'Raw Materials Supplier', 'Golden Supplies Co.', 'Supply Hub Ltd'
        ]
        
        # Create sample invoices
        sample_invoices = []
        
        # Sales invoices
        for i in range(1, 11):
            invoice = Invoice(
                invoice_number=f'SAL-2024-{i:03d}',
                invoice_type='sales',
                customer_supplier=random.choice(customers),
                total_amount=round(random.uniform(500, 5000), 2),
                paid_amount=0,
                due_date=datetime.now().date() + timedelta(days=random.randint(7, 60)),
                user_id=admin_user.id
            )
            # Randomly pay some invoices partially or fully
            if random.random() > 0.3:  # 70% chance of having some payment
                payment_ratio = random.uniform(0.2, 1.0)
                invoice.paid_amount = round(invoice.total_amount * payment_ratio, 2)
            
            invoice.update_status()
            sample_invoices.append(invoice)
        
        # Purchase invoices
        for i in range(1, 8):
            invoice = Invoice(
                invoice_number=f'PUR-2024-{i:03d}',
                invoice_type='purchases',
                customer_supplier=random.choice(suppliers),
                total_amount=round(random.uniform(1000, 8000), 2),
                paid_amount=0,
                due_date=datetime.now().date() + timedelta(days=random.randint(15, 45)),
                user_id=admin_user.id
            )
            # Randomly pay some invoices
            if random.random() > 0.4:  # 60% chance of having some payment
                payment_ratio = random.uniform(0.3, 1.0)
                invoice.paid_amount = round(invoice.total_amount * payment_ratio, 2)
            
            invoice.update_status()
            sample_invoices.append(invoice)
        
        # Expense invoices
        expense_types = [
            'إيجار المكتب', 'فواتير الكهرباء', 'مصاريف الصيانة',
            'Office Rent', 'Electricity Bills', 'Maintenance Costs'
        ]
        
        for i in range(1, 6):
            invoice = Invoice(
                invoice_number=f'EXP-2024-{i:03d}',
                invoice_type='expenses',
                customer_supplier=random.choice(expense_types),
                total_amount=round(random.uniform(200, 2000), 2),
                paid_amount=0,
                due_date=datetime.now().date() + timedelta(days=random.randint(1, 30)),
                user_id=admin_user.id
            )
            # Most expenses are paid
            if random.random() > 0.2:  # 80% chance of being paid
                invoice.paid_amount = invoice.total_amount
            
            invoice.update_status()
            sample_invoices.append(invoice)
        
        # Add all invoices to database
        for invoice in sample_invoices:
            db.session.add(invoice)
        
        db.session.commit()
        
        print(f'Created {len(sample_invoices)} sample invoices successfully!')
        print('- Sales invoices: 10')
        print('- Purchase invoices: 7') 
        print('- Expense invoices: 5')

if __name__ == '__main__':
    create_sample_invoices()
