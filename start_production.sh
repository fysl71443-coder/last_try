#!/bin/bash
# Production startup script for Render

set -e

echo "🚀 Starting Restaurant System Production Deployment"

# Set environment variables
export FLASK_ENV=production
export USE_EVENTLET=0
export PYTHONPATH=/opt/render/project/src

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🗄️ Setting up database..."
python -m flask db upgrade || echo "⚠️ Migration failed, continuing..."

echo "👤 Creating default admin user..."
python create_user.py --default || echo "⚠️ User creation failed, continuing..."

echo "🌐 Starting web server..."
exec gunicorn --worker-class sync --workers 1 --bind 0.0.0.0:$PORT wsgi:application
