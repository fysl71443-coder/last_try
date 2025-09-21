from app import db, bcrypt
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class AppKV(db.Model):
    """Simple key-value JSON storage for lightweight settings/drafts.
    Use db.create_all() to create this table automatically.
    """
    id = db.Column(db.Integer, primary_key=True)
    k = db.Column(db.String(100), unique=True, nullable=False)
    v = db.Column(db.Text, nullable=False)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---- Basic restaurant models (minimal fields to make POS work) ----
# NOTE: MenuCategory and MenuItem are defined in the main models.py
# to avoid duplicate class names in the SQLAlchemy registry. Use:
#   from models import MenuCategory, MenuItem

class SalesInvoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    branch_code = db.Column(db.String(50), nullable=False)
    table_number = db.Column(db.Integer)
    customer_name = db.Column(db.String(150))
    customer_phone = db.Column(db.String(50))
    payment_method = db.Column(db.String(20), default='CASH')
    discount_pct = db.Column(db.Float, default=0.0)
    tax_pct = db.Column(db.Float, default=15.0)
    total_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SalesInvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoice.id'), nullable=False)
    meal_id = db.Column(db.Integer)
    name = db.Column(db.String(150))
    unit_price = db.Column(db.Float, default=0.0)
    qty = db.Column(db.Float, default=1.0)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))
    discount_percent = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
