"""Reusable list panel component with search functionality."""

from typing import Any, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Signal, Qt
import qtawesome as qta


class ListPanel(QWidget):
    """A reusable list panel with search and optional add button."""

    item_selected = Signal(object)  # Emits the selected item's data
    add_clicked = Signal()  # Emits when add button is clicked

    def __init__(
        self,
        title: str = "",
        show_search: bool = True,
        show_add_button: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("listPanel")
        self._items: list[dict[str, Any]] = []
        self._filtered_items: list[dict[str, Any]] = []

        self._setup_ui(title, show_search, show_add_button)

    def _setup_ui(self, title: str, show_search: bool, show_add_button: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with title and optional add button
        if title or show_add_button:
            header = QHBoxLayout()
            header.setContentsMargins(16, 12, 16, 12)

            if title:
                title_label = QLabel(title)
                title_label.setObjectName("sectionTitle")
                header.addWidget(title_label)

            header.addStretch()

            if show_add_button:
                add_btn = QPushButton()
                add_btn.setObjectName("iconButton")
                add_btn.setIcon(qta.icon("fa5s.plus"))
                add_btn.setToolTip("Add new")
                add_btn.clicked.connect(self.add_clicked.emit)
                header.addWidget(add_btn)

            layout.addLayout(header)

        # Search box
        if show_search:
            search_container = QHBoxLayout()
            search_container.setContentsMargins(16, 0, 16, 12)

            self._search_input = QLineEdit()
            self._search_input.setObjectName("searchBox")
            self._search_input.setPlaceholderText("Search...")
            self._search_input.textChanged.connect(self._on_search)
            search_container.addWidget(self._search_input)

            layout.addLayout(search_container)

        # List widget
        self._list_widget = QListWidget()
        self._list_widget.setObjectName("itemList")
        self._list_widget.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list_widget)

    def set_items(self, items: list[dict[str, Any]]) -> None:
        """
        Set the list items.

        Each item should be a dict with at least:
        - 'name': Display name
        - 'data': The data object to emit when selected

        Optional:
        - 'description': Secondary text
        - 'badge': Badge text to show
        - 'badge_type': 'builtin', 'user', 'project' for styling
        """
        self._items = items
        self._filtered_items = items
        self._update_list()

    def _update_list(self) -> None:
        """Update the list widget with filtered items."""
        self._list_widget.clear()

        for item in self._filtered_items:
            list_item = QListWidgetItem()
            name = item.get("name", "Unknown")
            description = item.get("description", "")
            badge = item.get("badge", "")

            # Format display text
            display_text = name
            if badge:
                display_text = f"{name}  [{badge}]"

            list_item.setText(display_text)

            if description:
                list_item.setToolTip(description)

            # Store the full item data
            list_item.setData(Qt.ItemDataRole.UserRole, item)

            self._list_widget.addItem(list_item)

        # Select first item if available
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _on_search(self, text: str) -> None:
        """Filter items based on search text."""
        search_lower = text.lower().strip()

        if not search_lower:
            self._filtered_items = self._items
        else:
            self._filtered_items = [
                item
                for item in self._items
                if search_lower in item.get("name", "").lower()
                or search_lower in item.get("description", "").lower()
            ]

        self._update_list()

    def _on_item_changed(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
    ) -> None:
        """Handle item selection change."""
        if current:
            data = current.data(Qt.ItemDataRole.UserRole)
            self.item_selected.emit(data)

    def select_item_by_name(self, name: str) -> None:
        """Select an item by its name."""
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get("name") == name:
                self._list_widget.setCurrentItem(item)
                break

    def get_selected_item(self) -> Optional[dict[str, Any]]:
        """Get the currently selected item data."""
        current = self._list_widget.currentItem()
        if current:
            return current.data(Qt.ItemDataRole.UserRole)
        return None

    def refresh(self) -> None:
        """Refresh the list while preserving selection."""
        selected = self.get_selected_item()
        self._update_list()
        if selected:
            self.select_item_by_name(selected.get("name", ""))
