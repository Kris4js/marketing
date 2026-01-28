"""
Global Logger Manager using loguru.

Configuration via .env file:
- LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- LOG_MODE: Environment mode (development, production)
- LOG_DIR: Log directory for production (default: logs)
- LOG_ROTATION: Rotation size (e.g., "10 MB", "1 GB", "1 day")
- LOG_RETENTION: Retention time (e.g., "7 days", "1 month")
- LOG_COMPRESSION: Compression format (e.g., "zip", "gz", "tar")
"""

import sys
import os
from pathlib import Path
from loguru import logger
from typing import Optional

# Default configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_MODE = "development"
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_ROTATION = "10 MB"
DEFAULT_LOG_RETENTION = "7 days"
DEFAULT_LOG_COMPRESSION = "zip"


class LoggerManager:
    """Global singleton logger manager."""

    _instance: Optional["LoggerManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once (singleton pattern)
        if LoggerManager._initialized:
            return
        LoggerManager._initialized = True

        # Read configuration from environment
        self.log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
        self.log_mode = os.getenv("LOG_MODE", DEFAULT_LOG_MODE).lower()
        self.log_dir = Path(os.getenv("LOG_DIR", DEFAULT_LOG_DIR))
        self.log_rotation = os.getenv("LOG_ROTATION", DEFAULT_LOG_ROTATION)
        self.log_retention = os.getenv("LOG_RETENTION", DEFAULT_LOG_RETENTION)
        self.log_compression = os.getenv("LOG_COMPRESSION", DEFAULT_LOG_COMPRESSION)

        # Remove default handler
        logger.remove()

        # Configure based on mode
        if self.log_mode == "production":
            self._configure_production()
        else:
            self._configure_development()

    def _configure_development(self):
        """Configure logger for development (console output)."""
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=self.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    def _configure_production(self):
        """Configure logger for production (file output with rotation)."""
        # Create log directory if not exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # General log file
        logger.add(
            self.log_dir / "app_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]}:{function}:{line} - {message}",
            level=self.log_level,
            rotation=self.log_rotation,
            retention=self.log_retention,
            compression=self.log_compression,
            encoding="utf-8",
            enqueue=True,  # Async logging
        )

        # Error log file (separate file for errors)
        logger.add(
            self.log_dir / "error_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]}:{function}:{line} - {message}",
            level="ERROR",
            rotation=self.log_rotation,
            retention=self.log_retention,
            compression=self.log_compression,
            encoding="utf-8",
            enqueue=True,
        )

    def get_logger(self, name: Optional[str] = None):
        """
        Get a logger instance.

        Args:
            name: Logger name (optional, for binding context). If not provided,
                  uses "root" as default.

        Returns:
            Logger instance

        Example:
            logger_manager = LoggerManager()
            log = logger_manager.get_logger(__name__)
            log.info("Hello, world!")
        """
        log_name = name if name else "root"
        return logger.bind(name=log_name)

    def set_level(self, level: str):
        """
        Change log level at runtime.

        Args:
            level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        Example:
            logger_manager = LoggerManager()
            logger_manager.set_level("DEBUG")
        """
        self.log_level = level.upper()
        # Update all handlers - logger._core.handlers is a dict {int_id: handler}
        for handler_id in logger._core.handlers:
            logger.remove(handler_id)
        if self.log_mode == "production":
            self._configure_production()
        else:
            self._configure_development()


# ======================================================================
## Convenience Functions
# ======================================================================


def get_logger(name: Optional[str] = None):
    """
    Get a logger instance. This is the recommended way to use the logger.

    Args:
        name: Logger name (optional)

    Returns:
        Logger instance

    Example:
        from src.utils.logger import get_logger

        log = get_logger(__name__)
        log.info("This is an info message")
        log.error("This is an error message")
    """
    manager = LoggerManager()
    return manager.get_logger(name)


def set_log_level(level: str):
    """
    Change log level at runtime.

    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        from src.utils.logger import set_log_level

        set_log_level("DEBUG")
    """
    manager = LoggerManager()
    manager.set_level(level)


# Export logger directly for convenience
__all__ = ["LoggerManager", "get_logger", "set_log_level", "logger"]
