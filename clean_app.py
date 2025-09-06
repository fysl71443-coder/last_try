import os
import logging
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy.pool import NullPool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== إنشاء التطبيق =====
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback_secret_key_12345')

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Production (Render) - PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"poolclass": NullPool}
    logger.info("Using PostgreSQL database")
else:
    # Development - SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"poolclass": NullPool}
    logger.info("Using SQLite database")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
def init_database():
    """Initialize database and create admin user"""
    try:
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()
            logger.info("Database tables created successfully")

            # Check if admin user exists
            admin = User.query.filter_by(username="admin").first()
            if not admin:
                logger.info("Creating admin user...")
                hashed_password = bcrypt.generate_password_hash("admin").decode("utf-8")
                admin_user = User(username="admin", password=hashed_password)
                db.session.add(admin_user)
                db.session.commit()
                logger.info("Admin user created successfully")
            else:
                logger.info("Admin user already exists")

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        # Don't fail completely, let the app start
        pass

# Initialize database
init_database()

# ===== معالجة الأخطاء =====
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return """
    <h2>Internal Server Error</h2>
    <p>Something went wrong. Please try again later.</p>
    <a href="/login">Go to Login</a>
    """, 500

@app.errorhandler(404)
def not_found(error):
    return """
    <h2>Page Not Found</h2>
    <p>The page you're looking for doesn't exist.</p>
    <a href="/login">Go to Login</a>
    """, 404

# ===== صفحات التطبيق =====
@app.route("/login", methods=["GET", "POST"])
def login():
    try:
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            logger.info(f"Login attempt for user: {username}")

            if not username or not password:
                flash("Please enter both username and password", "danger")
                return render_template("simple_login.html")

            try:
                user = User.query.filter_by(username=username).first()
                if user and bcrypt.check_password_hash(user.password, password):
                    login_user(user)
                    logger.info(f"User {username} logged in successfully")
                    return redirect(url_for("dashboard"))
                else:
                    logger.warning(f"Invalid login attempt for user: {username}")
                    flash("Invalid credentials", "danger")
            except Exception as db_error:
                logger.error(f"Database error during login: {db_error}")
                flash("Login system temporarily unavailable", "danger")

        return render_template("simple_login.html")

    except Exception as e:
        logger.error(f"Login route error: {e}")
        return f"Login error: {str(e)}", 500

@app.route("/dashboard")
@login_required
def dashboard():
    try:
        return render_template("simple_dashboard.html", username=current_user.username)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"<h2>Welcome, {current_user.username}!</h2><a href='/logout'>Logout</a>"

@app.route("/logout")
@login_required
def logout():
    try:
        username = current_user.username
        logout_user()
        logger.info(f"User {username} logged out")
        return redirect(url_for("login"))
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return redirect(url_for("login"))

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "App is running"}

# ===== تشغيل التطبيق =====
if __name__ == "__main__":
    # عند استخدام Render/Gunicorn، سيتم استدعاء gunicorn وليس هذا السطر
    app.run(debug=True)
