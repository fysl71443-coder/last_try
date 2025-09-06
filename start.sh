#!/bin/bash
# Alternative start script for Render

set -e

echo "🚀 Starting Restaurant System (Production Mode)"

# Set critical environment variables
export FLASK_ENV=production
export USE_EVENTLET=0
export PYTHONPATH=/opt/render/project/src

echo "📦 Environment:"
echo "  - FLASK_ENV: $FLASK_ENV"
echo "  - USE_EVENTLET: $USE_EVENTLET"
echo "  - PORT: $PORT"

echo "🗄️ Setting up database..."
python -m flask db upgrade || echo "⚠️ Migration failed, continuing..."

echo "👤 Creating admin user..."
python create_user.py --default || echo "⚠️ User creation failed, continuing..."

echo "🌐 Starting web server with gevent workers..."
exec gunicorn simple_app:app -k gevent --workers 3 --threads 2 --timeout 120 --bind 0.0.0.0:$PORT
