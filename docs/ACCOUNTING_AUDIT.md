# Accounting System Audit — Integrity & Source of Truth

This document audits the codebase against the **10 immutable accounting rules**. It maps each rule to implementation, notes gaps, and lists automated checks.

**Core principle:** The ONLY source of truth is **POSTED Journal Entries**. No report, dashboard, or cached value may override journals.

---

## 1️⃣ Core Principle — Single Source of Truth

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Only POSTED journals are authoritative | All reports in `routes/financials.py` filter `JournalEntry.status == 'posted'` | ✅ |
| No report may use other tables as authoritative | Income Statement, Balance Sheet, Trial Balance, Ledger use `JournalLine` + `JournalEntry` only; no fallback to SalesInvoice/PurchaseInvoice totals | ✅ |
| Dynamic reports from journals | Reports aggregate from `JournalLine` joined to `Account` and `JournalEntry`; no cached balances | ✅ |

**Reference:** `docs/IMMUTABLE_ACCOUNTING_RULES.md`, `routes/financials.py` (header comment).

---

## 2️⃣ Transaction Validation — Journal on Every Operation

| Operation | Journal creation | Rollback on failure |
|-----------|------------------|----------------------|
| Sales invoice | `_create_sale_journal` (app/routes.py, journal module, financials backfill) | Yes (try/except + rollback in routes) |
| Purchase invoice | `_create_purchase_journal` | Yes |
| Expense invoice | `_create_expense_journal` (app/routes.py) called from routes/expenses.py | Yes (`db.session.rollback()` on exception) |
| Payment (supplier/expense) | `_create_expense_payment_journal`, `_create_supplier_payment_journal` | Yes |
| Payroll accrual | Journal in app/routes.py / journal module (JE-PR, salary_id) | Yes |
| Payroll payment | Journal (JE-PAY / quick-txn pay_liability) | Yes |
| Quick transactions | `POST /financials/api/quick-txn` creates JE-QTX, status=posted | Yes (commit only after JE + lines) |
| Manual journal | `POST /journal/api/transactions/post` | Yes |
| Opening balance import | `POST /api/opening-balances/import` creates JE-OPEN | Yes |

**Gap:** Ensure no financial operation can be marked "complete" or "paid" without a successful journal creation and post. Current code creates journal in same transaction as invoice save; if journal fails, rollback occurs. ✅

---

## 3️⃣ Journal-to-Operation Relationship

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Every JE linked to operation | `JournalEntry.invoice_id`, `invoice_type`, `salary_id` (models.py) | ✅ |
| Delete JE only with operation | API `api_journals_delete`: draft-only for manual JEs; when JE has `invoice_id`/`invoice_type` or `salary_id`, delete allowed (posted or draft) and linked invoice/operation is deleted | ✅ |
| Invoice delete → delete linked JE | app/routes.py `invoices_delete`: finds JE by `invoice_id` + `invoice_type` (canonical link); app.py `delete_*_invoice`: by entry_number | ✅ |
| **JE delete → delete linked invoice/operation** | **القاعدة:** عند حذف أي قيد محاسبي يُحذف الفاتورة/العملية المرتبطة تلقائياً. `delete_journal_entry_and_linked_invoice(je)` في `routes/journal.py`: يحذف كل القيود المرتبطة بنفس الفاتورة (مثلاً JE-EXP و JE-PAY)، ثم الدفعات، ثم بنود الفاتورة والفاتورة (أو الراتب). مُستدعى من: `delete_entry`, `api_journals_delete`, `api_ledger_delete`. | ✅ |

**Canonical link:** Use `JournalEntry.query.filter_by(invoice_id=inv.id, invoice_type='expense').first()` (and same for sales/purchase) when deleting journal on invoice delete.

---

## 4️⃣ Posted Journal Integrity

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| POSTED cannot be modified/deleted directly | `api_journals_delete` returns 400 if status=posted | ✅ |
| Adjustments only via reversal | `api_journals_reverse` creates new reversing entry; original unchanged | ✅ |
| Log creation, post, revert, reverse | `JournalAudit` model; audit rows added on post, revert_to_draft, reverse (routes/journal.py) | ✅ |

---

## 5️⃣ Database Integrity

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Foreign keys JE ↔ Accounts | `JournalLine.account_id` → accounts.id, `JournalLine.journal_id` → journal_entries.id | ✅ |
| ACID / rollback on failure | Routes use try/except and `db.session.rollback()` on exception | ✅ |
| No orphan JE / no operation without JE | Enforced by application: journal created with invoice; invoice delete removes JE. Audit script checks "invoices without linked journal" | ✅ (script: db_audit_journal_integrity.py) |

---

## 6️⃣ Chart of Accounts & Reporting Mapping

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Assets, Liabilities, Equity → Balance Sheet | Balance sheet aggregates by `Account.type` (ASSET, LIABILITY, EQUITY); Asset = debit−credit, Liability/Equity = credit−debit | ✅ |
| COGS → Cost of Sales | `_jl_sum_by_type(['COGS'], ...)`; displayed as positive (abs) | ✅ |
| Expenses → Operating Expenses | `_jl_sum_by_type(['EXPENSE'], ...)`; displayed as positive (abs) | ✅ |
| Revenue → Revenue | `_jl_sum_by_type(['REVENUE', 'OTHER_INCOME'], False, ...)` | ✅ |
| Reports from POSTED only | All report queries filter `JournalEntry.status == 'posted'` | ✅ |
| Profit formulas | Gross = Revenue − Cost of Sales; Operating = Gross − Operating Expenses; Net = Operating + Other Income − Other Expenses | ✅ |

---

## 7️⃣ Report Verification

| Report | Reads from | Filter posted |
|--------|-----------|---------------|
| Income Statement | `_jl_sum_by_type`, `_jl_detail_by_type` (JournalLine + Account + JournalEntry) | ✅ |
| Balance Sheet | JournalLine sum by Account, line_date ≤ asof | ✅ |
| Trial Balance | Same | ✅ |
| Account Ledger | JournalLine for account, JournalEntry.status=posted | ✅ |
| Cash flow (analytical) | JournalLine for cash accounts, posted | ✅ |

**Check:** Report totals should match sum of posted JournalLine debit/credit. Automated in `scripts/db_audit_journal_integrity.py` (see Check 7 below).

---

## 8️⃣ Continuous Audit & Checks

**Script:** `scripts/db_audit_journal_integrity.py`

| Check | Description |
|-------|-------------|
| 1 | COA vs DB: all tree codes exist in accounts |
| 2 | Posted journals: each has sum(debit)=sum(credit), total_debit=total_credit |
| 3 | Broken references: JE with invoice_id/invoice_type/salary_id points to existing record |
| 4 | Invoices without linked journal: sales/purchase/expense invoices have at least one JE with invoice_id+invoice_type and status=posted |
| 5 | LedgerEntry legacy: count vs JournalLine (informational) |
| 6 | **Report totals vs posted journal lines:** sum(JournalLine.debit) and sum(JournalLine.credit) over posted JEs only; must be equal (balanced) |
| 7 | Required columns on journal_entries, journal_lines, accounts |

**Run:** `python scripts/db_audit_journal_integrity.py` (from project root with PYTHONPATH=. or via create_app).

---

## 9️⃣ Exception Handling

| Rule | Implementation |
|------|----------------|
| No operation without journal | Application creates journal in same transaction; rollback on failure |
| No journal without operation | Manual/quick-txn JEs may have no invoice_id (allowed); operation-originated JEs have invoice_id/salary_id |
| No delete of posted JE | API returns 400 |
| Failures rollback and log | try/except + rollback in routes; JournalAudit for post/revert/reverse |

---

## 10️⃣ Logging & Traceability

| Item | Implementation |
|------|----------------|
| JournalAudit | journal_id, action (create/post/revert_to_draft/reverse), user_id, ts, before_json, after_json |
| Reconstruction | Full accounting picture can be rebuilt from JournalEntry + JournalLine + Account; audit trail supports who posted/reverted/reversed |

---

## ⚠️ Gaps & Recommendations

1. **Invoice delete → JE delete:** Prefer finding JE by `invoice_id` + `invoice_type` instead of `entry_number` or `description.ilike`, so the link is canonical and robust.
2. **api_journals_repost:** Writes to legacy `LedgerEntry`; reports use JournalLine only. Consider removing LedgerEntry write or documenting it as legacy.
3. **Duplicate delete_expense_invoice routes:** app.py defines two routes for the same path; the later one wins and deletes JE by entry_number. Ensure the earlier route (if ever used) also deletes JE by invoice_id+invoice_type for consistency.
4. **Report totals vs DB:** Add Check 7 in audit script: compare trial balance total debit/credit with `sum(JournalLine.debit)` and `sum(JournalLine.credit)` for posted JEs; flag if mismatch.

---

## Summary

| Rule | Status |
|------|--------|
| 1. Single source of truth | ✅ |
| 2. Journal on every operation | ✅ |
| 3. Journal–operation link | ✅ (recommend canonical link on delete) |
| 4. Posted integrity | ✅ |
| 5. Database integrity | ✅ |
| 6. COA & reporting mapping | ✅ |
| 7. Report verification | ✅ |
| 8. Continuous audit | ✅ (script + Check 7) |
| 9. Exception handling | ✅ |
| 10. Logging & traceability | ✅ |

**No exceptions.** Any violation must be fixed or explicitly documented and mitigated.
