"""Main application window."""

import os
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPushButton,
    QLabel,
    QFrame,
)
import qtawesome as qta

from app.pages.chat import ChatPage
from app.pages.resources import ResourcesPage
from app.pages.settings import SettingsDialog
from app.themes import load_theme


class MainWindow(QMainWindow):
    """Main application window with tab navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wild Goose Agent")
        self.setMinimumSize(1024, 768)

        # Theme state
        self._is_dark = os.getenv("THEME", "light") == "dark"

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = self._create_header()
        layout.addWidget(header)

        # Main tab widget
        self._tab_widget = QTabWidget()
        self._tab_widget.setObjectName("navTabs")
        self._tab_widget.setDocumentMode(True)

        # Chat page
        self._chat_page = ChatPage()
        self._tab_widget.addTab(self._chat_page, "Chat")

        # Resources page
        self._resources_page = ResourcesPage()
        self._tab_widget.addTab(self._resources_page, "Resources")

        layout.addWidget(self._tab_widget)

    def _create_header(self) -> QFrame:
        """Create the header bar."""
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(56)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        # App icon/logo
        logo_label = QLabel()
        logo_label.setPixmap(
            qta.icon("fa5s.feather-alt", color="#6366f1").pixmap(24, 24)
        )
        layout.addWidget(logo_label)

        # App title
        title = QLabel("Wild Goose Agent")
        title.setObjectName("headerTitle")
        layout.addWidget(title)

        layout.addStretch()

        # Theme toggle
        self._theme_btn = QPushButton()
        self._theme_btn.setObjectName("iconButton")
        self._theme_btn.setToolTip("Toggle dark/light mode")
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._update_theme_button()
        layout.addWidget(self._theme_btn)

        # Settings button
        settings_btn = QPushButton()
        settings_btn.setObjectName("iconButton")
        settings_btn.setIcon(qta.icon("fa5s.cog"))
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)

        return header

    def _update_theme_button(self) -> None:
        """Update theme button icon based on current theme."""
        if self._is_dark:
            self._theme_btn.setIcon(qta.icon("fa5s.sun", color="#fcd34d"))
        else:
            self._theme_btn.setIcon(qta.icon("fa5s.moon", color="#6366f1"))

    def _toggle_theme(self) -> None:
        """Toggle between light and dark theme."""
        self._is_dark = not self._is_dark
        self._apply_theme()
        self._update_theme_button()

        # Update environment variable
        os.environ["THEME"] = "dark" if self._is_dark else "light"

    def _apply_theme(self) -> None:
        """Apply the current theme."""
        theme_name = "dark" if self._is_dark else "light"
        stylesheet = load_theme(theme_name)
        self.setStyleSheet(stylesheet)

        # Update child pages
        self._chat_page.set_dark_theme(self._is_dark)
        self._resources_page.set_dark_theme(self._is_dark)

    def _open_settings(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(self)
        dialog.set_dark_mode(self._is_dark)
        dialog.theme_changed.connect(self._on_theme_changed)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    def _on_theme_changed(self, is_dark: bool) -> None:
        """Handle theme change from settings."""
        self._is_dark = is_dark
        self._apply_theme()
        self._update_theme_button()
        os.environ["THEME"] = "dark" if is_dark else "light"

    def _on_settings_changed(self, settings: dict) -> None:
        """Handle settings change."""
        # Update model configuration in chat page
        model = settings.get("model", "google/gemini-3-flash-preview")
        provider = settings.get("provider", "openrouter")
        self._chat_page.set_model(model, provider)

        # Refresh resources to pick up any tool changes
        self._resources_page.refresh()

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Perform any cleanup here if needed
        event.accept()
