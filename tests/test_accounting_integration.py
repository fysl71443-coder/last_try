# -*- coding: utf-8 -*-
"""
Phase 5–6: Integration tests + failure scenarios for Flask ↔ Node.js accounting.

Run:
  - Start Node accounting service (npm start in accounting-service).
  - Set ACCOUNTING_API, ACCOUNTING_KEY.
  - For balance + fiscal-close tests: DATABASE_URL (Postgres, same as Node).
  - pytest tests/test_accounting_integration.py -v
"""

from __future__ import annotations

import os
import pytest

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Skip all if adapter not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("ACCOUNTING_API") or not os.getenv("ACCOUNTING_KEY"),
    reason="ACCOUNTING_API and ACCOUNTING_KEY required",
)

def _db_url():
    u = os.getenv("DATABASE_URL") or ""
    if u.startswith("postgres://"):
        u = u.replace("postgres://", "postgresql://", 1)
    return u if "postgresql" in u else None


def test_adapter_is_configured():
    from services.accounting_adapter import is_configured
    assert is_configured() is True


def test_sales_invoice_success():
    from services.accounting_adapter import post_sales_invoice
    key = f"test-sales-{os.urandom(4).hex()}"
    r = post_sales_invoice(
        invoice_number=f"INV-TEST-{key}",
        date="2026-01-27",
        branch="china_town",
        total_before_tax=100,
        discount_amount=0,
        vat_amount=15,
        total_after_tax=115,
        payment_method="cash",
        items=[{"product_name": "Test", "quantity": 1, "price": 100, "total": 100}],
        idempotency_key=key,
    )
    assert "journal_entry_id" in r
    assert r["journal_entry_id"] is not None


def test_sales_invoice_idempotency():
    from services.accounting_adapter import post_sales_invoice
    key = f"test-idem-{os.urandom(4).hex()}"
    inv = f"INV-IDEM-{key}"
    r1 = post_sales_invoice(
        invoice_number=inv,
        date="2026-01-27",
        branch="place_india",
        total_before_tax=50,
        discount_amount=0,
        vat_amount=7.5,
        total_after_tax=57.5,
        payment_method="card",
        idempotency_key=key,
    )
    r2 = post_sales_invoice(
        invoice_number=inv,
        date="2026-01-27",
        branch="place_india",
        total_before_tax=50,
        discount_amount=0,
        vat_amount=7.5,
        total_after_tax=57.5,
        payment_method="card",
        idempotency_key=key,
    )
    assert r1["journal_entry_id"] == r2["journal_entry_id"]


@pytest.mark.skipif(not _db_url(), reason="DATABASE_URL (Postgres) required")
def test_journal_entries_balanced():
    """All journal entries must have SUM(debit) = SUM(credit). Zero unbalanced rows."""
    import psycopg2
    conn = psycopg2.connect(_db_url())
    cur = conn.cursor()
    cur.execute("""
        SELECT journal_id, SUM(debit) AS debit, SUM(credit) AS credit
        FROM journal_lines
        GROUP BY journal_id
        HAVING ABS(COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0)) > 0.01
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    assert len(rows) == 0, f"Unbalanced journal entries: {rows}"


@pytest.mark.skipif(not _db_url(), reason="DATABASE_URL (Postgres) required")
def test_fiscal_year_closed_rejects_invoice():
    """Close year 2026 → POST from Flask → 403 Fiscal Year Closed. Reopen year after."""
    import psycopg2
    from services.accounting_adapter import post_sales_invoice, FiscalYearClosedError

    conn = psycopg2.connect(_db_url())
    cur = conn.cursor()
    try:
        cur.execute("UPDATE fiscal_years SET closed = TRUE WHERE year = 2026")
        conn.commit()
        key = f"test-fy-close-{os.urandom(4).hex()}"
        with pytest.raises(FiscalYearClosedError):
            post_sales_invoice(
                invoice_number=f"INV-FY-{key}",
                date="2026-01-27",
                branch="china_town",
                total_before_tax=10,
                discount_amount=0,
                vat_amount=1.5,
                total_after_tax=11.5,
                payment_method="cash",
                idempotency_key=key,
            )
    finally:
        cur.execute("UPDATE fiscal_years SET closed = FALSE WHERE year = 2026")
        conn.commit()
        cur.close()
        conn.close()


def test_invalid_source_system_rejected():
    """Node rejects payload with unknown source_system (400)."""
    import requests
    api = (os.getenv("ACCOUNTING_API") or "").rstrip("/")
    key = os.getenv("ACCOUNTING_KEY") or ""
    if not api or not key:
        pytest.skip("ACCOUNTING_API and ACCOUNTING_KEY required")
    r = requests.post(
        f"{api}/api/external/sales-invoice",
        headers={"Content-Type": "application/json", "X-API-KEY": key},
        json={
            "source_system": "unknown-system",
            "invoice_number": "INV-BAD",
            "date": "2026-01-27",
            "branch": "china_town",
            "total_before_tax": 100,
            "vat_amount": 15,
            "total_after_tax": 115,
            "payment_method": "cash",
        },
        timeout=10,
    )
    assert r.status_code == 400
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    assert "source_system" in (body.get("message") or "").lower() or "invalid" in (body.get("error") or "").lower()


# Failure scenarios: test manually or via E2E.
# - Invalid API key -> 401, Flask returns 400, no invoice persisted.
# - Node down / timeout -> AccountingUnavailableError, Flask rollback, 503.
# - Fiscal year closed -> 403, Flask rollback, 403. (Covered by test_fiscal_year_closed_rejects_invoice if DB available.)
# - Payload missing required fields -> 400 from Node.
# - Rate limit -> 429, adapter raises AccountingUnavailableError.
# - Invalid source_system -> 400 (test_invalid_source_system_rejected).
