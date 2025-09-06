"""
Local error logging setup for development.

Adds a RotatingFileHandler to capture errors from Flask app,
Werkzeug, and root loggers into logs/local-errors.log.

Usage (local):
    from logging_setup import setup_logging
    setup_logging(app)
"""
from __future__ import annotations
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

try:
    from flask import got_request_exception, Request
except Exception:  # Runtime import guard if Flask not installed in context
    got_request_exception = None  # type: ignore


def setup_logging(app: Optional[object] = None,
                  log_dir: str = 'logs',
                  log_file: str = 'local-errors.log',
                  level: int = logging.ERROR) -> None:
    """Configure rotating file logging for local server errors.

    - Creates logs/<log_file>
    - Attaches a RotatingFileHandler to root, Flask, and Werkzeug loggers
    - Optionally hooks Flask got_request_exception to log extra request context
    """
    # Ensure logs directory exists
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    # Avoid duplicate handlers on re-run (debug/reloader)
    logger = logging.getLogger()
    existing = [h for h in logger.handlers if isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '') == os.path.abspath(log_path)]
    if existing:
        return

    fmt = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')

    file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)

    # Attach to root logger
    root = logging.getLogger()
    root.setLevel(min(root.level or level, level))
    root.addHandler(file_handler)

    # Flask app logger
    try:
        if app is not None:
            app_logger = getattr(app, 'logger', None)
            if app_logger and not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '') == os.path.abspath(log_path) for h in app_logger.handlers):
                app_logger.addHandler(file_handler)
                app_logger.setLevel(min(app_logger.level or level, level))
    except Exception:
        pass

    # Werkzeug request logger
    try:
        wlog = logging.getLogger('werkzeug')
        if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '') == os.path.abspath(log_path) for h in wlog.handlers):
            wlog.addHandler(file_handler)
            wlog.setLevel(min(wlog.level or level, level))
    except Exception:
        pass

    # Log unhandled exceptions
    def _excepthook(exc_type, exc, tb):
        logging.getLogger(__name__).exception('Unhandled exception', exc_info=(exc_type, exc, tb))
        # Delegate to default hook to keep default behavior in console
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    # Hook Flask request exception signal to add context
    if app is not None and got_request_exception is not None:
        try:
            @got_request_exception.connect_via(app)
            def _log_exception(sender, exception, **extra):  # type: ignore
                try:
                    from flask import request
                    logging.getLogger('flask.app').exception(
                        'Request error: %s %s (remote=%s)',
                        request.method, request.path, request.remote_addr
                    )
                except Exception:
                    logging.getLogger('flask.app').exception('Request error (no request context)')
        except Exception:
            pass

    # Startup info
    logging.getLogger(__name__).info('Local error logging initialized -> %s', log_path)

