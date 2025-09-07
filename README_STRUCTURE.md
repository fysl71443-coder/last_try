# Restaurant System - New Architecture

## 📁 Project Structure

```
RESTAURANT-SYSTEM/
├── app.py              # Main application with create_app() factory
├── extensions.py       # All Flask extensions
├── config.py          # Configuration classes
├── models.py          # Database models
├── wsgi.py            # Production WSGI entry point
├── run_dev.py         # Development server with SocketIO
├── create_user.py     # User creation script
└── migrations/        # Database migrations
```

## 🔧 Key Components

### 1. **extensions.py**
All Flask extensions in one place:
```python
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()
login_manager = LoginManager()
babel = Babel()
csrf = CSRFProtect()
```

### 2. **config.py**
Environment-specific configurations:
```python
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    # ... other settings

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
```

### 3. **app.py**
Application factory pattern:
```python
def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_object(config[config_name or 'default'])
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    # ... other extensions
    
    return app
```

## 🚀 Usage

### Development Server
```bash
# With SocketIO support
python run_dev.py

# Or direct run
python app.py
```

### Production Deployment
```bash
# Using gunicorn
gunicorn wsgi:application

# Using waitress
waitress-serve --host=0.0.0.0 --port=8000 wsgi:application
```

### Database Operations
```bash
# Create migration
python -m flask db revision -m "description"

# Apply migrations
python -m flask db upgrade

# Check current version
python -m flask db current
```

### User Management
```bash
# Create admin user interactively
python create_user.py

# Create default admin (admin/admin123)
python create_user.py --default
```

## ✅ Benefits

1. **Clean Separation**: Extensions, config, and app logic are separated
2. **No Circular Imports**: Extensions are initialized properly
3. **Flask DB Compatible**: Database commands work without eventlet conflicts
4. **Environment Specific**: Different configs for dev/prod/test
5. **Easy Testing**: Can create app instances with test config
6. **Scalable**: Easy to add new extensions and blueprints

## 🔄 Migration from Old Structure

The old monolithic `app.py` has been refactored to:
- ✅ Use application factory pattern
- ✅ Separate extensions into `extensions.py`
- ✅ Move configuration to `config.py`
- ✅ Conditional SocketIO initialization
- ✅ Proper error handling for missing extensions

All existing functionality is preserved while improving maintainability and deployment flexibility.
