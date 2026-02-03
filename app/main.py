"""
Wild Goose Agent - Desktop Application Entry Point

Usage:
    python -m app.main
    # or
    python app/main.py
"""

from __future__ import annotations

import sys
import os


def _setup_path() -> None:
    """Add project root to path for imports."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _load_env() -> None:
    """Load environment variables from .env file if available."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def main() -> None:
    """Main entry point for the application."""
    # Setup before importing Qt modules
    _setup_path()
    _load_env()

    # Import Qt modules after path setup
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    from app.window import MainWindow

    # High DPI settings (must be set before QApplication creation)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("Wild Goose Agent")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("WildGoose")

    # Set default font
    font = QFont()
    font.setFamily("-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif")
    font.setPointSize(13)
    app.setFont(font)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
