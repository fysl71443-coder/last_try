# Phase 3 – Cache helpers. TTLs: settings 10min, COA 15min, VAT 5min, reports preview 2min.
from __future__ import annotations

import json
from types import SimpleNamespace

SETTINGS_TTL = 600       # 10 min
COA_TTL = 900            # 15 min
VAT_TTL = 300            # 5 min
REPORTS_PREVIEW_TTL = 120  # 2 min

SETTINGS_CACHE_KEY = "settings"
COA_CACHE_KEY = "coa"
VAT_CACHE_KEY_PREFIX = "vat:"
REPORTS_PREVIEW_KEY_PREFIX = "rprev:"


def _cache():
    """Use the Cache instance from extensions (Flask-Caching stores backends in extensions['cache'] dict)."""
    try:
        from extensions import cache
        if cache is not None and hasattr(cache, "get") and hasattr(cache, "set"):
            return cache
        return None
    except Exception:
        return None


def _settings_to_dict(s):
    if s is None:
        return None
    out = {}
    for k in ("id", "company_name", "tax_number", "address", "phone", "email",
              "vat_rate", "place_india_label", "china_town_label", "currency",
              "default_theme", "printer_type", "currency_image", "footer_message",
              "china_town_void_password", "china_town_vat_rate", "china_town_discount_rate",
              "china_town_phone1", "china_town_phone2", "china_town_logo_url",
              "place_india_void_password", "place_india_vat_rate", "place_india_discount_rate",
              "place_india_phone1", "place_india_phone2", "place_india_logo_url",
              "receipt_paper_width", "receipt_margin_top_mm", "receipt_margin_bottom_mm",
              "receipt_margin_left_mm", "receipt_margin_right_mm", "receipt_font_size",
              "receipt_show_logo", "receipt_show_tax_number", "receipt_footer_text",
              "receipt_logo_height", "receipt_extra_bottom_mm", "logo_url",
              "receipt_high_contrast", "receipt_bold_totals", "receipt_border_style", "receipt_font_bump"):
        v = getattr(s, k, None)
        if hasattr(v, "isoformat"):
            v = v.isoformat() if v else None
        elif hasattr(v, "__float__") and not isinstance(v, bool):
            try:
                v = float(v)
            except Exception:
                pass
        out[k] = v
    return out


def _dict_to_settings_ns(d):
    if d is None:
        return None
    return SimpleNamespace(**d)


def get_cached_settings(ttl: int = SETTINGS_TTL):
    c = _cache()
    if c is None:
        return _fetch_settings()
    val = c.get(SETTINGS_CACHE_KEY)
    if val is not None:
        return _dict_to_settings_ns(val)
    s = _fetch_settings()
    if s is not None:
        c.set(SETTINGS_CACHE_KEY, _settings_to_dict(s), timeout=ttl)
    return s


def _fetch_settings():
    from extensions import db
    from models import Settings
    try:
        return Settings.query.first()
    except Exception:
        return None


def invalidate_settings_cache():
    c = _cache()
    if c is not None:
        try:
            c.delete(SETTINGS_CACHE_KEY)
        except Exception:
            pass


def get_cached_coa(ttl: int = COA_TTL):
    c = _cache()
    if c is None:
        return _fetch_coa()
    val = c.get(COA_CACHE_KEY)
    if val is not None:
        return val
    out = _fetch_coa()
    if out is not None:
        c.set(COA_CACHE_KEY, out, timeout=ttl)
    return out


def _fetch_coa():
    from extensions import db
    from models import Account
    try:
        rows = Account.query.order_by(Account.code.asc()).all()
        out = []
        for a in rows:
            out.append({
                "account_code": getattr(a, "code", None),
                "account_name_ar": getattr(a, "name_ar", None),
                "account_name_en": getattr(a, "name_en", None),
                "account_type": getattr(a, "type", None),
                "level": getattr(a, "level", None),
                "parent_account_code": getattr(a, "parent_account_code", None),
                "allow_opening_balance": bool(getattr(a, "allow_opening_balance", True)),
                "vat_link_code": getattr(a, "vat_link_code", None),
                "pos_mapping_key": getattr(a, "pos_mapping_key", None),
                "inventory_link": bool(getattr(a, "inventory_link", False)),
                "depreciation_policy_id": getattr(a, "depreciation_policy_id", None),
                "notes": getattr(a, "notes", None),
            })
        return out
    except Exception:
        return None


def invalidate_coa_cache():
    c = _cache()
    if c is not None:
        try:
            c.delete(COA_CACHE_KEY)
        except Exception:
            pass


def vat_cache_key(start_date, end_date, branch: str) -> str:
    s = getattr(start_date, "isoformat", lambda: str(start_date))()
    e = getattr(end_date, "isoformat", lambda: str(end_date))()
    return f"{VAT_CACHE_KEY_PREFIX}{s}:{e}:{branch or 'all'}"


def get_cached_vat_data(key: str, fetcher, ttl: int = VAT_TTL):
    c = _cache()
    if c is None:
        return fetcher()
    val = c.get(key)
    if val is not None:
        return val
    data = fetcher()
    if data is not None:
        try:
            c.set(key, data, timeout=ttl)
        except Exception:
            pass
    return data


def reports_preview_cache_key(inv_type: str, start_s: str, end_s: str, branch: str, pm: str) -> str:
    return f"{REPORTS_PREVIEW_KEY_PREFIX}{inv_type}:{start_s}:{end_s}:{branch or 'all'}:{pm or 'all'}"


def get_cached_reports_preview(key: str, fetcher, ttl: int = REPORTS_PREVIEW_TTL):
    c = _cache()
    if c is None:
        return fetcher()
    val = c.get(key)
    if val is not None:
        return val
    data = fetcher()
    if data is not None:
        try:
            c.set(key, data, timeout=ttl)
        except Exception:
            pass
    return data
