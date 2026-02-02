"""Extract sales-related routes to routes/sales.py and remove from app/routes.py."""
from __future__ import annotations

ROUTES_PATH = "app/routes.py"
OUT_PATH = "routes/sales.py"

# Line ranges to extract (1-based, end exclusive)
# These need to be extracted from bottom to top to avoid line shift issues
BLOCKS = [
    # Scattered late routes (will find actual lines)
    # Main sales routes are in a contiguous block around 3320-5200
]

HEADER = '''# Phase 2 – Sales/POS blueprint. Same URLs.
from __future__ import annotations

import json
import re
import os
import base64
import mimetypes
from datetime import datetime, date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_, text

from app import db
from models import (
    SalesInvoice,
    SalesInvoiceItem,
    MenuItem,
    MenuCategory,
    Customer,
    Payment,
    Settings,
    LedgerEntry,
    JournalEntry,
    JournalLine,
    get_saudi_now,
)
from routes.common import BRANCH_LABELS, kv_get, kv_set, safe_table_number, user_can
from app.routes import (
    _set_table_status_concurrent,
    _post_ledger,
    _pm_account,
    CHART_OF_ACCOUNTS,
    _account,
)

bp = Blueprint("sales", __name__)

'''


def find_route_blocks(lines):
    """Find all sales-related route blocks."""
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this is a sales/pos/draft/print route
        if line.strip().startswith("@main.route("):
            route_str = line.strip()
            if any(x in route_str for x in [
                "'/sales'", "'/sales/", "'/pos/'", "'/pos/<",
                "'/api/draft", "'/api/sales/", "'/api/table", "'/api/menu/",
                "'/api/branch-settings/", "'/print/receipt'", "'/print/order'",
                "'/invoice/print/", "'/api/invoice/"
            ]):
                # Find the end of this route (next @main.route or @vat.route or end of file)
                start = i
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith("@main.route(") or next_line.startswith("@vat.route("):
                        break
                    j += 1
                blocks.append((start + 1, j, route_str))  # 1-based
                i = j
                continue
        i += 1
    return blocks


def transform_block(text: str) -> str:
    s = text
    s = s.replace("@main.route(", "@bp.route(")
    # Update internal url_for references
    s = s.replace("url_for('main.sales'", "url_for('sales.sales'")
    s = s.replace("url_for('main.sales_tables'", "url_for('sales.sales_tables'")
    s = s.replace("url_for('main.sales_china'", "url_for('sales.sales_china'")
    s = s.replace("url_for('main.sales_india'", "url_for('sales.sales_india'")
    s = s.replace("url_for('main.pos_home'", "url_for('sales.pos_home'")
    s = s.replace("url_for('main.pos_table'", "url_for('sales.pos_table'")
    s = s.replace("url_for('main.print_receipt'", "url_for('sales.print_receipt'")
    s = s.replace("url_for('main.print_order_preview'", "url_for('sales.print_order_preview'")
    s = s.replace("url_for('main.print_order_slip'", "url_for('sales.print_order_slip'")
    s = s.replace("url_for('main.invoice_print'", "url_for('sales.invoice_print'")
    s = s.replace("url_for('main.api_draft_get'", "url_for('sales.api_draft_get'")
    s = s.replace("url_for('main.api_tables_status'", "url_for('sales.api_tables_status'")
    return s


def main():
    with open(ROUTES_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"Total lines in {ROUTES_PATH}: {len(lines)}")
    
    # Find all sales-related blocks
    blocks = find_route_blocks(lines)
    print(f"Found {len(blocks)} sales-related route blocks")
    
    # Extract chunks
    extracted_chunks = []
    for start, end, route_str in sorted(blocks, key=lambda x: x[0]):
        chunk = "".join(lines[start - 1 : end])
        transformed = transform_block(chunk)
        extracted_chunks.append((start, end, transformed, route_str[:60]))
        print(f"Will extract lines {start}-{end}: {route_str[:50]}...")

    # Build output content
    body_parts = [chunk for _, _, chunk, _ in extracted_chunks]
    content = HEADER + "\n".join(body_parts)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {OUT_PATH}")

    # Remove blocks from app/routes.py (bottom to top to avoid line shift)
    for start, end, _, name in sorted(extracted_chunks, key=lambda x: -x[0]):
        del lines[start - 1 : end]
        print(f"Removed lines {start}-{end}: {name}")

    with open(ROUTES_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Updated {ROUTES_PATH}")


if __name__ == "__main__":
    main()
