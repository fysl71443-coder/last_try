#!/usr/bin/env bash
set -e
set -o pipefail

# Simple, safe startup for Render
# 1) Apply DB migrations (disable eventlet in CLI)
# 2) Run DB consistency fixes (best-effort)
# 3) Create admin user if needed (best-effort)
# 4) Start Gunicorn with chosen worker

# Defaults
export USE_EVENTLET=${USE_EVENTLET:-0}
export USE_EVENTLET_FOR_SERVER=${USE_EVENTLET_FOR_SERVER:-0}
export WORKERS=${WORKERS:-1}
export PORT=${PORT:-10000}

# Disable eventlet during CLI operations
export USE_EVENTLET=0
export FLASK_APP=app

echo "[start_render] Applying Alembic migrations..."
if ! python -m flask db upgrade heads; then
  echo "[start_render] WARNING: flask db upgrade failed; continuing with best-effort fixes"
fi

echo "[start_render] Running DB consistency fixes (best-effort)..."
python scripts/fix_db_consistency.py || echo "[start_render] fix_db_consistency skipped/failed"
python scripts/ensure_draft_orders_columns.py || echo "[start_render] ensure_draft_orders_columns skipped/failed"

echo "[start_render] Creating/ensuring admin user (best-effort)..."
python create_user.py || echo "[start_render] create_user.py skipped/failed"

# Start server
if [ "${USE_EVENTLET_FOR_SERVER}" = "1" ]; then
  echo "[start_render] Starting Gunicorn (eventlet)..."
  exec gunicorn -k eventlet -w ${WORKERS} -b 0.0.0.0:${PORT} app:app
else
  echo "[start_render] Starting Gunicorn (sync worker) for stability..."
  # simple_app:app is a lightweight WSGI that imports routes safely
  exec gunicorn --worker-class sync --workers ${WORKERS} -b 0.0.0.0:${PORT} simple_app:app
fi

