#!/usr/bin/env python3
"""
ربط فواتير المشتريات بالموردين: تعيين supplier_id حيث supplier_name يطابق اسم مورد والـ supplier_id فارغ.
تشغيل مرة واحدة لتصحيح البيانات القديمة حتى تظهر الفواتير في شاشة العمليات (سداد → مورد).
Run from project root: python scripts/sync_purchase_invoices_supplier_id.py
"""
import os
import sys

# جذر المشروع
base = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(base)
sys.path.insert(0, project_root)
os.chdir(project_root)

# قاعدة SQLite المحلية
os.environ.pop('DATABASE_URL', None)
db_path = os.path.join(project_root, 'instance', 'accounting_app.db')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{db_path}'.replace('\\', '/'))

def main():
    from app import create_app
    from extensions import db
    from models import PurchaseInvoice, Supplier

    app = create_app()
    with app.app_context():
        suppliers = {s.id: (s.name or '').strip() for s in Supplier.query.all()}
        invs = PurchaseInvoice.query.filter(
            (PurchaseInvoice.supplier_id == None) | (PurchaseInvoice.supplier_id == 0)
        ).filter(PurchaseInvoice.supplier_name != None).filter(PurchaseInvoice.supplier_name != '').all()

        updated = 0
        for inv in invs:
            name = (inv.supplier_name or '').strip()
            if not name:
                continue
            for sid, sname in suppliers.items():
                if not sname:
                    continue
                if name == sname or name in sname or sname in name:
                    inv.supplier_id = sid
                    updated += 1
                    try:
                        print(f"  Linked {inv.invoice_number} -> supplier_id={sid} ({sname})")
                    except UnicodeEncodeError:
                        print(f"  Linked {inv.invoice_number} -> supplier_id={sid}")
                    break
        if updated:
            db.session.commit()
            print(f"Updated {updated} purchase invoice(s).")
        else:
            print("No invoices needed updating (supplier_id already set or no name match).")

if __name__ == '__main__':
    main()
