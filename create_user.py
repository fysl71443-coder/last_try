from app import app, db, bcrypt
from models import User, Invoice, SalesInvoice, SalesInvoiceItem, Product, RawMaterial, Meal, MealIngredient, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem

def create_admin_user():
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Check if admin user already exists
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print('Admin user already exists')
            return
        
        # Create admin user
        admin_user = User(
            username='admin',
            email='admin@example.com',
            role='admin',
            language_pref='en',
            active=True
        )
        admin_user.set_password('admin123', bcrypt)
        
        db.session.add(admin_user)
        db.session.commit()
        
        print('Admin user created successfully!')
        print('Username: admin')
        print('Password: admin123')

if __name__ == '__main__':
    create_admin_user()
