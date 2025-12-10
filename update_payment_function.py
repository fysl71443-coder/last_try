#!/usr/bin/env python3
"""
تحديث دالة تسجيل المدفوعات لضمان التوافق المحاسبي
"""

import sys
sys.path.append('.')

# الآن دعني أحدث دالة register_payment_ajax في app/routes.py
def update_payment_registration():
    """تحديث دالة تسجيل المدفوعات"""
    
    # قراءة الملف الحالي
    with open('app/routes.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # البحث عن الدالة الحالية
    start_marker = "@main.route('/api/payments/register', methods=['POST'], endpoint='register_payment_ajax')"
    end_marker = "return jsonify({'status': 'error', 'message': str(e)}), 400"
    
    # إيجاد موقع الدالة
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("لم يتم العثور على دالة register_payment_ajax")
        return False
    
    # إيجاد نهاية الدالة
    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        print("لم يتم العثور على نهاية الدالة")
        return False
    
    # حساب نهاية الدالة بالضبط
    end_idx = content.find('}', end_idx) + 1
    
    # استخراج الدالة القديمة
    old_function = content[start_idx:end_idx]
    
    # إنشاء الدالة المحدثة
    new_function = '''@main.route('/api/payments/register', methods=['POST'], endpoint='register_payment_ajax')
@login_required
def register_payment_ajax():
    # Accept both form and JSON
    payload = request.get_json(silent=True) or {}
    invoice_id = request.form.get('invoice_id') or payload.get('invoice_id')
    invoice_type = (request.form.get('invoice_type') or payload.get('invoice_type') or '').strip().lower()
    amount = request.form.get('amount') or payload.get('amount')
    payment_method = (request.form.get('payment_method') or payload.get('payment_method') or 'CASH').strip().upper()
    try:
        inv_id = int(invoice_id)
        amt = float(amount or 0)
    except Exception:
        return jsonify({'status': 'error', 'message': 'Invalid invoice id or amount'}), 400
    if amt <= 0:
        return jsonify({'status': 'error', 'message': 'Amount must be > 0'}), 400
    if invoice_type not in ('purchase','expense','sales'):
        return jsonify({'status': 'error', 'message': 'Unsupported invoice type'}), 400

    try:
        # Create payment record
        p = Payment(invoice_id=inv_id, invoice_type=invoice_type, amount_paid=amt, payment_method=payment_method)
        db.session.add(p)
        db.session.flush()

        # Fetch invoice and totals
        if invoice_type == 'purchase':
            inv = PurchaseInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0
        elif invoice_type == 'sales':
            inv = SalesInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0
        else:
            inv = ExpenseInvoice.query.get(inv_id)
            total = float(inv.total_after_tax_discount or 0.0) if inv else 0.0

        # Sum paid so far (including this payment)
        paid = float(db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0))
                     .filter(Payment.invoice_id == inv_id, Payment.invoice_type == invoice_type).scalar() or 0.0)

        # Robust status calculation with rounding tolerance (0.01)
        from decimal import Decimal, ROUND_HALF_UP
        def to_cents(value):
            try:
                return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return Decimal('0.00')
        total_c = to_cents(total)
        paid_c = to_cents(paid)
        if inv:
            if (total_c - paid_c) <= Decimal('0.01') and total_c > Decimal('0.00'):
                inv.status = 'paid'
            elif paid_c > Decimal('0.00'):
                inv.status = 'partial'
            else:
                inv.status = inv.status or ('unpaid' if invoice_type=='purchase' else 'paid')
        db.session.commit()
        
        # === التحسين الجديد: إنشاء قيود محاسبية متوافقة ===
        try:
            # Create Journal Entry for payment using correct AR account
            from models import JournalEntry, JournalLine
            
            # تحديد حساب المدينين الصحيح بناءً على القيد الأصلي
            ar_account_code = get_original_ar_account_code(inv_id, invoice_type)
            ar_acc = _account(ar_account_code, CHART_OF_ACCOUNTS.get(ar_account_code, {'name':'Accounts Receivable','type':'ASSET'}).get('name','Accounts Receivable'), 'ASSET')
            
            # حساب النقدية المناسب
            cash_account_code = '1013' if payment_method in ('BANK','TRANSFER','CARD','VISA','MASTERCARD') else '1011'
            cash_acc = _account(cash_account_code, CHART_OF_ACCOUNTS.get(cash_account_code, {'name':'Cash','type':'ASSET'}).get('name','Cash'), 'ASSET')
            
            # إنشاء قيد التحصيل
            base_en = f"JE-REC-{invoice_type}-{inv_id}"
            en = base_en
            i = 2
            from sqlalchemy import func
            while JournalEntry.query.filter(func.lower(JournalEntry.entry_number) == en.lower()).first():
                en = f"{base_en}-{i}"; i += 1
            
            je = JournalEntry(
                entry_number=en,
                date=get_saudi_now().date(),
                branch_code=None,
                description=f"Receipt {invoice_type} #{inv_id}",
                status='posted',
                total_debit=amt,
                total_credit=amt,
                created_by=getattr(current_user,'id',None),
                posted_by=getattr(current_user,'id',None),
                invoice_id=int(inv_id),
                invoice_type=f"{invoice_type}_payment"
            )
            db.session.add(je); db.session.flush()
            
            # استخدام نفس حساب المدينين من القيد الأصلي
            db.session.add(JournalLine(journal_id=je.id, line_no=1, account_id=cash_acc.id, debit=amt, credit=0, description=f"Cash receipt {inv_id}", line_date=get_saudi_now().date()))
            db.session.add(JournalLine(journal_id=je.id, line_no=2, account_id=ar_acc.id, debit=0, credit=amt, description=f"Clear AR {inv_id}", line_date=get_saudi_now().date()))
            db.session.commit()
            
            # تسجيل في audit log
            try:
                from models import JournalAudit
                db.session.add(JournalAudit(journal_id=je.id, action='create', user_id=getattr(current_user,'id',None), before_json=None, after_json=json.dumps({'entry_number': je.entry_number, 'total_debit': float(je.total_debit or 0), 'total_credit': float(je.total_credit or 0)})))
                db.session.commit()
            except Exception:
                pass
                
        except Exception as e:
            print(f"Warning: Failed to create journal entry for payment: {e}")
            db.session.rollback()
        
        return jsonify({'status': 'success', 'invoice_id': inv_id, 'amount': amt, 'paid': paid, 'total': total, 'new_status': getattr(inv, 'status', None)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400

def get_original_ar_account_code(invoice_id, invoice_type):
    """الحصول على رمز حساب المدينين المستخدم في القيد الأصلي"""
    try:
        # البحث عن القيد المحاسبي الأصلي
        original_je = JournalEntry.query.filter_by(
            invoice_id=invoice_id,
            invoice_type=invoice_type
        ).first()
        
        if original_je:
            # البحث عن سجل المدينين في القيد الأصلي
            ar_line = JournalLine.query.filter(
                JournalLine.journal_id == original_je.id,
                JournalLine.debit > 0,
                JournalLine.description.like('%AR%')
            ).first()
            
            if ar_line and ar_line.account:
                return ar_line.account.code
    except Exception as e:
        print(f"خطأ في الحصول على حساب المدينين الأصلي: {e}")
    
    # القيمة الافتراضية
    return '1020'  # حساب المدينين العام'''
    
    # استبدال الدالة القديمة بالجديدة
    new_content = content[:start_idx] + new_function + content[end_idx:]
    
    # حفظ النسخة الاحتياطية
    with open('app/routes.py.backup', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # حفظ الملف المحدث
    with open('app/routes.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("تم تحديث دالة register_payment_ajax بنجاح")
    print("تم إنشاء نسخة احتياطية في app/routes.py.backup")
    return True

if __name__ == "__main__":
    update_payment_registration()