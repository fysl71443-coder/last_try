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

# Use Render start script to apply migrations and start Gunicorn safely
COPY scripts/start_render.sh /app/scripts/start_render.sh
RUN chmod +x /app/scripts/start_render.sh
CMD ["/app/scripts/start_render.sh"]
