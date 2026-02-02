# Accounting Service (Node.js)

Single Source of Truth for accounting. Integrates with Flask POS via REST.

## Setup

```bash
npm install
```

## Env

- `DATABASE_URL` — PostgreSQL
- `ACCOUNTING_KEY` — API key for `X-API-KEY`
- `PORT` — optional (default 3000)
- `RATE_LIMIT_WINDOW_MS` — optional (default 60000)
- `RATE_LIMIT_MAX_REQUESTS` — optional (default 60 per window)

## Security

- **Rate limit** on `/api/external/*` (configurable via env).
- **Payload validation:** `source_system` required and must be allowed (e.g. `flask-pos`); `source_ref_type` if present must be allowed.
- **Unique index** on `(source_system, source_ref_type, source_ref_id)` to prevent DB-level duplication.

## Schema

Run once (do **not** auto-seed on deploy):

```bash
psql $DATABASE_URL -f src/schema.sql
```

Optionally seed fiscal year:

```sql
INSERT INTO fiscal_years (year, start_date, end_date, closed)
VALUES (2026, '2026-01-01', '2026-12-31', FALSE)
ON CONFLICT (year) DO NOTHING;
```

## Run

```bash
npm start
```

## Endpoints

- `GET /health` — health check
- `POST /api/external/sales-invoice` — requires `X-API-KEY`
- `POST /api/external/purchase-invoice`
- `POST /api/external/expense-invoice`
- `POST /api/external/payment`
- `POST /api/external/salary-payment`
- `POST /api/external/salary-accrual`

See `docs/ACCOUNTING_INTEGRATION_API_CONTRACT.md` for request/response shapes.
