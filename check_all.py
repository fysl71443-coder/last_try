import sys
import py_compile
from pathlib import Path

# Optional Jinja2 checks
try:
    from jinja2 import Environment, FileSystemLoader
    HAVE_JINJA2 = True
except Exception:
    HAVE_JINJA2 = False

BASE = Path(__file__).resolve().parent
errors: list[str] = []

# 1) Python syntax check for all .py files
for p in BASE.rglob('*.py'):
    # Skip common virtual env or cache dirs
    parts = set(p.parts)
    if any(x in parts for x in {'.venv', 'venv', 'env', '__pycache__'}):
        continue
    try:
        py_compile.compile(str(p), doraise=True)
    except Exception as e:
        errors.append(f"PY:{p}: {e}")

# 2) Jinja2 templates syntax check
TPL_DIR = BASE / 'templates'
if HAVE_JINJA2 and TPL_DIR.exists():
    env = Environment(loader=FileSystemLoader(str(TPL_DIR)))
    for t in TPL_DIR.rglob('*.html'):
        try:
            # Load and compile template
            rel = t.relative_to(TPL_DIR).as_posix()
            env.get_template(rel)
        except Exception as e:
            errors.append(f"J2:{t}: {e}")

if errors:
    print("\n".join(errors))
    sys.exit(1)
else:
    print("OK")
    sys.exit(0)

