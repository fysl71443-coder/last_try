import os
import sys
import json

# Usage: python scripts/update_remote_permissions.py <DATABASE_URL>

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_remote_permissions.py <DATABASE_URL>")
        sys.exit(1)
    db_url = sys.argv[1].strip()
    if not db_url:
        print("Invalid DATABASE_URL")
        sys.exit(1)

    # Point the app to the remote database
    os.environ['DATABASE_URL'] = db_url

    from app import create_app, db
    from app.models import AppKV

    app = create_app()

    updated = 0
    created = 0
    with app.app_context():
        # Ensure table exists (no-op if already present)
        try:
            db.create_all()
        except Exception:
            pass

        rows = AppKV.query.filter(AppKV.k.like('user_perms:%')).all()
        for row in rows:
            try:
                data = json.loads(row.v) if row.v else {}
            except Exception:
                data = {}
            items = data.get('items') or []
            keys = { (it.get('screen_key') or '').strip() for it in items }
            if 'employees' not in keys:
                items.append({
                    'screen_key': 'employees',
                    'view': False,
                    'add': False,
                    'edit': False,
                    'delete': False,
                    'print': False,
                })
                data['items'] = items
                row.v = json.dumps(data, ensure_ascii=False)
                try:
                    db.session.add(row)
                    db.session.commit()
                    updated += 1
                except Exception:
                    db.session.rollback()
        print(f"Updated {updated} permission entries to include 'employees'.")

if __name__ == '__main__':
    main()
