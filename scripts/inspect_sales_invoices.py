import os, sys
os.environ.setdefault('USE_EVENTLET','0')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
from models import SalesInvoice, SalesInvoiceItem


def main():
    with app.app_context():
        db.create_all()
        total = SalesInvoice.query.count()
        print('SalesInvoice total:', total)
        invoices = SalesInvoice.query.order_by(SalesInvoice.id.asc()).limit(50).all()
        for inv in invoices:
            items_count = SalesInvoiceItem.query.filter_by(invoice_id=inv.id).count()
            print(f"ID={inv.id} invoice_number={getattr(inv,'invoice_number',None)} branch={getattr(inv,'branch',None)} items={items_count}")

if __name__ == '__main__':
    main()

