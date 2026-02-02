"""Extract reports-related routes to routes/reports.py and remove from app/routes.py."""
from __future__ import annotations

ROUTES_PATH = "app/routes.py"
OUT_PATH = "routes/reports.py"

# Line ranges to extract (1-based, inclusive start, exclusive end based on next route)
# Format: (start_line, end_line_exclusive, route_name)
BLOCKS = [
    # Must extract from bottom to top to avoid line shift issues
    (8843, 8861, 'print_selected'),
    (8690, 8792, 'print_payroll'),
    (8590, 8689, 'reports_print_all_invoices_expenses'),
    (8493, 8589, 'reports_print_daily_items_summary'),
    (8381, 8492, 'reports_print_all_invoices_purchases'),
    (8128, 8380, 'reports_print_daily_sales'),
    (7907, 8127, 'reports_print_all_invoices_sales'),
    (7801, 7862, 'api_reports_all_purchases'),
    (3827, 3944, 'reports_print_customer_sales'),
    (3690, 3826, 'api_reports_monthly'),
    (3681, 3689, 'reports_monthly'),
    (3644, 3680, 'api_reports_customer_sales'),
    (3563, 3643, 'api_reports_preview'),
    (3558, 3562, 'reports'),
    (3550, 3556, 'reports_print_salaries_legacy'),
    (2464, 2616, 'reports_print_salaries_detailed'),
    (2450, 2463, 'reports_print_salaries'),
    (1172, 1278, 'reports_print_payments'),
]

HEADER = '''# Phase 2 – Reports blueprint. Same URLs.
from __future__ import annotations

import json
import re
from datetime import datetime, date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_, text

from app import db
from models import (
    SalesInvoice,
    SalesInvoiceItem,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    ExpenseInvoice,
    ExpenseInvoiceItem,
    Payment,
    Settings,
    Employee,
    Salary,
    JournalEntry,
    JournalLine,
    get_saudi_now,
)
from routes.common import BRANCH_LABELS

bp = Blueprint("reports", __name__)

'''


def transform_block(text: str) -> str:
    s = text
    s = s.replace("@main.route(", "@bp.route(")
    s = s.replace("url_for('main.reports'", "url_for('reports.reports'")
    s = s.replace("url_for('main.reports_monthly'", "url_for('reports.reports_monthly'")
    s = s.replace("url_for('main.reports_print_customer_sales'", "url_for('reports.reports_print_customer_sales'")
    return s


def main():
    with open(ROUTES_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"Total lines in {ROUTES_PATH}: {len(lines)}")

    # Extract chunks (in original order for writing, but sorted for deletion)
    extracted_chunks = []
    for start, end, name in sorted(BLOCKS, key=lambda x: x[0]):
        chunk = "".join(lines[start - 1 : end])
        transformed = transform_block(chunk)
        extracted_chunks.append((start, transformed, name))
        print(f"Extracted {name}: lines {start}-{end}")

    # Build output content
    body_parts = [chunk for _, chunk, _ in extracted_chunks]
    content = HEADER + "\n".join(body_parts)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {OUT_PATH}")

    # Remove blocks from app/routes.py (bottom to top to avoid line shift)
    for start, end, name in sorted(BLOCKS, key=lambda x: -x[0]):
        del lines[start - 1 : end]
        print(f"Removed {name} (lines {start}-{end})")

    with open(ROUTES_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Updated {ROUTES_PATH}")


if __name__ == "__main__":
    main()
