import os, sys
from datetime import date

def main():
    try:
        sys.path.insert(0, os.getcwd())
    except Exception:
        pass
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        proj = os.path.dirname(base)
        inst = os.path.join(proj, 'instance')
        db_file = os.path.join(inst, 'accounting_app.db').replace('\\','/')
        os.environ['DATABASE_URL'] = f"sqlite:///{db_file}"
    except Exception:
        pass
    from app import create_app, db
    from models import Account
    app = create_app()
    with app.app_context():
        try:
            from app.routes import CHART_OF_ACCOUNTS
        except Exception:
            CHART_OF_ACCOUNTS = {}
        created = 0
        for code, meta in (CHART_OF_ACCOUNTS or {}).items():
            a = Account.query.filter(Account.code == code).first()
            if not a:
                a = Account(code=code, name=meta.get('name',''), type=meta.get('type','EXPENSE'))
                db.session.add(a); db.session.flush(); created += 1
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        print(f"Seeded accounts: {created}")
        # Sync POS sales into journals for the period
        start = '2025-10-01'
        end = date.today().isoformat()
        with app.test_request_context(f"/api/sync/pos?start={start}&end={end}"):
            try:
                from app.routes import api_sync_pos
                resp = api_sync_pos()
                print('POS sync result:', getattr(resp, 'json', None) or resp)
            except Exception as e:
                print('POS sync error:', e)
        # Fallback: create missing journals for sales directly
        try:
            from routes.journal import create_missing_journal_entries_for
            created, errors = create_missing_journal_entries_for('sales')
            print('Direct sales journal creation:', 'created', len(created), 'errors', len(errors))
        except Exception as e:
            print('Direct create sales journals error:', e)

if __name__ == '__main__':
    main()
