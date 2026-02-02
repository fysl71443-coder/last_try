"""Extract inventory-related routes to routes/inventory.py and remove from app/routes.py."""
from __future__ import annotations

ROUTES_PATH = "app/routes.py"
OUT_PATH = "routes/inventory.py"

# 1-based inclusive line ranges (remove from bottom to top)
BLOCKS = [
    (1718, 2083),  # api_inventory_intelligence
    (1475, 1716),  # inventory_intelligence
    (1049, 1473),  # inventory (main view)
]

HEADER = '''# Phase 2 – Inventory blueprint. Same URLs.
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_, text

from app import db
from models import (
    RawMaterial,
    Meal,
    MealIngredient,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    SalesInvoice,
    SalesInvoiceItem,
    get_saudi_now,
)
from routes.common import BRANCH_LABELS

bp = Blueprint("inventory", __name__)

'''


def transform_block(text: str) -> str:
    s = text
    s = s.replace("@main.route(", "@bp.route(")
    s = s.replace("url_for('main.inventory'", "url_for('inventory.inventory'")
    s = s.replace("url_for('main.inventory_intelligence'", "url_for('inventory.inventory_intelligence'")
    return s


def main():
    with open(ROUTES_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find actual end of api_inventory_intelligence
    start_line = 1718
    end_line = start_line
    for i in range(start_line - 1, min(len(lines), start_line + 400)):
        if i < len(lines) - 1 and lines[i].strip().startswith("@main.route"):
            end_line = i
            break
    if end_line == start_line:
        end_line = start_line + 350  # Fallback

    BLOCKS[0] = (1718, end_line)

    extracted = []
    for start, end in BLOCKS:
        chunk = "".join(lines[start - 1 : end])
        extracted.append(transform_block(chunk))

    body = "\n".join(extracted)
    content = HEADER + body

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    # Remove blocks from app/routes.py (bottom to top)
    for start, end in sorted(BLOCKS, reverse=True):
        del lines[start - 1 : end]

    with open(ROUTES_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("Wrote", OUT_PATH)
    print("Removed", len(BLOCKS), "blocks from", ROUTES_PATH)
    print("api_inventory_intelligence ends at line", end_line)


if __name__ == "__main__":
    main()
