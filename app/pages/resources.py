"""Resources page - container with sub-tabs for Tools, Skills, Prompts."""

from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Signal

from app.pages.tools import ToolsPage
from app.pages.skills import SkillsPage
from app.pages.prompts import PromptsPage


class ResourcesPage(QWidget):
    """Container page with sub-tabs for Tools, Skills, and Prompts."""

    tab_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_dark = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sub-navigation tabs
        self._tab_widget = QTabWidget()
        self._tab_widget.setObjectName("subNavTabs")
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.currentChanged.connect(self.tab_changed.emit)

        # Tools tab
        self._tools_page = ToolsPage()
        self._tab_widget.addTab(self._tools_page, "Tools")

        # Skills tab
        self._skills_page = SkillsPage()
        self._tab_widget.addTab(self._skills_page, "Skills")

        # Prompts tab
        self._prompts_page = PromptsPage()
        self._tab_widget.addTab(self._prompts_page, "Prompts")

        layout.addWidget(self._tab_widget)

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update theme for all sub-pages."""
        self._is_dark = is_dark
        self._tools_page.set_dark_theme(is_dark)
        self._skills_page.set_dark_theme(is_dark)
        self._prompts_page.set_dark_theme(is_dark)

    def refresh(self) -> None:
        """Refresh all sub-pages."""
        self._tools_page.refresh()
        self._skills_page.refresh()
        self._prompts_page.refresh()

    def set_current_tab(self, index: int) -> None:
        """Set the current sub-tab."""
        if 0 <= index < self._tab_widget.count():
            self._tab_widget.setCurrentIndex(index)
