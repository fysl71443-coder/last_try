import sys
import os
import json

# أضف مجلد المشروع إلى sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Meal, SalesInvoice, SalesInvoiceItem, Payment

def get_user(identifier):
    """ احصل على المستخدم بواسطة username أو id """
    with app.app_context():
        if identifier.isdigit():
            u = User.query.get(int(identifier))
        else:
            u = User.query.filter_by(username=identifier).first()

        if not u:
            print(f"❌ User '{identifier}' not found")
            sys.exit(1)
        print(f"✅ Selected user: {u.username} (id={u.id})")
        return u

def create_invoice(user, branch_code, items, customer_name=None, customer_phone=None):
    """ إنشاء فاتورة مباشرة في قاعدة البيانات """
    with app.app_context():
        from datetime import datetime as _dt, timezone as _tz

        # توليد رقم الفاتورة
        last = SalesInvoice.query.order_by(SalesInvoice.id.desc()).first()
        new_num = 1
        if last and last.invoice_number and '-' in last.invoice_number:
            try:
                last_num = int(str(last.invoice_number).split('-')[-1])
                new_num = last_num + 1
            except:
                pass
        _now = _dt.now(_tz.utc)
        invoice_number = f"SAL-{_now.year}-{new_num:03d}"

        # جمع العناصر وحساب الإجمالي
        subtotal = 0.0
        tax_total = 0.0
        invoice_items_data = []
        for meal_id, qty in items:
            meal = Meal.query.get(int(meal_id))
            qty = float(qty)
            if not meal or qty <= 0:
                continue
            unit = float(meal.selling_price or 0)
            line_sub = unit * qty
            line_tax = line_sub * 0.15  # ضريبة 15%
            subtotal += line_sub
            tax_total += line_tax
            invoice_items_data.append({
                'name': meal.display_name,
                'qty': qty,
                'price_before_tax': unit,
                'tax': line_tax,
                'total': line_sub + line_tax
            })

        grand_total = subtotal + tax_total

        # إنشاء الفاتورة
        inv = SalesInvoice(
            invoice_number=invoice_number,
            date=_now.date(),
            payment_method="CASH",
            branch=branch_code,
            customer_name=customer_name,
            customer_phone=customer_phone,
            total_before_tax=subtotal,
            tax_amount=tax_total,
            discount_amount=0,
            total_after_tax_discount=grand_total,
            status='paid',
            user_id=user.id
        )
        db.session.add(inv)
        db.session.flush()  # للحصول على inv.id

        # إضافة العناصر
        for it in invoice_items_data:
            db.session.add(SalesInvoiceItem(
                invoice_id=inv.id,
                product_name=it['name'],
                quantity=it['qty'],
                price_before_tax=it['price_before_tax'],
                tax=it['tax'],
                discount=0,
                total_price=it['total']
            ))

        # تسجيل الدفع
        db.session.add(Payment(
            invoice_id=inv.id,
            invoice_type='sales',
            amount_paid=grand_total,
            payment_method='CASH'
        ))

        db.session.commit()
        print(f"✅ Invoice created: {invoice_number}, ID={inv.id}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python shell.py <username_or_id> <meal_id:qty> [meal_id:qty ...]")
        sys.exit(1)

    identifier = sys.argv[1]
    item_args = sys.argv[2:]
    items = []
    for arg in item_args:
        try:
            mid, qty = arg.split(":")
            items.append((mid, qty))
        except:
            print(f"Invalid item format: {arg}")
            sys.exit(1)

    user = get_user(identifier)

    # تجربة بفرع "1"
    create_invoice(user, branch_code="1", items=items)
