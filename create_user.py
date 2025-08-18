from app import app, db, bcrypt
from models import User, Invoice, SalesInvoice, SalesInvoiceItem, Product, RawMaterial, Meal, MealIngredient, PurchaseInvoice, PurchaseInvoiceItem, ExpenseInvoice, ExpenseInvoiceItem, Settings, Payment, Account, LedgerEntry
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
# Optional models added by POS features
try:
    from models import MenuCategory, Customer
except Exception:
    MenuCategory = None
    Customer = None

def safe_commit(tag=''):
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f'[create_user] commit failed {tag}:', e)


def create_admin_user():
    with app.app_context():
        # Create tables (ensure all models are imported before this call)
        try:
            db.create_all()
            safe_commit('after create_all')
        except SQLAlchemyError as e:
            db.session.rollback()
            print('[create_user] create_all failed:', e)

        # Seed default menu categories if table exists and empty
        try:
            if MenuCategory is not None:
                cnt = MenuCategory.query.count()
                if cnt == 0:
                    defaults = [
                        'Appetizers','Soups','Salads','House Special','Prawns','Seafoods','Chinese Sizzling','Shaw Faw',
                        'Chicken','Beef & Lamb','Rice & Biryani','Noodles & Chopsuey','Charcoal Grill / Kebabs',
                        'Indian Delicacy (Chicken)','Indian Delicacy (Fish)','Indian Delicacy (Vegetables)','Juices','Soft Drink'
                    ]
                    for name in defaults:
                        db.session.add(MenuCategory(name=name))
                    safe_commit('seed categories')
        except SQLAlchemyError as e:
            db.session.rollback()
            print('[create_user] seed categories failed:', e)

        # Ensure a single Settings row exists
        try:
            s = Settings.query.first()
            if not s:
                s = Settings()
                db.session.add(s)
                safe_commit('create settings')
        except SQLAlchemyError as e:
            db.session.rollback()
            print('[create_user] settings ensure failed:', e)

        # Check if admin user already exists
        try:
            admin = User.query.filter_by(username='admin').first()
        except SQLAlchemyError as e:
            db.session.rollback()
            print('[create_user] admin lookup failed, retrying after rollback:', e)
            admin = User.query.filter_by(username='admin').first()
        if admin:
            print('Admin user already exists')
            return

        # Create admin user
        try:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                role='admin',
                language_pref='en',
                active=True
            )
            admin_user.set_password('admin123', bcrypt)
            db.session.add(admin_user)
            safe_commit('create admin')
            print('Admin user created successfully!')
            print('Username: admin')
            print('Password: admin123')
        except SQLAlchemyError as e:
            db.session.rollback()
            print('[create_user] admin create failed:', e)

if __name__ == '__main__':
    create_admin_user()
