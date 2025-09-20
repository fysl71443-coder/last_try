# POS E2E Enablers Applied

This patch enables practical end-to-end testing for the unified POS flow without changing business logic.

Changes:

1) /api/pay-and-print
- Stop using a non-existent template for temp receipt. Now returns `receipt_url` pointing to `/sales/receipt/<id>` which renders `templates/sales_receipt.html`.

2) /api/draft-order/<branch>/<table>
- Expose GET to read current draft and POST to save/update draft items. Updates table status accordingly.

3) Added a minimal `templates/thermal_receipt.html`
- Kept as a fallback simple thermal-styled template used by old code paths. New flow uses `/sales/receipt/<id>`.

Notes:
- China Town POS template uses `/api/draft-order/...` and `/api/pay-and-print`; both are now operational.
- If you prefer a single API namespace (`/api/pos/...`) we can align the POS templates accordingly.

