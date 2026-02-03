"""Reusable preview panel component for displaying item details."""

from typing import Any, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Signal, Qt
import qtawesome as qta

from app.components.markdown_viewer import MarkdownViewer


class PreviewPanel(QWidget):
    """A reusable preview panel for displaying item details."""

    action_clicked = Signal(str, object)  # (action_name, item_data)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("previewPanel")
        self._current_item: Optional[dict[str, Any]] = None
        self._is_dark = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header section
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Title and badge
        title_container = QVBoxLayout()
        title_container.setSpacing(4)

        self._title_label = QLabel()
        self._title_label.setObjectName("previewTitle")
        self._title_label.setWordWrap(True)
        title_container.addWidget(self._title_label)

        self._badge_label = QLabel()
        self._badge_label.setObjectName("subtleText")
        title_container.addWidget(self._badge_label)

        header_layout.addLayout(title_container)
        header_layout.addStretch()

        # Action buttons container
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(8)
        header_layout.addLayout(self._actions_layout)

        layout.addLayout(header_layout)

        # Description
        self._description_label = QLabel()
        self._description_label.setObjectName("previewDescription")
        self._description_label.setWordWrap(True)
        layout.addWidget(self._description_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #e2e8f0;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Content area (markdown viewer in scroll area)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._content_viewer = MarkdownViewer()
        scroll_area.setWidget(self._content_viewer)

        layout.addWidget(scroll_area, 1)

        # Empty state
        self._empty_label = QLabel("Select an item to view details")
        self._empty_label.setObjectName("subtleText")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        # Initially show empty state
        self._show_empty_state(True)

    def _show_empty_state(self, show: bool) -> None:
        """Toggle between empty state and content."""
        self._empty_label.setVisible(show)
        self._title_label.setVisible(not show)
        self._badge_label.setVisible(not show)
        self._description_label.setVisible(not show)

    def set_item(self, item: Optional[dict[str, Any]]) -> None:
        """
        Set the item to preview.

        Expected item structure:
        - 'name': Title
        - 'description': Short description
        - 'content': Markdown content to display
        - 'badge': Optional badge text
        - 'badge_type': Optional badge styling
        - 'actions': Optional list of {'name': str, 'label': str, 'icon': str}
        """
        self._current_item = item

        if not item:
            self._show_empty_state(True)
            self._content_viewer.clear_content()
            self._clear_actions()
            return

        self._show_empty_state(False)

        # Set title
        self._title_label.setText(item.get("name", "Unknown"))

        # Set badge
        badge = item.get("badge", "")
        badge_type = item.get("badge_type", "")
        if badge:
            self._badge_label.setText(f"{badge_type.title()}: {badge}" if badge_type else badge)
            self._badge_label.setVisible(True)
        else:
            self._badge_label.setVisible(False)

        # Set description
        description = item.get("description", "")
        self._description_label.setText(description)
        self._description_label.setVisible(bool(description))

        # Set content
        content = item.get("content", "")
        self._content_viewer.set_markdown(content)

        # Set up actions
        self._setup_actions(item.get("actions", []))

    def _clear_actions(self) -> None:
        """Clear all action buttons."""
        while self._actions_layout.count():
            child = self._actions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _setup_actions(self, actions: list[dict[str, str]]) -> None:
        """Set up action buttons."""
        self._clear_actions()

        for action in actions:
            btn = QPushButton(action.get("label", "Action"))

            icon_name = action.get("icon")
            if icon_name:
                btn.setIcon(qta.icon(icon_name))

            # Style based on action type
            if action.get("primary"):
                pass  # Default primary style
            else:
                btn.setObjectName("secondaryButton")

            action_name = action.get("name", "")
            btn.clicked.connect(
                lambda checked, name=action_name: self._on_action_clicked(name)
            )

            self._actions_layout.addWidget(btn)

    def _on_action_clicked(self, action_name: str) -> None:
        """Handle action button click."""
        self.action_clicked.emit(action_name, self._current_item)

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update theme for the preview panel."""
        self._is_dark = is_dark
        self._content_viewer.set_dark_theme(is_dark)

    def set_content(self, markdown_text: str) -> None:
        """Directly set markdown content."""
        self._content_viewer.set_markdown(markdown_text)
