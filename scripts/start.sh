#!/usr/bin/env bash
set -euo pipefail

export FLASK_APP=app
export FLASK_ENV=production
export PYTHONUNBUFFERED=1

# Apply DB migrations (safe if none)
flask db upgrade || true

# Start Gunicorn with eventlet for Socket.IO
exec gunicorn -k eventlet -w 1 -b 0.0.0.0:8000 --timeout 120 --graceful-timeout 120 app:app

