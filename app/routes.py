from flask import Blueprint, render_template, request, redirect, url_for, flash
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
        # تحقق من المستخدم
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            return redirect(url_for('main.home'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور')
    return render_template('login.html')
