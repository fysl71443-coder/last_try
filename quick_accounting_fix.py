#!/usr/bin/env python3
"""
سكريبت تصحيح سريع للمشكلة المحاسبية
تصحيح فاتورة INV-1765371221-pl4 وغيرها من الفواتير المدفوعة بدون قيود محاسبية
"""

import sys
sys.path.append('.')

from app import create_app
from models import (
    db, SalesInvoice, JournalEntry, JournalLine, Account, Payment, get_saudi_now
)
from sqlalchemy import func
from decimal import Decimal

def fix_missing_accounting_entries():
    """تصحيح القيود المحاسبية المفقودة"""
    
    app = create_app()
    with app.app_context():
        print("=== بدء تصحيح القيود المحاسبية المفقودة ===")
        
        # البحث عن الفواتير المدفوعة بدون قيود محاسبية
        paid_invoices = SalesInvoice.query.filter(
            SalesInvoice.status == 'paid'
        ).all()
        
        print(f"تم العثور على {len(paid_invoices)} فاتورة مدفوعة")
        
        fixed_count = 0
        
        for invoice in paid_invoices:
            # التحقق من وجود قيود محاسبية
            invoice_entries = JournalEntry.query.filter_by(
                invoice_id=invoice.id
            ).all()
            
            if len(invoice_entries) == 0:
                print(f"\nالفاتورة {invoice.invoice_number} مدفوعة لكن بدون قيود محاسبية!")
                
                # إنشاء القيود المحاسبية المفقودة
                success = create_accounting_entries_for_invoice(invoice)
                if success:
                    fixed_count += 1
                    print(f"تم إنشاء القيود المحاسبية للفاتورة {invoice.invoice_number}")
                else:
                    print(f"فشل إنشاء القيود المحاسبية للفاتورة {invoice.invoice_number}")
        
        print(f"\nتم تصحيح {fixed_count} فاتورة")
        
        # إنشاء تقرير
        generate_fix_report()
        
        print("=== اكتمال التصحيح ===")

def create_accounting_entries_for_invoice(invoice):
    """إنشاء القيود المحاسبية للفاتورة"""
    try:
        # تحديد نوع العميل
        customer_name = (invoice.customer_name or '').lower()
        if 'keeta' in customer_name or 'كيتا' in customer_name:
            ar_code = '1130'  # كيتا
            revenue_code = '4013'
        elif 'hunger' in customer_name or 'هنقر' in customer_name:
            ar_code = '1140'  # هنقرستيشن
            revenue_code = '4014'
        else:
            # عملاء المطعم المباشرين
            ar_code = '1021'  # عملاء المطعم
            revenue_code = '4012' if invoice.branch == 'place_india' else '4011'
        
        # حساب المبالغ
        total_amount = float(invoice.total_after_tax_discount)
        tax_amount = float(invoice.tax_amount or 0)
        revenue_amount = total_amount - tax_amount
        
        # إنشاء قيد المبيعات
        sales_entry_number = f"JE-SAL-{invoice.invoice_number}"
        
        # التحقق من عدم وجود القيد مسبقًا
        existing_entry = JournalEntry.query.filter_by(
            entry_number=sales_entry_number
        ).first()
        
        if existing_entry:
            print(f"القيد {sales_entry_number} موجود بالفعل")
            return True
        
        # إنشاء الحسابات إذا لم تكن موجودة
        ar_account = get_or_create_account(ar_code, 'Accounts Receivable', 'ASSET')
        revenue_account = get_or_create_account(revenue_code, 'Sales Revenue', 'REVENUE')
        vat_account = get_or_create_account('2024', 'VAT Output', 'LIABILITY')
        
        # إنشاء قيد المبيعات
        sales_je = JournalEntry(
            entry_number=sales_entry_number,
            date=invoice.date,
            description=f"مبيعات {invoice.invoice_number}",
            status='posted',
            total_debit=total_amount,
            total_credit=total_amount,
            invoice_id=invoice.id,
            invoice_type='sales'
        )
        
        db.session.add(sales_je)
        db.session.flush()
        
        # إضافة سطور القيد
        # المدين: حساب المدينين
        db.session.add(JournalLine(
            journal_id=sales_je.id,
            line_no=1,
            account_id=ar_account.id,
            debit=total_amount,
            credit=0,
            description=f"مدينين - {invoice.invoice_number}",
            line_date=invoice.date
        ))
        
        # الدائن: الإيرادات
        if revenue_amount > 0:
            db.session.add(JournalLine(
                journal_id=sales_je.id,
                line_no=2,
                account_id=revenue_account.id,
                debit=0,
                credit=revenue_amount,
                description=f"إيرادات - {invoice.invoice_number}",
                line_date=invoice.date
            ))
        
        # الدائن: ضريبة القيمة المضافة
        if tax_amount > 0:
            db.session.add(JournalLine(
                journal_id=sales_je.id,
                line_no=3,
                account_id=vat_account.id,
                debit=0,
                credit=tax_amount,
                description=f"ضريبة مخرجات - {invoice.invoice_number}",
                line_date=invoice.date
            ))
        
        # إذا كانت الفاتورة مدفوعة، إنشاء قيد التحصيل
        if invoice.status == 'paid':
            create_payment_entry(invoice, ar_account)
        
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"خطأ في إنشاء القيود المحاسبية: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_payment_entry(invoice, ar_account):
    """إنشاء قيد التحصيل"""
    try:
        # تحديد حساب النقدية
        payment_method = (invoice.payment_method or '').upper()
        if 'BANK' in payment_method or 'CARD' in payment_method or 'TRANSFER' in payment_method:
            cash_code = '1013'  # حساب البنك
            cash_name = 'Bank Account'
        else:
            cash_code = '1011'  # الصندوق الرئيسي
            cash_name = 'Main Cash'
        
        cash_account = get_or_create_account(cash_code, cash_name, 'ASSET')
        
        total_amount = float(invoice.total_after_tax_discount)
        
        # إنشاء قيد التحصيل
        payment_entry_number = f"JE-REC-{invoice.invoice_number}"
        
        payment_je = JournalEntry(
            entry_number=payment_entry_number,
            date=invoice.date,
            description=f"تحصيل {invoice.invoice_number}",
            status='posted',
            total_debit=total_amount,
            total_credit=total_amount,
            invoice_id=invoice.id,
            invoice_type='sales_payment'
        )
        
        db.session.add(payment_je)
        db.session.flush()
        
        # المدين: حساب النقدية
        db.session.add(JournalLine(
            journal_id=payment_je.id,
            line_no=1,
            account_id=cash_account.id,
            debit=total_amount,
            credit=0,
            description=f"نقدية محصلة - {invoice.invoice_number}",
            line_date=invoice.date
        ))
        
        # الدائن: تصفية حساب المدينين
        db.session.add(JournalLine(
            journal_id=payment_je.id,
            line_no=2,
            account_id=ar_account.id,
            debit=0,
            credit=total_amount,
            description=f"تصفية مدينين - {invoice.invoice_number}",
            line_date=invoice.date
        ))
        
        print(f"تم إنشاء قيد التحصيل: {payment_entry_number}")
        
    except Exception as e:
        print(f"خطأ في إنشاء قيد التحصيل: {e}")
        raise

def get_or_create_account(code, name, account_type):
    """الحصول على حساب أو إنشاؤه"""
    account = Account.query.filter_by(code=code).first()
    
    if not account:
        account = Account(
            code=code,
            name=name,
            type=account_type
        )
        db.session.add(account)
        db.session.flush()
        print(f"تم إنشاء الحساب {code}: {name}")
    
    return account

def generate_fix_report():
    """توليد تقرير عن التصحيحات"""
    try:
        app = create_app()
        with app.app_context():
            print("\n=== تقرير التصحيحات ===")
            
            # حساب رصيد المدينين بعد التصحيح
            ar_accounts = ['1020', '1021', '1022', '1130', '1140']
            total_ar = 0
            
            for account_code in ar_accounts:
                account = Account.query.filter_by(code=account_code).first()
                if account:
                    # حساب الرصيد
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
                    
                    if balance != 0:
                        print(f"حساب {account_code}: الرصيد = {balance:.2f}")
            
            # مقارنة مع الفواتير غير المدفوعة
            unpaid_invoices = SalesInvoice.query.filter(
                SalesInvoice.status.in_(['unpaid', 'partial'])
            ).all()
            
            total_unpaid = sum(float(inv.total_after_tax_discount) for inv in unpaid_invoices)
            
            print(f"\nإجمالي رصيد المدينين: {total_ar:.2f}")
            print(f"إجمالي الفواتير غير المدفوعة: {total_unpaid:.2f}")
            print(f"الفرق: {abs(total_ar - total_unpaid):.2f}")
            
            if abs(total_ar - total_unpaid) > 0.01:
                print("⚠️  تحذير: لا تزال هناك تناقضات محاسبية")
            else:
                print("✅ المطابقة المحاسبية صحيحة")
                
    except Exception as e:
        print(f"خطأ في توليد التقرير: {e}")

if __name__ == "__main__":
    fix_missing_accounting_entries()