"""
Example usage of the LoggerManager.

This demonstrates how to use the global logger in your application.
"""

from src.utils.logger import get_logger, set_log_level


def example_basic_usage():
    """Example 1: Basic logger usage"""
    log = get_logger(__name__)

    log.debug("This is a debug message")
    log.info("This is an info message")
    log.warning("This is a warning message")
    log.error("This is an error message")
    log.critical("This is a critical message")


def example_with_context():
    """Example 2: Logger with context binding"""
    log = get_logger("my_module").bind(user_id="12345", action="login")

    log.info("User logged in successfully")
    log.warning("Failed login attempt")


def example_exception_logging():
    """Example 3: Exception logging"""
    log = get_logger(__name__)

    try:
        result = 1 / 0
    except ZeroDivisionError as e:
        log.error(f"Division by zero: {e}")
        # Or with exception info
        log.exception("Detailed error information")


def example_runtime_level_change():
    """Example 4: Change log level at runtime"""
    log = get_logger(__name__)

    log.info("\n--- Before level change ---")
    log.debug("This debug message might not appear")
    log.info("This info message appears")

    # Change to DEBUG level
    set_log_level("DEBUG")

    log.info("\n--- After level change to DEBUG ---")
    log.debug("Now debug messages appear!")
    log.info("Info messages still appear")


def example_multiple_modules():
    """Example 5: Multiple modules using the same logger"""
    # Module A
    log_a = get_logger("module_a")
    log_a.info("Processing in module A")

    # Module B
    log_b = get_logger("module_b")
    log_b.info("Processing in module B")

    # Main module
    main_log = get_logger(__name__)
    main_log.info("Main module coordinating")


if __name__ == "__main__":
    log = get_logger(__name__)
    log.info("=" * 50)
    log.info("Example 1: Basic Usage")
    log.info("=" * 50)
    example_basic_usage()

    log.info("\n" + "=" * 50)
    log.info("Example 2: Logger with Context")
    log.info("=" * 50)
    example_with_context()

    log.info("\n" + "=" * 50)
    log.info("Example 3: Exception Logging")
    log.info("=" * 50)
    example_exception_logging()

    log.info("\n" + "=" * 50)
    log.info("Example 4: Runtime Level Change")
    log.info("=" * 50)
    example_runtime_level_change()

    log.info("\n" + "=" * 50)
    log.info("Example 5: Multiple Modules")
    log.info("=" * 50)
    example_multiple_modules()
