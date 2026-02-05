# -*- coding: utf-8 -*-
"""
مصدر الحقيقة: قيود اليومية (GL-Centric).

- لا تقرير، لا فاتورة، لا رصيد، لا إقفال — بدون المرور عبر قيود اليومية.
- التحكم الزمني = السنوات المالية فقط.
- أي قيد يومية يمر بـ 7 بوابات تحقق قبل القبول.
"""

from __future__ import annotations

import time
import logging
from datetime import date
from typing import List, Optional, Tuple, Any, Dict

logger = logging.getLogger(__name__)

# تتبّع فشل sync_ledger_from_journal المتكرر للتنبيه (يُصفّر عند النجاح)
_sync_ledger_failure_count = 0
_sync_ledger_last_failure_ts: Optional[float] = None
SYNC_LEDGER_ALERT_THRESHOLD = 3  # تنبيه بعد هذا العدد من الفشل المتتالي
SYNC_LEDGER_ALERT_WINDOW_SEC = 300  # نافذة زمنية (ثانية) لاعتبار الفشل "متكرراً"

# Lazy imports inside functions to avoid circular import / app context


def get_fiscal_year_for_date(d: date):
    """السنة المالية التي يقع فيها التاريخ (أول سنة تطابق start_date <= d <= end_date)."""
    from models import FiscalYear
    fy = FiscalYear.query.filter(
        FiscalYear.start_date <= d,
        FiscalYear.end_date >= d
    ).order_by(FiscalYear.start_date.desc()).first()
    return fy


def is_in_exceptional_period(d: date) -> bool:
    """هل التاريخ داخل فترة استثنائية مفتوحة؟"""
    from models import FiscalYearExceptionalPeriod
    q = FiscalYearExceptionalPeriod.query.filter(
        FiscalYearExceptionalPeriod.start_date <= d,
        FiscalYearExceptionalPeriod.end_date >= d
    )
    return q.first() is not None


def is_period_open_for_date(d: date) -> Tuple[bool, Optional[str]]:
    """
    هل الفترة مفتوحة للقيود/الفواتير في هذا التاريخ؟
    Returns (ok, error_message).
    - 1️⃣ السنة المالية موجودة
    - 2️⃣ التاريخ داخل الفترة
    - 3️⃣ الفترة مفتوحة (أو داخل فترة استثنائية)
    """
    fy = get_fiscal_year_for_date(d)
    if not fy:
        return False, "لا توجد سنة مالية تغطي هذا التاريخ."
    if d < fy.start_date or d > fy.end_date:
        return False, "التاريخ خارج نطاق السنة المالية."
    status = (fy.status or "").strip().lower()
    if status == "closed":
        if is_in_exceptional_period(d):
            return True, None
        return False, "السنة المالية مغلقة لهذه الفترة."
    if status == "locked":
        if is_in_exceptional_period(d):
            return True, None
        return False, "السنة المالية مقفلة."
    if status == "partial" and fy.closed_until:
        if d <= fy.closed_until:
            if is_in_exceptional_period(d):
                return True, None
            return False, "الفترة مقفلة حتى " + str(fy.closed_until)
    return True, None


def can_mutate_journal(entry) -> Tuple[bool, Optional[str]]:
    """هل يُسمح بتعديل/حذف هذا القيد؟ (الفترة مفتوحة لتاريخ القيد)."""
    entry_date = getattr(entry, "date", None)
    if not entry_date:
        return False, "القيد بدون تاريخ."
    return is_period_open_for_date(entry_date)


def _get_account(account_id: int):
    from models import Account
    return Account.query.get(account_id) if account_id else None


def _account_allows_posting(acc) -> bool:
    if not acc:
        return False
    # نشط = موجود وغير محذوف. allow_posting يسمح بالقيود المباشرة.
    if getattr(acc, "allow_posting", True) is False:
        return False
    if getattr(acc, "is_control", False):
        return False  # حساب تحكم لا يُقيد عليه مباشرة إلا عبر عمليات محددة
    return True


def validate_journal_gates(
    entry_date: date,
    lines: List[Any],
    allow_no_fiscal_year: bool = False,
) -> List[str]:
    """
    البوابات السبع لقيود اليومية.
    lines: list of dicts with account_id, debit, credit (or objects with .account_id, .debit, .credit).
    Returns list of error messages (empty = passed).
    """
    errors: List[str] = []

    # 1️⃣ السنة المالية موجودة
    fy = get_fiscal_year_for_date(entry_date)
    if not fy:
        if not allow_no_fiscal_year:
            errors.append("لا توجد سنة مالية تغطي تاريخ القيد.")
        # إذا سمحنا بعدم وجود سنة نكمل بقية البوابات

    # 2️⃣ التاريخ داخل الفترة
    if fy:
        if entry_date < fy.start_date or entry_date > fy.end_date:
            errors.append("تاريخ القيد خارج نطاق السنة المالية.")

    # 3️⃣ الفترة مفتوحة
    ok, msg = is_period_open_for_date(entry_date)
    if not ok and fy:
        errors.append(msg or "الفترة مغلقة لهذا التاريخ.")

    # تجميع المدين والدائن من الأسطر
    total_debit = 0.0
    total_credit = 0.0
    for line in lines or []:
        if hasattr(line, "debit"):
            total_debit += float(getattr(line, "debit", 0) or 0)
            total_credit += float(getattr(line, "credit", 0) or 0)
        else:
            total_debit += float(line.get("debit", 0) or 0)
            total_credit += float(line.get("credit", 0) or 0)

    # 5️⃣ المدين = الدائن
    if round(total_debit, 2) != round(total_credit, 2):
        errors.append(f"القيد غير متوازن: مدين={total_debit:.2f}، دائن={total_credit:.2f}.")

    # 4️⃣ و 6️⃣ الحساب نشط ونوع الحساب يسمح بالقيد
    for i, line in enumerate(lines or []):
        acc_id = line.get("account_id") if isinstance(line, dict) else getattr(line, "account_id", None)
        if not acc_id:
            errors.append(f"سطر {i+1}: بدون حساب.")
            continue
        acc = _get_account(int(acc_id))
        if not acc:
            errors.append(f"سطر {i+1}: الحساب غير موجود.")
            continue
        if not _account_allows_posting(acc):
            errors.append(f"سطر {i+1}: الحساب '{getattr(acc, 'code', '')}' لا يقبل قيوداً أو هو حساب تحكم.")
            continue
        code = (getattr(acc, "code") or "").strip().upper()
        if code and not is_leaf_account(code):
            errors.append(f"سطر {i+1}: الحساب '{code}' تجميعي؛ لا يمكن ترحيل أرصدة عليه. استخدم حساباً ورقياً فقط.")

    # 7️⃣ لا تلاعب زمني (Backdating): يمكن إضافة تحقق إضافي لاحقاً (مثلاً ألا يتجاوز التاريخ X أيام في الماضي إلا بصلاحية).
    # حالياً لا نطبق قيداً إضافياً.

    return errors


def can_create_invoice_on_date(d: date) -> Tuple[bool, Optional[str]]:
    """استخدام قبل إنشاء فاتورة مبيعات/مشتريات/مصروف أو راتب: هل التاريخ في فترة مفتوحة؟"""
    return is_period_open_for_date(d)


# ---- مصدر الحقيقة للأرصدة: قيود اليومية المرحّلة فقط ----

def get_account_debit_credit_from_gl(account_id: int, asof_date: date) -> Tuple[float, float]:
    """مجموع مدين ودائن حساب من قيود اليومية المرحّلة فقط (مصدر الحقيقة)."""
    from sqlalchemy import func
    from app import db
    from models import JournalLine, JournalEntry
    debit = db.session.query(func.coalesce(func.sum(JournalLine.debit), 0)).join(
        JournalEntry, JournalLine.journal_id == JournalEntry.id
    ).filter(
        JournalLine.account_id == account_id,
        JournalLine.line_date <= asof_date,
        JournalEntry.status == 'posted'
    ).scalar() or 0
    credit = db.session.query(func.coalesce(func.sum(JournalLine.credit), 0)).join(
        JournalEntry, JournalLine.journal_id == JournalEntry.id
    ).filter(
        JournalLine.account_id == account_id,
        JournalLine.line_date <= asof_date,
        JournalEntry.status == 'posted'
    ).scalar() or 0
    return float(debit), float(credit)


def get_account_balance_from_gl_by_code(account_code: str, asof_date: date) -> Tuple[float, str]:
    """رصيد حساب من القيود المرحّلة فقط. يرجع (الرصيد، نوع الحساب)."""
    from models import Account
    acc = Account.query.filter_by(code=(account_code or '').strip()).first()
    if not acc:
        return 0.0, ''
    d, c = get_account_debit_credit_from_gl(acc.id, asof_date)
    t = (acc.type or '').upper()
    if t in ('LIABILITY', 'EQUITY'):
        return round(c - d, 2), t
    return round(d - c, 2), t


def sum_gl_by_account_code_and_date_range(
    account_codes: List[str],
    start_date: date,
    end_date: date,
    credit_minus_debit: bool = True,
) -> float:
    """مجموع (دائن - مدين) أو (مدين - دائن) لحساب/حسابات في نطاق تاريخ من القيود المرحّلة فقط."""
    from sqlalchemy import func, and_
    from app import db
    from models import JournalLine, JournalEntry, Account
    if not account_codes:
        return 0.0
    codes = [c.strip().upper() for c in account_codes if (c or '').strip()]
    if not codes:
        return 0.0
    q = db.session.query(
        func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0) if credit_minus_debit
        else func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)
    ).join(JournalEntry, JournalLine.journal_id == JournalEntry.id).join(
        Account, JournalLine.account_id == Account.id
    ).filter(
        Account.code.in_(codes),
        JournalLine.line_date >= start_date,
        JournalLine.line_date <= end_date,
        JournalEntry.status == 'posted'
    ).scalar() or 0
    return round(float(q), 2)


def sync_ledger_from_journal(je) -> Dict[str, Any]:
    """
    كتابة قيد مرحّل إلى دفتر الأستاذ (LedgerEntry) لضمان تطابق الشاشات التي ما زالت تقرأ من LedgerEntry.
    Returns: dict with keys success (bool), duration_sec (float), lines_synced (int), error (str|None),
             entry_number (str), repeated_failure_alert (bool).
    """
    global _sync_ledger_failure_count, _sync_ledger_last_failure_ts
    result = {
        'success': False,
        'duration_sec': 0.0,
        'lines_synced': 0,
        'error': None,
        'entry_number': getattr(je, 'entry_number', '') or '',
        'repeated_failure_alert': False,
    }
    if (getattr(je, 'status', None) or '').strip().lower() != 'posted':
        result['success'] = True
        return result
    start = time.perf_counter()
    try:
        from app import db
        from models import LedgerEntry
        db.session.flush()
        lines = getattr(je, 'lines', []) or []
        count = 0
        for ln in lines:
            acc = getattr(ln, 'account', None)
            if not acc:
                from models import Account
                acc = Account.query.get(getattr(ln, 'account_id', None))
            if not acc:
                continue
            desc = f"JE {getattr(je, 'entry_number', '')} L{getattr(ln, 'line_no', 0)} {getattr(ln, 'description', '')}"
            db.session.add(LedgerEntry(
                date=getattr(ln, 'line_date'),
                account_id=acc.id,
                debit=ln.debit or 0,
                credit=ln.credit or 0,
                description=desc,
            ))
            count += 1
        result['lines_synced'] = count
        result['success'] = True
        _sync_ledger_failure_count = 0
        duration = time.perf_counter() - start
        result['duration_sec'] = round(duration, 3)
        logger.info(
            "sync_ledger_from_journal success entry_number=%s lines_synced=%s duration_sec=%s",
            result['entry_number'], count, result['duration_sec'],
            extra={'entry_number': result['entry_number'], 'lines_synced': count, 'duration_sec': result['duration_sec']},
        )
        return result
    except Exception as e:
        duration = time.perf_counter() - start
        result['duration_sec'] = round(duration, 3)
        result['error'] = str(e)
        _sync_ledger_failure_count += 1
        _sync_ledger_last_failure_ts = time.time()
        now = time.time()
        window_ok = (_sync_ledger_last_failure_ts is None or
                     (now - _sync_ledger_last_failure_ts) <= SYNC_LEDGER_ALERT_WINDOW_SEC)
        if _sync_ledger_failure_count >= SYNC_LEDGER_ALERT_THRESHOLD and window_ok:
            result['repeated_failure_alert'] = True
            logger.warning(
                "sync_ledger_from_journal repeated failures count=%s entry_number=%s error=%s",
                _sync_ledger_failure_count, result['entry_number'], result['error'],
                extra={'failure_count': _sync_ledger_failure_count, 'entry_number': result['entry_number']},
            )
        logger.exception(
            "sync_ledger_from_journal failed entry_number=%s duration_sec=%s error=%s",
            result['entry_number'], result['duration_sec'], result['error'],
        )
        return result


def get_sync_ledger_metrics() -> Dict[str, Any]:
    """للتنبيه أو المراقبة: عدد مرات الفشل المتتالي ووقت آخر فشل."""
    return {
        'failure_count': _sync_ledger_failure_count,
        'last_failure_ts': _sync_ledger_last_failure_ts,
        'alert_threshold': SYNC_LEDGER_ALERT_THRESHOLD,
        'alert_window_sec': SYNC_LEDGER_ALERT_WINDOW_SEC,
    }
