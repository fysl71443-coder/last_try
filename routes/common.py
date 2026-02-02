# Phase 2 – Shared helpers. No route handlers.
# Used by main and other blueprints. Avoid loading accounts/settings/permissions
# in context_processor/before_request; each route loads what it needs.
# Lazy import of AppKV to avoid circular import (app.routes -> common -> app.models -> app).

from __future__ import annotations

import json
from flask_login import current_user
from extensions import db

BRANCH_LABELS = {
    'place_india': 'Place India',
    'china_town': 'China Town',
}


def safe_table_number(table_number) -> int:
    try:
        return int(table_number or 0)
    except (ValueError, TypeError):
        return 0


def kv_get(key, default=None):
    from app.models import AppKV
    rec = AppKV.query.filter_by(k=key).first()
    if not rec:
        return default
    try:
        return json.loads(rec.v)
    except Exception:
        return default


def kv_set(key, value):
    from app.models import AppKV
    data = json.dumps(value or {})
    rec = AppKV.query.filter_by(k=key).first()
    if rec:
        rec.v = data
    else:
        rec = AppKV(k=key, v=data)
        db.session.add(rec)
    db.session.commit()


def _normalize_scope(s: str) -> str:
    s = (s or '').strip().lower()
    if s in ('place', 'palace', 'india', 'palace_india'):
        return 'place_india'
    if s in ('china', 'china town', 'chinatown'):
        return 'china_town'
    return s or 'all'


def _read_user_perms(uid: int, scope: str):
    try:
        from app.models import AppKV
        k = f"user_perms:{scope}:{int(uid)}"
        row = AppKV.query.filter_by(k=k).first()
        if not row:
            return {}
        data = json.loads(row.v)
        items = data.get('items') or []
        out = {}
        for it in items:
            key = (it.get('screen_key') or '').strip()
            if not key:
                continue
            out[key] = {
                'view': bool(it.get('view')),
                'add': bool(it.get('add')),
                'edit': bool(it.get('edit')),
                'delete': bool(it.get('delete')),
                'print': bool(it.get('print')),
            }
        return out
    except Exception:
        return {}


def user_can(screen: str, action: str = 'view', branch_scope: str = None) -> bool:
    try:
        if not getattr(current_user, 'is_authenticated', False):
            return False
        if getattr(current_user, 'username', '') == 'admin' or getattr(current_user, 'id', None) == 1:
            return True
        if getattr(current_user, 'role', '') == 'admin':
            return True
        return True
    except Exception:
        return True
