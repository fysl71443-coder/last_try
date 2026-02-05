# -*- coding: utf-8 -*-
"""
السنوات المالية (Fiscal Years) — التحكم المحاسبي الزمني.
إنشاء سنة، إغلاق/قفل، فترات استثنائية، استيراد قيود، سجل تدقيق.
"""
from __future__ import annotations

import json
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app import db
from models import FiscalYear, FiscalYearExceptionalPeriod, FiscalYearAuditLog, get_saudi_now

bp = Blueprint('fiscal_years', __name__, url_prefix='/fiscal-years')


def _audit(fiscal_year_id: int, action: str, details: dict = None):
    try:
        log = FiscalYearAuditLog(
            fiscal_year_id=fiscal_year_id,
            action=action,
            user_id=getattr(current_user, 'id', None),
            details_json=json.dumps(details or {}, ensure_ascii=False)
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


@bp.route('/')
@login_required
def list_years():
    years = FiscalYear.query.order_by(FiscalYear.year.desc()).all()
    return render_template('fiscal_years/list.html', years=years)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        year = request.form.get('year', type=int)
        start_str = request.form.get('start_date', '').strip()
        end_str = request.form.get('end_date', '').strip()
        notes = request.form.get('notes', '').strip()
        if not year or not start_str or not end_str:
            flash(_('Year, start date and end date are required.'), 'danger')
            return redirect(url_for('fiscal_years.create'))
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            flash(_('Invalid date format.'), 'danger')
            return redirect(url_for('fiscal_years.create'))
        if start_date >= end_date:
            flash(_('Start date must be before end date.'), 'danger')
            return redirect(url_for('fiscal_years.create'))
        if FiscalYear.query.filter_by(year=year).first():
            flash(_('Fiscal year already exists for this year.'), 'warning')
            return redirect(url_for('fiscal_years.list_years'))
        fy = FiscalYear(year=year, start_date=start_date, end_date=end_date, status='open', notes=notes or None)
        db.session.add(fy)
        db.session.commit()
        _audit(fy.id, 'create', {'year': year, 'start_date': start_str, 'end_date': end_str})
        flash(_('Fiscal year created successfully.'), 'success')
        return redirect(url_for('fiscal_years.detail', id=fy.id))
    return render_template('fiscal_years/create.html')


def _last_closure_log(fy):
    """آخر سجل إقفال (close أو close_override) لهذه السنة."""
    if not fy or not getattr(fy, "audit_logs", None):
        return None
    for log in sorted(fy.audit_logs, key=lambda x: (x.created_at or x.id or 0), reverse=True):
        if log.action in ("close", "close_override"):
            return log
    return None


def _last_reopen_log(fy):
    """آخر سجل إعادة فتح (reopen) لهذه السنة."""
    if not fy or not getattr(fy, "audit_logs", None):
        return None
    for log in sorted(fy.audit_logs, key=lambda x: (x.created_at or x.id or 0), reverse=True):
        if log.action == "reopen":
            return log
    return None


@bp.route('/<int:id>')
@login_required
def detail(id):
    fy = FiscalYear.query.get_or_404(id)
    closure_audit_status = None
    closure_log = _last_closure_log(fy)

    # قراءة آخر لقطة من الكاش فقط — لا تشغيل محرك تدقيق عند فتح الشاشة
    if fy.status in ("open", "partial"):
        try:
            from services.audit_snapshot_cache import get_last_audit_snapshot
            snapshot = get_last_audit_snapshot(fy.id)
            if snapshot:
                closure_audit_status = {
                    "snapshot": snapshot,
                    "has_critical": (snapshot.get("summary") or {}).get("high", 0) > 0,
                    "critical_count": (snapshot.get("summary") or {}).get("high", 0),
                }
            else:
                closure_audit_status = {"snapshot": None, "has_critical": False, "critical_count": 0, "no_snapshot_yet": True}
        except Exception:
            closure_audit_status = {"snapshot": None, "has_critical": False, "critical_count": 0, "no_snapshot_yet": True}

    closure_details = None
    if closure_log and getattr(closure_log, "details_json", None):
        try:
            closure_details = json.loads(closure_log.details_json)
        except (ValueError, TypeError):
            pass

    reopen_log = _last_reopen_log(fy)
    reopen_details = None
    if reopen_log and getattr(reopen_log, "details_json", None):
        try:
            reopen_details = json.loads(reopen_log.details_json)
        except (ValueError, TypeError):
            pass

    # سجل التدقيق: آخر 20 سطراً فقط (pagination)
    audit_logs_page = []
    if getattr(fy, "audit_logs", None):
        audit_logs_page = sorted(
            fy.audit_logs,
            key=lambda x: (x.created_at or x.id or 0),
            reverse=True,
        )[:20]

    return render_template(
        "fiscal_years/detail.html",
        fy=fy,
        closure_audit_status=closure_audit_status,
        closure_log=closure_log,
        closure_details=closure_details,
        reopen_log=reopen_log,
        reopen_details=reopen_details,
        audit_logs_page=audit_logs_page,
    )


@bp.route('/<int:id>/close', methods=['POST'])
@login_required
def close(id):
    fy = FiscalYear.query.get_or_404(id)
    if fy.status == 'closed':
        flash(_('Year is already closed.'), 'warning')
        return redirect(url_for('fiscal_years.detail', id=id))

    # لقطة تدقيق عند الإقفال — تُحفظ دوماً في السجل
    try:
        from modules.audit.engine import get_closure_audit_snapshot
        audit_snapshot = get_closure_audit_snapshot(fy.start_date, fy.end_date)
    except Exception:
        audit_snapshot = {"run_at": None, "summary": {"total": 0, "high": 0, "medium": 0, "low": 0}}

    critical_count = (audit_snapshot.get("summary") or {}).get("high", 0)

    # لا يمكن إغلاق السنة إذا وُجدت ملاحظات حرجة إلا بتجاوز مع مبرر وتسجيل المستخدم
    if critical_count > 0:
        override_reason = (request.form.get("override_reason") or "").strip()
        if not override_reason:
            flash(
                _("Cannot close fiscal year: audit has %(count)s critical finding(s). Fix them or close with override (enter justification below).") % {"count": critical_count},
                "danger",
            )
            return redirect(url_for("fiscal_years.detail", id=id))
        if len(override_reason) < 20:
            flash(_("Override reason must be at least 20 characters."), "danger")
            return redirect(url_for("fiscal_years.detail", id=id))
        # إقفال مع التجاوز — تسجيل المبرر والمستخدم
        fy.status = "closed"
        fy.closed_until = None
        fy.closed_at = get_saudi_now()
        fy.closed_by = getattr(current_user, "id", None)
        db.session.commit()
        _audit(fy.id, "close_override", {
            "audit_snapshot": audit_snapshot,
            "override_reason": override_reason,
            "closed_by_user_id": getattr(current_user, "id", None),
            "closed_by_username": getattr(current_user, "username", None),
        })
        try:
            from services.audit_snapshot_cache import save_audit_snapshot
            save_audit_snapshot(fy.id, audit_snapshot.get("summary") or {}, None)
        except Exception:
            pass
        flash(_("Fiscal year closed with override. Critical findings were present; justification has been logged."), "warning")
        return redirect(url_for("fiscal_years.detail", id=id))

    # إقفال عادي — لا توجد ملاحظات حرجة
    fy.status = "closed"
    fy.closed_until = None
    fy.closed_at = get_saudi_now()
    fy.closed_by = getattr(current_user, "id", None)
    db.session.commit()
    _audit(fy.id, "close", {"audit_snapshot": audit_snapshot})
    try:
        from services.audit_snapshot_cache import save_audit_snapshot
        save_audit_snapshot(fy.id, audit_snapshot.get("summary") or {}, None)
    except Exception:
        pass
    flash(_("Fiscal year closed. Invoices and journal entries are no longer allowed for this period."), "success")
    return redirect(url_for("fiscal_years.detail", id=id))


@bp.route('/<int:id>/partial-close', methods=['POST'])
@login_required
def partial_close(id):
    fy = FiscalYear.query.get_or_404(id)
    closed_until_str = request.form.get('closed_until', '').strip()
    if not closed_until_str:
        flash(_('Please enter "Closed until" date.'), 'danger')
        return redirect(url_for('fiscal_years.detail', id=id))
    try:
        closed_until = datetime.strptime(closed_until_str, '%Y-%m-%d').date()
    except ValueError:
        flash(_('Invalid date format.'), 'danger')
        return redirect(url_for('fiscal_years.detail', id=id))
    if closed_until < fy.start_date or closed_until > fy.end_date:
        flash(_('Closed until must be within the fiscal year range.'), 'danger')
        return redirect(url_for('fiscal_years.detail', id=id))
    # فحص تدقيق لفترة الإقفال الجزئي — منع الإقفال عند وجود ملاحظات حرجة إلا بتجاوز
    try:
        from modules.audit.engine import get_closure_audit_snapshot
        audit_snapshot = get_closure_audit_snapshot(fy.start_date, closed_until)
    except Exception:
        audit_snapshot = {"run_at": None, "summary": {"total": 0, "high": 0, "medium": 0, "low": 0}}
    critical_count = (audit_snapshot.get("summary") or {}).get("high", 0)
    if critical_count > 0:
        override_reason = (request.form.get("override_reason") or "").strip()
        if not override_reason:
            flash(
                _("Cannot partial-close: audit has %(count)s critical finding(s) in this period. Fix them or enter override reason (20+ chars) and submit again.") % {"count": critical_count},
                "danger",
            )
            return redirect(url_for("fiscal_years.detail", id=id))
        if len(override_reason) < 20:
            flash(_("Override reason must be at least 20 characters."), "danger")
            return redirect(url_for("fiscal_years.detail", id=id))
    fy.status = 'partial'
    fy.closed_until = closed_until
    db.session.commit()
    details = {'closed_until': closed_until_str}
    if critical_count > 0:
        details['audit_snapshot'] = audit_snapshot
        details['override_reason'] = (request.form.get("override_reason") or "").strip()
    _audit(fy.id, 'partial_close', details)
    flash(_('Fiscal year partially closed until %(date)s.', date=closed_until_str), 'success')
    return redirect(url_for('fiscal_years.detail', id=id))


@bp.route('/<int:id>/reopen', methods=['POST'])
@login_required
def reopen(id):
    fy = FiscalYear.query.get_or_404(id)
    if fy.status != "closed" and fy.status != "partial":
        flash(_("Only closed or partially closed years can be reopened."), "warning")
        return redirect(url_for("fiscal_years.detail", id=id))

    reopen_reason = (request.form.get("reopen_reason") or "").strip()
    if not reopen_reason:
        flash(_("Reopen reason is required (mandatory)."), "danger")
        return redirect(url_for("fiscal_years.detail", id=id))
    if len(reopen_reason) < 20:
        flash(_("Reopen reason must be at least 20 characters."), "danger")
        return redirect(url_for("fiscal_years.detail", id=id))

    now = get_saudi_now()
    fy.status = "open"
    fy.closed_until = None
    fy.reopened_at = now
    fy.reopened_by = getattr(current_user, "id", None)
    db.session.commit()

    # لقطة تدقيق بعد إعادة الفتح — تسجيل أثر الفتح
    try:
        from modules.audit.engine import get_closure_audit_snapshot
        audit_snapshot = get_closure_audit_snapshot(fy.start_date, fy.end_date)
    except Exception:
        audit_snapshot = {"run_at": None, "summary": {"total": 0, "high": 0, "medium": 0, "low": 0}}

    _audit(fy.id, "reopen", {
        "reopen_reason": reopen_reason,
        "reopened_by_user_id": getattr(current_user, "id", None),
        "reopened_by_username": getattr(current_user, "username", None),
        "reopened_at": now.isoformat() if now else None,
        "audit_snapshot": audit_snapshot,
    })
    try:
        from services.audit_snapshot_cache import save_audit_snapshot
        save_audit_snapshot(fy.id, audit_snapshot.get("summary") or {}, now)
    except Exception:
        pass
    flash(_("Fiscal year reopened. Reason and post-reopen audit snapshot have been logged."), "success")
    return redirect(url_for("fiscal_years.detail", id=id))


@bp.route('/<int:id>/exceptional-period', methods=['POST'])
@login_required
def add_exceptional_period(id):
    fy = FiscalYear.query.get_or_404(id)
    start_str = request.form.get('start_date', '').strip()
    end_str = request.form.get('end_date', '').strip()
    reason = request.form.get('reason', '').strip()
    if not start_str or not end_str:
        flash(_('Start and end dates are required.'), 'danger')
        return redirect(url_for('fiscal_years.detail', id=id))
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        flash(_('Invalid date format.'), 'danger')
        return redirect(url_for('fiscal_years.detail', id=id))
    if start_date >= end_date:
        flash(_('Start date must be before end date.'), 'danger')
        return redirect(url_for('fiscal_years.detail', id=id))
    if start_date < fy.start_date or end_date > fy.end_date:
        flash(_('Exceptional period must be within the fiscal year.'), 'danger')
        return redirect(url_for('fiscal_years.detail', id=id))
    ep = FiscalYearExceptionalPeriod(
        fiscal_year_id=fy.id,
        start_date=start_date,
        end_date=end_date,
        reason=reason or None,
        created_by=getattr(current_user, 'id', None)
    )
    db.session.add(ep)
    db.session.commit()
    _audit(fy.id, 'open_exceptional', {'start_date': start_str, 'end_date': end_str, 'reason': reason})
    flash(_('Exceptional period added. All operations in this period will be audited.'), 'success')
    return redirect(url_for('fiscal_years.detail', id=id))


@bp.route('/<int:id>/import-journal', methods=['GET', 'POST'])
@login_required
def import_journal(id):
    fy = FiscalYear.query.get_or_404(id)
    if request.method == 'POST':
        # Stub: في الإنتاج نتحقق من الملف (CSV/Excel)، نعرض معاينة، ثم نعتمد
        flash(_('Journal import: upload and validation will be implemented here (CSV/Excel → Preview → Approve).'), 'info')
        return redirect(url_for('fiscal_years.detail', id=id))
    return render_template('fiscal_years/import_journal.html', fy=fy)
