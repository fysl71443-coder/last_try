from flask import Flask, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy.pool import NullPool

app = Flask(__name__)
app.config['SECRET_KEY'] = 'minimal_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///minimal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"poolclass": NullPool}

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables and admin user
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        hashed_password = bcrypt.generate_password_hash("admin").decode("utf-8")
        db.session.add(User(username="admin", password=hashed_password))
        db.session.commit()

@app.route("/")
def index():
    return redirect(url_for("login"))

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
            return "Invalid credentials. <a href='/login'>Try again</a>"
    return """
    <h2>Login</h2>
    <form method='POST'>
        <input name='username' placeholder='Username' required><br><br>
        <input name='password' type='password' placeholder='Password' required><br><br>
        <button type='submit'>Login</button>
    </form>
    <p>Use: admin / admin</p>
    """

@app.route("/dashboard")
@login_required
def dashboard():
    return f"<h2>Welcome, {current_user.username}!</h2><a href='/logout'>Logout</a>"

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
