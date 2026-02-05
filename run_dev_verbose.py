#!/usr/bin/env python3
"""تشغيل الخادم في وضع المطور مع كونسول تفصيلي (verbose logging)."""
import os
import sys
import logging

# تفعيل التسجيل التفصيلي قبل تحميل التطبيق
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logging.getLogger("werkzeug").setLevel(logging.DEBUG)
logging.getLogger("flask").setLevel(logging.DEBUG)

# إجبار عدم التخزين المؤقت للمخرجات
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_ENV", "development")

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    print("=" * 60, file=sys.stderr)
    print("  خادم المطور (وضع تفصيلي) — http://127.0.0.1:5000", file=sys.stderr)
    print("  أوقف الخادم بـ Ctrl+C", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=True)
