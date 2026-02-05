# -*- coding: utf-8 -*-
"""
كاش لقطات التدقيق — الشاشة تقرأ سطراً واحداً بدل تشغيل محرك التدقيق.
الحساب يتم عند: تشغيل التدقيق، الإقفال، إعادة الفتح.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional


def get_last_audit_snapshot(fiscal_year_id: int) -> Optional[Dict[str, Any]]:
    """آخر لقطة تدقيق محفوظة لهذه السنة — استعلام خفيف (سطر واحد)."""
    try:
        from models import AuditSnapshot
        row = AuditSnapshot.query.filter_by(fiscal_year_id=fiscal_year_id).order_by(
            AuditSnapshot.run_at.desc()
        ).first()
        if not row:
            return None
        return {
            "run_at": row.run_at,
            "summary": {
                "total": row.total,
                "high": row.high,
                "medium": row.medium,
                "low": row.low,
            },
        }
    except Exception:
        return None


def save_audit_snapshot(
    fiscal_year_id: int,
    summary: Dict[str, Any],
    run_at: Optional[datetime] = None,
) -> None:
    """حفظ لقطة تدقيق (يُستدعى بعد تشغيل التدقيق أو عند الإقفال/إعادة الفتح)."""
    try:
        from extensions import db
        from models import AuditSnapshot, get_saudi_now
        total = int(summary.get("total", 0) or 0)
        high = int(summary.get("high", 0) or 0)
        medium = int(summary.get("medium", 0) or 0)
        low = int(summary.get("low", 0) or 0)
        ts = run_at or get_saudi_now()
        row = AuditSnapshot(
            fiscal_year_id=fiscal_year_id,
            total=total,
            high=high,
            medium=medium,
            low=low,
            run_at=ts,
        )
        db.session.add(row)
        db.session.commit()
    except Exception:
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass
