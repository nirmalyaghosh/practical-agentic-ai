import logging
import logging.handlers
import os
import platform

from pathlib import Path
from typing import (
    Any,
    Dict,
)


# Import the concurrent log handler only if needed (conditionally)
try:
    from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
    concurrent_handler_available = True
except ImportError:
    concurrent_handler_available = False


def get_logger(name: str):
    """
    Creates and returns a logger with console and file handlers.
    File handler uses settings from the config for rotation, paths, etc.

    Returns:
        A configured logger instance
    """

    module_name = os.environ.get(
        "MODULE_NAME",
        "filesystem-archaeologist-agent")

    # Get the logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    # Get the appropriate configuration for this module
    logging_config = _setup_logging_config()

    # Create a formatter
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Create console handler and set level to WARNING
    # (to avoid duplicating what the CLI's typer displays to console)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)

    # Default to 'logs' directory if no path specified
    # (Create the default logs directory if needed)
    default_log_dir = Path("logs")
    default_log_dir.mkdir(parents=True, exist_ok=True)
    default_log_path = default_log_dir / f"{module_name}.log"
    # Get log file path from config or use default
    log_file_path = Path(logging_config.get("log_file_path",
                                            str(default_log_path)))
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure the logs directory exists using Path
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    backup_count = logging_config.get("backup_count", 5)

    # Choose the appropriate handler based on OS and package availability
    is_windows = platform.system() == "Windows"

    # On Windows, use ConcurrentTimedRotatingFileHandler if available
    if is_windows and concurrent_handler_available:
        # Use ConcurrentTimedRotatingFileHandler for Windows
        # (this is done to prevent permission errors)
        file_handler = ConcurrentTimedRotatingFileHandler(
            log_file_path,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
            use_gzip=False
        )
    else:
        # For non-Windows or when concurrent_log_handler is unavailable
        # use the standard TimedRotatingFileHandler
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file_path,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
            atTime=None,
            utc=False
        )

    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(ch)
    logger.addHandler(file_handler)

    return logger


def _setup_logging_config() -> Dict[str, Any]:
    """
    Helper function used to setup the logging configuration
    """
    # Check for environment variables first
    module_name = os.environ.get("MODULE_NAME", "newsletter-declutter-agent")
    key_prefix = module_name.upper()
    log_file = os.environ.get(f"{key_prefix}_LOG_FILE_PATH")
    backup_count = os.environ.get(f"{key_prefix}_BACKUP_COUNT", 5)
    timezone = os.environ.get(f"{key_prefix}_TIMEZONE", "Asia/Singapore")

    log_config = {}

    # Override with environment variables if available
    if log_file:
        log_config["log_file_path"] = log_file
    if backup_count:
        try:
            log_config["backup_count"] = int(backup_count)
        except ValueError:
            pass
    if timezone:
        log_config["timezone"] = timezone

    return log_config
