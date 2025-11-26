from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, DateField, DecimalField, FieldList, FormField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
try:
    from flask_babel import lazy_gettext as _l
except Exception:
    def _l(s):
        return s

PAYMENT_METHODS = [
    ('MADA', 'مدى / MADA'),
    ('BANK', 'بنك / BANK'),
    ('CASH', 'نقداً / CASH'),
    ('VISA', 'فيزا / VISA'),
    ('MASTERCARD', 'ماستركارد / MASTERCARD'),
    ('AKS', 'AKS / AKS'),
    ('GCC', 'GCC / GCC'),
    ('آجل', 'آجل / Credit'),
]

# Purchases should restrict payment methods to CASH or BANK
PURCHASE_PAYMENT_METHODS = [
    ('CASH', 'نقداً / CASH'),
    ('BANK', 'بنك / BANK'),
]

# Expenses should restrict payment methods to CASH or BANK
EXPENSE_PAYMENT_METHODS = [
    ('CASH', 'نقداً / CASH'),
    ('BANK', 'بنك / BANK'),
]

EXPENSE_ACCOUNT_CHOICES = [
    ('RENT', 'Rent / إيجار'),
    ('MAINT', 'Maintenance / صيانة'),
    ('UTIL', 'Utilities / مرافق'),
    ('LOG', 'Logistics / لوجستيات'),
    ('MKT', 'Marketing / تسويق'),
    ('TEL', 'Telecom & Internet / اتصالات وإنترنت'),
    ('STAT', 'Stationery / قرطاسية'),
    ('CLEAN', 'Cleaning / نظافة'),
    ('GOV', 'Government Payments / مدفوعات حكومية'),
    ('EXP', 'Operating Expenses / مصروفات تشغيلية'),
]

BRANCHES = [
    ('place_india', 'Place India'),
    ('china_town', 'China Town'),
]

class LoginForm(FlaskForm):
    username = StringField(_l('Username / اسم المستخدم'), validators=[DataRequired(), Length(min=3, max=150)])
    password = PasswordField(_l('Password / كلمة المرور'), validators=[DataRequired()])
    remember = BooleanField(_l('Remember Me / تذكرني'))
    submit = SubmitField(_l('Login / تسجيل الدخول'))

class InvoiceItemForm(FlaskForm):
    class Meta:
        csrf = False  # disable CSRF for nested subform
    product_id = SelectField(_l('Meal / الوجبة'), coerce=int, validators=[DataRequired()])
    quantity = IntegerField(_l('Quantity / الكمية'), validators=[DataRequired(), NumberRange(min=1)], default=1)
    discount = DecimalField(_l('Discount %% / نسبة الخصم %%'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)
    price_before_tax = DecimalField(_l('Price / السعر'), places=2, render_kw={'readonly': True})
    tax_amount = DecimalField(_l('Tax / الضريبة'), places=2, render_kw={'readonly': True})
    total_price = DecimalField(_l('Total / الإجمالي'), places=2, render_kw={'readonly': True})

class SalesInvoiceForm(FlaskForm):
    class Meta:
        csrf = False
    date = DateField(_l('Date / التاريخ'), validators=[DataRequired()], format='%Y-%m-%d')
    payment_method = SelectField(_l('Payment Method / طريقة الدفع'), choices=PAYMENT_METHODS, validators=[DataRequired()])
    branch = SelectField(_l('Branch / الفرع'), choices=BRANCHES, validators=[DataRequired()])
    customer_name = StringField(_l('Customer Name / اسم العميل'))
    special_discount_pct = DecimalField(_l('Special Discount % (KEETA/HUNGER)'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)
    items = FieldList(FormField(InvoiceItemForm), min_entries=1)
    submit = SubmitField(_l('Save Invoice / حفظ الفاتورة'))

# Raw Materials Form
class RawMaterialForm(FlaskForm):
    name = StringField(_l('Name / الاسم'), validators=[DataRequired()])
    name_ar = StringField(_l('Arabic Name / الاسم بالعربية'))
    unit = SelectField(_l('Unit / الوحدة'), choices=[
        ('kg', 'Kilogram / كيلوجرام'),
        ('gram', 'Gram / جرام'),
        ('liter', 'Liter / لتر'),
        ('ml', 'Milliliter / مليلتر'),
        ('piece', 'Piece / قطعة'),
        ('cup', 'Cup / كوب'),
        ('tbsp', 'Tablespoon / ملعقة كبيرة'),
        ('tsp', 'Teaspoon / ملعقة صغيرة')
    ], validators=[DataRequired()])
    cost_per_unit = DecimalField(_l('Cost per Unit / التكلفة لكل وحدة'), validators=[DataRequired(), NumberRange(min=0)], places=4)
    category = StringField(_l('Category / الفئة'))
    submit = SubmitField(_l('Save / حفظ'))

# Meal Ingredient Form (for adding ingredients to meals)
class MealIngredientForm(FlaskForm):
    class Meta:
        csrf = False
    raw_material_id = SelectField(_l('Ingredient / المكون'), coerce=int, validators=[DataRequired()])
    quantity = DecimalField(_l('Quantity / الكمية'), validators=[DataRequired(), NumberRange(min=0.0001)], places=4)

# Meal Form
class MealForm(FlaskForm):
    name = StringField(_l('Meal Name / اسم الوجبة'), validators=[DataRequired()])
    name_ar = StringField(_l('Arabic Name / الاسم بالعربية'))
    description = StringField(_l('Description / الوصف'))
    category = StringField(_l('Category / الفئة'))
    profit_margin_percent = DecimalField(_l('Profit Margin %% / هامش الربح %%'), validators=[DataRequired(), NumberRange(min=0, max=1000)], places=2, default=30)
    ingredients = FieldList(FormField(MealIngredientForm), min_entries=1)
    submit = SubmitField(_l('Save Meal / حفظ الوجبة'))

# Purchase Invoice Item Form
class PurchaseInvoiceItemForm(FlaskForm):
    class Meta:
        csrf = False
    category = SelectField(_l('Category / الفئة'), choices=[], validators=[Optional()])
    raw_material_id = SelectField(_l('Raw Material / المادة الخام'), coerce=int, validators=[DataRequired()])
    quantity = DecimalField(_l('Quantity / الكمية'), validators=[DataRequired(), NumberRange(min=0.0001)], places=4)
    price_before_tax = DecimalField(_l('Unit Price / سعر الوحدة'), validators=[DataRequired(), NumberRange(min=0)], places=4)
    discount = DecimalField(_l('Discount %% / نسبة الخصم %%'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)

# Purchase Invoice Form
class PurchaseInvoiceForm(FlaskForm):
    class Meta:
        csrf = False
    date = DateField(_l('Date / التاريخ'), validators=[DataRequired()], format='%Y-%m-%d')
    supplier_name = StringField(_l('Supplier Name / اسم المورد'))
    payment_method = SelectField(_l('Payment Method / طريقة الدفع'), choices=PURCHASE_PAYMENT_METHODS, validators=[DataRequired()])
    items = FieldList(FormField(PurchaseInvoiceItemForm), min_entries=1)
    submit = SubmitField(_l('Save Purchase Invoice / حفظ فاتورة الشراء'))

# Expense Invoice Item Form
class ExpenseInvoiceItemForm(FlaskForm):
    class Meta:
        csrf = False
    description = StringField(_l('Description / الوصف'), validators=[DataRequired()])
    account_code = SelectField(_l('Account / الحساب'), choices=EXPENSE_ACCOUNT_CHOICES, validators=[Optional()])
    quantity = DecimalField(_l('Quantity / الكمية'), default=1, validators=[DataRequired(), NumberRange(min=0.01)], places=2)
    price_before_tax = DecimalField(_l('Unit Price / سعر الوحدة'), validators=[DataRequired(), NumberRange(min=0)], places=2)
    tax = DecimalField(_l('Tax / الضريبة'), validators=[Optional(), NumberRange(min=0)], places=2)
    discount = DecimalField(_l('Discount %% / نسبة الخصم %%'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)

# Expense Invoice Form

# Supplier Form
class SupplierForm(FlaskForm):
    class Meta:
        csrf = False
    name = StringField(_l('Supplier Name / اسم المورد'), validators=[DataRequired()])
    phone = StringField(_l('Phone / الهاتف'))
    email = StringField(_l('Email / البريد الإلكتروني'))
    address = StringField(_l('Address / العنوان'))
    tax_number = StringField(_l('Tax Number / الرقم الضريبي'))
    contact_person = StringField(_l('Contact Person / شخص التواصل'))
    notes = StringField(_l('Notes / ملاحظات'))
    active = BooleanField(_l('Active / نشط'), default=True)
    submit = SubmitField(_l('Save / حفظ'))

class ExpenseInvoiceForm(FlaskForm):
    class Meta:
        csrf = False
    date = DateField(_l('Date / التاريخ'), validators=[DataRequired()], format='%Y-%m-%d')
    payment_method = SelectField(_l('Payment Method / طريقة الدفع'), choices=EXPENSE_PAYMENT_METHODS, validators=[DataRequired()])
    items = FieldList(FormField(ExpenseInvoiceItemForm), min_entries=1)
    submit = SubmitField(_l('Save Expense Invoice / حفظ فاتورة المصروفات'))

# Employee and Salary Forms
class EmployeeForm(FlaskForm):
    employee_code = StringField(_l('Employee Code / رقم الموظف'), validators=[DataRequired()])
    full_name = StringField(_l('Full Name / الاسم الكامل'), validators=[DataRequired()])
    national_id = StringField(_l('National ID / رقم الهوية'), validators=[DataRequired()])
    department = StringField(_l('Department / القسم'))
    position = StringField(_l('Position / الوظيفة'))
    phone = StringField(_l('Phone / الهاتف'))
    email = StringField(_l('Email / البريد الإلكتروني'))
    hire_date = DateField(_l('Hire Date / تاريخ التعيين'), format='%Y-%m-%d')
    status = SelectField(_l('Status / الحالة'), choices=[('active', _l('Active / نشط')), ('inactive', _l('Inactive / غير نشط'))], default='active')
    # Defaults section
    base_salary = DecimalField(_l('Default Basic Salary / الراتب الأساسي الافتراضي'), validators=[Optional(), NumberRange(min=0)], places=2, default=0)
    allowances = DecimalField(_l('Default Allowances / البدلات الافتراضية'), validators=[Optional(), NumberRange(min=0)], places=2, default=0)
    deductions = DecimalField(_l('Default Deductions / الاستقطاعات الافتراضية'), validators=[Optional(), NumberRange(min=0)], places=2, default=0)
    submit = SubmitField(_l('Save Employee / حفظ الموظف'))

class SalaryForm(FlaskForm):
    employee_id = SelectField(_l('Employee / الموظف'), coerce=int, validators=[DataRequired()])
    year = IntegerField(_l('Year / السنة'), validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    month = SelectField(_l('Month / الشهر'), choices=[(i, str(i)) for i in range(1, 13)], coerce=int, validators=[DataRequired()])
    basic_salary = DecimalField(_l('Basic Salary / الراتب الأساسي'), validators=[DataRequired(), NumberRange(min=0)])
    allowances = DecimalField(_l('Allowances / البدلات'), validators=[Optional(), NumberRange(min=0)])
    deductions = DecimalField(_l('Deductions / الاستقطاعات'), validators=[Optional(), NumberRange(min=0)])
    previous_salary_due = DecimalField(_l('Previous Salary Due / رواتب سابقة'), validators=[Optional(), NumberRange(min=0)])
    total_salary = DecimalField(_l('Total / الإجمالي'), validators=[DataRequired()])
    status = SelectField(_l('Status / الحالة'), choices=[('paid', _l('Paid / مدفوع')), ('due', _l('Due / مستحق')), ('partial', _l('Partial / مدفوع جزئياً'))], default='due')
    submit = SubmitField(_l('Save Salary / حفظ الراتب'))
