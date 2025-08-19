#!/bin/bash
# Build script for Render

set -e

echo "🔧 Setting up environment..."
export FLASK_ENV=production
export USE_EVENTLET=0

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🗄️ Setting up database..."
python -m flask db upgrade || echo "⚠️ Migration skipped"

echo "👤 Creating admin user..."
python create_user.py --default || echo "⚠️ User creation skipped"

echo "✅ Build completed successfully!"
