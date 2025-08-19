import os
import sys
import subprocess

if __name__ == "__main__":
    port = os.getenv("PORT", "8000")  # Render يرسل PORT تلقائيًا

    cmd = [
        "gunicorn",
        "wsgi:application",
        "-k", "gevent",
        "--workers", "3",
        "--threads", "2",
        "--timeout", "120",
        f"--bind=0.0.0.0:{port}"
    ]
    
    try:
        print(f"🚀 Starting Gunicorn on port {port} ...")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running gunicorn: {e}")
        sys.exit(1)
