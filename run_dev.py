#!/usr/bin/env python3
"""
وضع المطور الموحّد: يشغّل tools/run_local.py (create_app، قاعدة محلية، منفذ 5000).
لتشغيل الخادم: python run_dev.py  ->  http://127.0.0.1:5000
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
script = os.path.join(ROOT, "tools", "run_local.py")
sys.exit(subprocess.run([sys.executable, script], cwd=ROOT).returncode)
