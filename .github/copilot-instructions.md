# Copilot Instructions for AI Coding Agents

## Project Overview
- Bilingual (Arabic/English) restaurant management system built with Flask and PostgreSQL.
- Major domains: POS, sales, purchases, expenses, inventory, user management, reporting.
- Two branches: "China Town" and "Place India"; branch-specific logic is common.

## Architecture & Key Files
- `app.py`: Main entry, Flask app factory, timezone logic, async/eventlet support, imports all models/extensions.
- `models.py`: SQLAlchemy models for all business entities (User, Invoice, SalesInvoice, etc.), Saudi timezone logic.
- `extensions.py`: Centralized Flask extension initialization (db, bcrypt, migrate, login_manager, babel, csrf).
- `config.py`: Environment-driven config, supports both PostgreSQL and SQLite (dev fallback).
- `db_helpers.py`: Safe DB commit, error handling, session management utilities.
- `render_setup.sql`: Database migration for Render PostgreSQL, adds columns/indexes for POS.
- `e2e_test_runner.py`: Selenium-based E2E test suite, outputs to `test_results/`.
- `app_patches.md`: Documents API changes for POS E2E enablement.
- `POS_CATEGORIES_SOLUTION.md`: Details category-meal linking and relevant API routes.

## Developer Workflows
- **Setup:**
  1. Copy `.env.example` to `.env` (if present) and update values.
  2. Create virtualenv: `python -m venv .venv && .venv\Scripts\activate` (Windows).
  3. Install dependencies: `pip install -r requirements.txt`
  4. Setup DB: `python apply_migration.py` or `psql $DATABASE_URL < render_setup.sql`
  5. Run app: `python app.py`
- **Testing:**
  - E2E: `python e2e_test_runner.py` (requires ChromeDriver, see script for details)
  - API: Use `/api/pos/<branch>/categories` and `/api/pos/<branch>/categories/<category_id>/items` for POS flows.
- **Debugging:**
  - Logging is configured in `app.py` and `e2e_test_runner.py`.
  - Use `debug_app.py`, `debug_login.py`, etc. for targeted debugging.

## Project-Specific Patterns
- **Timezone:** All business logic uses Saudi timezone (`Asia/Riyadh`).
- **Branch Logic:** Use canonical branch codes (`china_town`, `place_india`) for all branch-specific operations.
- **Async Support:** Eventlet monkey-patching is enabled by default for async compatibility (can be disabled via `USE_EVENTLET=0`).
- **POS APIs:** `/api/draft-order/<branch>/<table>` and `/api/pay-and-print` are the main endpoints for POS flows.
- **Templates:** Thermal receipt templates are minimal; main receipt rendering is via `/sales/receipt/<id>`.

## Integration Points
- **Database:** PostgreSQL (preferred), SQLite (dev fallback).
- **External:** ChromeDriver for E2E tests, Render.com for deployment.
- **Arabic Text:** Uses `arabic-reshaper` and `python-bidi` for PDF receipts.
- **SocketIO:** Initialized only if needed (see `extensions.py`).

## Conventions
- All extensions are imported from `extensions.py`.
- Models are imported in `app.py` to avoid circular imports.
- API routes for POS are documented in `POS_CATEGORIES_SOLUTION.md`.
- All migrations for Render are in `render_setup.sql`.

---

**If any section is unclear or missing, please provide feedback so this guide can be improved for future AI agents.**
