"""Extract payments-related routes to routes/payments.py and remove from app/routes.py."""
from __future__ import annotations

ROUTES_PATH = "app/routes.py"
OUT_PATH = "routes/payments.py"

# 1-based inclusive line ranges (remove from bottom to top)
BLOCKS = [
    (7344, 7386),   # api_payments_pay_all
    (7261, 7342),   # register_payment_supplier
    (7118, 7257),   # register_payment_ajax + get_original_ar_account_code helper
    (5080, 5271),   # payments_export
    (4952, 5078),   # payments_json
    (4588, 4950),   # payments (main view)
]

HEADER = '''# Phase 2 – Payments blueprint. Same URLs.
from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app import db, csrf
from models import (
    PurchaseInvoice,
    ExpenseInvoice,
    SalesInvoice,
    SalesInvoiceItem,
    Payment,
    JournalEntry,
    JournalLine,
    JournalAudit,
    Settings,
    get_saudi_now,
)
from routes.common import BRANCH_LABELS, kv_get
from app.routes import (
    _post_ledger,
    _pm_account,
    _account,
    CHART_OF_ACCOUNTS,
)

bp = Blueprint("payments", __name__)


def _to_ascii_digits(s: str) -> str:
    try:
        arabic = '٠١٢٣٤٥٦٧٨٩'
        for i, d in enumerate('0123456789'):
            s = s.replace(arabic[i], d)
        return s
    except Exception:
        return s


def _parse_date(s: str) -> datetime | None:
    s = _to_ascii_digits((s or '').strip())
    try:
        if '-' in s:
            return datetime.fromisoformat(s)
        if '/' in s:
            try:
                return datetime.strptime(s, '%d/%m/%Y')
            except Exception:
                return datetime.strptime(s, '%m/%d/%Y')
    except Exception:
        pass
    return None


def to_cents(value):
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal('0.00')


def compute_status(total_amt, paid_amt):
    total_c = to_cents(total_amt)
    paid_c = to_cents(paid_amt)
    if (total_c - paid_c) <= Decimal('0.01'):
        return 'paid'
    if paid_c > Decimal('0.00'):
        return 'partial'
    return 'unpaid'


def _norm_group(n: str) -> str:
    raw = (n or '').lower()
    if ('هنقر' in raw) or ('هونقر' in raw) or ('هَنقَر' in raw):
        return 'hunger'
    if ('كيتا' in raw) or ('كيت' in raw):
        return 'keeta'
    s = re.sub(r'[^a-z]', '', raw)
    if s.startswith('hunger'):
        return 'hunger'
    if s.startswith('keeta') or s.startswith('keet'):
        return 'keeta'
    return ''


def get_original_ar_account_code(invoice_id, invoice_type):
    """Get AR account code from original journal entry."""
    try:
        original_je = JournalEntry.query.filter_by(
            invoice_id=invoice_id,
            invoice_type=invoice_type,
        ).first()
        if original_je:
            ar_line = JournalLine.query.filter(
                JournalLine.journal_id == original_je.id,
                JournalLine.debit > 0,
                JournalLine.description.like('%AR%'),
            ).first()
            if ar_line and ar_line.account:
                return ar_line.account.code
    except Exception:
        pass
    return '1141'  # Default AR (عملاء)

'''


def transform_block(text: str) -> str:
    s = text
    s = s.replace("@main.route(", "@bp.route(")
    s = s.replace("url_for('main.payments'", "url_for('payments.payments'")
    s = s.replace("url_for('payments')", "url_for('payments.payments')")
    return s


def main():
    with open(ROUTES_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    extracted = []
    for start, end in BLOCKS:
        chunk = "".join(lines[start - 1 : end])
        extracted.append(transform_block(chunk))

    body = "\n".join(extracted)
    content = HEADER + body

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    # Remove blocks from app/routes.py (bottom to top)
    for start, end in BLOCKS:
        del lines[start - 1 : end]

    with open(ROUTES_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("Wrote", OUT_PATH)
    print("Removed", len(BLOCKS), "blocks from", ROUTES_PATH)


if __name__ == "__main__":
    main()
