import logging
import sys
from logging import Logger
from logging.handlers import RotatingFileHandler
from typing import Optional


def _has_handler(logger: Logger, cls, filename: Optional[str] = None) -> bool:
    for h in logger.handlers:
        if isinstance(h, cls):
            if filename is None:
                return True
            # For file handlers, ensure same target file if possible
            if hasattr(h, 'baseFilename') and h.baseFilename:
                try:
                    if str(h.baseFilename).endswith(str(filename)):
                        return True
                except Exception:
                    pass
    return False


def setup_logging(log_level: int = logging.DEBUG, logfile: str = 'app.log') -> Logger:
    """
    Configure root logging to stream to stdout AND write to a rotating file.
    Idempotent: safe to call multiple times without duplicating handlers.
    """
    logger = logging.getLogger()
    logger.setLevel(log_level)

    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Console handler (stdout)
    if not _has_handler(logger, logging.StreamHandler):
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(log_level)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # File handler (rotating)
    if not _has_handler(logger, RotatingFileHandler, filename=logfile):
        fh = RotatingFileHandler(logfile, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
        fh.setLevel(log_level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    # Make werkzeug (Flask dev server) logs go through root as well
    try:
        werk = logging.getLogger('werkzeug')
        werk.setLevel(logging.INFO)
        werk.propagate = True
    except Exception:
        pass

    return logger


if __name__ == "__main__":
    log = setup_logging()
    log.info("تم إعداد اللوق بنجاح / Logging initialized successfully")
    log.debug("Debug message test")
    log.warning("Warning message test")
    log.error("Error message test")

