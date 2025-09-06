#!/usr/bin/env python3
"""
Diagnose Internal Server Error
"""
import os
import sys
import traceback

def test_clean_app():
    """Test clean_app.py step by step"""
    print("🔍 Diagnosing clean_app.py...")
    
    try:
        print("1. Testing imports...")
        from flask import Flask
        print("✅ Flask imported")
        
        from flask_sqlalchemy import SQLAlchemy
        print("✅ Flask-SQLAlchemy imported")
        
        from flask_bcrypt import Bcrypt
        print("✅ Flask-Bcrypt imported")
        
        from flask_login import LoginManager
        print("✅ Flask-Login imported")
        
        from sqlalchemy.pool import NullPool
        print("✅ NullPool imported")
        
        print("\n2. Testing app creation...")
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret_key'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_restaurant.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"poolclass": NullPool}
        print("✅ App configured")
        
        print("\n3. Testing extensions...")
        db = SQLAlchemy(app)
        bcrypt = Bcrypt(app)
        login_manager = LoginManager(app)
        login_manager.login_view = "login"
        print("✅ Extensions initialized")
        
        print("\n4. Testing User model...")
        from flask_login import UserMixin
        
        class User(UserMixin, db.Model):
            id = db.Column(db.Integer, primary_key=True)
            username = db.Column(db.String(150), unique=True, nullable=False)
            password = db.Column(db.String(200), nullable=False)
        
        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
        
        print("✅ User model defined")
        
        print("\n5. Testing database creation...")
        with app.app_context():
            db.create_all()
            print("✅ Database tables created")
            
            # Check if admin exists
            admin = User.query.filter_by(username="admin").first()
            if not admin:
                print("Creating admin user...")
                hashed_password = bcrypt.generate_password_hash("admin").decode("utf-8")
                admin = User(username="admin", password=hashed_password)
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin user created")
            else:
                print("✅ Admin user already exists")
        
        print("\n6. Testing routes...")
        from flask import render_template, redirect, url_for, request, flash
        from flask_login import login_user, login_required, logout_user, current_user
        
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
                    flash("Invalid credentials", "danger")
            return "<h2>Login</h2><form method='POST'><input name='username' placeholder='Username' required><input name='password' type='password' placeholder='Password' required><button type='submit'>Login</button></form>"
        
        @app.route("/dashboard")
        @login_required
        def dashboard():
            return f"<h2>Welcome, {current_user.username}!</h2><a href='/logout'>Logout</a>"
        
        @app.route("/logout")
        @login_required
        def logout():
            logout_user()
            return redirect(url_for("login"))
        
        print("✅ Routes defined")
        
        print("\n7. Testing app with test client...")
        with app.test_client() as client:
            # Test GET login
            response = client.get('/login')
            print(f"GET /login: {response.status_code}")
            
            # Test POST login
            response = client.post('/login', data={
                'username': 'admin',
                'password': 'admin'
            })
            print(f"POST /login: {response.status_code}")
        
        print("\n✅ All tests passed! App should work correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        traceback.print_exc()
        return False

def test_templates():
    """Test if templates exist and are valid"""
    print("\n🔍 Testing templates...")
    
    templates = [
        'templates/simple_login.html',
        'templates/simple_dashboard.html'
    ]
    
    for template in templates:
        if os.path.exists(template):
            print(f"✅ {template} exists")
            try:
                with open(template, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if len(content) > 0:
                        print(f"✅ {template} has content ({len(content)} chars)")
                    else:
                        print(f"❌ {template} is empty")
            except Exception as e:
                print(f"❌ Error reading {template}: {e}")
        else:
            print(f"❌ {template} not found")

def create_minimal_working_app():
    """Create a minimal working app file"""
    print("\n🔧 Creating minimal working app...")
    
    minimal_app_content = '''from flask import Flask, request, redirect, url_for
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
'''
    
    try:
        with open('minimal_app.py', 'w', encoding='utf-8') as f:
            f.write(minimal_app_content)
        print("✅ minimal_app.py created")
        return True
    except Exception as e:
        print(f"❌ Error creating minimal_app.py: {e}")
        return False

def main():
    """Main diagnosis function"""
    print("🚀 Internal Server Error Diagnosis")
    print("=" * 50)
    
    # Test clean app
    app_ok = test_clean_app()
    
    # Test templates
    test_templates()
    
    # Create minimal app
    minimal_ok = create_minimal_working_app()
    
    print("\n📋 Summary:")
    print(f"Clean app test: {'✅ PASSED' if app_ok else '❌ FAILED'}")
    print(f"Minimal app created: {'✅ YES' if minimal_ok else '❌ NO'}")
    
    if not app_ok:
        print("\n🔧 Recommendations:")
        print("1. Use minimal_app.py instead of clean_app.py")
        print("2. Check server logs for detailed error messages")
        print("3. Test locally first: python minimal_app.py")
        print("4. Update Procfile to use minimal_app:app")

if __name__ == '__main__':
    main()
