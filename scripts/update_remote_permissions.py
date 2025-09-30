import os
import sys
import json
import pathlib

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

    # Ensure project root on sys.path so 'app' can be imported
    ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from app import create_app, db
    from app.models import AppKV, User

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
        # Ensure rows exist for all users and scopes
        scopes = ['all','china_town','place_india']
        perm_screens = ['dashboard','sales','purchases','inventory','expenses','employees','salaries','financials','vat','reports','invoices','payments','customers','menu','settings','suppliers','table_settings','users','sample_data']
        users = User.query.all()
        for u in users:
            for sc in scopes:
                k = f"user_perms:{sc}:{int(u.id)}"
                row = AppKV.query.filter_by(k=k).first()
                if row:
                    continue
                payload = {
                    'items': [{ 'screen_key': s, 'view': False, 'add': False, 'edit': False, 'delete': False, 'print': False } for s in perm_screens],
                    'saved_at': __import__('datetime').datetime.utcnow().isoformat()
                }
                try:
                    db.session.add(AppKV(k=k, v=json.dumps(payload, ensure_ascii=False)))
                    db.session.commit()
                    created += 1
                except Exception:
                    db.session.rollback()
        print(f"Updated {updated} entries; created {created} missing permission rows with 'employees' included.")

if __name__ == '__main__':
    main()
