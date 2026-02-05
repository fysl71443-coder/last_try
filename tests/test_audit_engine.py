# -*- coding: utf-8 -*-
"""
اختبارات محرك التدقيق: modules/audit، مسارات التدقيق، وحارس إغلاق السنة المالية.
"""
from __future__ import annotations

import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def seed_admin(test_app):
    """إنشاء مستخدم admin في قاعدة الاختبار."""
    with test_app.app_context():
        from app import db
        from models import User
        u = User.query.filter_by(username="admin").first()
        if not u:
            u = User(username="admin", email="admin@test.com", role="admin", active=True)
            u.set_password("admin123")
            db.session.add(u)
            db.session.commit()


@pytest.fixture
def authed_client(client, seed_admin):
    """عميل مسجّل الدخول (admin / admin123)."""
    client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    return client


@pytest.fixture
def app_context(test_app):
    """توفير سياق التطبيق للاستيراد والاستعلام."""
    with test_app.app_context():
        yield test_app


def test_audit_engine_import(app_context):
    """التحقق من استيراد محرك التدقيق وتشغيله بدون أخطاء."""
    from modules.audit import run_audit
    from modules.audit.engine import has_critical_findings

    report = run_audit(from_date=None, to_date=None)
    assert isinstance(report, dict)
    assert "findings" in report
    assert "summary" in report
    assert "meta" in report
    assert isinstance(report["findings"], list)
    assert report["summary"]["total"] == report["summary"]["high"] + report["summary"]["medium"] + report["summary"]["low"]
    assert report["summary"]["total"] == len(report["findings"])

    ok = has_critical_findings(None, None)
    assert isinstance(ok, bool)


def test_audit_engine_with_dates(app_context):
    """تشغيل التدقيق بنطاق تواريخ."""
    from modules.audit import run_audit

    report = run_audit(from_date=date(2024, 1, 1), to_date=date(2024, 12, 31))
    assert report["meta"]["from_date"] == date(2024, 1, 1)
    assert report["meta"]["to_date"] == date(2024, 12, 31)
    assert "run_at" in report["meta"]


def test_audit_report_structure(app_context):
    """هيكل كل ملاحظة: أعمدة التقرير المطلوبة."""
    from modules.audit import run_audit

    report = run_audit(None, None)
    for f in report["findings"]:
        assert "number" in f
        assert "issue_type_ar" in f
        assert "place_ar" in f
        assert "ref_number" in f
        assert "description" in f
        assert "root_cause_ar" in f
        assert "severity" in f
        assert "severity_ar" in f
        assert "correction_method" in f
        assert f["severity"] in ("high", "medium", "low")


def test_audit_route_get(authed_client):
    """صفحة التدقيق تعيد 200 بدون تشغيل."""
    r = authed_client.get("/journal/audit", follow_redirects=True)
    assert r.status_code == 200
    assert b"audit" in r.data.lower() or "تدقيق" in (r.data.decode("utf-8", errors="ignore"))


def test_audit_route_post_empty(authed_client):
    """POST بدون تواريخ يشغّل التدقيق على كامل البيانات."""
    r = authed_client.post(
        "/journal/audit",
        data={"from_date": "", "to_date": ""},
        follow_redirects=True,
    )
    assert r.status_code == 200
    # التقرير يعرض إما لا توجد ملاحظات أو جدول الملاحظات
    body = r.data.decode("utf-8", errors="ignore")
    assert "audit" in r.data.decode("utf-8", errors="ignore").lower() or "الملخص" in body or "findings" in body


def test_audit_route_run_from_fiscal(authed_client, test_app):
    """تشغيل التدقيق من رابط السنة المالية (run=1 + from_date + to_date + fiscal_year_id)."""
    with test_app.app_context():
        from models import FiscalYear
        from datetime import datetime
        fy = FiscalYear.query.order_by(FiscalYear.id.desc()).first()
        if not fy:
            fy = FiscalYear(year=2025, start_date=date(2025, 1, 1), end_date=date(2025, 12, 31), status="open")
            from app import db
            db.session.add(fy)
            db.session.commit()
    from_date = fy.start_date.strftime("%Y-%m-%d")
    to_date = fy.end_date.strftime("%Y-%m-%d")
    r = authed_client.get(
        f"/journal/audit?run=1&from_date={from_date}&to_date={to_date}&fiscal_year_id={fy.id}",
        follow_redirects=True,
    )
    assert r.status_code == 200


def test_fiscal_years_list_and_detail(authed_client):
    """شاشة السنوات المالية وتفاصيل سنة تحتوي زر التدقيق."""
    r = authed_client.get("/fiscal-years/", follow_redirects=True)
    assert r.status_code == 200
    # إن وُجدت سنة مالية، تفاصيلها يجب أن تحتوي رابط تدقيق
    with authed_client.application.app_context():
        from models import FiscalYear
        fy = FiscalYear.query.first()
        if fy:
            r2 = authed_client.get(f"/fiscal-years/{fy.id}", follow_redirects=True)
            assert r2.status_code == 200
            body2 = r2.data.decode("utf-8", errors="ignore")
            assert "audit" in body2.lower() or "تدقيق" in body2 or "الفترة" in body2
