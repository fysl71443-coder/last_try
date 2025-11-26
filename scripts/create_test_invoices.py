from app import create_app, generate_branch_invoice_number
from extensions import db
from models import SalesInvoice, User, Supplier
from datetime import date

def main():
    app = create_app()
    with app.app_context():
        u = db.session.query(User).first()
        if not u:
            u = User(username='admin', email='admin@example.com', password_hash='x', role='admin')
            db.session.add(u)
            db.session.flush()
        uid = u.id

        sup = db.session.query(Supplier).filter(Supplier.active == True).first()
        if not sup:
            sup = Supplier(name='TEST SUPPLIER')
            db.session.add(sup)
            db.session.flush()

        inv1 = SalesInvoice(
            invoice_number=generate_branch_invoice_number('china_town'),
            date=date.today(),
            payment_method='CASH',
            branch='china_town',
            customer_name='هنقر',
            total_before_tax=100.0,
            tax_amount=15.0,
            discount_amount=0.0,
            total_after_tax_discount=115.0,
            status='unpaid',
            user_id=uid
        )
        db.session.add(inv1)

        inv2 = SalesInvoice(
            invoice_number=generate_branch_invoice_number('china_town'),
            date=date.today(),
            payment_method='CASH',
            branch='china_town',
            customer_name=sup.name,
            total_before_tax=200.0,
            tax_amount=30.0,
            discount_amount=0.0,
            total_after_tax_discount=230.0,
            status='unpaid',
            user_id=uid
        )
        db.session.add(inv2)

        try:
            db.session.commit()
            print('CREATED', inv1.id, inv1.customer_name, '|', inv2.id, inv2.customer_name)
        except Exception as e:
            db.session.rollback()
            print('ERROR', e)

if __name__ == '__main__':
    main()