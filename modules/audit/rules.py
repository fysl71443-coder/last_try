# -*- coding: utf-8 -*-
"""
قواعد التدقيق — المدقق لا يثق بأحد.
كل قاعدة تُرجع قائمة ملاحظات (raw findings) بدون ترقيم؛ الترقيم والملخص في report_builder.
"""
from __future__ import annotations

from datetime import date
from typing import List, Dict, Any, Optional

# تصنيفات نوع الخلل
ISSUE_TYPES = {
    "unbalanced": "قيد غير متوازن",
    "tax": "ضريبة",
    "closing": "إقفال",
    "accounts": "حسابات",
    "fiscal_period": "فترات مالية",
    "opening_balance": "أرصدة افتتاحية",
    "reference": "مرجع مكسور",
    "missing_je": "فاتورة بدون قيد",
    "accounting": "اختلال محاسبي",
}
# موضع الخلل
PLACES = {
    "journal": "قيود اليومية",
    "sales": "المبيعات",
    "purchase": "المشتريات",
    "expense": "المصروفات",
    "salary": "الرواتب",
    "fiscal_years": "السنوات المالية",
    "chart_of_accounts": "شجرة الحسابات",
}
# سبب الخطأ
ROOT_CAUSES = {
    "manual_entry": "إدخال يدوي",
    "incomplete_setup": "إعداد غير مكتمل",
    "permissions": "ضعف ضبط الصلاحيات",
    "auto_post_failed": "ترحيل تلقائي فشل",
    "edit_after_close": "تعديل بعد الإقفال",
    "deleted_reference": "حذف مرجع",
    "late_entry": "إدخال متأخر بدون صلاحية",
    "no_fiscal_year": "عدم تعريف سنة مالية",
}
# طريقة التصحيح
CORRECTIONS = {
    "edit_entry": "تعديل القيد",
    "correcting_entry": "إنشاء قيد تصحيحي",
    "reverse_entry": "عكس القيد وإعادة تسجيله",
    "repost": "إعادة الترحيل",
    "recalc_tax": "إعادة احتساب الضريبة وترحيل قيد",
    "activate_account": "تفعيل الحساب أو تغيير الحساب وإعادة الترحيل",
    "define_fiscal": "تعريف سنة مالية تغطي التاريخ أو تصحيح التاريخ",
    "remap_or_void": "ربط بحساب صحيح أو إلغاء السطر",
    "backfill": "تشغيل ترحيل تلقائي أو إنشاء قيود من الفواتير",
    "fix_unbalanced": "معالجة القيود غير المتوازنة أعلاه",
}


def _raw(
    issue_type_ar: str,
    place_ar: str,
    ref_number: str,
    entry_date: Optional[date],
    description: str,
    difference_details: str,
    root_cause_ar: str,
    severity: str,
    correction_method: str,
    ref_type: Optional[str] = None,
    ref_id: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "issue_type_ar": issue_type_ar,
        "place_ar": place_ar,
        "ref_number": ref_number,
        "entry_date": entry_date,
        "description": description,
        "difference_details": difference_details,
        "root_cause_ar": root_cause_ar,
        "severity": severity,
        "correction_method": correction_method,
        "ref_type": ref_type,
        "ref_id": ref_id,
    }


def rule_unbalanced(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """قيود غير متوازنة: مدين ≠ دائن أو مجموع الأسطر ≠ رؤوس القيد."""
    from extensions import db
    from models import JournalEntry, JournalLine

    out: List[Dict[str, Any]] = []
    try:
        q = JournalEntry.query.filter_by(status="posted")
        if from_date:
            q = q.filter(JournalEntry.date >= from_date)
        if to_date:
            q = q.filter(JournalEntry.date <= to_date)
        for je in q.all():
            lines = JournalLine.query.filter_by(journal_id=je.id).all()
            sum_d = sum(float(l.debit or 0) for l in lines)
            sum_c = sum(float(l.credit or 0) for l in lines)
            td = float(je.total_debit or 0)
            tc = float(je.total_credit or 0)
            entry_no = getattr(je, "entry_number", "") or f"ID:{je.id}"
            entry_d = getattr(je, "date", None)
            if round(sum_d, 2) != round(sum_c, 2):
                diff = f"المدين: {sum_d:,.2f} | الدائن: {sum_c:,.2f} | الفرق: {abs(sum_d - sum_c):,.2f}"
                out.append(_raw(
                    ISSUE_TYPES["unbalanced"], PLACES["journal"], entry_no, entry_d,
                    "مجموع المدين لا يساوي الدائن", diff,
                    ROOT_CAUSES["manual_entry"], "high", "تعديل القيد أو إنشاء قيد تصحيحي",
                    "journal", je.id,
                ))
            elif round(td, 2) != round(tc, 2):
                diff = f"total_debit: {td:,.2f} | total_credit: {tc:,.2f}"
                out.append(_raw(
                    ISSUE_TYPES["unbalanced"], PLACES["journal"], entry_no, entry_d,
                    "رؤوس القيد (إجمالي مدين/دائن) غير متطابقة", diff,
                    ROOT_CAUSES["manual_entry"], "high", "مطابقة رؤوس القيد مع مجموع الأسطر",
                    "journal", je.id,
                ))
            elif round(sum_d, 2) != round(td, 2):
                diff = f"مجموع الأسطر مدين: {sum_d:,.2f} | إجمالي القيد: {td:,.2f}"
                out.append(_raw(
                    ISSUE_TYPES["unbalanced"], PLACES["journal"], entry_no, entry_d,
                    "مجموع الأسطر لا يطابق إجمالي القيد", diff,
                    ROOT_CAUSES["manual_entry"], "medium", "إعادة حساب وإصلاح القيد",
                    "journal", je.id,
                ))
    except Exception as e:
        out.append(_raw(
            ISSUE_TYPES["unbalanced"], PLACES["journal"], "-", None,
            f"خطأ في فحص القيود: {e}", "", ROOT_CAUSES["incomplete_setup"],
            "high", "مراجعة السجلات.",
        ))
    return out


def rule_empty_lines(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """قيد بدون سطور (منشور بلا أسطر)."""
    from models import JournalEntry, JournalLine

    out: List[Dict[str, Any]] = []
    try:
        q = JournalEntry.query.filter_by(status="posted")
        if from_date:
            q = q.filter(JournalEntry.date >= from_date)
        if to_date:
            q = q.filter(JournalEntry.date <= to_date)
        for je in q.all():
            cnt = JournalLine.query.filter_by(journal_id=je.id).count()
            if cnt == 0:
                entry_no = getattr(je, "entry_number", "") or f"ID:{je.id}"
                out.append(_raw(
                    ISSUE_TYPES["unbalanced"], PLACES["journal"], entry_no, getattr(je, "date", None),
                    "قيد بدون سطور (منشور بلا تفاصيل)", "عدد الأسطر: 0",
                    ROOT_CAUSES["manual_entry"], "high", "تعديل القيد أو إعادة إنشائه",
                    "journal", je.id,
                ))
    except Exception:
        pass
    return out


def rule_vat(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """ضريبة: فاتورة لها ضريبة لكن القيد لا يحتوي سطر ضريبة أو القيمة لا تطابق."""
    from models import (
        JournalEntry, JournalLine, Account,
        SalesInvoice, PurchaseInvoice, ExpenseInvoice,
    )

    out: List[Dict[str, Any]] = []
    place_map = {"sales": PLACES["sales"], "purchase": PLACES["purchase"], "expense": PLACES["expense"]}
    vat_output_code, vat_input_code = "2141", "1170"
    try:
        for je in JournalEntry.query.filter_by(status="posted", invoice_type="sales").filter(
            JournalEntry.invoice_id.isnot(None)
        ).limit(500).all():
            inv = SalesInvoice.query.get(je.invoice_id) if je.invoice_id else None
            if not inv:
                continue
            if from_date and getattr(inv, "date", None) and inv.date < from_date:
                continue
            if to_date and getattr(inv, "date", None) and inv.date > to_date:
                continue
            expected = float(getattr(inv, "tax_amount", 0) or 0)
            lines = JournalLine.query.filter_by(journal_id=je.id).all()
            recorded = 0.0
            for line in lines:
                acc = Account.query.get(line.account_id) if line.account_id else None
                if acc and (getattr(acc, "code", "") or "").strip() == vat_output_code:
                    recorded += float(line.credit or 0) - float(line.debit or 0)
            if expected > 0 and round(recorded, 2) == 0:
                out.append(_raw(
                    ISSUE_TYPES["tax"], place_map.get("sales", PLACES["journal"]),
                    getattr(je, "entry_number", "") or f"ID:{je.id}", getattr(je, "date", None),
                    "فاتورة بدون قيد ضريبة أو ضريبة غير مرحّلة",
                    f"قيمة الضريبة المتوقعة: {expected:,.2f} | المسجّلة في القيد: {recorded:,.2f}",
                    ROOT_CAUSES["incomplete_setup"], "medium", CORRECTIONS["recalc_tax"],
                    "journal", je.id,
                ))
            elif expected > 0 and round(abs(recorded - expected), 2) > 0.01:
                out.append(_raw(
                    ISSUE_TYPES["tax"], place_map.get("sales", PLACES["journal"]),
                    getattr(je, "entry_number", "") or f"ID:{je.id}", getattr(je, "date", None),
                    "ضريبة في القيد لا تطابق الفاتورة",
                    f"المتوقعة: {expected:,.2f} | المسجّلة: {recorded:,.2f} | الفرق: {abs(expected - recorded):,.2f}",
                    ROOT_CAUSES["incomplete_setup"], "medium", CORRECTIONS["recalc_tax"],
                    "journal", je.id,
                ))

        for je in JournalEntry.query.filter(
            JournalEntry.status == "posted",
            JournalEntry.invoice_type.in_(["purchase", "expense"]),
            JournalEntry.invoice_id.isnot(None),
        ).limit(500).all():
            inv = PurchaseInvoice.query.get(je.invoice_id) if je.invoice_type == "purchase" else ExpenseInvoice.query.get(je.invoice_id)
            if not inv:
                continue
            if from_date and getattr(inv, "date", None) and inv.date < from_date:
                continue
            if to_date and getattr(inv, "date", None) and inv.date > to_date:
                continue
            expected = float(getattr(inv, "tax_amount", 0) or 0)
            lines = JournalLine.query.filter_by(journal_id=je.id).all()
            recorded = 0.0
            for line in lines:
                acc = Account.query.get(line.account_id) if line.account_id else None
                if acc and (getattr(acc, "code", "") or "").strip() == vat_input_code:
                    recorded += float(line.debit or 0) - float(line.credit or 0)
            if expected > 0 and round(recorded, 2) == 0:
                out.append(_raw(
                    ISSUE_TYPES["tax"], place_map.get(je.invoice_type, PLACES["journal"]),
                    getattr(je, "entry_number", "") or f"ID:{je.id}", getattr(je, "date", None),
                    "فاتورة بدون قيد ضريبة أو ضريبة غير مرحّلة",
                    f"قيمة الضريبة المتوقعة: {expected:,.2f} | المسجّلة في القيد: {recorded:,.2f}",
                    ROOT_CAUSES["incomplete_setup"], "medium", CORRECTIONS["recalc_tax"],
                    "journal", je.id,
                ))
            elif expected > 0 and round(abs(recorded - expected), 2) > 0.01:
                out.append(_raw(
                    ISSUE_TYPES["tax"], place_map.get(je.invoice_type, PLACES["journal"]),
                    getattr(je, "entry_number", "") or f"ID:{je.id}", getattr(je, "date", None),
                    "ضريبة في القيد لا تطابق الفاتورة",
                    f"المتوقعة: {expected:,.2f} | المسجّلة: {recorded:,.2f} | الفرق: {abs(expected - recorded):,.2f}",
                    ROOT_CAUSES["incomplete_setup"], "medium", CORRECTIONS["recalc_tax"],
                    "journal", je.id,
                ))
    except Exception as e:
        out.append(_raw(
            ISSUE_TYPES["tax"], PLACES["journal"], "-", None,
            f"خطأ في فحص الضريبة: {e}", "", ROOT_CAUSES["incomplete_setup"], "medium", "مراجعة السجلات.",
        ))
    return out


def rule_fiscal_period(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """قيد بتاريخ خارج سنة مالية."""
    from models import JournalEntry
    from services.gl_truth import get_fiscal_year_for_date

    out: List[Dict[str, Any]] = []
    try:
        q = JournalEntry.query.filter_by(status="posted")
        if from_date:
            q = q.filter(JournalEntry.date >= from_date)
        if to_date:
            q = q.filter(JournalEntry.date <= to_date)
        for je in q.limit(500).all():
            d = getattr(je, "date", None)
            if d and not get_fiscal_year_for_date(d):
                entry_no = getattr(je, "entry_number", "") or f"ID:{je.id}"
                out.append(_raw(
                    ISSUE_TYPES["fiscal_period"], PLACES["fiscal_years"], entry_no, d,
                    "قيد داخل فترة غير مغطاة بسنة مالية",
                    f"التاريخ: {d} | لا توجد سنة مالية تحتوي هذا التاريخ",
                    ROOT_CAUSES["no_fiscal_year"], "medium", CORRECTIONS["define_fiscal"],
                    "journal", je.id,
                ))
    except Exception:
        pass
    return out


def rule_accounts(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """حساب غير موجود أو حساب لا يقبل قيوداً (غير نشط)."""
    from models import JournalEntry, JournalLine, Account

    out: List[Dict[str, Any]] = []
    seen_je: set = set()
    try:
        q = JournalLine.query.join(JournalEntry).filter(JournalEntry.status == "posted")
        if from_date:
            q = q.filter(JournalEntry.date >= from_date)
        if to_date:
            q = q.filter(JournalEntry.date <= to_date)
        for line in q.limit(1000).all():
            je = getattr(line, "journal", None) or JournalEntry.query.get(line.journal_id)
            if not je or je.id in seen_je:
                continue
            acc = Account.query.get(line.account_id) if line.account_id else None
            entry_no = getattr(je, "entry_number", "") or f"ID:{je.id}"
            entry_d = getattr(je, "date", None)
            if not acc:
                out.append(_raw(
                    ISSUE_TYPES["accounts"], PLACES["chart_of_accounts"], entry_no, entry_d,
                    "سطر قيد يشير لحساب غير موجود", f"account_id: {line.account_id}",
                    ROOT_CAUSES["deleted_reference"], "high", CORRECTIONS["remap_or_void"],
                    "journal", je.id,
                ))
                seen_je.add(je.id)
                continue
            if getattr(acc, "allow_posting", True) is False:
                out.append(_raw(
                    ISSUE_TYPES["accounts"], PLACES["chart_of_accounts"], entry_no, entry_d,
                    "قيد على حساب متوقف أو لا يقبل قيوداً", f"الحساب: {getattr(acc, 'code', '')}",
                    ROOT_CAUSES["permissions"], "medium", CORRECTIONS["activate_account"],
                    "journal", je.id,
                ))
                seen_je.add(je.id)
    except Exception:
        pass
    return out


def rule_global_balance(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """اختلال محاسبي عام: إجمالي مدين ≠ دائن في كل القيود المنشورة."""
    from extensions import db
    from sqlalchemy import func
    from models import JournalEntry, JournalLine

    out: List[Dict[str, Any]] = []
    try:
        q = db.session.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(JournalEntry.status == "posted")
        if from_date:
            q = q.filter(JournalEntry.date >= from_date)
        if to_date:
            q = q.filter(JournalEntry.date <= to_date)
        row = q.first()
        if row:
            total_d, total_c = float(row[0] or 0), float(row[1] or 0)
            if abs(round(total_d - total_c, 2)) > 0.01:
                out.append(_raw(
                    ISSUE_TYPES["accounting"], PLACES["journal"], "—", None,
                    "إجمالي المدين لا يساوي إجمالي الدائن في كل القيود المنشورة",
                    f"المدين: {total_d:,.2f} | الدائن: {total_c:,.2f} | الفرق: {abs(total_d - total_c):,.2f}",
                    ROOT_CAUSES["manual_entry"], "high", CORRECTIONS["fix_unbalanced"],
                ))
    except Exception as e:
        out.append(_raw(
            ISSUE_TYPES["accounting"], PLACES["journal"], "—", None,
            f"خطأ في التحقق من التوازن العام: {e}", "", ROOT_CAUSES["incomplete_setup"],
            "high", "مراجعة قاعدة البيانات.",
        ))
    return out


def rule_cash_credit_balance(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """حسابات نقدية (صندوق/بنك) ذات رصيد دائن — غير طبيعي ويستدعي مراجعة."""
    from extensions import db
    from sqlalchemy import func
    from models import Account, JournalEntry, JournalLine

    CASH_CODES = ["1111", "1112", "1121"]
    out: List[Dict[str, Any]] = []
    try:
        end_d = to_date or date.today()
        for code in CASH_CODES:
            acc = Account.query.filter_by(code=code).first()
            if not acc:
                continue
            q = db.session.query(
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).filter(
                JournalLine.account_id == acc.id,
                JournalLine.line_date <= end_d,
                JournalEntry.status == "posted",
            )
            row = q.first()
            if row:
                d, c = float(row[0] or 0), float(row[1] or 0)
                balance = round(d - c, 2)
                if balance < -0.01:
                    out.append(
                        _raw(
                            ISSUE_TYPES["accounting"],
                            PLACES["journal"],
                            code,
                            end_d,
                            "حساب نقدي (صندوق/بنك) برصيد دائن — يفضّل أن يكون الرصيد مديناً",
                            f"الحساب {code} | مدين: {d:,.2f} | دائن: {c:,.2f} | الرصيد: {balance:,.2f}",
                            ROOT_CAUSES["manual_entry"],
                            "medium",
                            "مراجعة القيود المرتبطة بهذا الحساب وتصحيح الترحيل",
                            "account",
                            acc.id,
                        )
                    )
    except Exception:
        pass
    return out


def rule_journal_account_not_in_coa(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """سطر قيد يستخدم حساباً غير موجود في شجرة الحسابات الرسمية — قيد قد يكون خاطئاً."""
    from extensions import db
    from models import Account, JournalEntry, JournalLine

    out: List[Dict[str, Any]] = []
    try:
        try:
            from data.coa_new_tree import build_coa_dict
            coa = build_coa_dict()
            allowed_codes = {str(k).strip().upper() for k in (coa.keys() if coa else [])}
        except Exception:
            allowed_codes = set()
        if not allowed_codes:
            return out
        q = (
            db.session.query(JournalLine, JournalEntry.entry_number, JournalEntry.date, Account.code)
            .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .filter(JournalEntry.status == "posted")
        )
        if from_date:
            q = q.filter(JournalLine.line_date >= from_date)
        if to_date:
            q = q.filter(JournalLine.line_date <= to_date)
        seen_je: set = set()
        for jl, entry_no, entry_d, acc_code in q.limit(500).all():
            code = (acc_code or "").strip().upper()
            if code and code not in allowed_codes:
                key = (getattr(jl, "journal_id"), code)
                if key not in seen_je:
                    seen_je.add(key)
                    out.append(
                        _raw(
                            ISSUE_TYPES["accounts"],
                            PLACES["journal"],
                            (entry_no or f"JE:{jl.journal_id}"),
                            entry_d,
                            "قيد يستخدم حساباً غير موجود في شجرة الحسابات الرسمية",
                            f"الحساب {code} غير في الشجرة — راجع التطابق مع دليل الحسابات",
                            ROOT_CAUSES["manual_entry"],
                            "high",
                            "تصحيح الحساب في سطر القيد أو إضافة الحساب للشجرة إن كان صحيحاً",
                            "journal",
                            jl.journal_id,
                        )
                    )
    except Exception:
        pass
    return out


def rule_broken_references(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """قيود تشير لفواتير/رواتب محذوفة."""
    from extensions import db
    from models import JournalEntry, SalesInvoice, PurchaseInvoice, ExpenseInvoice, Salary

    out: List[Dict[str, Any]] = []
    try:
        q = JournalEntry.query.filter(JournalEntry.status == "posted").filter(
            (JournalEntry.invoice_id.isnot(None)) | (JournalEntry.salary_id.isnot(None))
        )
        if from_date:
            q = q.filter(JournalEntry.date >= from_date)
        if to_date:
            q = q.filter(JournalEntry.date <= to_date)
        for je in q.limit(500).all():
            entry_no = getattr(je, "entry_number", "") or f"ID:{je.id}"
            entry_d = getattr(je, "date", None)
            if je.invoice_id and je.invoice_type:
                if je.invoice_type == "sales" and not db.session.get(SalesInvoice, je.invoice_id):
                    out.append(_raw(
                        ISSUE_TYPES["reference"], PLACES["sales"], entry_no, entry_d,
                        "قيد يشير لفاتورة مبيعات محذوفة أو غير موجودة", f"invoice_id: {je.invoice_id}",
                        ROOT_CAUSES["deleted_reference"], "medium", "ربط القيد بفاتورة صحيحة أو تحويل لقيد يدوي.",
                        "journal", je.id,
                    ))
                elif je.invoice_type == "purchase" and not db.session.get(PurchaseInvoice, je.invoice_id):
                    out.append(_raw(
                        ISSUE_TYPES["reference"], PLACES["purchase"], entry_no, entry_d,
                        "قيد يشير لفاتورة مشتريات محذوفة أو غير موجودة", f"invoice_id: {je.invoice_id}",
                        ROOT_CAUSES["deleted_reference"], "medium", "ربط القيد بفاتورة صحيحة أو تحويل لقيد يدوي.",
                        "journal", je.id,
                    ))
                elif je.invoice_type == "expense" and not db.session.get(ExpenseInvoice, je.invoice_id):
                    out.append(_raw(
                        ISSUE_TYPES["reference"], PLACES["expense"], entry_no, entry_d,
                        "قيد يشير لفاتورة مصروفات محذوفة أو غير موجودة", f"invoice_id: {je.invoice_id}",
                        ROOT_CAUSES["deleted_reference"], "medium", "ربط القيد بفاتورة صحيحة أو تحويل لقيد يدوي.",
                        "journal", je.id,
                    ))
            if je.salary_id and not db.session.get(Salary, je.salary_id):
                out.append(_raw(
                    ISSUE_TYPES["reference"], PLACES["salary"], entry_no, entry_d,
                    "قيد يشير لراتب محذوف أو غير موجود", f"salary_id: {je.salary_id}",
                    ROOT_CAUSES["deleted_reference"], "medium", "ربط القيد براتب صحيح أو تحويل لقيد يدوي.",
                    "journal", je.id,
                ))
    except Exception as e:
        out.append(_raw(
            ISSUE_TYPES["reference"], PLACES["journal"], "-", None,
            f"خطأ في فحص المراجع: {e}", "", ROOT_CAUSES["incomplete_setup"], "medium", "مراجعة السجلات.",
        ))
    return out


def rule_missing_je(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """فواتير بدون قيد يومية مرتبط."""
    from models import JournalEntry, SalesInvoice, PurchaseInvoice, ExpenseInvoice

    out: List[Dict[str, Any]] = []
    try:
        sales_without = []
        for inv in SalesInvoice.query.limit(1000).all():
            if from_date and getattr(inv, "date", None) and inv.date < from_date:
                continue
            if to_date and getattr(inv, "date", None) and inv.date > to_date:
                continue
            if not JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type="sales", status="posted").first():
                sales_without.append((getattr(inv, "invoice_number", inv.id), getattr(inv, "date", None)))
        if sales_without:
            sample = sales_without[:5]
            ref_nos = "، ".join(str(s[0]) for s in sample) + (" …" if len(sales_without) > 5 else "")
            out.append(_raw(
                ISSUE_TYPES["missing_je"], PLACES["sales"], ref_nos, sample[0][1] if sample else None,
                f"عدد {len(sales_without)} فاتورة مبيعات بدون قيد يومية مرتبط",
                f"عدد الفواتير: {len(sales_without)} | عينة: {ref_nos}",
                ROOT_CAUSES["auto_post_failed"], "medium", CORRECTIONS["backfill"],
            ))
        purch_without = []
        for inv in PurchaseInvoice.query.limit(1000).all():
            if from_date and getattr(inv, "date", None) and inv.date < from_date:
                continue
            if to_date and getattr(inv, "date", None) and inv.date > to_date:
                continue
            if not JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type="purchase", status="posted").first():
                purch_without.append((getattr(inv, "invoice_number", inv.id), getattr(inv, "date", None)))
        if purch_without:
            sample = purch_without[:5]
            ref_nos = "، ".join(str(s[0]) for s in sample) + (" …" if len(purch_without) > 5 else "")
            out.append(_raw(
                ISSUE_TYPES["missing_je"], PLACES["purchase"], ref_nos, sample[0][1] if sample else None,
                f"عدد {len(purch_without)} فاتورة مشتريات بدون قيد يومية مرتبط",
                f"عدد الفواتير: {len(purch_without)} | عينة: {ref_nos}",
                ROOT_CAUSES["auto_post_failed"], "medium", CORRECTIONS["backfill"],
            ))
        exp_without = []
        for inv in ExpenseInvoice.query.limit(1000).all():
            if from_date and getattr(inv, "date", None) and inv.date < from_date:
                continue
            if to_date and getattr(inv, "date", None) and inv.date > to_date:
                continue
            if not JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type="expense", status="posted").first():
                exp_without.append((getattr(inv, "invoice_number", inv.id), getattr(inv, "date", None)))
        if exp_without:
            sample = exp_without[:5]
            ref_nos = "، ".join(str(s[0]) for s in sample) + (" …" if len(exp_without) > 5 else "")
            out.append(_raw(
                ISSUE_TYPES["missing_je"], PLACES["expense"], ref_nos, sample[0][1] if sample else None,
                f"عدد {len(exp_without)} فاتورة مصروفات بدون قيد يومية مرتبط",
                f"عدد الفواتير: {len(exp_without)} | عينة: {ref_nos}",
                ROOT_CAUSES["auto_post_failed"], "medium", CORRECTIONS["backfill"],
            ))
    except Exception as e:
        out.append(_raw(
            ISSUE_TYPES["missing_je"], PLACES["journal"], "-", None,
            f"خطأ في فحص الفواتير: {e}", "", ROOT_CAUSES["incomplete_setup"], "medium", "مراجعة السجلات.",
        ))
    return out


def rule_closed_period_entries(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """قيود داخل فترة مغلقة (سنة مغلقة تحتوي قيوداً منشورة)."""
    from models import JournalEntry, FiscalYear

    out: List[Dict[str, Any]] = []
    try:
        for fy in FiscalYear.query.filter(FiscalYear.status.in_(["closed", "locked"])).all():
            q = JournalEntry.query.filter(
                JournalEntry.status == "posted",
                JournalEntry.date >= fy.start_date,
                JournalEntry.date <= fy.end_date,
            )
            if from_date:
                q = q.filter(JournalEntry.date >= from_date)
            if to_date:
                q = q.filter(JournalEntry.date <= to_date)
            entries_in_closed = q.limit(500).all()
            if not entries_in_closed:
                continue
            sample = entries_in_closed[:3]
            ref_nos = "، ".join(getattr(je, "entry_number", "") or f"ID:{je.id}" for je in sample) + (" …" if len(entries_in_closed) > 3 else "")
            out.append(_raw(
                ISSUE_TYPES["closing"], PLACES["fiscal_years"], ref_nos, sample[0].date if sample else None,
                "قيود داخل فترة مغلقة",
                f"السنة {getattr(fy, 'year', '')} مغلقة | عدد القيود في الفترة: {len(entries_in_closed)} | عينة: {ref_nos}",
                ROOT_CAUSES["late_entry"], "high", CORRECTIONS["reverse_entry"],
                "journal", sample[0].id if sample else None,
            ))
    except Exception:
        pass
    return out


def rule_supplier_overpayment(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """مدفوعات مورد تتجاوز إجمالي فواتيره (ربط خاطئ أو دفعات مكررة)."""
    from extensions import db
    from models import PurchaseInvoice, Payment, Account, JournalEntry, JournalLine
    from sqlalchemy import func

    out: List[Dict[str, Any]] = []
    try:
        q = PurchaseInvoice.query
        if from_date:
            q = q.filter(PurchaseInvoice.date >= from_date)
        if to_date:
            q = q.filter(PurchaseInvoice.date <= to_date)
        # تجميع حسب المورد (supplier_id أو supplier_name)
        invs = q.all()
        by_supplier: Dict[Any, List[Any]] = {}
        for inv in invs:
            key = (inv.supplier_id, (inv.supplier_name or "").strip())
            by_supplier.setdefault(key, []).append(inv)
        acc_2111 = Account.query.filter_by(code="2111").first()
        for (sid, sname), list_inv in by_supplier.items():
            inv_ids = [i.id for i in list_inv]
            total_inv = sum(float(i.total_after_tax_discount or 0) for i in list_inv)
            # مصدر الحقيقة ككشف المورد: قيد 2111 مرتبط بالفاتورة، وإلا جدول الدفعات (لا نجمع الاثنين)
            paid_per_inv = {}
            for inv in list_inv:
                p_je = 0.0
                if acc_2111:
                    p_je = float(
                        db.session.query(func.coalesce(func.sum(JournalLine.debit), 0))
                        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
                        .filter(
                            JournalLine.account_id == acc_2111.id,
                            JournalLine.invoice_id == inv.id,
                            JournalLine.invoice_type == "purchase",
                            JournalEntry.status == "posted",
                        )
                        .scalar() or 0
                    )
                if p_je < 0.01:
                    p_je = float(
                        db.session.query(func.coalesce(func.sum(Payment.amount_paid), 0)).filter(
                            Payment.invoice_type == "purchase", Payment.invoice_id == inv.id
                        ).scalar() or 0
                    )
                paid_per_inv[inv.id] = round(p_je, 2)
            total_paid = round(sum(paid_per_inv.values()), 2)
            total_inv_r = round(total_inv, 2)
            if total_paid > total_inv_r + 0.01:
                label = sname or (f"supplier_id:{sid}" if sid else "?")
                out.append(
                    _raw(
                        ISSUE_TYPES["accounting"],
                        PLACES["purchase"],
                        label,
                        list_inv[0].date if list_inv else None,
                        "مدفوعات المورد تتجاوز إجمالي فواتيره",
                        f"إجمالي فواتير: {total_inv_r:,.2f} | إجمالي مدفوع: {total_paid:,.2f} | زيادة: {total_paid - total_inv_r:,.2f}",
                        ROOT_CAUSES["manual_entry"],
                        "high",
                        "مراجعة ربط الدفعات بالفواتير أو تصحيح القيود",
                        "supplier",
                        sid,
                    )
                )
    except Exception:
        pass
    return out


def run_all_rules(from_date: Optional[date], to_date: Optional[date]) -> List[Dict[str, Any]]:
    """تشغيل كل قواعد التدقيق وإرجاع قائمة واحدة من الملاحظات (بدون ترقيم)."""
    raw: List[Dict[str, Any]] = []
    raw.extend(rule_unbalanced(from_date, to_date))
    raw.extend(rule_empty_lines(from_date, to_date))
    raw.extend(rule_vat(from_date, to_date))
    raw.extend(rule_fiscal_period(from_date, to_date))
    raw.extend(rule_accounts(from_date, to_date))
    raw.extend(rule_global_balance(from_date, to_date))
    raw.extend(rule_cash_credit_balance(from_date, to_date))
    raw.extend(rule_journal_account_not_in_coa(from_date, to_date))
    raw.extend(rule_broken_references(from_date, to_date))
    raw.extend(rule_missing_je(from_date, to_date))
    raw.extend(rule_closed_period_entries(from_date, to_date))
    raw.extend(rule_supplier_overpayment(from_date, to_date))
    return raw
