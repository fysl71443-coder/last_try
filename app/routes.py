from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('index.html')

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
                    flash('تم إنشاء مستخدم المدير الافتراضي بنجاح', 'success')
                    return redirect(url_for('main.home'))
                except Exception as e:
                    db.session.rollback()
                    flash('خطأ في تهيئة المستخدم الافتراضي', 'danger')

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.home'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور', 'danger')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))
