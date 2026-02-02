# -*- coding: utf-8 -*-
"""
Accounting Adapter — Flask → Node.js Accounting Service (REST only).

Flask does NOT compute debit/credit. It sends operational payloads and stores
journal_entry_id returned by Node. On failure, raise; caller must rollback.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

ACCOUNTING_API = (os.getenv("ACCOUNTING_API") or "").rstrip("/")
ACCOUNTING_KEY = os.getenv("ACCOUNTING_KEY") or os.getenv("ACCOUNTING_API_KEY")
TIMEOUT = int(os.getenv("ACCOUNTING_TIMEOUT", "15"))

SOURCE = "flask-pos"


class AccountingAdapterError(Exception):
    """Base for adapter failures."""
    pass


class AccountingUnavailableError(AccountingAdapterError):
    """Node down, timeout, or non-2xx."""
    pass


class FiscalYearClosedError(AccountingAdapterError):
    """403 — fiscal year closed for this date."""
    pass


class InvalidApiKeyError(AccountingAdapterError):
    """401 — invalid or missing X-API-KEY."""
    pass


class BadRequestError(AccountingAdapterError):
    """400 — invalid payload."""
    pass


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-KEY": ACCOUNTING_KEY or "",
    }


def _request(method: str, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not requests:
        raise AccountingAdapterError("requests not installed; pip install requests")
    if not ACCOUNTING_API or not ACCOUNTING_KEY:
        raise AccountingAdapterError("ACCOUNTING_API and ACCOUNTING_KEY must be set")
    url = f"{ACCOUNTING_API}{path}"
    try:
        r = requests.request(method, url, json=json, headers=_headers(), timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        raise AccountingUnavailableError("Accounting service timeout")
    except requests.exceptions.RequestException as e:
        raise AccountingUnavailableError(f"Accounting service unreachable: {e}")

    if r.status_code == 401:
        raise InvalidApiKeyError("Invalid or missing X-API-KEY")
    if r.status_code == 403:
        raise FiscalYearClosedError("Fiscal year closed for this date")
    if r.status_code == 400:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        raise BadRequestError(body.get("message", "Bad request"))
    if r.status_code == 409:
        return r.json()
    if r.status_code == 429:
        raise AccountingUnavailableError("Accounting service rate limited")
    if r.status_code not in (200, 201):
        raise AccountingUnavailableError(f"Accounting API error: {r.status_code}")

    return r.json() if r.content else {}


def post_sales_invoice(
    invoice_number: str,
    date: str,
    branch: str,
    total_before_tax: float,
    discount_amount: float,
    vat_amount: float,
    total_after_tax: float,
    payment_method: str,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    table_number: Optional[int] = None,
    customer_ref: Optional[int] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    idempotency_key: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "source_system": SOURCE,
        "idempotency_key": idempotency_key or f"flask-sales-{invoice_number}",
        "invoice_number": invoice_number,
        "date": date,
        "branch": branch,
        "total_before_tax": round(total_before_tax, 2),
        "discount_amount": round(discount_amount or 0, 2),
        "vat_amount": round(vat_amount or 0, 2),
        "total_after_tax": round(total_after_tax, 2),
        "payment_method": (payment_method or "cash").strip().upper(),
        "customer_name": (customer_name or "").strip() or None,
        "customer_phone": (customer_phone or "").strip() or None,
        "table_number": table_number,
        "customer_ref": customer_ref,
        "items": items or [],
    }
    if status is not None:
        payload["status"] = str(status).strip().lower()
    out = _request("POST", "/api/external/sales-invoice", json=payload)
    return {"journal_entry_id": out.get("journal_entry_id"), "invoice_id": out.get("invoice_id")}


def post_purchase_invoice(
    invoice_number: str,
    date: str,
    total_before_tax: float,
    vat_amount: float,
    total_after_tax: float,
    payment_method: str,
    status: str = "unpaid",
    supplier_name: Optional[str] = None,
    supplier_ref: Optional[int] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "source_system": SOURCE,
        "idempotency_key": idempotency_key or f"flask-pur-{invoice_number}",
        "invoice_number": invoice_number,
        "date": date,
        "total_before_tax": round(total_before_tax, 2),
        "vat_amount": round(vat_amount or 0, 2),
        "total_after_tax": round(total_after_tax, 2),
        "payment_method": (payment_method or "cash").strip().upper(),
        "status": (status or "unpaid").strip().lower(),
        "supplier_name": (supplier_name or "").strip() or None,
        "supplier_ref": supplier_ref,
        "items": items or [],
    }
    out = _request("POST", "/api/external/purchase-invoice", json=payload)
    return {"journal_entry_id": out.get("journal_entry_id"), "invoice_id": out.get("invoice_id")}


def post_expense_invoice(
    invoice_number: str,
    date: str,
    total_before_tax: float,
    vat_amount: float,
    total_after_tax: float,
    payment_method: str,
    status: str = "paid",
    discount_amount: float = 0,
    items: Optional[List[Dict[str, Any]]] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "source_system": SOURCE,
        "idempotency_key": idempotency_key or f"flask-exp-{invoice_number}",
        "invoice_number": invoice_number,
        "date": date,
        "total_before_tax": round(total_before_tax, 2),
        "discount_amount": round(discount_amount or 0, 2),
        "vat_amount": round(vat_amount or 0, 2),
        "total_after_tax": round(total_after_tax, 2),
        "payment_method": (payment_method or "cash").strip().upper(),
        "status": (status or "paid").strip().lower(),
        "items": items or [],
    }
    out = _request("POST", "/api/external/expense-invoice", json=payload)
    return {"journal_entry_id": out.get("journal_entry_id"), "invoice_id": out.get("invoice_id")}


def post_payment(
    invoice_type: str,
    invoice_id: int,
    invoice_number: str,
    amount: float,
    payment_method: str,
    date: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "source_system": SOURCE,
        "idempotency_key": idempotency_key or f"flask-pay-{invoice_type}-{invoice_id}",
        "invoice_type": invoice_type.strip().lower(),
        "invoice_id": int(invoice_id),
        "invoice_number": str(invoice_number),
        "amount": round(amount, 2),
        "payment_method": (payment_method or "cash").strip().upper(),
        "date": date,
    }
    out = _request("POST", "/api/external/payment", json=payload)
    return {"journal_entry_id": out.get("journal_entry_id"), "payment_id": out.get("payment_id")}


def post_salary_payment(
    salary_id: int,
    employee_id: int,
    year: int,
    month: int,
    amount: float,
    payment_method: str,
    date: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "source_system": SOURCE,
        "idempotency_key": idempotency_key or f"flask-salary-{employee_id}-{year}-{month}",
        "salary_id": int(salary_id),
        "employee_id": int(employee_id),
        "year": int(year),
        "month": int(month),
        "amount": round(amount, 2),
        "payment_method": (payment_method or "cash").strip().upper(),
        "date": date,
    }
    out = _request("POST", "/api/external/salary-payment", json=payload)
    return {"journal_entry_id": out.get("journal_entry_id"), "payment_id": out.get("payment_id")}


def post_salary_accrual(
    salary_id: int,
    employee_id: int,
    year: int,
    month: int,
    amount: float,
    date: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "source_system": SOURCE,
        "idempotency_key": idempotency_key or f"flask-accrual-{employee_id}-{year}-{month}",
        "salary_id": int(salary_id),
        "employee_id": int(employee_id),
        "year": int(year),
        "month": int(month),
        "amount": round(amount, 2),
        "date": date,
    }
    out = _request("POST", "/api/external/salary-accrual", json=payload)
    return {"journal_entry_id": out.get("journal_entry_id")}


def is_configured() -> bool:
    if os.getenv("ACCOUNTING_DISABLED", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return bool(ACCOUNTING_API and ACCOUNTING_KEY)
