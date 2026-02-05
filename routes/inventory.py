# Phase 2 – Inventory blueprint. Same URLs.
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


@bp.route('/inventory-intelligence', methods=['GET'], endpoint='inventory_intelligence')
@login_required
def inventory_intelligence():
    try:
        today = get_saudi_now().date()
        start_month = today.replace(day=1)
        def latest_cost_per_unit(rm_id: int):
            try:
                row = (
                    db.session.query(PurchaseInvoiceItem.price_before_tax, PurchaseInvoice.date)
                    .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                    .filter(PurchaseInvoiceItem.raw_material_id == rm_id)
                    .order_by(PurchaseInvoice.date.desc(), PurchaseInvoiceItem.id.desc())
                    .first()
                )
                if row and row[0] is not None:
                    return float(row[0])
            except Exception:
                pass
            try:
                avg = (
                    db.session.query(func.coalesce(func.avg(PurchaseInvoiceItem.price_before_tax), 0))
                    .filter(PurchaseInvoiceItem.raw_material_id == rm_id)
                    .scalar()
                ) or 0
                if float(avg) > 0:
                    return float(avg)
            except Exception:
                pass
            try:
                rm = RawMaterial.query.get(int(rm_id))
                return float(getattr(rm, 'cost_per_unit', 0) or 0)
            except Exception:
                return 0.0

        raw_materials = RawMaterial.query.filter_by(active=True).all()
        total_inventory_cost = 0.0
        for rm in (raw_materials or []):
            unit_cost = latest_cost_per_unit(int(getattr(rm, 'id', 0) or 0))
            qty = float(getattr(rm, 'stock_quantity', 0) or 0)
            total_inventory_cost += unit_cost * qty

        try:
            total_purchases_month = float(
                db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
                .filter(PurchaseInvoice.date >= start_month, PurchaseInvoice.date <= today)
                .scalar() or 0
            )
        except Exception:
            total_purchases_month = 0.0

        try:
            sales_invoices_q = (
                db.session.query(SalesInvoice.id, SalesInvoice.date, SalesInvoice.total_after_tax_discount)
                .filter(SalesInvoice.date >= start_month, SalesInvoice.date <= today)
            )
            sales_invoices_rows = sales_invoices_q.all()
            sales_invoice_ids = [int(r[0]) for r in sales_invoices_rows]
            total_sales_revenue_month = float(sum(float(r[2] or 0) for r in sales_invoices_rows))
            sales_qty_rows = (
                db.session.query(func.coalesce(func.sum(SalesInvoiceItem.quantity), 0))
                .filter(SalesInvoiceItem.invoice_id.in_(sales_invoice_ids))
                .scalar() or 0
            )
            total_meals_sold_month = float(sales_qty_rows or 0)
        except Exception:
            total_sales_revenue_month = 0.0
            total_meals_sold_month = 0.0

        meals = Meal.query.filter_by(active=True).all()
        meal_by_name = { (getattr(m, 'name', '') or '').strip(): m for m in (meals or []) }
        sales_qty_by_meal = {}
        try:
            rows = (
                db.session.query(SalesInvoiceItem.product_name, func.coalesce(func.sum(SalesInvoiceItem.quantity), 0))
                .filter(SalesInvoiceItem.invoice_id.in_(sales_invoice_ids))
                .group_by(SalesInvoiceItem.product_name)
                .all()
            )
            for name, qty in (rows or []):
                k = (name or '').strip()
                sales_qty_by_meal[k] = float(qty or 0)
        except Exception:
            sales_qty_by_meal = {}

        estimated_total_meal_cost = 0.0
        meals_analysis = []
        outdated_meals = []
        def latest_purchase_date(rm_id: int):
            try:
                d = (
                    db.session.query(PurchaseInvoice.date)
                    .join(PurchaseInvoiceItem, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                    .filter(PurchaseInvoiceItem.raw_material_id == rm_id)
                    .order_by(PurchaseInvoice.date.desc(), PurchaseInvoiceItem.id.desc())
                    .first()
                )
                return d[0] if d and d[0] else None
            except Exception:
                return None
        OUTDATED_DAYS = 60
        for m_name, sold_qty in sales_qty_by_meal.items():
            meal = meal_by_name.get(m_name)
            if not meal:
                continue
            total_cost = 0.0
            outdated_flag = False
            try:
                ingrs = MealIngredient.query.filter_by(meal_id=int(meal.id)).all()
            except Exception:
                ingrs = []
            for ing in (ingrs or []):
                unit_cost = latest_cost_per_unit(int(getattr(ing, 'raw_material_id', 0) or 0))
                last_dt = latest_purchase_date(int(getattr(ing, 'raw_material_id', 0) or 0))
                if not last_dt or (today - last_dt).days > OUTDATED_DAYS:
                    outdated_flag = True
                qty_needed = float(getattr(ing, 'quantity', 0) or 0)
                total_cost += unit_cost * qty_needed * float(sold_qty or 0)
            estimated_total_meal_cost += total_cost
            revenue = float(getattr(meal, 'selling_price', 0) or 0) * float(sold_qty or 0)
            profit = revenue - total_cost
            meals_analysis.append({
                'meal_name': m_name,
                'sold_qty': float(sold_qty or 0),
                'consumption_cost': float(total_cost or 0),
                'revenue': float(revenue or 0),
                'profit': float(profit or 0),
            })
            if outdated_flag:
                outdated_meals.append(m_name)

        total_profit_generated = float(total_sales_revenue_month or 0) - float(estimated_total_meal_cost or 0)

        purchases_rows = []
        try:
            invs = (
                PurchaseInvoice.query
                .filter(PurchaseInvoice.date >= start_month, PurchaseInvoice.date <= today)
                .order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc())
                .limit(500)
                .all()
            )
            for inv in (invs or []):
                items_count = int(PurchaseInvoiceItem.query.filter_by(invoice_id=inv.id).count() or 0)
                purchases_rows.append({
                    'date': inv.date.isoformat() if getattr(inv, 'date', None) else '',
                    'invoice_number': getattr(inv, 'invoice_number', ''),
                    'supplier': getattr(inv, 'supplier_name', '') or '-',
                    'payment_method': getattr(inv, 'payment_method', '') or '-',
                    'status': getattr(inv, 'status', '') or '-',
                    'subtotal': float(getattr(inv, 'total_before_tax', 0) or 0),
                    'vat': float(getattr(inv, 'tax_amount', 0) or 0),
                    'discount': float(getattr(inv, 'discount_amount', 0) or 0),
                    'final_total': float(getattr(inv, 'total_after_tax_discount', 0) or 0),
                    'items_count': items_count,
                })
        except Exception:
            purchases_rows = []

        # Top purchased ingredients and trend (this month)
        top_ingredients = []
        purchase_trend = []
        try:
            rows = (
                db.session.query(PurchaseInvoiceItem.raw_material_name, func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0))
                .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                .filter(PurchaseInvoice.date >= start_month, PurchaseInvoice.date <= today)
                .group_by(PurchaseInvoiceItem.raw_material_name)
                .order_by(func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0).desc())
                .limit(10)
                .all()
            )
            top_ingredients = [{'name': n, 'total': float(t or 0)} for n, t in (rows or [])]
            trows = (
                db.session.query(PurchaseInvoice.date, func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
                .filter(PurchaseInvoice.date >= start_month, PurchaseInvoice.date <= today)
                .group_by(PurchaseInvoice.date)
                .order_by(PurchaseInvoice.date.asc())
                .all()
            )
            purchase_trend = [{'date': (d.isoformat() if d else ''), 'total': float(t or 0)} for d, t in (trows or [])]
        except Exception:
            top_ingredients = []
            purchase_trend = []

        stock_rows = []
        try:
            p_qty_rows = (
                db.session.query(PurchaseInvoiceItem.raw_material_id, func.coalesce(func.sum(PurchaseInvoiceItem.quantity), 0))
                .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                .filter(PurchaseInvoice.date >= start_month, PurchaseInvoice.date <= today)
                .group_by(PurchaseInvoiceItem.raw_material_id)
                .all()
            )
            p_qty_map = {int(rm_id): float(qty or 0) for rm_id, qty in (p_qty_rows or []) if rm_id is not None}
            usage_map = {}
            for m in (meals or []):
                sold = float(sales_qty_by_meal.get((getattr(m, 'name', '') or '').strip(), 0) or 0)
                if sold <= 0:
                    continue
                ingrs = MealIngredient.query.filter_by(meal_id=int(m.id)).all()
                for ing in (ingrs or []):
                    usage_map[int(getattr(ing, 'raw_material_id', 0) or 0)] = usage_map.get(int(getattr(ing, 'raw_material_id', 0) or 0), 0.0) + (float(getattr(ing, 'quantity', 0) or 0) * sold)
            for rm in (raw_materials or []):
                rid = int(getattr(rm, 'id', 0) or 0)
                opening_qty = float(getattr(rm, 'stock_quantity', 0) or 0)
                purchases_qty = float(p_qty_map.get(rid, 0) or 0)
                estimated_usage = float(usage_map.get(rid, 0) or 0)
                expected_stock = max(opening_qty + purchases_qty - estimated_usage, 0.0)
                risk = 'low' if expected_stock < max(1.0, opening_qty * 0.1) else ('excess' if purchases_qty > estimated_usage * 1.5 else 'ok')
                stock_rows.append({
                    'ingredient': rm.display_name,
                    'opening_qty': opening_qty,
                    'purchases_qty': purchases_qty,
                    'estimated_usage': estimated_usage,
                    'expected_stock': expected_stock,
                    'risk': risk,
                })
        except Exception:
            stock_rows = []

        return render_template(
            'inventory_intelligence.html',
            kpi={
                'total_inventory_cost': float(total_inventory_cost or 0),
                'total_purchases_month': float(total_purchases_month or 0),
                'total_meals_sold_month': float(total_meals_sold_month or 0),
                'estimated_total_meal_cost': float(estimated_total_meal_cost or 0),
                'total_profit_generated': float(total_profit_generated or 0),
            },
            purchases=purchases_rows,
            top_ingredients=top_ingredients,
            purchase_trend=purchase_trend,
            meals_analysis=meals_analysis,
            outdated_meals=outdated_meals,
            stock_rows=stock_rows,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(_('فشل تحميل لوحة الذكاء: %(error)s', error=e), 'danger')
        return redirect(url_for('inventory.inventory'))

@bp.route('/inventory', endpoint='inventory')
@login_required
def inventory():
    from sqlalchemy import func
    raw_materials = RawMaterial.query.filter_by(active=True).all()
    meals = Meal.query.filter_by(active=True).all()

    # Build inventory cost ledger from purchases
    ledger_rows = []
    try:
        q = db.session.query(
            PurchaseInvoiceItem.raw_material_id.label('rm_id'),
            func.max(PurchaseInvoice.date).label('last_date'),
            func.sum(PurchaseInvoiceItem.quantity).label('qty'),
            func.sum(PurchaseInvoiceItem.total_price).label('total_cost')
        ).join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
        q = q.group_by(PurchaseInvoiceItem.raw_material_id)
        rm_map = {m.id: m for m in raw_materials}
        for r in q.all():
            rm = rm_map.get(int(r.rm_id)) if r.rm_id is not None else None
            name = (rm.display_name if rm else '-')
            unit = (rm.unit if rm else '-')
            # Quantities and costs
            qty = float(r.qty or 0)
            total_cost = float(r.total_cost or 0)
            avg_cost = (total_cost / qty) if qty else 0.0
            # Current stock equals cumulative purchased quantity (no consumption tracking here)
            current_stock = qty
            stock_value = current_stock * avg_cost
            ledger_rows.append({
                'material': name,
                'unit': unit,
                'purchased_qty': qty,
                'avg_cost': avg_cost,
                'total_cost': total_cost,
                'current_stock': current_stock,
                'stock_value': stock_value,
                'last_date': r.last_date.strftime('%Y-%m-%d') if r.last_date else ''
            })
        ledger_rows.sort(key=lambda x: (x['material'] or '').lower())
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        ledger_rows = []

    start_ledger = get_saudi_now().date().replace(day=1)
    end_ledger = get_saudi_now().date()
    try:
        sd = (request.args.get('start_date') or '').strip()
        ed = (request.args.get('end_date') or '').strip()
        if sd:
            start_ledger = datetime.strptime(sd, '%Y-%m-%d').date()
        if ed:
            end_ledger = datetime.strptime(ed, '%Y-%m-%d').date()
    except Exception:
        pass
    purchases = []
    try:
        q = PurchaseInvoice.query.filter(
            PurchaseInvoice.date >= start_ledger,
            PurchaseInvoice.date <= end_ledger
        ).order_by(PurchaseInvoice.id.desc()).limit(1000)
        invs = q.all()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        invs = []
    items_map = {}
    try:
        ids = [inv.id for inv in invs]
        if ids:
            rows = PurchaseInvoiceItem.query.filter(PurchaseInvoiceItem.invoice_id.in_(ids)).order_by(PurchaseInvoiceItem.id.asc()).all()
            for it in rows:
                items_map.setdefault(it.invoice_id, []).append(it)
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        items_map = {}
    for inv in invs:
        items_ctx = []
        for it in items_map.get(inv.id, []):
            items_ctx.append({
                'name': it.raw_material_name,
                'quantity': float(it.quantity or 0),
                'price_before_tax': float(it.price_before_tax or 0),
                'discount': float(it.discount or 0),
                'tax': float(it.tax or 0),
                'total_price': float(it.total_price or 0),
            })
        purchases.append({
            'id': inv.id,
            'invoice_number': inv.invoice_number,
            'date': inv.date.strftime('%Y-%m-%d') if getattr(inv, 'date', None) else '',
            'supplier_name': getattr(inv, 'supplier_name', '') or '',
            'payment_method': (getattr(inv, 'payment_method', '') or '').upper(),
            'status': getattr(inv, 'status', '') or '',
            'total_before_tax': float(getattr(inv, 'total_before_tax', 0.0) or 0.0),
            'tax_amount': float(getattr(inv, 'tax_amount', 0.0) or 0.0),
            'discount_amount': float(getattr(inv, 'discount_amount', 0.0) or 0.0),
            'total_after_tax_discount': float(getattr(inv, 'total_after_tax_discount', 0.0) or 0.0),
            'items': items_ctx,
        })
    try:
        today = get_saudi_now().date()
        start_month = today.replace(day=1)
        start_arg = (request.args.get('start_date') or '').strip()
        end_arg = (request.args.get('end_date') or '').strip()
        branch_arg = (request.args.get('branch') or '').strip()
        def _parse_date(s):
            try:
                from datetime import datetime as _dt
                return _dt.strptime(s, '%Y-%m-%d').date()
            except Exception:
                return None
        start_period = _parse_date(start_arg) or start_month
        end_period = _parse_date(end_arg) or today
        def latest_cost_per_unit(rm_id: int):
            try:
                row = (
                    db.session.query(PurchaseInvoiceItem.price_before_tax, PurchaseInvoice.date)
                    .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                    .filter(PurchaseInvoiceItem.raw_material_id == rm_id)
                    .order_by(PurchaseInvoice.date.desc(), PurchaseInvoiceItem.id.desc())
                    .first()
                )
                if row and row[0] is not None:
                    return float(row[0])
            except Exception:
                pass
            try:
                avg = (
                    db.session.query(func.coalesce(func.avg(PurchaseInvoiceItem.price_before_tax), 0))
                    .filter(PurchaseInvoiceItem.raw_material_id == rm_id)
                    .scalar()
                ) or 0
                if float(avg) > 0:
                    return float(avg)
            except Exception:
                pass
            try:
                rm = RawMaterial.query.get(int(rm_id))
                return float(getattr(rm, 'cost_per_unit', 0) or 0)
            except Exception:
                return 0.0

        total_inventory_cost = 0.0
        for rm in (raw_materials or []):
            unit_cost = latest_cost_per_unit(int(getattr(rm, 'id', 0) or 0))
            qty = float(getattr(rm, 'stock_quantity', 0) or 0)
            total_inventory_cost += unit_cost * qty

        try:
            total_purchases_month = float(
                db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
                .filter(PurchaseInvoice.date >= start_period, PurchaseInvoice.date <= end_period)
                .scalar() or 0
            )
        except Exception:
            total_purchases_month = 0.0

        try:
            sales_invoices_q = (
                db.session.query(SalesInvoice.id, SalesInvoice.date, SalesInvoice.total_after_tax_discount)
                .filter(SalesInvoice.date >= start_period, SalesInvoice.date <= end_period)
            )
            if branch_arg:
                sales_invoices_q = sales_invoices_q.filter(SalesInvoice.branch == branch_arg)
            sales_invoices_rows = sales_invoices_q.all()
            sales_invoice_ids = [int(r[0]) for r in sales_invoices_rows]
            total_sales_revenue_month = float(sum(float(r[2] or 0) for r in sales_invoices_rows))
            sales_qty_rows = (
                db.session.query(func.coalesce(func.sum(SalesInvoiceItem.quantity), 0))
                .filter(SalesInvoiceItem.invoice_id.in_(sales_invoice_ids))
                .scalar() or 0
            )
            total_meals_sold_month = float(sales_qty_rows or 0)
        except Exception:
            total_sales_revenue_month = 0.0
            total_meals_sold_month = 0.0

        meals_list = Meal.query.filter_by(active=True).all()
        meal_by_name = { (getattr(m, 'name', '') or '').strip(): m for m in (meals_list or []) }
        sales_qty_by_meal = {}
        try:
            rows = (
                db.session.query(SalesInvoiceItem.product_name, func.coalesce(func.sum(SalesInvoiceItem.quantity), 0))
                .filter(SalesInvoiceItem.invoice_id.in_(sales_invoice_ids))
                .group_by(SalesInvoiceItem.product_name)
                .all()
            )
            for name, qty in (rows or []):
                k = (name or '').strip()
                sales_qty_by_meal[k] = float(qty or 0)
        except Exception:
            sales_qty_by_meal = {}

        estimated_total_meal_cost = 0.0
        meals_analysis = []
        outdated_meals = []
        sold_details_map = {}
        def latest_purchase_date(rm_id: int):
            try:
                d = (
                    db.session.query(PurchaseInvoice.date)
                    .join(PurchaseInvoiceItem, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                    .filter(PurchaseInvoiceItem.raw_material_id == rm_id)
                    .order_by(PurchaseInvoice.date.desc(), PurchaseInvoiceItem.id.desc())
                    .first()
                )
                return d[0] if d and d[0] else None
            except Exception:
                return None
        OUTDATED_DAYS = 60
        for m_name, sold_qty in sales_qty_by_meal.items():
            meal = meal_by_name.get(m_name)
            if not meal:
                continue
            total_cost = 0.0
            outdated_flag = False
            try:
                ingrs = MealIngredient.query.filter_by(meal_id=int(meal.id)).all()
            except Exception:
                ingrs = []
            for ing in (ingrs or []):
                unit_cost = latest_cost_per_unit(int(getattr(ing, 'raw_material_id', 0) or 0))
                last_dt = latest_purchase_date(int(getattr(ing, 'raw_material_id', 0) or 0))
                if not last_dt or (today - last_dt).days > OUTDATED_DAYS:
                    outdated_flag = True
                qty_needed = float(getattr(ing, 'quantity', 0) or 0)
                total_cost += unit_cost * qty_needed * float(sold_qty or 0)
            estimated_total_meal_cost += total_cost
            revenue = float(getattr(meal, 'selling_price', 0) or 0) * float(sold_qty or 0)
            profit = revenue - total_cost
            meals_analysis.append({
                'meal_name': m_name,
                'sold_qty': float(sold_qty or 0),
                'consumption_cost': float(total_cost or 0),
                'revenue': float(revenue or 0),
                'profit': float(profit or 0),
            })
            if outdated_flag:
                outdated_meals.append(m_name)

        try:
            det_rows = (
                db.session.query(
                    SalesInvoiceItem.product_name,
                    SalesInvoice.invoice_number,
                    SalesInvoice.date,
                    SalesInvoiceItem.quantity,
                    SalesInvoiceItem.total_price,
                    SalesInvoiceItem.price_before_tax
                )
                .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id)
                .filter(SalesInvoiceItem.invoice_id.in_(sales_invoice_ids))
                .filter((SalesInvoice.branch == branch_arg) if branch_arg else True)
                .order_by(SalesInvoice.date.desc(), SalesInvoiceItem.id.desc())
                .limit(1000)
                .all()
            )
            for name, inv_no, dt, qty, total_p, unit_p in (det_rows or []):
                key = (name or '').strip()
                sold_details_map.setdefault(key, []).append({
                    'invoice_number': inv_no,
                    'date': (dt.isoformat() if dt else ''),
                    'quantity': float(qty or 0),
                    'unit_price': float(unit_p or 0),
                    'total_price': float(total_p or 0),
                })
        except Exception:
            sold_details_map = {}

        total_profit_generated = float(total_sales_revenue_month or 0) - float(estimated_total_meal_cost or 0)

        purchases_rows = []
        try:
            invs_m = (
                PurchaseInvoice.query
                .filter(PurchaseInvoice.date >= start_period, PurchaseInvoice.date <= end_period)
                .order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc())
                .limit(500)
                .all()
            )
            for inv in (invs_m or []):
                items_count = int(PurchaseInvoiceItem.query.filter_by(invoice_id=inv.id).count() or 0)
                purchases_rows.append({
                    'date': inv.date.isoformat() if getattr(inv, 'date', None) else '',
                    'invoice_number': getattr(inv, 'invoice_number', ''),
                    'supplier': getattr(inv, 'supplier_name', '') or '-',
                    'payment_method': getattr(inv, 'payment_method', '') or '-',
                    'status': getattr(inv, 'status', '') or '-',
                    'subtotal': float(getattr(inv, 'total_before_tax', 0) or 0),
                    'vat': float(getattr(inv, 'tax_amount', 0) or 0),
                    'discount': float(getattr(inv, 'discount_amount', 0) or 0),
                    'final_total': float(getattr(inv, 'total_after_tax_discount', 0) or 0),
                    'items_count': items_count,
                })
        except Exception:
            purchases_rows = []

        top_ingredients = []
        purchase_trend = []
        try:
            rows_t = (
                db.session.query(PurchaseInvoiceItem.raw_material_name, func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0))
                .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                .filter(PurchaseInvoice.date >= start_period, PurchaseInvoice.date <= end_period)
                .group_by(PurchaseInvoiceItem.raw_material_name)
                .order_by(func.coalesce(func.sum(PurchaseInvoiceItem.total_price), 0).desc())
                .limit(10)
                .all()
            )
            top_ingredients = [{'name': n, 'total': float(t or 0)} for n, t in (rows_t or [])]
            trows = (
                db.session.query(PurchaseInvoice.date, func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
                .filter(PurchaseInvoice.date >= start_period, PurchaseInvoice.date <= end_period)
                .group_by(PurchaseInvoice.date)
                .order_by(PurchaseInvoice.date.asc())
                .all()
            )
            purchase_trend = [{'date': (d.isoformat() if d else ''), 'total': float(t or 0)} for d, t in (trows or [])]
        except Exception:
            top_ingredients = []
            purchase_trend = []
        try:
            trend_max_total = max([float(x.get('total') or 0) for x in (purchase_trend or [])]) if purchase_trend else 1.0
        except Exception:
            trend_max_total = 1.0
        try:
            top_total_max = max([float(x.get('total') or 0) for x in (top_ingredients or [])]) if top_ingredients else 1.0
        except Exception:
            top_total_max = 1.0

        stock_rows = []
        try:
            p_qty_rows = (
                db.session.query(PurchaseInvoiceItem.raw_material_id, func.coalesce(func.sum(PurchaseInvoiceItem.quantity), 0))
                .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                .filter(PurchaseInvoice.date >= start_period, PurchaseInvoice.date <= end_period)
                .group_by(PurchaseInvoiceItem.raw_material_id)
                .all()
            )
            p_qty_map = {int(rm_id): float(qty or 0) for rm_id, qty in (p_qty_rows or []) if rm_id is not None}
            usage_map = {}
            for m in (meals_list or []):
                sold = float(sales_qty_by_meal.get((getattr(m, 'name', '') or '').strip(), 0) or 0)
                if sold <= 0:
                    continue
                ingrs = MealIngredient.query.filter_by(meal_id=int(m.id)).all()
                for ing in (ingrs or []):
                    usage_map[int(getattr(ing, 'raw_material_id', 0) or 0)] = usage_map.get(int(getattr(ing, 'raw_material_id', 0) or 0), 0.0) + (float(getattr(ing, 'quantity', 0) or 0) * sold)
            for rm in (raw_materials or []):
                rid = int(getattr(rm, 'id', 0) or 0)
                opening_qty = float(getattr(rm, 'stock_quantity', 0) or 0)
                purchases_qty = float(p_qty_map.get(rid, 0) or 0)
                estimated_usage = float(usage_map.get(rid, 0) or 0)
                expected_stock = max(opening_qty + purchases_qty - estimated_usage, 0.0)
                risk = 'low' if expected_stock < max(1.0, opening_qty * 0.1) else ('excess' if purchases_qty > estimated_usage * 1.5 else 'ok')
                stock_rows.append({
                    'ingredient': rm.display_name,
                    'opening_qty': opening_qty,
                    'purchases_qty': purchases_qty,
                    'estimated_usage': estimated_usage,
                    'expected_stock': expected_stock,
                    'risk': risk,
                })
        except Exception:
            stock_rows = []

        try:
            db.session.rollback()
        except Exception:
            pass
        return render_template(
            'inventory.html',
            raw_materials=raw_materials,
            meals=meals,
            ledger_rows=ledger_rows,
            purchases=purchases,
            _=(lambda s, **kw: s),
            kpi={
                'total_inventory_cost': float(total_inventory_cost or 0),
                'total_purchases_month': float(total_purchases_month or 0),
                'total_meals_sold_month': float(total_meals_sold_month or 0),
                'estimated_total_meal_cost': float(estimated_total_meal_cost or 0),
                'total_profit_generated': float(total_profit_generated or 0),
            },
            purchases_summary=purchases_rows,
            top_ingredients=top_ingredients,
            purchase_trend=purchase_trend,
            trend_max_total=trend_max_total,
            top_total_max=top_total_max,
            meals_analysis=meals_analysis,
            outdated_meals=outdated_meals,
            sold_details_map=sold_details_map,
            stock_rows=stock_rows,
            branches=BRANCH_LABELS,
            selected_branch=branch_arg,
            start_date_val=start_period.isoformat() if start_period else '',
            end_date_val=end_period.isoformat() if end_period else '',
            start_ledger_val=start_ledger.isoformat(),
            end_ledger_val=end_ledger.isoformat(),
        )
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return render_template(
            'inventory.html',
            raw_materials=raw_materials,
            meals=meals,
            ledger_rows=ledger_rows,
            purchases=purchases,
            _=(lambda s, **kw: s),
            kpi={
                'total_inventory_cost': 0.0,
                'total_purchases_month': 0.0,
                'total_meals_sold_month': 0.0,
                'estimated_total_meal_cost': 0.0,
                'total_profit_generated': 0.0,
            },
            purchases_summary=[],
            top_ingredients=[],
            purchase_trend=[],
            trend_max_total=1.0,
            top_total_max=1.0,
            meals_analysis=[],
            outdated_meals=[],
            sold_details_map={},
            stock_rows=[],
            branches=BRANCH_LABELS,
            selected_branch='',
            start_date_val='',
            end_date_val='',
            start_ledger_val=start_ledger.isoformat(),
            end_ledger_val=end_ledger.isoformat(),
        )


@bp.route('/api/inventory/intelligence', methods=['GET'], endpoint='api_inventory_intelligence')
@login_required
def api_inventory_intelligence():
    try:
        import math
        # Feature flag and access control
        if not current_app.config.get('INVENTORY_INTEL_ENABLED', False):
            return jsonify({"message": "⚠ Inventory Intelligence is disabled"}), 403
        role = (getattr(current_user, 'role', '') or '').strip().lower()
        username = (getattr(current_user, 'username', '') or '').strip().lower()
        if role != 'admin' and username != 'admin' and getattr(current_user, 'id', None) != 1:
            return jsonify({"error": "Access denied"}), 403

        cost_method = (request.args.get('method') or 'avg').strip().lower()
        locale = (request.args.get('locale') or 'ar').strip().lower()
        sd = (request.args.get('start_date') or '').strip()
        ed = (request.args.get('end_date') or '').strip()
        today = get_saudi_now().date()
        start_date = today.replace(day=1)
        end_date = today
        try:
            if sd:
                start_date = datetime.strptime(sd, '%Y-%m-%d').date()
        except Exception:
            start_date = today.replace(day=1)
        try:
            if ed:
                end_date = datetime.strptime(ed, '%Y-%m-%d').date()
        except Exception:
            end_date = today

        # If not preview mode, return lightweight KPI-only response
        if (request.args.get('preview') or '').strip() != '1':
            try:
                month_purchases_total = float(
                    db.session.query(func.coalesce(func.sum(PurchaseInvoice.total_after_tax_discount), 0))
                    .filter(PurchaseInvoice.date >= start_date, PurchaseInvoice.date <= end_date)
                    .scalar() or 0
                )
            except Exception:
                month_purchases_total = 0.0
            try:
                inv_ids = [int(r[0]) for r in db.session.query(SalesInvoice.id).filter(SalesInvoice.date >= start_date, SalesInvoice.date <= end_date).all()] or []
                meals_sold = float(
                    db.session.query(func.coalesce(func.sum(SalesInvoiceItem.quantity), 0))
                    .filter(SalesInvoiceItem.invoice_id.in_(inv_ids) if inv_ids else text('1=0'))
                    .scalar() or 0
                )
            except Exception:
                meals_sold = 0.0
            kpi = {
                'total_inventory_value': 0.0,
                'month_purchases_total': month_purchases_total,
                'meals_sold': meals_sold,
                'estimated_production_cost': 0.0,
                'total_profit': 0.0,
                'label_en': 'KPI Overview',
                'label_ar': 'المؤشرات الرئيسية',
                'note': 'Preview mode required for full analysis (use preview=1)'
            }
            return jsonify({
                'kpi': kpi,
                'purchases_summary': [],
                'meal_analysis': [],
                'stock_analysis': [],
                'alerts': []
            })

        def latest_unit_cost_map():
            rows = (
                db.session.query(PurchaseInvoiceItem.raw_material_id, PurchaseInvoiceItem.price_before_tax, PurchaseInvoice.date)
                .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                .order_by(PurchaseInvoiceItem.raw_material_id.asc(), PurchaseInvoice.date.desc(), PurchaseInvoiceItem.id.desc())
                .all()
            )
            m = {}
            seen = set()
            for rid, price, dt in rows:
                if rid is None:
                    continue
                if rid in seen:
                    continue
                m[int(rid)] = float(price or 0)
                seen.add(int(rid))
            return m

        def avg_unit_cost_map():
            rows = (
                db.session.query(PurchaseInvoiceItem.raw_material_id, func.coalesce(func.sum(PurchaseInvoiceItem.quantity * PurchaseInvoiceItem.price_before_tax), 0), func.coalesce(func.sum(PurchaseInvoiceItem.quantity), 0))
                .group_by(PurchaseInvoiceItem.raw_material_id)
                .all()
            )
            m = {}
            for rid, total_cost, total_qty in rows:
                if rid is None:
                    continue
                denom = float(total_qty or 0)
                m[int(rid)] = (float(total_cost or 0) / denom) if denom > 0 else 0.0
            return m

        def get_purchase_lots(rm_id: int):
            lots = (
                db.session.query(PurchaseInvoiceItem.quantity, PurchaseInvoiceItem.price_before_tax)
                .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
                .filter(PurchaseInvoiceItem.raw_material_id == rm_id)
                .order_by(PurchaseInvoice.date.asc(), PurchaseInvoiceItem.id.asc())
                .all()
            )
            return [{'qty': float(q or 0), 'price': float(p or 0)} for q, p in (lots or [])]

        def fifo_cost(usage_qty: float, lots: list):
            remaining = float(usage_qty or 0)
            cost = 0.0
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(remaining, float(lot.get('qty') or 0))
                cost += take * float(lot.get('price') or 0)
                remaining -= take
            return cost

        latest_cost = latest_unit_cost_map()
        avg_cost = avg_unit_cost_map()
        cost_map = avg_cost if cost_method == 'fifo' and not avg_cost else (avg_cost if cost_method == 'avg' else latest_cost)

        invs = (
            db.session.query(PurchaseInvoice)
            .filter(PurchaseInvoice.date >= start_date, PurchaseInvoice.date <= end_date)
            .order_by(PurchaseInvoice.date.desc(), PurchaseInvoice.id.desc())
            .limit(500)
            .all()
        )
        purchases_summary = []
        for inv in (invs or []):
            items_count = int(PurchaseInvoiceItem.query.filter_by(invoice_id=inv.id).count() or 0)
            purchases_summary.append({
                'date': inv.date.isoformat() if getattr(inv, 'date', None) else '',
                'invoice_no': getattr(inv, 'invoice_number', ''),
                'supplier': getattr(inv, 'supplier_name', '') or '-',
                'subtotal': float(getattr(inv, 'total_before_tax', 0) or 0),
                'vat': float(getattr(inv, 'tax_amount', 0) or 0),
                'discount': float(getattr(inv, 'discount_amount', 0) or 0),
                'final_total': float(getattr(inv, 'total_after_tax_discount', 0) or 0),
                'items_count': items_count,
                'label_en': 'Purchases Summary',
                'label_ar': 'ملخص المشتريات',
            })

        sales_ids = [int(r[0]) for r in (
            db.session.query(SalesInvoice.id)
            .filter(SalesInvoice.date >= start_date, SalesInvoice.date <= end_date)
            .all()
        )]

        name_qty_rev = {}
        if sales_ids:
            rows = (
                db.session.query(SalesInvoiceItem.product_name, func.coalesce(func.sum(SalesInvoiceItem.quantity), 0), func.coalesce(func.sum(SalesInvoiceItem.quantity * SalesInvoiceItem.price_before_tax), 0))
                .filter(SalesInvoiceItem.invoice_id.in_(sales_ids))
                .group_by(SalesInvoiceItem.product_name)
                .all()
            )
            for name, qty, rev in (rows or []):
                k = (name or '').strip()
                name_qty_rev[k] = {'qty_sold': float(qty or 0), 'revenue': float(rev or 0)}

        meals = Meal.query.filter_by(active=True).all()
        def _norm_txt(x: str) -> str:
            import unicodedata, re
            t = (x or '').strip().lower()
            t = t.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩٬٫', '0123456789,.'))
            repl = {'أ':'ا','إ':'ا','آ':'ا','ى':'ي','ؤ':'و','ئ':'ي','ة':'ه'}
            t = ''.join(repl.get(ch, ch) for ch in t)
            t = unicodedata.normalize('NFD', t)
            t = ''.join(ch for ch in t if unicodedata.category(ch) != 'Mn')
            t = re.sub(r"[^0-9a-z\u0621-\u064A ]+", " ", t)
            t = re.sub(r"\s+", " ", t).strip()
            return t
        def _meal_index(meals_list):
            idx = {}
            for m in (meals_list or []):
                n1 = (getattr(m, 'name', '') or '').strip()
                n2 = (getattr(m, 'name_ar', '') or '').strip()
                if n1:
                    idx[_norm_txt(n1)] = m
                if n2:
                    idx[_norm_txt(n2)] = m
                dn = (getattr(m, 'display_name', '') or '').strip()
                if dn:
                    for part in [p.strip() for p in dn.split('/') if p.strip()]:
                        idx[_norm_txt(part)] = m
            return idx
        _idx = _meal_index(meals)
        from difflib import SequenceMatcher
        def _resolve_meal(name):
            if not (name or '').strip():
                return None
            q = _norm_txt(name)
            m = _idx.get(q)
            if m:
                return m
            best = None
            best_score = 0.0
            for k, mv in _idx.items():
                r = SequenceMatcher(None, q, k).ratio()
                if r > best_score:
                    best = mv
                    best_score = r
            if best_score >= 0.86:
                return best
            tokens_q = set(q.split())
            for k, mv in _idx.items():
                toks_k = set(k.split())
                inter = len(tokens_q & toks_k)
                base = max(len(tokens_q), 1)
                if base > 0 and (inter / base) >= 0.7:
                    return mv
            return None
        meal_analysis = []
        total_profit = 0.0
        for m_name, s in name_qty_rev.items():
            meal = _resolve_meal(m_name)
            if not meal:
                continue
            ingrs = MealIngredient.query.filter_by(meal_id=int(meal.id)).all()
            cost_val = 0.0
            for ing in (ingrs or []):
                rid = int(getattr(ing, 'raw_material_id', 0) or 0)
                usage = float(s['qty_sold'] or 0) * float(getattr(ing, 'quantity', 0) or 0)
                if cost_method == 'fifo':
                    cost_val += fifo_cost(usage, get_purchase_lots(rid))
                else:
                    unit_cost = float(cost_map.get(rid, latest_cost.get(rid, 0)) or 0)
                    cost_val += usage * unit_cost
            revenue = float(s['revenue'] or 0)
            profit = revenue - cost_val
            total_profit += profit
            meal_analysis.append({
                'meal_id': int(getattr(meal, 'id', 0) or 0),
                'meal_name': m_name,
                'qty_sold': float(s['qty_sold'] or 0),
                'consumption_cost': float(cost_val or 0),
                'revenue': float(revenue or 0),
                'profit': float(profit or 0),
            })
        for m in meal_analysis:
            rev = float(m.get('revenue') or 0)
            prof = float(m.get('profit') or 0)
            m['margin_pct'] = (prof / rev) if rev > 0 else 0.0
            m['contribution_pct'] = (prof / total_profit) if total_profit > 0 else 0.0

        usage_map = {}
        for m_name, s in name_qty_rev.items():
            meal = _resolve_meal(m_name)
            if not meal:
                continue
            ingrs = MealIngredient.query.filter_by(meal_id=int(meal.id)).all()
            for ing in (ingrs or []):
                rid = int(getattr(ing, 'raw_material_id', 0) or 0)
                usage_map[rid] = usage_map.get(rid, 0.0) + (float(s['qty_sold'] or 0) * float(getattr(ing, 'quantity', 0) or 0))

        opening_map = {int(getattr(rm, 'id', 0) or 0): float(getattr(rm, 'stock_quantity', 0) or 0) for rm in RawMaterial.query.filter_by(active=True).all()}
        p_qty_rows = (
            db.session.query(PurchaseInvoiceItem.raw_material_id, func.coalesce(func.sum(PurchaseInvoiceItem.quantity), 0))
            .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
            .filter(PurchaseInvoice.date >= start_date, PurchaseInvoice.date <= end_date)
            .group_by(PurchaseInvoiceItem.raw_material_id)
            .all()
        )
        purchases_qty = {int(rm_id): float(qty or 0) for rm_id, qty in (p_qty_rows or []) if rm_id is not None}
        last_batch_rows = (
            db.session.query(PurchaseInvoiceItem.raw_material_id, PurchaseInvoiceItem.quantity)
            .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
            .order_by(PurchaseInvoiceItem.raw_material_id.asc(), PurchaseInvoice.date.desc(), PurchaseInvoiceItem.id.desc())
            .all()
        )
        last_batch_qty = {}
        seen = set()
        for rid, q in (last_batch_rows or []):
            if rid is None:
                continue
            if int(rid) in seen:
                continue
            last_batch_qty[int(rid)] = float(q or 0)
            seen.add(int(rid))

        stock_analysis = []
        for rid in set(list(opening_map.keys()) + list(purchases_qty.keys()) + list(usage_map.keys())):
            opening_qty = float(opening_map.get(rid, 0) or 0)
            purchases_q = float(purchases_qty.get(rid, 0) or 0)
            usage_q = float(usage_map.get(rid, 0) or 0)
            expected = opening_qty + purchases_q - usage_q
            last_q = float(last_batch_qty.get(rid, 0) or 0)
            thr = last_q * 0.10
            risk = 'ok'
            if expected < 0:
                risk = 'negative'
            elif expected <= thr:
                risk = 'low'
            stock_analysis.append({
                'ingredient_id': rid,
                'opening_qty': opening_qty,
                'purchases_qty': purchases_q,
                'estimated_usage': usage_q,
                'expected_stock': expected,
                'risk': risk,
                'label_en': 'Stock Analysis',
                'label_ar': 'تحليل المخزون',
            })

        total_inventory_value = 0.0
        for s in stock_analysis:
            rid = int(s.get('ingredient_id') or 0)
            unit_cost = float(latest_cost.get(rid, avg_cost.get(rid, 0)) or 0)
            total_inventory_value += max(float(s.get('expected_stock') or 0), 0.0) * unit_cost

        kpi = {
            'total_inventory_value': float(total_inventory_value or 0),
            'month_purchases_total': float(sum([ps['final_total'] for ps in purchases_summary]) or 0),
            'meals_sold': float(sum([s['qty_sold'] for s in name_qty_rev.values()]) or 0),
            'estimated_production_cost': float(sum([m['consumption_cost'] for m in meal_analysis]) or 0),
            'total_profit': float(sum([m['profit'] for m in meal_analysis]) or 0),
            'label_en': 'KPI Overview',
            'label_ar': 'المؤشرات الرئيسية',
        }

        outdated_ids = []
        rows_last = (
            db.session.query(PurchaseInvoiceItem.raw_material_id, PurchaseInvoice.date)
            .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
            .order_by(PurchaseInvoiceItem.raw_material_id.asc(), PurchaseInvoice.date.desc())
            .all()
        )
        seen = set()
        for rid, dt in (rows_last or []):
            if rid is None:
                continue
            if int(rid) in seen:
                continue
            seen.add(int(rid))
            if not dt or (today - dt).days > 60:
                outdated_ids.append(int(rid))
        alerts = []
        for m in meal_analysis:
            if float(m.get('margin_pct', 0) or 0) < 0.15:
                alerts.append({'type': 'low_margin', 'meal_id': int(m.get('meal_id') or 0), 'label_en': 'Low Margin', 'label_ar': 'هامش منخفض'})
        for rid in outdated_ids:
            alerts.append({'type': 'outdated_cost', 'ingredient_id': rid, 'label_en': 'Outdated Cost', 'label_ar': 'سعر قديم'})
        for s in stock_analysis:
            if (s.get('risk') or '') in ('negative','low'):
                alerts.append({'type': 'stock_risk', 'ingredient_id': int(s.get('ingredient_id') or 0), 'risk': s.get('risk'), 'label_en': 'Stock Risk', 'label_ar': 'مخاطر المخزون'})

        payload = {
            'kpi': kpi,
            'purchases_summary': purchases_summary,
            'meal_analysis': meal_analysis,
            'stock_analysis': stock_analysis,
            'alerts': alerts,
        }
        return jsonify(payload)
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
