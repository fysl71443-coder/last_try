#!/usr/bin/env python3
"""
Ultra-simple production app with minimal configuration
"""
import os
import sys

# Set environment variables
os.environ.setdefault('USE_EVENTLET', '0')
os.environ.setdefault('FLASK_ENV', 'production')

# Block eventlet imports
class EventletBlocker:
    def find_spec(self, name, path, target=None):
        if name.startswith('eventlet'):
            raise ImportError(f"eventlet blocked: {name}")
        return None

sys.meta_path.insert(0, EventletBlocker())

# Import Flask and create simple app
from flask import Flask
from extensions import db, bcrypt, migrate, login_manager, babel, csrf

def create_simple_app():
    """Create a simple Flask app with minimal config"""
    app = Flask(__name__)
    
    # Simple configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', 'simple-secret-key'),
        'SQLALCHEMY_DATABASE_URI': "sqlite:///app.db",
        'SQLALCHEMY_ENGINE_OPTIONS': {
            "connect_args": {"check_same_thread": False}
        },
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'DEBUG': False,
        'TESTING': False,
        'WTF_CSRF_ENABLED': True,
        'BABEL_DEFAULT_LOCALE': 'ar',
    })
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    babel.init_app(app)
    csrf.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        try:
            from models import User
            return db.session.get(User, int(user_id))
        except Exception:
            return None
    
    return app

# Import the main app to get all routes registered
from app import app as main_app_with_routes

# Copy all routes from main app to simple app
def copy_routes():
    """Copy routes from main app to simple app"""
    simple_app = create_simple_app()

    # Copy URL rules
    for rule in main_app_with_routes.url_map.iter_rules():
        if rule.endpoint != 'static':  # Skip static files
            try:
                # Get the view function
                view_func = main_app_with_routes.view_functions.get(rule.endpoint)
                if view_func:
                    # Add the rule to simple app
                    simple_app.add_url_rule(
                        rule.rule,
                        endpoint=rule.endpoint,
                        view_func=view_func,
                        methods=rule.methods
                    )
            except Exception as e:
                print(f"Warning: Could not copy route {rule.endpoint}: {e}")

    return simple_app

# Create the app with all routes
app = copy_routes()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
