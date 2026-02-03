# Immutable Accounting Backbone — Rules (No Exceptions)

This document defines the **mandatory** rules for the financial system. Failure to enforce any rule breaks the system. There are **no exceptions**.

---

## 1️⃣ Single Source of Truth

- The **only** source of truth is **POSTED Journal Entries**.
- No other table, report, or cached summary may be used as authoritative.
- All reports (Income Statement, Balance Sheet, Trial Balance) **must** be generated **dynamically** from POSTED Journal Entries.

---

## 2️⃣ Mandatory Journal Entry Creation

- Any financial operation (expense, payment, invoice, receipt, stock transaction) **must** generate a corresponding journal entry.
- The operation **cannot** be marked completed unless the journal entry is successfully created and **POSTED**.
- If journal creation fails, the operation **must fail entirely**; rollback all changes.

---

## 3️⃣ Journal-to-Operation Relationship

- Every journal entry **must** have a direct, immutable link to its originating operation or invoice (e.g. `invoice_id` + `invoice_type`, or `salary_id`).
- **Deleting a journal entry is strictly forbidden** unless its related operation or invoice is deleted.
- If a journal entry is deleted, the corresponding operation or invoice **must** be deleted automatically (cascade delete).
- **For invoices:**
  - Deleting an invoice **must** automatically delete the linked journal entry.
  - Deleting a journal entry **must** automatically delete the linked invoice.
- The relationship is **bi-directional** and must always be enforced.

---

## 4️⃣ Immutable Posted Entries

- **POSTED** journal entries **cannot** be modified or deleted directly.
- Only **reversing entries** may adjust accounting balances, preserving original entry integrity.
- Any attempted direct modification **must** be blocked and logged.

---

## 5️⃣ Database Integrity

- All financial tables **must** enforce foreign keys linking operations/invoices to journal entries.
- Transactions **must** be ACID-compliant:
  - Any failure in journal creation, posting, or linking **must** rollback the entire operation.
- No operation may leave the system in a state where:
  - A journal entry exists without a linked operation (when the JE was created from an operation),
  - An operation exists without a linked journal entry (when the operation is financial),
  - Reports do not reflect posted journals.

---

## 6️⃣ Operational Rules

- Any action (expense, payment, invoice, stock movement) **without** a journal entry **must** be rejected.
- Undo, rollback, or cancellation **must** respect journal entry immutability:
  - **Deleting an operation** → delete linked journal (and only if journal is draft or cascade rule applies).
  - **Deleting a journal** → delete linked operation (cascade).

---

## 7️⃣ Reporting

- All reports **must** read **directly** from **POSTED** journals only.
- No cached balances, no computed aggregates from other sources.
- Any report displaying numbers not backed by POSTED journal entries is **invalid**.
- **Income Statement signs:** Cost of Sales and Operating Expenses (and Other Expenses, Tax) are **displayed and used as positive magnitudes** (Debit side). Formulas: Gross Profit = Revenue − Cost of Sales; Operating Profit = Gross Profit − Operating Expenses; Net = Operating Profit + Other Income − Other Expenses − Tax. Only profit/loss line may be negative.
- **Balance Sheet signs:** Assets = sum(Debit − Credit) for accounts of type ASSET; Liabilities = sum(Credit − Debit) for LIABILITY; Equity = sum(Credit − Debit) for EQUITY. Equation: Assets = Liabilities + Equity. If assets show negative (e.g. 1160, 1111, 1121), the **data** has more Credits than Debits (e.g. no opening balance recorded). Fix: record **opening balances** or **capital injection** (Debit 1111/1121/1160, Credit 3210) so assets are positive.
- **Opening balance / تمويل:** To show positive cash, bank, or inventory: (1) Use **Quick transaction** `capital_injection` (Debit 1111 or 1121, Credit 3210), or (2) Use **API** `POST /api/opening-balances/import` with CSV (account_code, opening_debit, opening_credit, as_of_date, description, source_ref). Ensure total_debit = total_credit.
- **3220 (أرباح السنة الحالية):** Current-year profit must be **closed** from P&amp;L at period end (closing entry: close Revenue/Expense/COGS to 3220). Until that entry is posted, 3220 may show zero and Equity will not include current-year profit.

---

## 8️⃣ Logging & Auditing

- Every creation, posting, reversal, or deletion **must** be logged with:
  - Timestamp
  - User (or system)
  - Reference IDs (journal_id, entry_number, etc.)
- Audit trails **must** always allow reconstructing the complete accounting picture from journal entries alone.

---

## 9️⃣ Security

- Enforce **strict referential integrity** in the database.
- Any attempt to **bypass** journal creation or **modify** posted journals **must** be blocked at the database and application level.

---

## Implementation Notes (This Codebase)

- **Reports:** Income Statement, Balance Sheet, Trial Balance in `routes/financials.py` read only from `journal_entries` (status='posted') + `journal_lines` + `accounts`. See comment at top of `routes/financials.py` (Single Source of Truth).
- **Journal link:** `JournalEntry` has `invoice_id`, `invoice_type`, `salary_id` for originating operation.
- **Posted delete:** `api_journals_delete` in `routes/journal.py` returns 400 if status is 'posted'; posted entries cannot be deleted via this API.
- **Reversal:** `api_journals_reverse` creates a new posted reversing entry; original entry is never modified.
- **Audit:** `JournalAudit` model and logs on post, revert_to_draft, and reverse.
- **Cascade:** Invoice delete → journal delete (and vice versa) should be enforced in application logic or DB constraints where applicable.
- **Quick transaction `capital_injection`:** `POST /financials/api/quick-txn` with `type: 'capital_injection'`, `amount`, `date`, optional `cash_code` (1111 or 1121), optional `equity_code` (3210 or 3220). Creates Debit cash/bank, Credit equity (تمويل / رصيد افتتاحي).
- **Balance sheet branch filter:** Balance sheet (and print/export) accept `branch` (all | china_town | place_india); when set, only posted journal entries for that branch are included.
