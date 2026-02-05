# -*- coding: utf-8 -*-
"""
قواعد التحقق من شجرة الحسابات والقيود.

- كل حساب له رمز فريد (Account.code).
- الحسابات التجميعية لا تحمل أرصدة؛ فقط الحسابات الورقية (Leaf) تُستخدم في القيود.
- عند ربط حساب بعملية: الحساب موجود في الشجرة، وهو ورقي، ومناسب لنوع العملية.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple

# أنواع العمليات
TRANSACTION_TYPE_EXPENSE = "expense"
TRANSACTION_TYPE_SALES = "sales"
TRANSACTION_TYPE_PURCHASE = "purchase"
TRANSACTION_TYPE_SALARY = "salary"
TRANSACTION_TYPE_PAYMENT = "payment"
TRANSACTION_TYPE_MANUAL = "manual"

# رموز نقدية (صندوق / بنك) من الشجرة الرسمية
CASH_MAIN_CODES = {"1111", "1112", "1113"}
BANK_CODES = {"1121", "1122", "1123"}
CASH_AND_BANK_CODES = CASH_MAIN_CODES | BANK_CODES

# أنواع الحساب في الشجرة (من data.coa_new_tree)
ACCOUNT_TYPE_ASSET = "ASSET"
ACCOUNT_TYPE_LIABILITY = "LIABILITY"
ACCOUNT_TYPE_EQUITY = "EQUITY"
ACCOUNT_TYPE_REVENUE = "REVENUE"
ACCOUNT_TYPE_EXPENSE = "EXPENSE"
ACCOUNT_TYPE_COGS = "COGS"
ACCOUNT_TYPE_TAX = "TAX"


def _get_leaf_codes() -> set:
    try:
        from data.coa_new_tree import LEAF_CODES
        return set(LEAF_CODES) if LEAF_CODES else set()
    except Exception:
        return set()


def _get_coa_dict() -> dict:
    try:
        from data.coa_new_tree import build_coa_dict
        return build_coa_dict() or {}
    except Exception:
        return {}


def is_leaf_account(account_code: str) -> bool:
    """الحساب ورقي (يُستخدم في القيود) وليس تجميعياً."""
    code = (account_code or "").strip().upper()
    return code in _get_leaf_codes()


def get_account_type(account_code: str) -> Optional[str]:
    """نوع الحساب من الشجرة (ASSET, LIABILITY, REVENUE, EXPENSE, ...)."""
    code = (account_code or "").strip().upper()
    coa = _get_coa_dict()
    meta = coa.get(code, {})
    return (meta.get("type") or "").strip().upper() or None


def validate_account_for_transaction(
    account_code: str,
    transaction_type: str,
    role: str = "debit",
    payment_method: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    التحقق من أن الحساب صالح لهذه العملية ودوره (مدين/دائن).

    Returns:
        (ok: bool, error_message: str)
        إذا ok=True فإن error_message قد يكون فارغاً.
    """
    code = (account_code or "").strip().upper()
    if not code:
        return False, "رمز الحساب مطلوب"

    leaf_codes = _get_leaf_codes()
    coa = _get_coa_dict()
    if code not in coa:
        return False, "الحساب غير موجود في شجرة الحسابات"
    if code not in leaf_codes:
        return False, "الحساب تجميعي، لا يمكن ترحيل أرصدة عليه"

    acc_type = get_account_type(code) or ""

    tt = (transaction_type or "").strip().lower()
    role_lower = (role or "debit").strip().lower()

    # مصروف: مدين = حساب مصروف (EXPENSE/COGS)، دائن = صندوق أو بنك حسب طريقة الدفع
    if tt == TRANSACTION_TYPE_EXPENSE:
        if role_lower == "debit":
            if acc_type not in (ACCOUNT_TYPE_EXPENSE, ACCOUNT_TYPE_COGS):
                return False, "نوع الحساب لا يتوافق مع نوع العملية (مصروف)"
        else:
            pm = (payment_method or "CASH").strip().upper()
            if pm in ("BANK", "CARD", "VISA", "MASTERCARD", "TRANSFER"):
                if code not in BANK_CODES:
                    return False, "مصروف بنك يجب أن يكون الدائن حساب بنك (1121، 1122، 1123)"
            else:
                if code not in CASH_MAIN_CODES:
                    return False, "مصروف نقدي يجب أن يكون الدائن صندوقاً (1111، 1112، 1113)"
        return True, ""

    # مبيعات: مدين = صندوق/بنك أو عملاء، دائن = إيرادات
    if tt == TRANSACTION_TYPE_SALES:
        if role_lower == "debit":
            if acc_type != ACCOUNT_TYPE_ASSET:
                return False, "مدين المبيعات يجب أن يكون أصل (صندوق/بنك/عملاء)"
        else:
            if acc_type != ACCOUNT_TYPE_REVENUE and acc_type != ACCOUNT_TYPE_TAX:
                return False, "دائن المبيعات يجب أن يكون إيراداً أو ضريبة مخرجات"
        return True, ""

    # مشتريات: مدين = مخزون/مصروف/ضريبة مدخلات، دائن = مورد أو صندوق/بنك
    if tt == TRANSACTION_TYPE_PURCHASE:
        if role_lower == "debit":
            if acc_type not in (ACCOUNT_TYPE_ASSET, ACCOUNT_TYPE_EXPENSE, ACCOUNT_TYPE_COGS):
                return False, "مدين المشتريات يجب أن يكون أصل أو مصروف"
        else:
            if acc_type not in (ACCOUNT_TYPE_LIABILITY,) and code not in CASH_AND_BANK_CODES:
                return False, "دائن المشتريات يجب أن يكون مورداً أو صندوقاً/بنكاً"
        return True, ""

    # راتب: مدين = مصروف رواتب، دائن = رواتب مستحقة
    if tt == TRANSACTION_TYPE_SALARY:
        if role_lower == "debit":
            if acc_type not in (ACCOUNT_TYPE_EXPENSE,):
                return False, "مدين الراتب يجب أن يكون حساب مصروف رواتب"
        else:
            if acc_type != ACCOUNT_TYPE_LIABILITY:
                return False, "دائن الراتب يجب أن يكون التزاماً (رواتب مستحقة)"
        return True, ""

    # قيد يدوي: أي حساب ورقي
    if tt in (TRANSACTION_TYPE_PAYMENT, TRANSACTION_TYPE_MANUAL, ""):
        return True, ""

    return True, ""


def validate_journal_entry_balanced(
    lines: List[Dict[str, Any]],
    debit_key: str = "debit",
    credit_key: str = "credit",
    tolerance: float = 0.01,
) -> Tuple[bool, str]:
    """
    التحقق من أن القيد متوازن: مجموع المدين = مجموع الدائن.

    lines: قائمة مثل [{"account_code": "1111", "debit": 100, "credit": 0}, ...]
    """
    total_d = 0.0
    total_c = 0.0
    for ln in lines or []:
        try:
            total_d += float(ln.get(debit_key) or 0)
            total_c += float(ln.get(credit_key) or 0)
        except (TypeError, ValueError):
            pass
    diff = abs(round(total_d, 2) - round(total_c, 2))
    if diff > tolerance:
        return False, f"القيد غير متوازن: مدين {total_d:,.2f}، دائن {total_c:,.2f}، الفرق {diff:,.2f}"
    return True, ""


def validate_account_codes_in_coa(account_codes: List[str]) -> Tuple[bool, List[str]]:
    """
    التحقق من أن كل الرموز موجودة في الشجرة وهي ورقية.
    Returns (all_ok, list of error messages per code).
    """
    leaf = _get_leaf_codes()
    coa = _get_coa_dict()
    errors = []
    for code in account_codes or []:
        c = (code or "").strip().upper()
        if not c:
            continue
        if c not in coa:
            errors.append(f"الحساب {c} غير موجود في شجرة الحسابات")
        elif c not in leaf:
            errors.append(f"الحساب {c} تجميعي ولا يمكن الترحيل عليه")
    return len(errors) == 0, errors
