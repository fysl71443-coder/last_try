from app import db, bcrypt
from flask_login import UserMixin
from datetime import datetime
from models import get_saudi_now

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class AppKV(db.Model):
    """Simple key-value JSON storage for lightweight settings/drafts.
    Use db.create_all() to create this table automatically.
    """
    id = db.Column(db.Integer, primary_key=True)
    k = db.Column(db.String(100), unique=True, nullable=False)
    v = db.Column(db.Text, nullable=False)  # JSON string
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)

    @classmethod
    def get(cls, key):
        """Get value by key, return None if not found"""
        try:
            item = cls.query.filter_by(k=key).first()
            if item:
                import json
                return json.loads(item.v)
            return None
        except Exception:
            return None

    @classmethod
    def set(cls, key, value):
        """Set value by key"""
        try:
            import json
            value_str = json.dumps(value)
            item = cls.query.filter_by(k=key).first()
            if item:
                item.v = value_str
                item.updated_at = get_saudi_now()
            else:
                item = cls(k=key, v=value_str)
                db.session.add(item)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e


class TableLayout(db.Model):
    """New table layout storage system"""
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(50), nullable=False, unique=True)
    layout_data = db.Column(db.Text, nullable=False)  # JSON string
    created_at = db.Column(db.DateTime, default=get_saudi_now)
    updated_at = db.Column(db.DateTime, default=get_saudi_now, onupdate=get_saudi_now)

    @classmethod
    def get_layout(cls, branch_code):
        """Get layout data for a branch"""
        try:
            layout = cls.query.filter_by(branch_code=branch_code).first()
            if layout:
                import json
                return json.loads(layout.layout_data)
            return None
        except Exception:
            return None

    @classmethod
    def save_layout(cls, branch_code, data):
        """Save layout data for a branch"""
        try:
            import json
            value_str = json.dumps(data)
            layout = cls.query.filter_by(branch_code=branch_code).first()
            if layout:
                layout.layout_data = value_str
                layout.updated_at = get_saudi_now()
            else:
                layout = cls(branch_code=branch_code, layout_data=value_str)
                db.session.add(layout)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e




# ---- Basic restaurant models (minimal fields to make POS work) ----
# NOTE: MenuCategory and MenuItem are defined in the main models.py
# to avoid duplicate class names in the SQLAlchemy registry. Use:
#   from models import MenuCategory, MenuItem

# NOTE: SalesInvoice, SalesInvoiceItem, and Customer are defined in the main models.py
# to avoid duplicate class names. Use imports from models instead.