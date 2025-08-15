from app import app, db, bcrypt
from models import User, Invoice, SalesInvoice, SalesInvoiceItem, Product, RawMaterial, Meal, MealIngredient, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Settings, Payment, Account, LedgerEntry
# Optional models added by POS features
try:
    from models import MenuCategory, Customer
except Exception:
    MenuCategory = None
    Customer = None

def create_admin_user():
    with app.app_context():
        # Create tables (ensure all models are imported before this call)
        db.create_all()

        # Seed default menu categories if table exists and empty
        try:
            if MenuCategory is not None:
                if MenuCategory.query.count() == 0:
                    defaults = [
                        'Appetizers','Soups','Salads','House Special','Prawns','Seafoods','Chinese Sizzling','Shaw Faw',
                        'Chicken','Beef & Lamb','Rice & Biryani','Noodles & Chopsuey','Charcoal Grill / Kebabs',
                        'Indian Delicacy (Chicken)','Indian Delicacy (Fish)','Indian Delicacy (Vegetables)','Juices','Soft Drink'
                    ]
                    for name in defaults:
                        db.session.add(MenuCategory(name=name))
                    db.session.commit()
        except Exception:
            pass

        # Ensure a single Settings row exists
        try:
            s = Settings.query.first()
            if not s:
                s = Settings()
                db.session.add(s)
                db.session.commit()
        except Exception:
            pass

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
