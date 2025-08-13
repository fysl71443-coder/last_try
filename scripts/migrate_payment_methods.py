from app import app, db
from models import SalesInvoice, PurchaseInvoice, ExpenseInvoice, Payment

ALLOWED = {'MADA','BANK','CASH','VISA','MASTERCARD','AKS','GCC','آجل'}

MAP_LOWER = {
    'cash': 'CASH',
    'bank': 'BANK',
    'bank_transfer': 'BANK',
    'transfer': 'BANK',
    'visa': 'VISA',
    'mada': 'MADA',
    'mastercard': 'MASTERCARD',
    'aks': 'AKS',
    'gcc': 'GCC',
    'card': 'VISA',          # default mapping for legacy generic 'card'
    'check': 'BANK',         # treat checks as bank-settled
    'اجل': 'آجل',
    'آجل': 'آجل',
    'credit': 'آجل',
}


def normalize(value: str) -> str:
    v = (value or '').strip()
    if not v:
        return v
    if v in ALLOWED:
        return v
    low = v.lower()
    if low in MAP_LOWER:
        return MAP_LOWER[low]
    # fallback: keep as-is
    return v


def distinct_methods(models):
    s = set()
    for m in models:
        rows = db.session.query(m.payment_method).all()
        for (pm,) in rows:
            if pm is not None:
                s.add(str(pm))
    return s


def migrate():
    with app.app_context():
        models = [SalesInvoice, PurchaseInvoice, ExpenseInvoice]
        print('Before:')
        before = distinct_methods(models + [Payment])
        print('payment_methods:', sorted(before))

        updated = 0
        for M in models:
            for r in M.query.all():
                new = normalize(getattr(r, 'payment_method', None))
                if new and new != r.payment_method:
                    r.payment_method = new
                    updated += 1
        for p in Payment.query.all():
            new = normalize(getattr(p, 'payment_method', None))
            if new and new != p.payment_method:
                p.payment_method = new
                updated += 1
        db.session.commit()
        print('Updated rows:', updated)

        after = distinct_methods(models + [Payment])
        print('After:')
        print('payment_methods:', sorted(after))
        extra = [x for x in after if x not in ALLOWED and x]
        if extra:
            print('WARNING: Found non-standard values after migration:', sorted(set(extra)))
        else:
            print('All payment methods conform to standard set.')


if __name__ == '__main__':
    migrate()

