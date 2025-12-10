#!/usr/bin/env python3
"""
سكريبت تصحيح الأخطاء المحاسبية في النظام
الهدف: تصحيح التناقضات بين أنظمة المحاسبة المختلفة
"""

import os
import sys
import django
from datetime import datetime, date
from decimal import Decimal

# إعداد Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# استيراد النماذج بطريقة آمنة
try:
    from extensions import db
    from app import create_app
    app = create_app()
    app.app_context().push()
except Exception as e:
    print(f"تحذير: لم يتم تحميل التطبيق الكامل: {e}")
    # محاولة الاستيراد المباشر
    try:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()
    except:
        pass

# توحيد رموز حسابات المدينين
AR_ACCOUNTS = {
    'restaurant': '1021',      # عملاء المطعم المباشرين
    'online': '1022',        # العملاء الإلكترونيين
    'keeta': '1130',         # كيتا
    'hunger': '1140',        # هنقرستيشن
    'general': '1020'        # حساب المدينين العام
}

def get_models():
    """الحصول على النماذج بطريقة آمنة"""
    try:
        from models import (
            SalesInvoice, PurchaseInvoice, ExpenseInvoice, 
            JournalEntry, JournalLine, Account, Payment, get_saudi_now
        )
        return SalesInvoice, PurchaseInvoice, ExpenseInvoice, JournalEntry, JournalLine, Account, Payment, get_saudi_now
    except Exception as e:
        print(f"خطأ في استيراد النماذج: {e}")
        return None, None, None, None, None, None, None, None

def get_customer_group_from_invoice(invoice):
    """تحديد مجموعة العميل من الفاتورة"""
    if not invoice:
        return 'restaurant'
    
    customer_name = (getattr(invoice, 'customer_name', '') or '').strip().lower()
    
    if 'keeta' in customer_name or 'كيتا' in customer_name:
        return 'keeta'
    elif 'hunger' in customer_name or 'هنقر' in customer_name or 'هونقر' in customer_name:
        return 'hunger'
    elif 'online' in customer_name or 'إلكتروني' in customer_name:
        return 'online'
    else:
        return 'restaurant'

def get_original_ar_account_code(invoice_id, invoice_type='sales'):
    """الحصول على رمز حساب المدينين المستخدم في القيد الأصلي"""
    try:
        SalesInvoice, _, _, JournalEntry, JournalLine, _, _, _ = get_models()
        if not JournalEntry:
            return '1020'
        
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
    return '1020'

def find_accounting_discrepancies():
    """العثور على التناقضات المحاسبية"""
    discrepancies = []
    
    try:
        SalesInvoice, _, _, JournalEntry, _, _, Payment, get_saudi_now = get_models()
        if not SalesInvoice:
            print("لم يتم تحميل النماذج")
            return discrepancies
        
        print("جاري البحث عن التناقضات المحاسبية...")
        
        # البحث عن فواتير مدفوعة بدون قيود تصفية
        paid_invoices = SalesInvoice.query.filter(
            SalesInvoice.status == 'paid'
        ).all()
        
        print(f"تم العثور على {len(paid_invoices)} فاتورة مدفوعة")
        
        for invoice in paid_invoices:
            # التحقق من وجود قيود تصفية
            payment_entries = JournalEntry.query.filter(
                JournalEntry.invoice_id == invoice.id,
                JournalEntry.invoice_type == 'sales_payment',
                JournalEntry.description.like('%Receipt%')
            ).all()
            
            if not payment_entries:
                discrepancies.append({
                    'type': 'missing_clearing_entry',
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'amount': float(invoice.total_after_tax_discount),
                    'customer_name': getattr(invoice, 'customer_name', ''),
                    'description': 'فاتورة مدفوعة بدون قيد تصفية محاسبي'
                })
        
        # البحث عن فواتير جزئية
        partial_invoices = SalesInvoice.query.filter(
            SalesInvoice.status == 'partial'
        ).all()
        
        for invoice in partial_invoices:
            # التحقق من المدفوعات المسجلة
            total_paid = db.session.query(
                func.coalesce(func.sum(Payment.amount_paid), 0)
            ).filter(
                Payment.invoice_id == invoice.id,
                Payment.invoice_type == 'sales'
            ).scalar() or 0
            
            invoice_total = float(invoice.total_after_tax_discount)
            
            if abs(total_paid - invoice_total) < 0.01:
                # الفاتورة مدفوعة بالكامل لكنها مظللة كجزئية
                discrepancies.append({
                    'type': 'incorrect_partial_status',
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'amount': invoice_total,
                    'paid': float(total_paid),
                    'description': 'فاتورة مدفوعة بالكامل لكنها مظللة كجزئية'
                })
        
        print(f"تم العثور على {len(discrepancies)} تناقض محاسبي")
        
    except Exception as e:
        print(f"خطأ في البحث عن التناقضات: {e}")
    
    return discrepancies

def create_missing_payment_journal_entry(invoice):
    """إنشاء قيد محاسبي لتصفية المدينين للفاتورة المدفوعة"""
    try:
        _, _, _, JournalEntry, JournalLine, Account, _, get_saudi_now = get_models()
        if not JournalEntry:
            return False
        
        # الحصول على حساب المدينين الأصلي
        original_ar_code = get_original_ar_account_code(invoice.id)
        
        # إنشاء قيد تصفية
        amount = float(invoice.total_after_tax_discount)
        
        entry_number = f"JE-REC-FIX-{invoice.id}-{datetime.now().strftime('%Y%m%d')}"
        
        je = JournalEntry(
            entry_number=entry_number,
            date=get_saudi_now().date(),
            description=f"تصفية مدينين - تصحيح: {invoice.invoice_number}",
            status='posted',
            total_debit=amount,
            total_credit=amount,
            invoice_id=invoice.id,
            invoice_type='sales_payment'
        )
        
        db.session.add(je)
        db.session.flush()
        
        # حساب النقدية المناسب
        payment_method = (getattr(invoice, 'payment_method', '') or '').upper()
        if 'BANK' in payment_method or 'CARD' in payment_method or 'TRANSFER' in payment_method:
            cash_code = '1013'  # حساب البنك
        else:
            cash_code = '1011'  # الصندوق الرئيسي
        
        # إنشاء حسابات إذا لم تكن موجودة
        cash_account = Account.query.filter_by(code=cash_code).first()
        if not cash_account:
            cash_account = Account(
                code=cash_code,
                name='Cash/Bank Account',
                type='ASSET'
            )
            db.session.add(cash_account)
            db.session.flush()
        
        ar_account = Account.query.filter_by(code=original_ar_code).first()
        if not ar_account:
            ar_account = Account(
                code=original_ar_code,
                name='Accounts Receivable',
                type='ASSET'
            )
            db.session.add(ar_account)
            db.session.flush()
        
        # إضافة سطور القيد
        db.session.add(JournalLine(
            journal_id=je.id,
            line_no=1,
            account_id=cash_account.id,
            debit=amount,
            credit=0,
            description=f"استلام نقدية - تصحيح: {invoice.invoice_number}",
            line_date=get_saudi_now().date()
        ))
        
        db.session.add(JournalLine(
            journal_id=je.id,
            line_no=2,
            account_id=ar_account.id,
            debit=0,
            credit=amount,
            description=f"تصفية مدينين - تصحيح: {invoice.invoice_number}",
            line_date=get_saudi_now().date()
        ))
        
        db.session.commit()
        print(f"تم إنشاء قيد تصفية للفاتورة {invoice.invoice_number} بمبلغ {amount}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"خطأ في إنشاء قيد التصفية للفاتورة {getattr(invoice, 'invoice_number', 'Unknown')}: {e}")
        return False

def fix_incorrect_status_invoices():
    """تصحيح حالة الفواتير غير الصحيحة"""
    try:
        SalesInvoice, _, _, _, _, _, Payment, _ = get_models()
        if not SalesInvoice:
            return 0
        
        # تصحيح الفواتير الجزئية
        partial_invoices = SalesInvoice.query.filter(
            SalesInvoice.status == 'partial'
        ).all()
        
        fixed_count = 0
        
        for invoice in partial_invoices:
            total_paid = db.session.query(
                func.coalesce(func.sum(Payment.amount_paid), 0)
            ).filter(
                Payment.invoice_id == invoice.id,
                Payment.invoice_type == 'sales'
            ).scalar() or 0
            
            invoice_total = float(invoice.total_after_tax_discount)
            
            if abs(total_paid - invoice_total) < 0.01:
                # تصحيح الحالة إلى مدفوعة
                invoice.status = 'paid'
                db.session.commit()
                fixed_count += 1
                print(f"تم تصحيح حالة الفاتورة {invoice.invoice_number} إلى مدفوعة")
        
        print(f"تم تصحيح {fixed_count} فاتورة")
        return fixed_count
        
    except Exception as e:
        db.session.rollback()
        print(f"خطأ في تصحيح حالات الفواتير: {e}")
        return 0

def generate_accounting_report():
    """توليد تقرير محاسبي شامل"""
    try:
        SalesInvoice, _, _, JournalEntry, JournalLine, Account, _, get_saudi_now = get_models()
        if not SalesInvoice:
            return None
        
        print("جاري توليد التقرير المحاسبي...")
        
        # حساب إجمالي المدينين
        total_ar = 0
        ar_accounts = ['1020', '1021', '1022', '1130', '1140']
        
        for account_code in ar_accounts:
            account = Account.query.filter_by(code=account_code).first()
            if account:
                # حساب الرصيد من سجلات اليومية
                debit_total = db.session.query(
                    func.coalesce(func.sum(JournalLine.debit), 0)
                ).filter(
                    JournalLine.account_id == account.id
                ).scalar() or 0
                
                credit_total = db.session.query(
                    func.coalesce(func.sum(JournalLine.credit), 0)
                ).filter(
                    JournalLine.account_id == account.id
                ).scalar() or 0
                
                balance = float(debit_total - credit_total)
                total_ar += balance
                
                print(f"حساب {account_code}: الرصيد = {balance:.2f}")
        
        # مقارنة مع فواتير المبيعات غير المدفوعة
        unpaid_invoices = SalesInvoice.query.filter(
            SalesInvoice.status.in_(['unpaid', 'partial'])
        ).all()
        
        total_unpaid = sum(float(inv.total_after_tax_discount) for inv in unpaid_invoices)
        
        print(f"\nإجمالي رصيد المدينين: {total_ar:.2f}")
        print(f"إجمالي الفواتير غير المدفوعة: {total_unpaid:.2f}")
        print(f"الفرق: {abs(total_ar - total_unpaid):.2f}")
        
        return {
            'total_ar_balance': total_ar,
            'total_unpaid_invoices': total_unpaid,
            'difference': abs(total_ar - total_unpaid)
        }
        
    except Exception as e:
        print(f"خطأ في توليد التقرير: {e}")
        return None

def main():
    """الدالة الرئيسية لتنفيذ التصحيحات"""
    print("=== بدء تصحيح الأخطاء المحاسبية ===")
    print(f"التاريخ: {datetime.now()}")
    
    try:
        # التحقق من تحميل النماذج
        SalesInvoice, _, _, _, _, _, _, _ = get_models()
        if not SalesInvoice:
            print("خطأ: لم يتم تحميل النماذج المطلوبة")
            return False
        
        # 1. البحث عن التناقضات
        discrepancies = find_accounting_discrepancies()
        
        if discrepancies:
            print(f"\nتم العثور على {len(discrepancies)} تناقض محاسبي")
            
            # 2. تصحيح القيود المفقودة
            missing_entries = [d for d in discrepancies if d['type'] == 'missing_clearing_entry']
            print(f"\nعدد القيود المفقودة: {len(missing_entries)}")
            
            fixed_count = 0
            for discrepancy in missing_entries:
                invoice_id = discrepancy['invoice_id']
                invoice = SalesInvoice.query.get(invoice_id)
                
                if invoice:
                    success = create_missing_payment_journal_entry(invoice)
                    if success:
                        fixed_count += 1
            
            print(f"تم تصحيح {fixed_count} قيد مفقود")
            
            # 3. تصحيح حالات الفواتير
            status_fixed = fix_incorrect_status_invoices()
            
        else:
            print("لا توجد تناقضات محاسبية")
        
        # 4. توليد التقرير النهائي
        report = generate_accounting_report()
        
        print("\n=== اكتمال تصحيح الأخطاء المحاسبية ===")
        
        return True
        
    except Exception as e:
        print(f"خطأ عام في تصحيح الأخطاء: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()