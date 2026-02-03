"""Prompts page - displays and edits prompt templates."""

from typing import Optional, Any
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QTextEdit,
    QLabel,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt

from app.components.list_panel import ListPanel

from src.agent.prompts import (
    SYSTEM_PROMPT,
    CONTEXT_SELECTION_SYSTEM_PROMPT,
    MESSAGE_SUMMARY_SYSTEM_PROMPT,
    MESSAGE_SELECTION_SYSTEM_PROMPT,
)


# Define available prompts
PROMPT_TEMPLATES = [
    {
        "name": "System Prompt",
        "key": "system",
        "description": "Main system prompt that defines the agent's personality and behavior",
        "content": SYSTEM_PROMPT,
        "editable": True,
    },
    {
        "name": "Context Selection",
        "key": "context_selection",
        "description": "Prompt for selecting relevant context from tool outputs",
        "content": CONTEXT_SELECTION_SYSTEM_PROMPT,
        "editable": True,
    },
    {
        "name": "Message Summary",
        "key": "message_summary",
        "description": "Prompt for summarizing messages",
        "content": MESSAGE_SUMMARY_SYSTEM_PROMPT,
        "editable": True,
    },
    {
        "name": "Message Selection",
        "key": "message_selection",
        "description": "Prompt for selecting relevant messages from history",
        "content": MESSAGE_SELECTION_SYSTEM_PROMPT,
        "editable": True,
    },
]


class PromptsPage(QWidget):
    """Page displaying and editing prompt templates."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_dark = False
        self._current_prompt: Optional[dict] = None
        self._modified = False

        self._setup_ui()
        self._load_prompts()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # List panel
        self._list_panel = ListPanel(
            title="Prompts",
            show_search=True,
            show_add_button=False,
        )
        self._list_panel.setMinimumWidth(250)
        self._list_panel.setMaximumWidth(400)
        self._list_panel.item_selected.connect(self._on_prompt_selected)
        splitter.addWidget(self._list_panel)

        # Editor panel
        editor_widget = QWidget()
        editor_widget.setObjectName("previewPanel")
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(24, 24, 24, 24)
        editor_layout.setSpacing(16)

        # Header
        header_layout = QHBoxLayout()

        self._title_label = QLabel()
        self._title_label.setObjectName("previewTitle")
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        # Action buttons
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setObjectName("secondaryButton")
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setEnabled(False)
        header_layout.addWidget(self._reset_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setEnabled(False)
        header_layout.addWidget(self._save_btn)

        editor_layout.addLayout(header_layout)

        # Description
        self._description_label = QLabel()
        self._description_label.setObjectName("subtleText")
        self._description_label.setWordWrap(True)
        editor_layout.addWidget(self._description_label)

        # Editor
        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Select a prompt to edit...")
        self._editor.textChanged.connect(self._on_text_changed)
        editor_layout.addWidget(self._editor, 1)

        # Variables hint
        variables_label = QLabel(
            "Tip: Use {variable} syntax for placeholders that will be filled at runtime."
        )
        variables_label.setObjectName("subtleText")
        editor_layout.addWidget(variables_label)

        splitter.addWidget(editor_widget)

        # Set initial sizes (30% list, 70% editor)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

    def _load_prompts(self) -> None:
        """Load prompt templates."""
        items = []
        for prompt in PROMPT_TEMPLATES:
            items.append({
                "name": prompt["name"],
                "description": prompt["description"],
                "data": prompt,
            })

        self._list_panel.set_items(items)

    def _on_prompt_selected(self, item: dict[str, Any]) -> None:
        """Handle prompt selection."""
        if self._modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        prompt = item.get("data")
        if not prompt:
            return

        self._current_prompt = prompt
        self._title_label.setText(prompt["name"])
        self._description_label.setText(prompt["description"])
        self._editor.setPlainText(prompt["content"])
        self._editor.setReadOnly(not prompt.get("editable", False))
        self._modified = False
        self._update_buttons()

    def _on_text_changed(self) -> None:
        """Handle text changes in editor."""
        if self._current_prompt:
            current_text = self._editor.toPlainText()
            original_text = self._current_prompt["content"]
            self._modified = current_text != original_text
            self._update_buttons()

    def _update_buttons(self) -> None:
        """Update button states based on current state."""
        self._save_btn.setEnabled(self._modified)
        self._reset_btn.setEnabled(self._modified)

    def _on_reset(self) -> None:
        """Reset editor to original content."""
        if self._current_prompt:
            self._editor.setPlainText(self._current_prompt["content"])
            self._modified = False
            self._update_buttons()

    def _on_save(self) -> None:
        """Save the edited prompt."""
        if not self._current_prompt:
            return

        # TODO: Implement actual saving (to config file or database)
        # For now, just update the in-memory template
        new_content = self._editor.toPlainText()
        self._current_prompt["content"] = new_content
        self._modified = False
        self._update_buttons()

        QMessageBox.information(
            self,
            "Saved",
            f"Prompt '{self._current_prompt['name']}' has been updated.\n\n"
            "Note: Changes are stored in memory only. "
            "Restart will reset to defaults.",
        )

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update theme."""
        self._is_dark = is_dark

    def refresh(self) -> None:
        """Refresh the prompts list."""
        self._load_prompts()
