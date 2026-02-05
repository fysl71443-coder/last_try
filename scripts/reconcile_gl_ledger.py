#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مهمة مصالحة دورية: مقارنة مجمّعات JournalLine (مرحّل) مقابل LedgerEntry.
- تصوّر الفروقات (تقارير، مخرجات JSON/HTML).
- إصلاح آلي أو شبه آلي: إضافة أسطر LedgerEntry الناقصة من القيود المرحّلة، أو اقتراح حذف زائد.

تشغيل:
  python scripts/reconcile_gl_ledger.py [--fix] [--report path]
  --fix: تطبيق إصلاح آلي (إضافة ناقص فقط؛ لا حذف تلقائي)
  --report: مسار ملف التقرير (JSON أو .html)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Tuple

def _bootstrap():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)
    from app import create_app
    app = create_app()
    app.app_context().push()
    return app

def aggregate_journal_lines(app) -> Dict[Tuple[int, date], Dict[str, float]]:
    """مجموع مدين/دائن لكل (account_id, line_date) من JournalLine حيث JournalEntry.status='posted'."""
    from app import db
    from models import JournalLine, JournalEntry
    from sqlalchemy import func

    q = (
        db.session.query(
            JournalLine.account_id,
            JournalLine.line_date,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
        )
        .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
        .filter(JournalEntry.status == "posted")
        .group_by(JournalLine.account_id, JournalLine.line_date)
    )
    out = {}
    for r in q.all():
        key = (int(r.account_id), r.line_date)
        out[key] = {"debit": float(r.debit or 0), "credit": float(r.credit or 0)}
    return out

def aggregate_ledger(app) -> Dict[Tuple[int, date], Dict[str, float]]:
    """مجموع مدين/دائن لكل (account_id, date) من LedgerEntry."""
    from app import db
    from models import LedgerEntry
    from sqlalchemy import func

    q = (
        db.session.query(
            LedgerEntry.account_id,
            LedgerEntry.date,
            func.coalesce(func.sum(LedgerEntry.debit), 0).label("debit"),
            func.coalesce(func.sum(LedgerEntry.credit), 0).label("credit"),
        )
        .group_by(LedgerEntry.account_id, LedgerEntry.date)
    )
    out = {}
    for r in q.all():
        key = (int(r.account_id), r.date)
        out[key] = {"debit": float(r.debit or 0), "credit": float(r.credit or 0)}
    return out

def reconcile(app) -> Dict[str, Any]:
    """مقارنة المجمّعين وإرجاع الفروقات والإحصائيات."""
    gl = aggregate_journal_lines(app)
    le = aggregate_ledger(app)
    all_keys = set(gl.keys()) | set(le.keys())
    differences: List[Dict[str, Any]] = []
    missing_in_ledger: List[Dict[str, Any]] = []
    extra_in_ledger: List[Dict[str, Any]] = []
    for key in all_keys:
        acc_id, dt = key
        g = gl.get(key, {"debit": 0.0, "credit": 0.0})
        l = le.get(key, {"debit": 0.0, "credit": 0.0})
        if key not in le:
            missing_in_ledger.append({"account_id": acc_id, "date": dt.isoformat(), "gl_debit": g["debit"], "gl_credit": g["credit"]})
        elif key not in gl:
            extra_in_ledger.append({"account_id": acc_id, "date": dt.isoformat(), "ledger_debit": l["debit"], "ledger_credit": l["credit"]})
        else:
            dd = round(g["debit"] - l["debit"], 2)
            dc = round(g["credit"] - l["credit"], 2)
            if dd != 0 or dc != 0:
                differences.append({
                    "account_id": acc_id,
                    "date": dt.isoformat(),
                    "gl_debit": g["debit"], "gl_credit": g["credit"],
                    "ledger_debit": l["debit"], "ledger_credit": l["credit"],
                    "diff_debit": dd, "diff_credit": dc,
                })
    return {
        "generated_at": datetime.now().isoformat(),
        "gl_keys_count": len(gl),
        "ledger_keys_count": len(le),
        "differences_count": len(differences),
        "missing_in_ledger_count": len(missing_in_ledger),
        "extra_in_ledger_count": len(extra_in_ledger),
        "differences": differences[:500],
        "missing_in_ledger": missing_in_ledger[:500],
        "extra_in_ledger": extra_in_ledger[:500],
        "ok": len(differences) == 0 and len(missing_in_ledger) == 0 and len(extra_in_ledger) == 0,
    }

def apply_fix_missing(app, report: Dict[str, Any]) -> int:
    """إصلاح آلي: إنشاء LedgerEntry من JournalLine المرحّل للحساب/التواريخ الناقصة (لا يحذف زائد)."""
    from app import db
    from models import LedgerEntry, JournalLine, JournalEntry

    missing = report.get("missing_in_ledger", [])
    if not missing:
        return 0
    added = 0
    for m in missing:
        acc_id = m["account_id"]
        dt_str = m["date"]
        try:
            dt = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        # نحصل على أسطر القيود المرحّلة لهذا الحساب وهذا التاريخ
        lines = (
            db.session.query(JournalLine, JournalEntry)
            .join(JournalEntry, JournalLine.journal_id == JournalEntry.id)
            .filter(
                JournalLine.account_id == acc_id,
                JournalLine.line_date == dt,
                JournalEntry.status == "posted",
            )
            .all()
        )
        for jl, je in lines:
            desc = f"JE {je.entry_number} L{jl.line_no} {jl.description}"
            db.session.add(LedgerEntry(date=dt, account_id=acc_id, debit=jl.debit or 0, credit=jl.credit or 0, description=desc))
            added += 1
    if added > 0:
        db.session.commit()
    return added

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="Apply auto-fix: add missing LedgerEntry from posted JournalLine")
    ap.add_argument("--report", type=str, default="", help="Write report to path (e.g. reconciliation.json or .html)")
    args = ap.parse_args()

    app = _bootstrap()
    with app.app_context():
        report = reconcile(app)
        print("Reconciliation:", "OK" if report["ok"] else "DIFFERENCES FOUND")
        print("  GL (account,date) keys:", report["gl_keys_count"])
        print("  Ledger (account,date) keys:", report["ledger_keys_count"])
        print("  Differences (mismatch):", report["differences_count"])
        print("  Missing in Ledger:", report["missing_in_ledger_count"])
        print("  Extra in Ledger:", report["extra_in_ledger_count"])

        if args.fix and report["missing_in_ledger_count"] > 0:
            n = apply_fix_missing(app, report)
            print(f"  Fix applied: added {n} LedgerEntry rows.")
            report = reconcile(app)
            print("  After fix - OK:", report["ok"])

        if args.report:
            path = args.report
            if path.endswith(".html"):
                html = _report_to_html(report)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
            print("  Report written to", path)
    return 0 if report.get("ok") else 1

def _report_to_html(report: Dict[str, Any]) -> str:
    rows = []
    for d in report.get("differences", [])[:100]:
        rows.append(f"<tr><td>{d['account_id']}</td><td>{d['date']}</td><td>{d['diff_debit']}</td><td>{d['diff_credit']}</td></tr>")
    missing = report.get("missing_in_ledger", [])[:100]
    for m in missing:
        rows.append(f"<tr><td>{m['account_id']}</td><td>{m['date']}</td><td colspan='2'>Missing in Ledger</td></tr>")
    table = "\n".join(rows) if rows else "<tr><td colspan='4'>None</td></tr>"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>GL vs Ledger Reconciliation</title></head>
<body><h1>Reconciliation {report['generated_at']}</h1>
<p>OK: {report['ok']} | Differences: {report['differences_count']} | Missing in Ledger: {report['missing_in_ledger_count']} | Extra in Ledger: {report['extra_in_ledger_count']}</p>
<table border="1"><thead><tr><th>Account</th><th>Date</th><th>Diff Debit</th><th>Diff Credit</th></tr></thead><tbody>
{table}
</tbody></table></body></html>"""

if __name__ == "__main__":
    sys.exit(main())
