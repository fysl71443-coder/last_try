import os
import sys

os.environ.setdefault('USE_EVENTLET','0')

try:
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app import create_app
    from extensions import db
    from models import User
except Exception as e:
    print('IMPORT_ERR', e)
    sys.exit(1)

def main():
    app = create_app()
    with app.app_context():
        try:
            db.create_all()
            u = User.query.filter_by(username='admin').first()
            if not u:
                u = User(username='admin', email='admin@example.com', role='admin', active=True)
                u.set_password('admin')
                db.session.add(u)
                db.session.commit()
                print('✅ Created admin with password: admin')
            else:
                u.set_password('admin')
                db.session.commit()
                print('✅ Updated admin password to: admin')
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            print('❌ Seed admin failed:', e)
            sys.exit(1)

if __name__ == '__main__':
    main()
