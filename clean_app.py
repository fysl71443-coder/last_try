from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy.pool import NullPool

# ===== إنشاء التطبيق =====
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ===== تصحيح Eventlet/SQLAlchemy =====
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"poolclass": NullPool}

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ===== نموذج المستخدم =====
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ===== إنشاء قاعدة البيانات =====
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        hashed_password = bcrypt.generate_password_hash("admin").decode("utf-8")
        db.session.add(User(username="admin", password=hashed_password))
        db.session.commit()

# ===== صفحات التطبيق =====
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("simple_login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("simple_dashboard.html", username=current_user.username)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/")
def index():
    return redirect(url_for("login"))

# ===== تشغيل التطبيق =====
if __name__ == "__main__":
    # عند استخدام Render/Gunicorn، سيتم استدعاء gunicorn وليس هذا السطر
    app.run(debug=True)
