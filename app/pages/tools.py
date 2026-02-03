"""Tools page - displays registered tools with preview."""

from typing import Optional, Any
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter
from PySide6.QtCore import Qt

from app.components.list_panel import ListPanel
from app.components.preview_panel import PreviewPanel

from src.tools.registry import get_tool_registry, RegisteredTool


class ToolsPage(QWidget):
    """Page displaying all registered tools."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tools: list[RegisteredTool] = []
        self._is_dark = False

        self._setup_ui()
        self._load_tools()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # List panel
        self._list_panel = ListPanel(
            title="Tools",
            show_search=True,
            show_add_button=False,
        )
        self._list_panel.setMinimumWidth(250)
        self._list_panel.setMaximumWidth(400)
        self._list_panel.item_selected.connect(self._on_tool_selected)
        splitter.addWidget(self._list_panel)

        # Preview panel
        self._preview_panel = PreviewPanel()
        self._preview_panel.action_clicked.connect(self._on_action_clicked)
        splitter.addWidget(self._preview_panel)

        # Set initial sizes (30% list, 70% preview)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

    def _load_tools(self) -> None:
        """Load tools from the registry."""
        try:
            # Use a default model for getting the registry
            self._tools = get_tool_registry("google/gemini-3-flash-preview")

            # Convert to list panel format
            items = []
            for tool in self._tools:
                # Extract first line of description for preview
                desc_lines = tool.description.strip().split("\n")
                short_desc = desc_lines[0] if desc_lines else ""

                items.append({
                    "name": tool.name,
                    "description": short_desc,
                    "data": tool,
                })

            self._list_panel.set_items(items)

        except Exception as e:
            print(f"Error loading tools: {e}")

    def _on_tool_selected(self, item: dict[str, Any]) -> None:
        """Handle tool selection."""
        tool: RegisteredTool = item.get("data")
        if not tool:
            return

        # Get tool parameters if available
        params_section = ""
        if hasattr(tool.tool, "args_schema") and tool.tool.args_schema:
            schema = tool.tool.args_schema.schema()
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            if properties:
                params_lines = ["## Parameters\n"]
                for name, prop in properties.items():
                    prop_type = prop.get("type", "any")
                    prop_desc = prop.get("description", "")
                    is_required = name in required
                    req_marker = " (required)" if is_required else " (optional)"

                    params_lines.append(f"- **{name}**: `{prop_type}`{req_marker}")
                    if prop_desc:
                        params_lines.append(f"  - {prop_desc}")

                params_section = "\n".join(params_lines)

        # Build preview content
        content = f"{tool.description}"
        if params_section:
            content += f"\n\n{params_section}"

        self._preview_panel.set_item({
            "name": tool.name,
            "description": f"Tool for {tool.name.replace('_', ' ')}",
            "content": content,
            "actions": [
                {"name": "test", "label": "Test", "icon": "fa5s.play"},
            ],
        })

    def _on_action_clicked(self, action: str, item: Optional[dict]) -> None:
        """Handle action button clicks."""
        if action == "test" and item:
            # TODO: Implement tool testing dialog
            print(f"Testing tool: {item.get('name')}")

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update theme."""
        self._is_dark = is_dark
        self._preview_panel.set_dark_theme(is_dark)

    def refresh(self) -> None:
        """Refresh the tools list."""
        self._load_tools()
