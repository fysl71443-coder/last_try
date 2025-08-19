"""
Application Configuration
========================
Configuration settings for different environments.
"""

import os
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    
    # Secret key
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    
    # Database configuration
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Default DB: SQLite
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(instance_dir, 'accounting_app.db')}"
    
    # Override with production DB if available
    _db_url = os.getenv('DATABASE_URL')
    if _db_url:
        if _db_url.startswith('postgres://'):
            _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = _db_url
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SQLAlchemy Engine Options for production stability
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0,
        'pool_size': 5
    }

    # Babel / i18n
    BABEL_DEFAULT_LOCALE = os.getenv('BABEL_DEFAULT_LOCALE', 'en')
    LANGUAGES = ['en', 'ar']

    # CSRF settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Session settings
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

    # Production-specific SQLAlchemy settings - disable pooling completely
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,  # Disable connection pooling
        'pool_pre_ping': False,
        'connect_args': {
            'check_same_thread': False,  # For SQLite in production
            'timeout': 20
        }
    }

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
