from app import app, db
from models import PurchaseInvoice, PurchaseInvoiceItem, RawMaterial, User
from datetime import datetime, timedelta
from decimal import Decimal
import random

def create_sample_purchases():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            print('Admin user not found. Please create admin user first.')
            return
        
        # Get raw materials
        raw_materials = RawMaterial.query.filter_by(active=True).all()
        if not raw_materials:
            print('No raw materials found. Please create raw materials first.')
            return
        
        # Sample suppliers
        suppliers = [
            'شركة المواد الغذائية المحدودة',
            'مؤسسة التوريدات الذهبية',
            'شركة الإمداد الشامل',
            'Golden Food Supplies Co.',
            'Fresh Market Suppliers',
            'Premium Ingredients Ltd.'
        ]
        
        payment_methods = ['MADA','BANK','CASH','VISA','MASTERCARD','AKS','GCC','آجل']

        # Create sample purchase invoices
        sample_invoices = []
        
        for i in range(1, 11):  # Create 10 purchase invoices
            # Random invoice data
            supplier = random.choice(suppliers)
            payment_method = random.choice(payment_methods)
            invoice_date = datetime.now().date() - timedelta(days=random.randint(0, 60))
            
            # Create invoice
            invoice = PurchaseInvoice(
                invoice_number=f'PUR-2024-{i:03d}',
                date=invoice_date,
                supplier_name=supplier,
                payment_method=payment_method,
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
            selected_materials = random.sample(raw_materials, min(num_items, len(raw_materials)))
            
            total_before_tax = 0
            total_tax = 0
            total_discount = 0
            
            for material in selected_materials:
                # Random quantities and prices
                quantity = round(random.uniform(5, 50), 4)  # 5-50 units
                
                # Price should be reasonable based on material type
                base_price = float(material.cost_per_unit)
                # Purchase price might be different from current cost
                unit_price = round(base_price * random.uniform(0.8, 1.2), 4)  # ±20% variation
                
                discount = round(random.uniform(0, unit_price * quantity * 0.1), 2)  # Up to 10% discount
                
                # Calculate amounts
                item_before_tax = quantity * unit_price
                item_tax = item_before_tax * 0.15  # 15% tax
                item_total = item_before_tax + item_tax - discount
                
                # Create purchase item
                item = PurchaseInvoiceItem(
                    invoice_id=invoice.id,
                    raw_material_id=material.id,
                    raw_material_name=material.display_name,
                    quantity=Decimal(str(quantity)),
                    price_before_tax=Decimal(str(unit_price)),
                    tax=Decimal(str(item_tax)),
                    discount=Decimal(str(discount)),
                    total_price=Decimal(str(item_total))
                )
                
                db.session.add(item)
                
                # Update material stock (simulate purchase)
                old_stock = float(material.stock_quantity)
                new_stock = old_stock + quantity
                
                # Update weighted average cost
                if new_stock > 0:
                    old_total_cost = float(material.cost_per_unit) * old_stock
                    new_total_cost = old_total_cost + (unit_price * quantity)
                    material.cost_per_unit = Decimal(str(new_total_cost / new_stock))
                
                material.stock_quantity = Decimal(str(new_stock))
                
                # Update invoice totals
                total_before_tax += item_before_tax
                total_tax += item_tax
                total_discount += discount
            
            # Update invoice totals
            invoice.total_before_tax = Decimal(str(total_before_tax))
            invoice.tax_amount = Decimal(str(total_tax))
            invoice.discount_amount = Decimal(str(total_discount))
            invoice.total_after_tax_discount = Decimal(str(total_before_tax + total_tax - total_discount))
            
            sample_invoices.append(invoice)
        
        db.session.commit()
        
        print(f'Created {len(sample_invoices)} sample purchase invoices successfully!')
        
        # Print summary by status
        paid_count = len([inv for inv in sample_invoices if inv.status == 'paid'])
        unpaid_count = len([inv for inv in sample_invoices if inv.status == 'unpaid'])
        partial_count = len([inv for inv in sample_invoices if inv.status == 'partial'])
        
        print(f'- Paid: {paid_count} invoices')
        print(f'- Unpaid: {unpaid_count} invoices')
        print(f'- Partial: {partial_count} invoices')
        
        # Print total purchase amount
        total_purchases = sum(float(inv.total_after_tax_discount) for inv in sample_invoices)
        print(f'- Total purchase amount: ${total_purchases:.2f}')
        
        # Print updated stock summary
        print('\nUpdated raw material stocks:')
        updated_materials = RawMaterial.query.filter_by(active=True).all()
        for material in updated_materials[:10]:  # Show first 10
            print(f'- {material.display_name}: {material.stock_quantity} {material.unit} @ ${material.cost_per_unit:.4f}/unit')
        
        if len(updated_materials) > 10:
            print(f'... and {len(updated_materials) - 10} more materials')

if __name__ == '__main__':
    create_sample_purchases()
