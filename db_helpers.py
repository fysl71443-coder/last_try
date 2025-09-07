"""
Database Helper Functions
========================
Helper functions to ensure proper database context with eventlet
"""

from functools import wraps
from flask import current_app
from extensions import db

def with_db_context(f):
    """
    Decorator to ensure database operations happen within app context
    مهم لـ eventlet لتجنب مشاكل threading
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_app:
            # Already in app context
            return f(*args, **kwargs)
        else:
            # Need to create app context
            from app import app
            with app.app_context():
                return f(*args, **kwargs)
    return decorated_function

def safe_db_commit():
    """
    Safe database commit with proper error handling
    """
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Database commit error: {e}")
        return False

def safe_db_query(model, **filters):
    """
    Safe database query with app context
    """
    try:
        if filters:
            return model.query.filter_by(**filters).all()
        else:
            return model.query.all()
    except Exception as e:
        print(f"Database query error: {e}")
        return []

def safe_db_get(model, id):
    """
    Safe database get by ID
    """
    try:
        return db.session.get(model, id)
    except Exception as e:
        print(f"Database get error: {e}")
        return None

# Example usage:
# @with_db_context
# def create_user(username, password):
#     user = User(username=username, password=password)
#     db.session.add(user)
#     return safe_db_commit()
