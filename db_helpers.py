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
        try:
            db.session.rollback()
        except Exception as rollback_error:
            print(f"Rollback error: {rollback_error}")
            # Force close the session to reset connection
            db.session.close()
        print(f"Database commit error: {e}")
        return False

def reset_db_session():
    """Reset database session to handle connection issues"""
    try:
        db.session.rollback()
        db.session.close()
        db.session.remove()
    except Exception as e:
        print(f"Error resetting database session: {e}")

def safe_db_operation(operation_func, operation_name="database operation", max_retries=2):
    """Execute database operation with retry logic"""
    for attempt in range(max_retries + 1):
        try:
            result = operation_func()
            db.session.commit()
            return result
        except Exception as e:
            print(f"Database operation '{operation_name}' failed (attempt {attempt + 1}): {e}")
            try:
                db.session.rollback()
            except Exception:
                reset_db_session()

            if attempt == max_retries:
                raise e

            # Wait a bit before retry
            import time
            time.sleep(0.1)

    return None

def handle_db_error(error, operation_name="database operation"):
    """Handle database errors with user-friendly messages"""
    error_str = str(error)

    if "InFailedSqlTransaction" in error_str:
        return "خطأ في قاعدة البيانات. يرجى المحاولة مرة أخرى."
    elif "connection" in error_str.lower():
        return "مشكلة في الاتصال بقاعدة البيانات. يرجى المحاولة لاحقاً."
    elif "timeout" in error_str.lower():
        return "انتهت مهلة الاتصال. يرجى المحاولة مرة أخرى."
    else:
        return f"خطأ في {operation_name}: {error_str}"

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
