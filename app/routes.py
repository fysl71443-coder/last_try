from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def home():
    # Redirect authenticated users to dashboard for main control screen
    return redirect(url_for('dashboard'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        # Safe bootstrap: if DB has no users at all, allow creating default admin/admin123 on first login
        if not user:
            try:
                total_users = User.query.count()
            except Exception:
                total_users = 0
            if total_users == 0 and username == 'admin' and password == 'admin123':
                try:
                    new_admin = User(username='admin')
                    new_admin.set_password('admin123')
                    db.session.add(new_admin)
                    db.session.commit()
                    login_user(new_admin)
                    flash('\u062a\u0645 \u0625\u0646\u0634\u0627\u0621 \u0645\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0645\u062f\u064a\u0631 \u0627\u0644\u0627\u0641\u062a\u0631\u0627\u0636\u064a \u0628\u0646\u062c\u0627\u062d', 'success')
                    return redirect(url_for('dashboard'))
                except Exception as e:
                    db.session.rollback()
                    flash('\u062e\u0637\u0623 \u0641\u064a \u062a\u0647\u064a\u0626\u0629 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0627\u0641\u062a\u0631\u0627\u0636\u064a', 'danger')

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('\u062e\u0637\u0623 \u0641\u064a \u0627\u0633\u0645 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645 \u0623\u0648 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631', 'danger')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


# ---------- Main application pages (simple render-only) ----------
@main.route('/dashboard', endpoint='dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@main.route('/sales', endpoint='sales')
@login_required
def sales():
    return render_template('sales.html')

@main.route('/purchases', endpoint='purchases')
@login_required
def purchases():
    return render_template('purchases.html')

@main.route('/raw-materials', endpoint='raw_materials')
@login_required
def raw_materials():
    return render_template('raw_materials.html')

@main.route('/meals', endpoint='meals')
@login_required
def meals():
    return render_template('meals.html')

@main.route('/inventory', endpoint='inventory')
@login_required
def inventory():
    return render_template('inventory.html')

@main.route('/expenses', endpoint='expenses')
@login_required
def expenses():
    return render_template('expenses.html')

@main.route('/invoices', endpoint='invoices')
@login_required
def invoices():
    return render_template('invoices.html')

@main.route('/employees', endpoint='employees')
@login_required
def employees():
    return render_template('employees.html')

@main.route('/payments', endpoint='payments')
@login_required
def payments():
    return render_template('payments.html')

@main.route('/reports', endpoint='reports')
@login_required
def reports():
    return render_template('reports.html')

@main.route('/customers', endpoint='customers')
@login_required
def customers():
    return render_template('customers.html')

@main.route('/suppliers', endpoint='suppliers')
@login_required
def suppliers():
    return render_template('suppliers.html')

@main.route('/menu', endpoint='menu')
@login_required
def menu():
    return render_template('menu.html')

@main.route('/settings', endpoint='settings')
@login_required
def settings():
    return render_template('settings.html')

@main.route('/table-settings', endpoint='table_settings')
@login_required
def table_settings():
    return render_template('table_settings.html')

@main.route('/users', endpoint='users')
@login_required
def users():
    return render_template('users.html')

@main.route('/create-sample-data', endpoint='create_sample_data_route')
@login_required
def create_sample_data_route():
    flash('\u062a\u0645 \u0625\u0646\u0634\u0627\u0621 \u0628\u064a\u0627\u0646\u0627\u062a \u062a\u062c\u0631\u064a\u0628\u064a\u0629 (\u0648\u0647\u0645\u064a\u0629) \u0644\u0623\u063a\u0631\u0627\u0636 \u0627\u0644\u0639\u0631\u0636 \u0641\u0642\u0637', 'info')
    return redirect(url_for('dashboard'))

# ---------- VAT blueprint ----------
vat = Blueprint('vat', __name__, url_prefix='/vat')

@vat.route('/', endpoint='vat_dashboard')
@login_required
def vat_dashboard():
    return render_template('vat/vat_dashboard.html')

# ---------- Financials blueprint ----------
financials = Blueprint('financials', __name__, url_prefix='/financials')

@financials.route('/income-statement', endpoint='income_statement')
@login_required
def income_statement():
    return render_template('financials/income_statement.html')

@financials.route('/balance-sheet', endpoint='balance_sheet')
@login_required
def balance_sheet():
    return render_template('financials/balance_sheet.html')

@financials.route('/trial-balance', endpoint='trial_balance')
@login_required
def trial_balance():
    return render_template('financials/trial_balance.html')
