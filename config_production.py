"""
Production Configuration - Optimized for Render deployment
"""
import os
from sqlalchemy.pool import StaticPool

class ProductionConfig:
    """Ultra-safe production configuration"""
    
    # Basic Flask settings
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'production-secret-key-change-me')
    
    # Database configuration - SQLite with thread safety
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Default to SQLite
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(instance_dir, 'accounting_app.db')}"
    
    # Override with production DB if available
    _db_url = os.getenv('DATABASE_URL')
    if _db_url:
        if _db_url.startswith('postgres://'):
            _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = _db_url
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CRITICAL: SQLAlchemy settings to prevent threading issues
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Use StaticPool for SQLite - single connection, thread-safe
        'poolclass': StaticPool,
        'pool_size': 1,
        'max_overflow': 0,
        'pool_timeout': 30,
        'pool_recycle': -1,
        'pool_pre_ping': False,
        'connect_args': {
            'check_same_thread': False,
            'timeout': 30,
            # SQLite-specific optimizations
            'isolation_level': None,  # Autocommit mode
        },
        # Disable all pool events that might cause threading issues
        'echo': False,
        'echo_pool': False,
    }
    
    # Babel / i18n
    BABEL_DEFAULT_LOCALE = os.getenv('BABEL_DEFAULT_LOCALE', 'ar')
    LANGUAGES = ['en', 'ar']
    
    # CSRF settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Logging
    LOG_LEVEL = 'WARNING'
