#!/bin/bash

export FLASK_APP=clean_app.py
gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT clean_app:app
