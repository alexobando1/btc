import logging
import os
from logging.handlers import RotatingFileHandler

from config import config


def setup_logger(name: str) -> logging.Logger:
    os.makedirs(config.LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Rotating file (10 MB × 5 backups)
    fh = RotatingFileHandler(
        os.path.join(config.LOG_DIR, "bot.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
