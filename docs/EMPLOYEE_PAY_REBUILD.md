# Employee Payment System Rebuild (UVD Screen)

## Overview
Rebuilt the salary payment system exclusively for the Employee UVD screen. Removed legacy payment blueprint and added a new, robust API with improved error handling and health checks.

## Changes
1. Removed legacy module: `app/payroll.py` and its blueprint registration.
2. Added new blueprint: `app/emp_pay.py` with endpoints:
   - `GET /api/employees/pay-health` – connectivity/DB sanity.
   - `POST /api/employees/pay-salary` – single employee payment.
   - `POST /api/employees/pay-salary-bulk` – bulk payments.
3. Updated `app/__init__.py`:
   - Registered `emp_pay_bp` blueprint.
   - CSRF exemptions for the new endpoints to support AJAX.
4. Updated `templates/employee_uvd.html`:
   - Switched calls to new endpoints.
   - Added health check call, improved error messages.
   - Added close button/backdrop for the slideover.
5. Added tests: `tests/test_employee_payment.py` – smoke coverage for the new API.

## API Specs
### POST /api/employees/pay-salary
Form fields: `employee_id`, `month` (YYYY-MM), `paid_amount`, `payment_method`, `notes`.
Response: `{ ok: true, payment_id, status, remaining }` or `{ ok: false, error }`.

### POST /api/employees/pay-salary-bulk
Form fields: `employee_ids` (CSV or `all`), `month`, `paid_amount`, `payment_method`, `notes`.
Response: `{ ok: true, success_count, failed_count }`.

### GET /api/employees/pay-health
Response: `{ ok: true, employees, time }`.

## Error Handling
- Validates required inputs and employee existence.
- Caps payment to remaining salary for the month.
- Logs detailed info via `current_app.logger` on success/failure.
- Returns structured JSON errors.

## CSRF
- Endpoints are exempted (`app/__init__.py`) and the UI includes `X-CSRFToken` and `csrf_token` in requests for compatibility.

## Testing & Verification
- Run `pytest -k employee_payment` to execute the test.
- Manual checks via Employee UVD screen:
  - Open any employee, use “دفع راتب” → verify success toast and status change.
  - Use bulk pay → verify counts.
  - Check browser console for network errors.

## Ledger Posting
- Uses chart of accounts mapping: DR Payroll Liabilities, CR Cash/Bank per payment method.

## Migration Notes
- Only Employee UVD payment system changed; sales/purchases unaffected.

## Rollback
- Restore `app/payroll.py` and revert UI changes if needed.

