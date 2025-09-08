import os
os.environ.setdefault('USE_EVENTLET', '0')

from app import app
from extensions import db


def apply_sql(path: str):
    if not os.path.exists(path):
        print(f"❌ SQL file not found: {path}")
        return False
    with app.app_context():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        print(f"🔌 DB URI: {uri}")
        with open(path, 'r', encoding='utf-8') as f:
            sql = f.read()
        # Split statements naively on semicolons; ignore empties
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        print(f"⚙️ Executing {len(statements)} SQL statements from {path} ...")
        try:
            for stmt in statements:
                db.session.execute(stmt)
            db.session.commit()
            print("✅ SQL applied successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to apply SQL: {e}")
            db.session.rollback()
            return False


if __name__ == '__main__':
    sql_path = os.path.join(os.path.dirname(__file__), '..', 'database_migration.sql')
    sql_path = os.path.abspath(sql_path)
    apply_sql(sql_path)

