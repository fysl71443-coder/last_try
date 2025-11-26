from app import create_app
from extensions import db
from models import SalesInvoice, Payment
from sqlalchemy import or_
from datetime import datetime
import re

def norm_group(n: str) -> str:
    s = re.sub(r'[^a-z]', '', (n or '').lower())
    if s.startswith('hunger'):
        return 'hunger'
    if s.startswith('keeta') or s.startswith('keet'):
        return 'keeta'
    return ''

def run(start_date: str = '2025-10-01', end_date: str | None = None):
    app = create_app()
    with app.app_context():
        sd_dt = datetime.fromisoformat(start_date)
        ed_dt = datetime.fromisoformat(end_date) if end_date else datetime.now()
        q = SalesInvoice.query
        try:
            q = q.filter(or_(SalesInvoice.created_at.between(sd_dt, ed_dt), SalesInvoice.date.between(sd_dt.date(), ed_dt.date())))
        except Exception:
            pass
        changed = 0
        removed = 0
        for inv in q.order_by(SalesInvoice.created_at.desc()).limit(5000).all():
            g = norm_group(inv.customer_name or '')
            if g not in ('keeta','hunger'):
                continue
            for p in db.session.query(Payment).filter(Payment.invoice_type=='sales', Payment.invoice_id==inv.id).all():
                try:
                    db.session.delete(p)
                    removed += 1
                except Exception:
                    pass
            inv.status = 'unpaid'
            changed += 1
        try:
            db.session.commit()
            print(f"OK changed={changed} removed_payments={removed}")
        except Exception as e:
            db.session.rollback()
            print('ERROR', e)

if __name__ == '__main__':
    import sys
    sd = '2025-10-01'
    ed = None
    if len(sys.argv) >= 2:
        sd = sys.argv[1]
    if len(sys.argv) >= 3:
        ed = sys.argv[2]
    run(sd, ed)