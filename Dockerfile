# Use official python runtime as a parent image
FROM python:3.11-slim

# set workdir
WORKDIR /app

# install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev --no-install-recommends && rm -rf /var/lib/apt/lists/*

# copy requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir eventlet gunicorn

# copy app
COPY . /app

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Render provides PORT env var
EXPOSE 8000

<<<<<<< HEAD
# Use start script to apply migrations then start server
COPY scripts/start.sh /app/scripts/start.sh
RUN chmod +x /app/scripts/start.sh
CMD ["/app/scripts/start.sh"]
=======
# run migrations then start gunicorn with eventlet worker and dynamic port
CMD sh -c "flask db upgrade && gunicorn -k eventlet -w 1 -b 0.0.0.0:${PORT:-8000} app:app"
>>>>>>> 4b7ff02 (chore(render): configure eventlet/gunicorn, dynamic PORT, db migrations; update render.yaml)
