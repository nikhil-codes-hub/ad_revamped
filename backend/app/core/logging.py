"""
Structured logging configuration for AssistedDiscovery.

Uses structlog for consistent, structured logging across the application.
"""

import sys
import logging
import platform
from pathlib import Path
from typing import Any, Dict
from logging.handlers import RotatingFileHandler

import structlog
from structlog.stdlib import LoggerFactory

from app.core.config import settings


def get_log_directory() -> Path:
    """
    Get platform-specific log directory.

    Returns:
        - macOS: ~/Library/Logs/AssistedDiscovery
        - Windows: %LOCALAPPDATA%/AssistedDiscovery/Logs
        - Linux: ~/.local/share/AssistedDiscovery/logs
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        log_dir = Path.home() / "Library" / "Logs" / "AssistedDiscovery"
    elif system == "Windows":
        log_dir = Path.home() / "AppData" / "Local" / "AssistedDiscovery" / "Logs"
    else:  # Linux and others
        log_dir = Path.home() / ".local" / "share" / "AssistedDiscovery" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging() -> None:
    """Configure structured logging for the application."""

    # Get log directory
    log_dir = get_log_directory()
    log_file = log_dir / "assisted_discovery.log"

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.dev.ConsoleRenderer() if settings.is_development else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create rotating file handler (max 10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    # Configure standard library logging with both console and file handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler with more detailed format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    ))

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set log levels for external libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if settings.DEBUG else logging.WARNING
    )

    # Log startup message with file location
    logging.info(f"Logging initialized. Log file: {log_file}")


def get_logger(name: str) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to provide structured logging to other classes."""

    @property
    def logger(self) -> Any:
        """Get logger instance for the class."""
        return get_logger(self.__class__.__name__)