from app import create_app, db
from models import SalesInvoice, SalesInvoiceItem
app = create_app()
with app.app_context():
    try:
        cnt = db.session.query(SalesInvoice, SalesInvoiceItem).join(SalesInvoiceItem, SalesInvoiceItem.invoice_id==SalesInvoice.id).count()
        print('JOIN_COUNT', cnt)
        invs = db.session.query(SalesInvoice).count()
        items = db.session.query(SalesInvoiceItem).count()
        print('INV_COUNT', invs)
        print('ITEM_COUNT', items)
    except Exception as e:
        import traceback; traceback.print_exc()
