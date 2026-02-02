"""Extract purchases-related routes to routes/purchases.py and remove from app/routes.py."""
from __future__ import annotations

import re

ROUTES_PATH = "app/routes.py"
OUT_PATH = "routes/purchases.py"

# 1-based inclusive line ranges for each block (will remove from bottom to top)
BLOCKS = [
    (1605, 1720),   # meals_import
    (1528, 1604),   # meals
    (1512, 1527),   # api_raw_materials_categories
    (1487, 1511),   # api_raw_materials
    (1439, 1486),   # raw_materials
    (1086, 1438),   # purchases
    (100, 115),     # api_purchase_categories
]

HEADER = '''# Phase 2 – Purchases blueprint (purchases, raw materials, meals). Same URLs.
from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db
from models import (
    PurchaseInvoice,
    PurchaseInvoiceItem,
    RawMaterial,
    Supplier,
    Meal,
    MealIngredient,
    Payment,
    get_saudi_now,
)
from forms import PurchaseInvoiceForm, MealForm, RawMaterialForm
from app.routes import (
    warmup_db_once,
    _post_ledger,
    _pm_account,
    _create_purchase_journal,
    CHART_OF_ACCOUNTS,
    ext_db,
)

bp = Blueprint("purchases", __name__)


def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

'''


def transform_block(text: str) -> str:
    s = text
    s = re.sub(r"@main\.route\(", "@bp.route(", s)
    s = re.sub(r"url_for\(['\"]main\.purchases['\"]\)", "url_for('purchases.purchases')", s)
    s = re.sub(r"url_for\(['\"]main\.raw_materials['\"]", "url_for('purchases.raw_materials'", s)
    s = re.sub(r"url_for\(['\"]main\.meals['\"]\)", "url_for('purchases.meals')", s)
    s = s.replace("if 'Supplier' in globals():\n            suppliers = Supplier.query", "            suppliers = Supplier.query")
    s = s.replace("RawMaterial.query.all() if 'RawMaterial' in globals() else []", "RawMaterial.query.all()")
    s = s.replace(
        "RawMaterial.query.filter_by(active=True).order_by(RawMaterial.name.asc()).all() if 'RawMaterial' in globals() else []",
        "RawMaterial.query.filter_by(active=True).order_by(RawMaterial.name.asc()).all()",
    )
    s = s.replace(
        "base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))",
        "base_dir = _project_root()",
    )
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

    # Remove blocks from app/routes.py (bottom to top so line numbers stay valid)
    for start, end in BLOCKS:
        del lines[start - 1 : end]

    with open(ROUTES_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("Wrote", OUT_PATH)
    print("Removed", len(BLOCKS), "blocks from", ROUTES_PATH)


if __name__ == "__main__":
    main()
