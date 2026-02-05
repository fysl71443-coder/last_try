# -*- coding: utf-8 -*-
"""
محرك التدقيق: يشغّل قواعد التدقيق ويبني التقرير.
كل شيء ينتهي إلى Journal Entries — المدقق لا يثق بأحد.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Any, Optional

from .rules import run_all_rules
from .report_builder import build_report, save_findings_to_db


def run_audit(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    fiscal_year_id: Optional[int] = None,
    entity_name: str = "النظام المحاسبي",
    persist_findings: bool = False,
) -> Dict[str, Any]:
    """
    تشغيل كل قواعد التدقيق على نطاق التواريخ، بناء التقرير، واختيارياً تخزين الملاحظات في DB.
    يرجع: { findings, summary: {total, high, medium, low}, meta }.
    """
    raw = run_all_rules(from_date, to_date)
    report = build_report(raw, from_date=from_date, to_date=to_date, entity_name=entity_name)
    if (persist_findings or fiscal_year_id) and report.get("findings"):
        save_findings_to_db(report, fiscal_year_id=fiscal_year_id)
    return report


def has_critical_findings(from_date: Optional[date], to_date: Optional[date]) -> bool:
    """
    يُستخدم قبل إغلاق السنة المالية: هل توجد ملاحظات حرجة (عالية) في النطاق؟
    يشغّل التدقيق دون تخزين ويرجع True إذا summary.high > 0.
    """
    report = run_audit(from_date=from_date, to_date=to_date, persist_findings=False)
    return (report.get("summary") or {}).get("high", 0) > 0


def get_closure_audit_snapshot(from_date: Optional[date], to_date: Optional[date]) -> Dict[str, Any]:
    """
    لقطة تدقيق للإقفال: تشغيل التدقيق دون تخزين وإرجاع ملخص + وقت التشغيل لحفظها في سجل الإقفال.
    يرجع: { run_at, summary: { total, high, medium, low } }.
    """
    report = run_audit(from_date=from_date, to_date=to_date, persist_findings=False)
    meta = report.get("meta") or {}
    summary = report.get("summary") or {}
    return {
        "run_at": meta.get("run_at").isoformat() if meta.get("run_at") else None,
        "summary": {
            "total": summary.get("total", 0),
            "high": summary.get("high", 0),
            "medium": summary.get("medium", 0),
            "low": summary.get("low", 0),
        },
    }
