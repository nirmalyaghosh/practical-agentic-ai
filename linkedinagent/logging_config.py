import os
import logging
import sys

from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/linkedinagent.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Ensure log directory exists
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
formatter = logging.Formatter(log_format)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8")
file_handler.setFormatter(formatter)

for h in (stream_handler, file_handler):
    h.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[stream_handler, file_handler])
logger = logging.getLogger(__name__)
