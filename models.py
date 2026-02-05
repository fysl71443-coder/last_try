from datetime import datetime, timezone
import pytz

# Saudi Arabia timezone
KSA_TZ = pytz.timezone("Asia/Riyadh")

def get_saudi_now():
    """Get current datetime in Saudi Arabia timezone"""
    return datetime.now(KSA_TZ)
from flask_login import UserMixin
from app import bcrypt
from extensions import db

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='user')
    twofa_enabled = db.Column(db.Boolean, default=False)
    twofa_secret = db.Column(db.String(64), nullable=True)
    language_pref = db.Column(db.String(10), default='en')
    last_login_at = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def last_login(self):
        self.last_login_at = get_saudi_now()

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
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)
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
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    date = db.Column(db.Date, default=lambda: get_saudi_now().date(), index=True)
    payment_method = db.Column(db.String(20), nullable=False)
    branch = db.Column(db.String(50), nullable=False, index=True)  # 'place_india' or 'china_town'
    table_number = db.Column(db.Integer, nullable=True)  # Table number
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)  # Customer reference
    customer_name = db.Column(db.String(100), nullable=True)
    customer_phone = db.Column(db.String(30), nullable=True)
    total_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_after_tax_discount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='unpaid')  # paid, partial, unpaid
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    journal_entry_id = db.Column(db.Integer, nullable=True)  # from Node.js accounting service

    items = db.relationship('SalesInvoiceItem', backref='invoice', lazy=True)

    def __repr__(self):
        return f'<SalesInvoice {self.invoice_number}>'

    def to_journal_entries(self):
        rows = []
        try:
            branch = (self.branch or '').strip()
            cust = (self.customer_name or '').strip().lower()
            def _channel(n: str):
                s = (n or '').lower()
                if ('hunger' in s) or ('هنقر' in s) or ('هونقر' in s):
                    return 'hunger'
                if ('keeta' in s) or ('كيتا' in s) or ('كيت' in s):
                    return 'keeta'
                return 'offline'
            ch = _channel(cust)
            rev_code = '4111'
            if ch in ('keeta', 'hunger'): rev_code = '4120'
            cash_code = '1121' if (str(self.payment_method or '').strip().upper() in ('BANK','TRANSFER','CARD','VISA','MASTERCARD')) else '1111'
            total_before = float(self.total_before_tax or 0)
            discount_amt = float(self.discount_amount or 0)
            tax_amt = float(self.tax_amount or 0)
            net_rev = max(0.0, total_before - discount_amt)
            total_inc_tax = round(net_rev + tax_amt, 2)
            rows.append({'account_code': cash_code, 'debit': total_inc_tax, 'credit': 0.0, 'description': f'Receipt {self.invoice_number}', 'ref_type': 'sales', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            if net_rev > 0:
                rows.append({'account_code': rev_code, 'debit': 0.0, 'credit': net_rev, 'description': f'Revenue {self.invoice_number}', 'ref_type': 'sales', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            if tax_amt > 0:
                rows.append({'account_code': '2141', 'debit': 0.0, 'credit': tax_amt, 'description': f'VAT Output {self.invoice_number}', 'ref_type': 'sales', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
        except Exception:
            pass
        return rows

class SalesInvoiceItem(db.Model):
    __tablename__ = 'sales_invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoices.id'), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    price_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)

    def __repr__(self):
        return f'<SalesInvoiceItem {self.product_name}>'


class OrderInvoice(db.Model):
    __tablename__ = 'order_invoices'
    id = db.Column(db.Integer, primary_key=True)
    branch = db.Column(db.String(100))
    invoice_no = db.Column(db.String(50), unique=True, nullable=False)
    invoice_date = db.Column(db.DateTime, default=get_saudi_now)
    customer = db.Column(db.String(255))
    # Use db.JSON for cross-DB compatibility (SQLite stores as TEXT, Postgres as JSON/JSONB)
    items = db.Column(db.JSON, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2))
    discount = db.Column(db.Numeric(12, 2), default=0)
    vat = db.Column(db.Numeric(12, 2))
    total = db.Column(db.Numeric(12, 2))
    payment_method = db.Column(db.String(50), default='PENDING')

    def __repr__(self):
        return f"<OrderInvoice {self.invoice_no}>"

class Product(db.Model):
    __tablename__ = 'product_catalog'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)  # Arabic name
    price_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    barcode = db.Column(db.String(50), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_saudi_now)

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
    created_at = db.Column(db.DateTime, default=get_saudi_now)

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
    created_at = db.Column(db.DateTime, default=get_saudi_now)
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
    date = db.Column(db.Date, default=lambda: get_saudi_now().date(), index=True)
    supplier_name = db.Column(db.String(200), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    supplier_invoice_number = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.String(20), nullable=False)  # مدى, فيزا, بنك, كاش, ...
    total_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_after_tax_discount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='unpaid')  # paid, partial, unpaid
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    supplier = db.relationship('Supplier', lazy=True)
    items = db.relationship('PurchaseInvoiceItem', backref='invoice', lazy=True)

    def __repr__(self):
        return f'<PurchaseInvoice {self.invoice_number}>'

    def get_effective_totals(self):
        """Return (total_before_tax, tax_amount, total_inc_tax). When header totals are 0, compute from items so journals display correctly."""
        total_inc = float(self.total_after_tax_discount or 0)
        tax_amt = float(self.tax_amount or 0)
        total_before = float(self.total_before_tax or 0)
        if total_inc != 0:
            return (total_before, tax_amt, round(total_inc, 2))
        try:
            from sqlalchemy import func
            r = db.session.query(
                func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0),
                func.coalesce(func.sum(PurchaseInvoiceItem.tax), 0),
            ).filter(PurchaseInvoiceItem.invoice_id == self.id).first()
            if r and (float(r[0] or 0) != 0 or float(r[1] or 0) != 0):
                total_inc = float(r[0] or 0)
                tax_amt = float(r[1] or 0)
                total_before = max(0, total_inc - tax_amt)
                return (total_before, tax_amt, round(total_inc, 2))
        except Exception:
            pass
        return (total_before, tax_amt, round(total_before + tax_amt, 2))

    def to_journal_entries(self):
        rows = []
        try:
            total_before, tax_amt, total_inc_tax = self.get_effective_totals()
            # Inventory or expense depending on production flag (not stored here) — default inventory 1210
            rows.append({'account_code': '1161', 'debit': (total_before if total_before>0 else 0.0), 'credit': 0.0, 'description': 'Purchase', 'ref_type': 'purchase', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            if tax_amt > 0:
                rows.append({'account_code': '1170', 'debit': tax_amt, 'credit': 0.0, 'description': 'VAT Input', 'ref_type': 'purchase', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            rows.append({'account_code': '2111', 'debit': 0.0, 'credit': total_inc_tax, 'description': 'Accounts Payable', 'ref_type': 'purchase', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
        except Exception:
            pass
        return rows

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
    date = db.Column(db.Date, default=lambda: get_saudi_now().date(), index=True)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, bank, visa, mada, etc.
    total_before_tax = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_after_tax_discount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='paid')  # paid, pending
    liability_account_code = db.Column(db.String(20), nullable=True)  # for platform/gov payables (2113,2114,2115,2116,2134,2131)
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    items = db.relationship('ExpenseInvoiceItem', backref='invoice', lazy=True)

    def __repr__(self):
        return f'<ExpenseInvoice {self.invoice_number}>'

    def to_journal_entries(self):
        rows = []
        try:
            total_before = float(self.total_before_tax or 0)
            tax_amt = float(self.tax_amount or 0)
            total_inc_tax = round(total_before + tax_amt, 2)
            # Map expense to proper account (payroll recorded via expenses)
            def _exp_code(inv):
                try:
                    txt = ''
                    try:
                        txt += ' ' + (inv.notes or '')
                    except Exception:
                        pass
                    try:
                        for it in (inv.items or []):
                            txt += ' ' + (getattr(it, 'description', '') or '')
                    except Exception:
                        pass
                    s = (txt or '').strip().lower()
                    if ('رواتب' in s) or ('اجور' in s) or ('أجور' in s) or ('salary' in s) or ('payroll' in s):
                        return '5310'
                    if ('رسوم' in s and 'حكومية' in s) or ('government' in s):
                        return '5410'
                    if ('ادوات' in s and 'مكتبية' in s) or ('office' in s):
                        return '5420'
                    if ('تنظيف' in s) or ('clean' in s):
                        return '5250'
                    if ('عمولات' in s) or ('bank fee' in s) or ('commission' in s):
                        return '5610'
                except Exception:
                    pass
                return '5410'
            rows.append({'account_code': _exp_code(self), 'debit': (total_before if total_before>0 else 0.0), 'credit': 0.0, 'description': 'Expense', 'ref_type': 'expense', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            if tax_amt > 0:
                rows.append({'account_code': '1170', 'debit': tax_amt, 'credit': 0.0, 'description': 'VAT Input', 'ref_type': 'expense', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            rows.append({'account_code': '2111', 'debit': 0.0, 'credit': total_inc_tax, 'description': 'Accounts Payable', 'ref_type': 'expense', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            try:
                pm = (self.payment_method or '').strip().upper()
                cash_code = '1121' if pm in ('BANK','TRANSFER','CARD','VISA','MASTERCARD') else '1111'
                # immediate payment: clear AP and credit cash/bank
                rows.append({'account_code': '2111', 'debit': total_inc_tax, 'credit': 0.0, 'description': 'Pay AP', 'ref_type': 'expense', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
                rows.append({'account_code': cash_code, 'debit': 0.0, 'credit': total_inc_tax, 'description': 'Cash/Bank', 'ref_type': 'expense', 'ref_id': int(self.id), 'date': str(self.date or get_saudi_now().date())})
            except Exception:
                pass
        except Exception:
            pass
        return rows

class ExpenseInvoiceItem(db.Model):
    __tablename__ = 'expense_invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('expense_invoices.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)  # Description of the expense item
    account_code = db.Column(db.String(20), nullable=True)   # حساب المصروف المختار (مثل 5230)
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
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_code = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    department = db.Column(db.String(50))
    position = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    hire_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='active')  # active/inactive
    active = db.Column(db.Boolean, default=True)
    work_hours = db.Column(db.Integer, default=0)

    salaries = db.relationship('Salary', backref='employee', lazy=True)
    # one-to-one default salary settings
    employee_salary_default = db.relationship('EmployeeSalaryDefault', uselist=False, backref='employee')

    def __repr__(self):
        return f'<Employee {self.employee_code} - {self.full_name}>'

    @staticmethod
    def generate_code():
        try:
            last = Employee.query.order_by(Employee.id.desc()).first()
            if last and last.id:
                return f"{last.id + 1:04d}"
        except Exception:
            pass
        return "0001"

    def __init__(self, **kwargs):
        # allow passing employee_code explicitly; generate if not provided or empty
        code = kwargs.get('employee_code')
        if not code:
            kwargs['employee_code'] = Employee.generate_code()
        super().__init__(**kwargs)


# Ensure employee_code is deterministic and based on the final autoincrement id.
# Using after_insert to set employee_code = formatted id (e.g., 0001) avoids
# race conditions when multiple workers create employees concurrently.
from sqlalchemy import event


@event.listens_for(Employee, 'after_insert')
def _set_employee_code(mapper, connection, target):
    try:
        if not target.employee_code and getattr(target, 'id', None):
            code = f"{target.id:04d}"
            # perform an UPDATE using the provided connection
            connection.execute(
                Employee.__table__.update().where(Employee.__table__.c.id == target.id).values(employee_code=code)
            )
    except Exception:
        pass


# Hourly payroll settings
class DepartmentRate(db.Model):
    __tablename__ = 'department_rates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # cooks, hall, admin
    hourly_rate = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    def __repr__(self):
        return f'<DepartmentRate {self.name}={self.hourly_rate}>'


class EmployeeHours(db.Model):
    __tablename__ = 'employee_hours'
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'year', 'month', name='uq_hours_period'),
    )
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    hours = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    employee = db.relationship('Employee')

    def __repr__(self):
        return f'<EmployeeHours emp={self.employee_id} {self.year}-{self.month} h={self.hours}>'

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
    extra = db.Column(db.Numeric(12, 2), default=0)  # إضافي
    absence = db.Column(db.Numeric(12, 2), default=0)  # غياب (خصم)
    incentive = db.Column(db.Numeric(12, 2), default=0)  # حافز
    allowances = db.Column(db.Numeric(12, 2), default=0)  # بدلات
    deductions = db.Column(db.Numeric(12, 2), default=0)  # استقطاعات
    previous_salary_due = db.Column(db.Numeric(12, 2), default=0)  # رواتب من شهور سابقة
    total_salary = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='due')  # paid/due/partial

    def to_journal_entries(self):
        rows = []
        try:
            total = float(self.total_salary or 0)
            rows.append({'account_code': '5310', 'debit': total, 'credit': 0.0, 'description': 'Payroll expense', 'ref_type': 'salary', 'ref_id': int(self.id), 'date': str(get_saudi_now().date())})
            rows.append({'account_code': '2121', 'debit': 0.0, 'credit': total, 'description': 'Salaries payable', 'ref_type': 'salary', 'ref_id': int(self.id), 'date': str(get_saudi_now().date())})
        except Exception:
            pass
        return rows



class EmployeeSalaryDefault(db.Model):
    __tablename__ = 'employee_salary_defaults'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False, unique=True)
    base_salary = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    allowances = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    deductions = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=get_saudi_now)

# Payments
class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, nullable=False, index=True)
    invoice_type = db.Column(db.String(20), nullable=False, index=True)  # sales, purchase, expense, salary
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=get_saudi_now)
    payment_method = db.Column(db.String(20))  # cash, visa, bank, etc.

    def __repr__(self):
        return f'<Payment {self.invoice_type} #{self.invoice_id} amount={self.amount_paid}>'


class Table(db.Model):
    __tablename__ = 'tables'
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(20), nullable=False)  # place_india, china_town
    table_number = db.Column(db.String(20), nullable=False)  # Changed to String to support custom numbering
    status = db.Column(db.String(20), default='available')  # available, reserved, occupied
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)

    __table_args__ = (db.UniqueConstraint('branch_code', 'table_number', name='unique_branch_table'),)

    def __repr__(self):
        return f'<Table {self.branch_code}-{self.table_number} ({self.status})>'

class TableSettings(db.Model):
    __tablename__ = 'table_settings'

    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(10), nullable=False, unique=True)
    table_count = db.Column(db.Integer, default=20)
    numbering_system = db.Column(db.String(20), default='numeric')  # numeric, alpha, custom
    custom_numbers = db.Column(db.Text)  # JSON string for custom table numbers
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)

    def __repr__(self):
        return f'<TableSettings {self.branch_code}: {self.table_count} tables ({self.numbering_system})>'


class TableSection(db.Model):
    __tablename__ = 'table_sections'
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)

    __table_args__ = (
        db.UniqueConstraint('branch_code', 'name', name='uq_section_branch_name'),
    )

    def __repr__(self):
        return f'<TableSection {self.branch_code}:{self.name}>'


class TableSectionAssignment(db.Model):
    __tablename__ = 'table_section_assignments'
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(20), nullable=False)
    table_number = db.Column(db.String(20), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('table_sections.id'), nullable=False)

    section = db.relationship('TableSection', backref='assignments')

    __table_args__ = (
        db.UniqueConstraint('branch_code', 'table_number', name='uq_branch_table_assignment'),
    )

    def __repr__(self):
        return f'<TableSectionAssignment {self.branch_code}:{self.table_number} -> {self.section_id}>'

class DraftOrder(db.Model):
    __tablename__ = 'draft_orders'
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(50), nullable=False)
    # Legacy compatibility: some SQLite DBs still have NOT NULL table_no; keep it mapped with a safe default
    table_no = db.Column(db.Integer, nullable=False, default=0)
    table_number = db.Column(db.String(50), nullable=False, default='0')  # NOT NULL with default for PostgreSQL
    customer_name = db.Column(db.String(100), nullable=True)
    customer_phone = db.Column(db.String(20), nullable=True)
    payment_method = db.Column(db.String(50), nullable=False, default='CASH')  # NOT NULL with default
    status = db.Column(db.String(20), nullable=False, default='draft')  # NOT NULL with default
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    items = db.relationship('DraftOrderItem', backref='draft_order', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DraftOrder {self.branch_code}-T{self.table_number} ({self.status})>'

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

    # New: unified print/currency settings
    printer_type = db.Column(db.String(20), default='thermal')  # thermal / A4
    currency_image = db.Column(db.String(300), nullable=True)   # PNG image URL/path for currency icon
    footer_message = db.Column(db.String(300), default='THANK YOU FOR VISIT')

    # Branch-specific settings
    # China Town settings
    china_town_void_password = db.Column(db.String(50), default='1991')
    china_town_vat_rate = db.Column(db.Numeric(5, 2), default=15.00)
    china_town_discount_rate = db.Column(db.Numeric(5, 2), default=0.00)
    # China Town phones
    china_town_phone1 = db.Column(db.String(50), nullable=True)
    china_town_phone2 = db.Column(db.String(50), nullable=True)
    # China Town logo
    china_town_logo_url = db.Column(db.String(300), nullable=True)

    # Palace India settings
    place_india_void_password = db.Column(db.String(50), default='1991')
    place_india_vat_rate = db.Column(db.Numeric(5, 2), default=15.00)
    place_india_discount_rate = db.Column(db.Numeric(5, 2), default=0.00)
    # Palace India phones
    place_india_phone1 = db.Column(db.String(50), nullable=True)
    place_india_phone2 = db.Column(db.String(50), nullable=True)
    # Palace India logo
    place_india_logo_url = db.Column(db.String(300), nullable=True)

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
    # Added to align with app usage
    receipt_logo_height = db.Column(db.Integer, default=40)
    receipt_extra_bottom_mm = db.Column(db.Integer, default=15)

    logo_url = db.Column(db.String(300), default='/static/chinese-logo.svg')  # receipt logo

    # Print tuning controls
    receipt_high_contrast = db.Column(db.Boolean, default=True)
    receipt_bold_totals = db.Column(db.Boolean, default=True)
    receipt_border_style = db.Column(db.String(10), default='solid')  # solid or dashed
    receipt_font_bump = db.Column(db.Integer, default=1)  # additional px in @media print


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    tax_number = db.Column(db.String(50), nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.String(20), default='CASH')  # BANK/CASH/TRANSFER
    notes = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_saudi_now)

    def __repr__(self):
        return f'<Supplier {self.name}>'


class Customer(db.Model):
    """عميل: نقدي (cash) = يدفع فوراً، آجل (credit) = يُنشأ له ذمة مدينة"""
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    customer_type = db.Column(db.String(20), default='cash')  # cash=نقدي | credit=آجل
    discount_percent = db.Column(db.Numeric(5, 2), default=0)  # للعملاء النقديين المسجلين
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_saudi_now)

    @property
    def is_cash(self):
        return (getattr(self, 'customer_type', '') or 'cash').lower() in ('cash', 'نقدي', '')
    @property
    def is_credit(self):
        return (getattr(self, 'customer_type', '') or '').lower() in ('credit', 'آجل')

    def __repr__(self):
        return f'<Customer {self.name}>'

class MenuCategory(db.Model):
    __tablename__ = 'menu_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)  # for UI ordering
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MenuCategory {self.name}>'


class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    # Backward-compatible fields used by admin UI
    name = db.Column(db.String(150), nullable=True)
    price = db.Column(db.Float, default=0.0)
    # Canonical relations
    category_id = db.Column(db.Integer, db.ForeignKey('menu_categories.id'), nullable=False)
    meal_id = db.Column(db.Integer, db.ForeignKey('meals.id'), nullable=True)
    price_override = db.Column(db.Numeric(12, 2), nullable=True)
    display_order = db.Column(db.Integer, nullable=True)

    category = db.relationship('MenuCategory', backref='items')
    meal = db.relationship('Meal')

    __table_args__ = (
        db.UniqueConstraint('category_id', 'meal_id', name='uq_category_meal'),
    )

    def __repr__(self):
        return f'<MenuItem cat={self.category_id} meal={self.meal_id}>'


# ========================================
# Simplified POS Models (Alternative approach)
# ========================================

class Category(db.Model):
    """Simplified category model for POS system"""
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Category {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status
        }


class Item(db.Model):
    """Simplified item model for POS system"""
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    status = db.Column(db.String(50), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    category = db.relationship('Category', backref='items')

    def __repr__(self):
        return f'<Item {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': float(self.price),
            'category_id': self.category_id,
            'status': self.status
        }



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
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # ASSET, LIABILITY, EQUITY, REVENUE, COGS, EXPENSE, OTHER_INCOME, OTHER_EXPENSE, TAX
    parent_account_code = db.Column(db.String(20), nullable=True, index=True)  # للحسابات الفرعية المُنشأة من الشاشة
    name_ar = db.Column(db.String(200), nullable=True)
    name_en = db.Column(db.String(200), nullable=True)
    # إعدادات الاستخدام (Usage): متى وأين يُستخدم الحساب — لا يغيّر شجرة الحسابات
    usage_group = db.Column(db.String(30), nullable=True, index=True)  # Cash, Bank, Supplier, Customer, Inventory, Expense
    is_control = db.Column(db.Boolean, default=False, nullable=True)  # حساب تحكم (مثل 2111) — لا يُقيد عليه مباشرة
    allow_posting = db.Column(db.Boolean, default=True, nullable=True)  # يسمح بالقيود المباشرة

    def __repr__(self):
        return f'<Account {self.code} {self.name}>'


class AccountUsageMap(db.Model):
    """ربط الاستخدام: في أي عملية (module/action) يُعرض أي حساب حسب usage_group. الوظيفة = Role (function_key/label)."""
    __tablename__ = 'account_usage_map'
    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(50), nullable=False, index=True)  # Payments, Purchases, Expenses, ...
    action = db.Column(db.String(50), nullable=False, index=True)  # PayExpense, PaySupplier, ReceiveCash, ...
    usage_group = db.Column(db.String(30), nullable=False, index=True)  # Cash, Bank, Supplier, Customer, ...
    function_key = db.Column(db.String(50), nullable=True, index=True)  # MAIN_CASH, SUPPLIER_CTRL, ...
    function_label_ar = db.Column(db.String(120), nullable=True)  # الصندوق الرئيسي، حساب الموردين (Control)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    is_default = db.Column(db.Boolean, default=False, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=True)
    locked = db.Column(db.Boolean, default=False, nullable=True)  # حساب نظامي لا يُحذف

    account = db.relationship('Account', backref='usage_mappings')

    def __repr__(self):
        return f'<AccountUsageMap {self.module}/{self.action} {self.usage_group} {self.function_key} acc={self.account_id}>'

class LedgerEntry(db.Model):
    __tablename__ = 'ledger_entries'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=lambda: get_saudi_now().date(), index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    description = db.Column(db.String(500))
    debit = db.Column(db.Numeric(12, 2), default=0)
    credit = db.Column(db.Numeric(12, 2), default=0)

    account = db.relationship('Account', backref='entries')

    def __repr__(self):
        return f'<LedgerEntry {self.date} acc={self.account_id} d={self.debit} c={self.credit}>'


class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'
    id = db.Column(db.Integer, primary_key=True)
    entry_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=lambda: get_saudi_now().date(), index=True)
    branch_code = db.Column(db.String(20), nullable=True, index=True)
    description = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='draft', index=True)
    total_debit = db.Column(db.Numeric(12, 2), default=0)
    total_credit = db.Column(db.Numeric(12, 2), default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)
    invoice_id = db.Column(db.Integer, nullable=True, index=True)
    invoice_type = db.Column(db.String(20), nullable=True, index=True)
    salary_id = db.Column(db.Integer, nullable=True, index=True)
    payment_method = db.Column(db.String(20), nullable=True)  # للقيود الناتجة عن سداد/تحصيل

    lines = db.relationship('JournalLine', backref='journal', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<JournalEntry {self.entry_number} {self.status}>'


class JournalLine(db.Model):
    __tablename__ = 'journal_lines'
    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False, index=True)
    line_no = db.Column(db.Integer, nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    debit = db.Column(db.Numeric(12, 2), default=0)
    credit = db.Column(db.Numeric(12, 2), default=0)
    cost_center = db.Column(db.String(100), nullable=True)
    description = db.Column(db.String(500), nullable=False)
    attachment_path = db.Column(db.String(300), nullable=True)
    line_date = db.Column(db.Date, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    invoice_id = db.Column(db.Integer, nullable=True, index=True)  # ربط سطر القيد بفاتورة (سداد/تحصيل)
    invoice_type = db.Column(db.String(20), nullable=True, index=True)  # purchase, expense, sales

    account = db.relationship('Account')

    def __repr__(self):
        return f'<JournalLine {self.journal_id} #{self.line_no}>'


class JournalAudit(db.Model):
    __tablename__ = 'journal_audit'
    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ts = db.Column(db.DateTime, default=get_saudi_now)
    before_json = db.Column(db.Text, nullable=True)
    after_json = db.Column(db.Text, nullable=True)


# ---- السنوات المالية (Fiscal Years) ----
class FiscalYear(db.Model):
    """سنة مالية: الحارس الأعلى للنظام — منع فواتير/قيود بعد الإغلاق، فتح فترات استثنائية."""
    __tablename__ = 'fiscal_years'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)  # 2024, 2025
    year_name = db.Column(db.String(50), nullable=True, index=True)  # اسم السنة، مثلاً "2024-2025"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='open', nullable=False, index=True)  # open | closed | partial | locked
    closed_until = db.Column(db.Date, nullable=True)  # عند partial: مقفل حتى هذا التاريخ
    closed_at = db.Column(db.DateTime, nullable=True)  # وقت الإغلاق
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # من أغلق
    reopened_at = db.Column(db.DateTime, nullable=True)  # آخر إعادة فتح (لتمييز القيود بعد إعادة الفتح)
    reopened_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # من أعاد الفتح
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)

    def __repr__(self):
        return f'<FiscalYear {self.year} {self.status}>'


class FiscalYearExceptionalPeriod(db.Model):
    """فترة استثنائية مفتوحة ضمن سنة مغلقة (استيراد قيود / تصحيح أخطاء) — مع سجل تدقيق إلزامي."""
    __tablename__ = 'fiscal_year_exceptional_periods'
    id = db.Column(db.Integer, primary_key=True)
    fiscal_year_id = db.Column(db.Integer, db.ForeignKey('fiscal_years.id'), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_saudi_now)

    fiscal_year = db.relationship('FiscalYear', backref='exceptional_periods')


class FiscalYearAuditLog(db.Model):
    """سجل تدقيق لكل عملية على السنة المالية (إنشاء، إغلاق، فتح استثنائي، استيراد قيود)."""
    __tablename__ = 'fiscal_year_audit_log'
    id = db.Column(db.Integer, primary_key=True)
    fiscal_year_id = db.Column(db.Integer, db.ForeignKey('fiscal_years.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # create, close, partial_close, open_exceptional, lock, import_approve
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_saudi_now)

    fiscal_year = db.relationship('FiscalYear', backref='audit_logs')


class AuditFinding(db.Model):
    """ملاحظة تدقيق محاسبي — مرتبطة بقيد أو بسنة مالية، لتاريخ تدقيق وتقرير."""
    __tablename__ = 'audit_findings'
    id = db.Column(db.Integer, primary_key=True)
    fiscal_year_id = db.Column(db.Integer, db.ForeignKey('fiscal_years.id'), nullable=True, index=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True, index=True)
    entry_number = db.Column(db.String(80), nullable=True)
    issue_type_ar = db.Column(db.String(100), nullable=False)
    place_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    difference_details = db.Column(db.Text, nullable=True)
    root_cause_ar = db.Column(db.String(150), nullable=True)
    severity = db.Column(db.String(20), nullable=False, default='medium')  # high, medium, low
    correction_method = db.Column(db.String(300), nullable=True)
    entry_date = db.Column(db.Date, nullable=True)
    audit_run_from = db.Column(db.Date, nullable=True)
    audit_run_to = db.Column(db.Date, nullable=True)
    audit_run_at = db.Column(db.DateTime, default=get_saudi_now)

    fiscal_year = db.relationship('FiscalYear', backref='audit_findings')
    journal_entry = db.relationship('JournalEntry', backref='audit_findings')


class AuditSnapshot(db.Model):
    """كاش لقطة تدقيق — شاشة السنة تقرأ سطراً واحداً بدل تشغيل المحرك."""
    __tablename__ = 'audit_snapshots'
    id = db.Column(db.Integer, primary_key=True)
    fiscal_year_id = db.Column(db.Integer, db.ForeignKey('fiscal_years.id'), nullable=False, index=True)
    total = db.Column(db.Integer, nullable=False, default=0)
    high = db.Column(db.Integer, nullable=False, default=0)
    medium = db.Column(db.Integer, nullable=False, default=0)
    low = db.Column(db.Integer, nullable=False, default=0)
    run_at = db.Column(db.DateTime, nullable=False, default=get_saudi_now, index=True)

    fiscal_year = db.relationship('FiscalYear', backref='audit_snapshots')
