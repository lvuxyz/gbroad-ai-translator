"""Logging configuration for Windows AI Translation Tool.

Provides rotating file logging, console logging, API key redaction,
and Privacy Mode scrubbing.
"""

import os
import re
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOGGER_NAME = "AITranslator"

# Regex patterns for sensitive credentials
API_KEY_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),          # OpenAI
    re.compile(r"AIza[0-9A-Za-z-_]{35}", re.IGNORECASE),          # Google/Gemini
    re.compile(r"(?:Bearer\s+)[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), # Bearer token
    re.compile(r"(?:key=)[a-zA-Z0-9_\-]{16,}", re.IGNORECASE),    # URL query key
]


class SensitiveDataFilter(logging.Filter):
    """Filters out API keys and credentials from log messages."""

    def __init__(self, privacy_mode: bool = False):
        super().__init__()
        self.privacy_mode = privacy_mode

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg)

        # Redact API keys
        for pattern in API_KEY_PATTERNS:
            msg = pattern.sub("[REDACTED_API_KEY]", msg)

        # In privacy mode, protect any user text contents that might be logged
        if self.privacy_mode and hasattr(record, "user_text"):
            msg = re.sub(r"text='.*?'", "text='[PROTECTED_IN_PRIVACY_MODE]'", msg)
            msg = re.sub(r'text=".*?"', 'text="[PROTECTED_IN_PRIVACY_MODE]"', msg)

        record.msg = msg
        return True


_logger_instance: Optional[logging.Logger] = None
_sensitive_filter: Optional[SensitiveDataFilter] = None


def setup_logger(
    log_dir: Optional[Path] = None,
    log_level: int = logging.INFO,
    privacy_mode: bool = False
) -> logging.Logger:
    """Initializes and returns the application logger with rotating file handler."""
    global _logger_instance, _sensitive_filter

    if _logger_instance is not None:
        if _sensitive_filter is not None:
            _sensitive_filter.privacy_mode = privacy_mode
        return _logger_instance

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)
    logger.propagate = False

    # Create logs directory
    if log_dir is None:
        app_data = os.getenv("APPDATA")
        if app_data:
            base_dir = Path(app_data) / "AITranslator"
        else:
            base_dir = Path(__file__).resolve().parent.parent
        log_dir = base_dir / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # Rotating file handler: 5MB per file, up to 3 backups
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Redaction filter
    _sensitive_filter = SensitiveDataFilter(privacy_mode=privacy_mode)
    file_handler.addFilter(_sensitive_filter)
    console_handler.addFilter(_sensitive_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    _logger_instance = logger
    logger.info("Application logger initialized. Log file: %s", log_file)
    return logger


def get_logger() -> logging.Logger:
    """Retrieves existing logger or creates one with defaults."""
    global _logger_instance
    if _logger_instance is None:
        return setup_logger()
    return _logger_instance


def set_privacy_mode(enabled: bool) -> None:
    """Updates the privacy mode state in the active logger filter."""
    global _sensitive_filter
    if _sensitive_filter is not None:
        _sensitive_filter.privacy_mode = enabled
