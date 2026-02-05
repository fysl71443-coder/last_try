# -*- coding: utf-8 -*-
"""
بناء التقرير الاحترافي: ترقيم الملاحظات، الملخص التنفيذي، وإعداد المخرجات للعرض والطباعة.
يمكن تخزين النتائج في جدول audit_findings.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Dict, Any, Optional


def _severity_ar(severity: str) -> str:
    if severity == "high":
        return "عالية"
    if severity == "medium":
        return "متوسطة"
    return "منخفضة"


def build_report(
    raw_findings: List[Dict[str, Any]],
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    entity_name: str = "النظام المحاسبي",
    run_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    يرقّم الملاحظات ويضيف severity_ar ويبني الملخص والـ meta.
    يرجع: { findings, summary: {total, high, medium, low}, meta }
    """
    if run_at is None:
        from models import get_saudi_now
        run_at = get_saudi_now()

    findings: List[Dict[str, Any]] = []
    for i, r in enumerate(raw_findings, 1):
        entry_date = r.get("entry_date")
        findings.append({
            "number": i,
            "issue_type_ar": r.get("issue_type_ar", ""),
            "place_ar": r.get("place_ar", ""),
            "ref_number": r.get("ref_number", ""),
            "ref_type": r.get("ref_type"),
            "ref_id": r.get("ref_id"),
            "entry_date": str(entry_date) if entry_date else "",
            "description": r.get("description", ""),
            "difference_details": r.get("difference_details", ""),
            "root_cause_ar": r.get("root_cause_ar", ""),
            "severity": r.get("severity", "medium"),
            "severity_ar": _severity_ar(r.get("severity", "medium")),
            "correction_method": r.get("correction_method", ""),
        })

    high = sum(1 for f in findings if f.get("severity") == "high")
    medium = sum(1 for f in findings if f.get("severity") == "medium")
    low = sum(1 for f in findings if f.get("severity") == "low")

    return {
        "findings": findings,
        "summary": {"total": len(findings), "high": high, "medium": medium, "low": low},
        "meta": {
            "run_at": run_at,
            "from_date": from_date,
            "to_date": to_date,
            "entity_name": entity_name,
        },
    }


def save_findings_to_db(
    report: Dict[str, Any],
    fiscal_year_id: Optional[int] = None,
) -> None:
    """
    تخزين ملاحظات التقرير في جدول audit_findings (إن وُجد النموذج).
    عند تمرير fiscal_year_id يتم حذف ملاحظات نفس السنة السابقة ثم إدراج الجديدة.
    """
    try:
        from extensions import db
        from models import AuditFinding
    except ImportError:
        return
    if not report or not report.get("findings"):
        return
    if fiscal_year_id:
        try:
            AuditFinding.query.filter_by(fiscal_year_id=fiscal_year_id).delete()
        except Exception:
            pass
    meta = report.get("meta") or {}
    run_at = meta.get("run_at")
    from_date = meta.get("from_date")
    to_date = meta.get("to_date")
    for f in report["findings"]:
        row = AuditFinding(
            fiscal_year_id=fiscal_year_id,
            journal_entry_id=f.get("ref_id") if f.get("ref_type") == "journal" else None,
            entry_number=f.get("ref_number", ""),
            issue_type_ar=f.get("issue_type_ar", ""),
            place_ar=f.get("place_ar", ""),
            description=f.get("description", ""),
            difference_details=f.get("difference_details", ""),
            root_cause_ar=f.get("root_cause_ar", ""),
            severity=f.get("severity", "medium"),
            correction_method=f.get("correction_method", ""),
            entry_date=run_at.date() if run_at else None,
            audit_run_from=from_date,
            audit_run_to=to_date,
            audit_run_at=run_at,
        )
        db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
