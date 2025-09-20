import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_babel import Babel

# إنشاء كائنات db و login و bcrypt فقط مرة واحدة

# These objects will be imported in models/routes
# and initialized once per app instance

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
migrate = Migrate()
babel = Babel()

def create_app(config_class=None):
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')
    app = Flask(__name__, template_folder=template_dir)

    # إعدادات أساسية
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL',
        'postgresql://china_town_system_user:0LnEU2QR57CaIyBHp2sw9DJBWF25AtrK@dpg-d2dn9895pdvs73aa90j0-a.frankfurt-postgres.render.com/china_town_system'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ربط الكائنات بالتطبيق
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app)
    # Flask-Login setup: login view and user loader
    login_manager.login_view = 'main.login'
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None



    # تسجيل Blueprints إذا كانت موجودة
    from app.routes import main
    app.register_blueprint(main)

    return app
