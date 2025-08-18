from datetime import datetime, timezone
from flask_login import UserMixin
from extensions import db

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='user')
    language_pref = db.Column(db.String(10), default='en')
    last_login_at = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=True)

    def set_password(self, password, bcrypt):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password, bcrypt):
        return bcrypt.check_password_hash(self.password_hash, password)

    def last_login(self):
        self.last_login_at = datetime.utcnow()

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_type = db.Column(db.String(20), nullable=False)  # sales, purchases, expenses
    customer_supplier = db.Column(db.String(200), nullable=False)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    paid_amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, partial, paid
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'

    @property
    def remaining_amount(self):
        return self.total_amount - self.paid_amount

    def update_status(self):
        if self.paid_amount >= self.total_amount:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'

class SalesInvoice(db.Model):
    __tablename__ = 'sales_invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    payment_method = db.Column(db.String(20), nullable=False)
    branch = db.Column(db.String(50), nullable=False)  # 'place_india' or 'china_town'
    table_no = db.Column(db.Integer, nullable=True)  # Table number
    customer_name = db.Column(db.String(100), nullable=True)
    customer_phone = db.Column(db.String(30), nullable=True)
    total_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_after_tax_discount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='unpaid')  # paid, partial, unpaid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    items = db.relationship('SalesInvoiceItem', backref='invoice', lazy=True)

    def __repr__(self):
        return f'<SalesInvoice {self.invoice_number}>'

class SalesInvoiceItem(db.Model):
    __tablename__ = 'sales_invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoices.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    price_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)

    def __repr__(self):
        return f'<SalesInvoiceItem {self.product_name}>'

class Product(db.Model):
    __tablename__ = 'product_catalog'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)  # Arabic name
    price_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    barcode = db.Column(db.String(50), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.name}>'

    @property
    def display_name(self):
        if self.name_ar:
            return f'{self.name} / {self.name_ar}'
        return self.name

class RawMaterial(db.Model):
    __tablename__ = 'raw_materials'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    unit = db.Column(db.String(50), nullable=False)  # kg, gram, liter, piece, etc.
    cost_per_unit = db.Column(db.Numeric(12, 4), nullable=False)  # Cost per unit
    stock_quantity = db.Column(db.Numeric(12, 4), default=0)  # Current stock quantity
    category = db.Column(db.String(100), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<RawMaterial {self.name}>'

    @property
    def display_name(self):
        if self.name_ar:
            return f'{self.name} / {self.name_ar}'
        return self.name

class Meal(db.Model):
    __tablename__ = 'meals'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    total_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)  # Calculated from ingredients
    profit_margin_percent = db.Column(db.Numeric(5, 2), nullable=False, default=30.00)  # Default 30%
    selling_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)  # Cost + profit margin
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relationship to ingredients
    ingredients = db.relationship('MealIngredient', backref='meal', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Meal {self.name}>'

    @property
    def display_name(self):
        if self.name_ar:
            return f'{self.name} / {self.name_ar}'
        return self.name

    def calculate_total_cost(self):
        """Calculate total cost from all ingredients"""
        total = 0
        for ingredient in self.ingredients:
            total += ingredient.total_cost
        self.total_cost = total
        return total

    def calculate_selling_price(self):
        """Calculate selling price with profit margin"""
        cost = float(self.total_cost)
        margin = float(self.profit_margin_percent) / 100
        self.selling_price = cost * (1 + margin)
        return self.selling_price

class MealIngredient(db.Model):
    __tablename__ = 'meal_ingredients'
    id = db.Column(db.Integer, primary_key=True)
    meal_id = db.Column(db.Integer, db.ForeignKey('meals.id'), nullable=False)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 4), nullable=False)  # Quantity needed
    total_cost = db.Column(db.Numeric(12, 4), nullable=False)  # quantity * cost_per_unit

    # Relationships
    raw_material = db.relationship('RawMaterial', backref='meal_ingredients')

    def __repr__(self):
        return f'<MealIngredient {self.raw_material.name if self.raw_material else "Unknown"}>'

    def calculate_cost(self):
        """Calculate total cost for this ingredient"""
        if self.raw_material:
            self.total_cost = self.quantity * self.raw_material.cost_per_unit
            return self.total_cost
        else:
            self.total_cost = 0
            return 0

class PurchaseInvoice(db.Model):
    __tablename__ = 'purchase_invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    supplier_name = db.Column(db.String(200), nullable=True)
    payment_method = db.Column(db.String(20), nullable=False)  # مدى, فيزا, بنك, كاش, ...
    total_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_after_tax_discount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='unpaid')  # paid, partial, unpaid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    items = db.relationship('PurchaseInvoiceItem', backref='invoice', lazy=True)

    def __repr__(self):
        return f'<PurchaseInvoice {self.invoice_number}>'

class PurchaseInvoiceItem(db.Model):
    __tablename__ = 'purchase_invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('purchase_invoices.id'), nullable=False)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False)
    raw_material_name = db.Column(db.String(200), nullable=False)  # Store name for history
    quantity = db.Column(db.Numeric(12, 4), nullable=False)
    price_before_tax = db.Column(db.Numeric(12, 4), nullable=False)  # Price per unit
    tax = db.Column(db.Numeric(12, 2), nullable=False)
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)  # بعد الضريبة والخصم

    # Relationship
    raw_material = db.relationship('RawMaterial', backref='purchase_items')

    def __repr__(self):
        return f'<PurchaseInvoiceItem {self.raw_material_name}>'

class ExpenseInvoice(db.Model):
    __tablename__ = 'expense_invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, bank, visa, mada, etc.
    total_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_after_tax_discount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='paid')  # paid, pending
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    items = db.relationship('ExpenseInvoiceItem', backref='invoice', lazy=True)

    def __repr__(self):
        return f'<ExpenseInvoice {self.invoice_number}>'

class ExpenseInvoiceItem(db.Model):
    __tablename__ = 'expense_invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('expense_invoices.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)  # Description of the expense item
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    price_before_tax = db.Column(db.Numeric(12, 2), nullable=False)  # Price per unit
    tax = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)  # After tax and discount

    def __repr__(self):
        return f'<ExpenseInvoiceItem {self.description}>'




# Employees and Salaries
class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    department = db.Column(db.String(50))
    position = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    hire_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='active')  # active/inactive

    salaries = db.relationship('Salary', backref='employee', lazy=True)

    def __repr__(self):
        return f'<Employee {self.employee_code} - {self.full_name}>'

class Salary(db.Model):
    __tablename__ = 'salaries'
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'year', 'month', name='uq_salary_period'),
    )
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    basic_salary = db.Column(db.Numeric(12, 2), nullable=False)
    allowances = db.Column(db.Numeric(12, 2), default=0)
    deductions = db.Column(db.Numeric(12, 2), default=0)
    previous_salary_due = db.Column(db.Numeric(12, 2), default=0)  # رواتب من شهور سابقة
    total_salary = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='due')  # paid/due/partial


# Payments
class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, nullable=False)
    invoice_type = db.Column(db.String(20), nullable=False)  # sales, purchase, expense, salary
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(20))  # cash, visa, bank, etc.

    def __repr__(self):
        return f'<Payment {self.invoice_type} #{self.invoice_id} amount={self.amount_paid}>'


class Table(db.Model):
    __tablename__ = 'tables'
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(20), nullable=False)  # place_india, china_town
    table_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='available')  # available, reserved, occupied
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('branch_code', 'table_number', name='unique_branch_table'),)

    def __repr__(self):
        return f'<Table {self.branch_code}-{self.table_number} ({self.status})>'

class DraftOrder(db.Model):
    __tablename__ = 'draft_orders'
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(20), nullable=False)
    table_no = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(100), nullable=True)
    customer_phone = db.Column(db.String(30), nullable=True)
    payment_method = db.Column(db.String(20), default='CASH')
    status = db.Column(db.String(20), default='draft')  # draft, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    items = db.relationship('DraftOrderItem', backref='draft_order', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DraftOrder {self.branch_code}-T{self.table_no} ({self.status})>'

class DraftOrderItem(db.Model):
    __tablename__ = 'draft_order_items'
    id = db.Column(db.Integer, primary_key=True)
    draft_order_id = db.Column(db.Integer, db.ForeignKey('draft_orders.id'), nullable=False)
    meal_id = db.Column(db.Integer, db.ForeignKey('meals.id'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    price_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)

    meal = db.relationship('Meal', backref='draft_items')

    def __repr__(self):
        return f'<DraftOrderItem {self.product_name} x{self.quantity}>'

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200))
    tax_number = db.Column(db.String(50))
    address = db.Column(db.String(300))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    vat_rate = db.Column(db.Numeric(5, 2), default=15.00)  # percent
    place_india_label = db.Column(db.String(100), default='Place India')
    china_town_label = db.Column(db.String(100), default='China Town')
    currency = db.Column(db.String(10), default='SAR')
    default_theme = db.Column(db.String(10), default='light')  # 'light' or 'dark'
    # Receipt print settings (sales invoices only)
    receipt_paper_width = db.Column(db.String(4), default='80')  # '80' or '58'
    receipt_margin_top_mm = db.Column(db.Integer, default=5)
    receipt_margin_bottom_mm = db.Column(db.Integer, default=5)
    receipt_margin_left_mm = db.Column(db.Integer, default=3)
    receipt_margin_right_mm = db.Column(db.Integer, default=3)
    receipt_font_size = db.Column(db.Integer, default=12)
    receipt_show_logo = db.Column(db.Boolean, default=True)
    receipt_show_tax_number = db.Column(db.Boolean, default=True)
    receipt_footer_text = db.Column(db.String(300), default='')

    logo_url = db.Column(db.String(300), default='/static/chinese-logo.svg')  # receipt logo

    def __repr__(self):
        return f'<Settings {self.company_name or "Settings"}>'


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    discount_percent = db.Column(db.Numeric(5, 2), default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Customer {self.name}>'

class MenuCategory(db.Model):
    __tablename__ = 'menu_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MenuCategory {self.name}>'


class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('menu_categories.id'), nullable=False)
    meal_id = db.Column(db.Integer, db.ForeignKey('meals.id'), nullable=False)
    price_override = db.Column(db.Numeric(12, 2), nullable=True)
    display_order = db.Column(db.Integer, nullable=True)

    category = db.relationship('MenuCategory', backref='items')
    meal = db.relationship('Meal')

    __table_args__ = (
        db.UniqueConstraint('category_id', 'meal_id', name='uq_category_meal'),
    )

    def __repr__(self):
        return f'<MenuItem cat={self.category_id} meal={self.meal_id}>'



class UserPermission(db.Model):
    __tablename__ = 'user_permissions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    screen_key = db.Column(db.String(50), nullable=False)  # e.g., 'sales','purchases','reports'
    branch_scope = db.Column(db.String(20), default='all')  # all/place/china
    can_view = db.Column(db.Boolean, default=True)
    can_add = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_print = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('user_id','screen_key','branch_scope', name='uq_user_screen_branch'),
    )


# Minimal accounting layer
class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # ASSET, LIABILITY, EQUITY, REVENUE, COGS, EXPENSE, OTHER_INCOME, OTHER_EXPENSE, TAX

    def __repr__(self):
        return f'<Account {self.code} {self.name}>'

class LedgerEntry(db.Model):
    __tablename__ = 'ledger_entries'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    description = db.Column(db.String(500))
    debit = db.Column(db.Numeric(12, 2), default=0)
    credit = db.Column(db.Numeric(12, 2), default=0)

    account = db.relationship('Account', backref='entries')

    def __repr__(self):
        return f'<LedgerEntry {self.date} acc={self.account_id} d={self.debit} c={self.credit}>'
