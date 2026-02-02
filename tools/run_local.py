"""
Single dev server entry point. Uses app package (create_app), local SQLite, debug+reloader.
Run: python tools/run_local.py  ->  http://127.0.0.1:5000
"""
import os
import sys
import importlib
import pathlib

# Match wsgi stability settings (before any app import)
os.environ.setdefault("USE_EVENTLET", "0")
os.environ.setdefault("DISABLE_SOCKETIO", "1")

# إجبار SQLite المحلي فقط – إلغاء أي اتصال بـ Render/PostgreSQL
u = os.environ.get("DATABASE_URL") or ""
if "postgres" in u.lower() or "render.com" in u.lower():
    os.environ.pop("DATABASE_URL", None)
instance_dir = pathlib.Path(os.path.join(os.path.dirname(__file__), "..", "instance")).resolve()
instance_dir.mkdir(parents=True, exist_ok=True)
db_file = instance_dir.joinpath("accounting_app.db").resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
os.environ.setdefault("SECRET_KEY", "dev")
os.environ["LOCAL_SQLITE_PATH"] = str(db_file)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

pkg = importlib.import_module("app")
app = pkg.create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=True)

