#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار تحميل على دوال services/gl_truth.py ببيانات حجمية.
الهدف: تحديد نقاط الاختناق وضمان كفاءة الفهارس (line_date, account_id, invoice_id).

تشغيل: من جذر المشروع
  python scripts/load_test_gl_truth.py [--seed N] [--calls M]
  --seed N: عدد قيود/أسطر تقريبية (افتراضي 5000)
  --calls M: عدد استدعاءات كل دالة (افتراضي 50)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta

def _bootstrap():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)
    from app import create_app
    app = create_app()
    app.app_context().push()
    return app

def run_timings(app, seed_size: int, num_calls: int):
    from app import db
    from models import JournalEntry, JournalLine, Account
    from services import gl_truth
    from sqlalchemy import func

    today = date.today()
    results = []

    # 1) get_account_debit_credit_from_gl(account_id, asof_date)
    acc_ids = [r[0] for r in db.session.query(Account.id).limit(20).all()]
    if not acc_ids:
        print("No accounts; create COA first.")
        return results
    acc_id = acc_ids[0]
    start = time.perf_counter()
    for _ in range(num_calls):
        gl_truth.get_account_debit_credit_from_gl(acc_id, today)
    elapsed = time.perf_counter() - start
    results.append(("get_account_debit_credit_from_gl", num_calls, elapsed, elapsed / num_calls * 1000))
    print(f"  get_account_debit_credit_from_gl: {num_calls} calls, {elapsed:.2f}s total, {elapsed/num_calls*1000:.1f} ms/call")

    # 2) get_account_balance_from_gl_by_code
    codes = [r[0] for r in db.session.query(Account.code).limit(10).all()]
    if codes:
        code = codes[0]
        start = time.perf_counter()
        for _ in range(num_calls):
            gl_truth.get_account_balance_from_gl_by_code(code, today)
        elapsed = time.perf_counter() - start
        results.append(("get_account_balance_from_gl_by_code", num_calls, elapsed, elapsed / num_calls * 1000))
        print(f"  get_account_balance_from_gl_by_code: {num_calls} calls, {elapsed:.2f}s total, {elapsed/num_calls*1000:.1f} ms/call")

    # 3) sum_gl_by_account_code_and_date_range
    start_d = today - timedelta(days=365)
    start = time.perf_counter()
    for _ in range(min(num_calls, 20)):
        gl_truth.sum_gl_by_account_code_and_date_range(
            ["4111", "4112", "2141", "1170"], start_d, today, credit_minus_debit=True
        )
    elapsed = time.perf_counter() - start
    n = min(num_calls, 20)
    results.append(("sum_gl_by_account_code_and_date_range", n, elapsed, elapsed / n * 1000))
    print(f"  sum_gl_by_account_code_and_date_range: {n} calls, {elapsed:.2f}s total, {elapsed/n*1000:.1f} ms/call")

    # 4) Raw query similar to trial balance (aggregate by account)
    from models import JournalEntry as JE, JournalLine as JL
    from sqlalchemy import or_, and_, func
    start = time.perf_counter()
    for _ in range(min(num_calls, 10)):
        q = db.session.query(
            Account.code,
            func.coalesce(func.sum(JL.debit), 0).label("debit"),
            func.coalesce(func.sum(JL.credit), 0).label("credit"),
        ).outerjoin(JL, JL.account_id == Account.id).outerjoin(
            JE, JL.journal_id == JE.id
        ).filter(
            or_(JL.id.is_(None), and_(JL.line_date <= today, JE.status == "posted"))
        ).group_by(Account.id).all()
    elapsed = time.perf_counter() - start
    n = min(num_calls, 10)
    results.append(("trial_balance_style_aggregate", n, elapsed, elapsed / n * 1000))
    print(f"  trial_balance_style_aggregate: {n} calls, {elapsed:.2f}s total, {elapsed/n*1000:.1f} ms/call")

    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0, help="Optional: seed extra journal lines for volume (0 = skip)")
    ap.add_argument("--calls", type=int, default=50, help="Number of calls per function")
    args = ap.parse_args()

    app = _bootstrap()
    with app.app_context():
        from app import db
        from models import JournalEntry, JournalLine, Account

        jl_count = db.session.query(JournalLine.id).count()
        je_count = db.session.query(JournalEntry.id).count()
        print(f"Current DB: JournalLine count={jl_count}, JournalEntry count={je_count}")

        if args.seed > 0:
            print(f"Seeding ~{args.seed} journal lines (slow for large N)...")
            # Create one posted journal with many lines for stress
            accounts = db.session.query(Account.id).limit(50).all()
            acc_ids = [a[0] for a in accounts]
            if not acc_ids:
                print("No accounts; run COA seed first.")
                return 1
            je = JournalEntry(
                entry_number=f"JE-LOAD-{int(time.time())}",
                date=date.today(),
                description="Load test seed",
                status="posted",
                total_debit=0,
                total_credit=0,
            )
            db.session.add(je)
            db.session.flush()
            for i in range(min(args.seed, 5000)):
                acc_id = acc_ids[i % len(acc_ids)]
                db.session.add(JournalLine(
                    journal_id=je.id,
                    line_no=i + 1,
                    account_id=acc_id,
                    debit=1.0 if i % 2 == 0 else 0,
                    credit=0 if i % 2 == 0 else 1.0,
                    description=f"Line {i}",
                    line_date=date.today(),
                ))
            db.session.commit()
            print("Seed done.")

        print("Running timings...")
        run_timings(app, args.seed, args.calls)
    return 0

if __name__ == "__main__":
    sys.exit(main())
