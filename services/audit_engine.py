# -*- coding: utf-8 -*-
"""
محرك التدقيق المحاسبي — واجهة الخدمة.
المنطق الفعلي في modules/audit (engine, rules, report_builder).
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Any, Optional


def run_audit(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    fiscal_year_id: Optional[int] = None,
    persist_findings: bool = False,
) -> Dict[str, Any]:
    """
    تشغيل التدقيق وإرجاع التقرير (findings, summary, meta).
    للاستدعاء من مسارات التدقيق وشاشة السنوات المالية.
    """
    from modules.audit import run_audit as _run
    return _run(
        from_date=from_date,
        to_date=to_date,
        fiscal_year_id=fiscal_year_id,
        persist_findings=persist_findings,
    )
