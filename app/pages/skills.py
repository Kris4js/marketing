"""Skills page - displays registered skills with markdown preview."""

from typing import Optional, Any
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter
from PySide6.QtCore import Qt

from app.components.list_panel import ListPanel
from app.components.preview_panel import PreviewPanel

from src.skills.registry import discover_skills, get_skill
from src.skills.types import SkillMetadata, SkillSource


class SkillsPage(QWidget):
    """Page displaying all registered skills."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._skills: list[SkillMetadata] = []
        self._is_dark = False

        self._setup_ui()
        self._load_skills()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # List panel
        self._list_panel = ListPanel(
            title="Skills",
            show_search=True,
            show_add_button=True,
        )
        self._list_panel.setMinimumWidth(250)
        self._list_panel.setMaximumWidth(400)
        self._list_panel.item_selected.connect(self._on_skill_selected)
        self._list_panel.add_clicked.connect(self._on_add_skill)
        splitter.addWidget(self._list_panel)

        # Preview panel
        self._preview_panel = PreviewPanel()
        self._preview_panel.action_clicked.connect(self._on_action_clicked)
        splitter.addWidget(self._preview_panel)

        # Set initial sizes (30% list, 70% preview)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

    def _load_skills(self) -> None:
        """Load skills from the registry."""
        try:
            self._skills = discover_skills()

            # Convert to list panel format
            items = []
            for skill in self._skills:
                # Determine badge based on source
                badge_type = ""
                if skill.source == SkillSource.BUILTIN:
                    badge_type = "builtin"
                elif skill.source == SkillSource.USER:
                    badge_type = "user"
                elif skill.source == SkillSource.PROJECT:
                    badge_type = "project"

                items.append({
                    "name": skill.name,
                    "description": skill.description,
                    "badge": skill.source.value,
                    "badge_type": badge_type,
                    "data": skill,
                })

            self._list_panel.set_items(items)

        except Exception as e:
            print(f"Error loading skills: {e}")

    def _on_skill_selected(self, item: dict[str, Any]) -> None:
        """Handle skill selection."""
        skill_meta: SkillMetadata = item.get("data")
        if not skill_meta:
            return

        # Load full skill with instructions
        full_skill = get_skill(skill_meta.name)
        if not full_skill:
            return

        # Determine badge
        badge_type = ""
        if skill_meta.source == SkillSource.BUILTIN:
            badge_type = "builtin"
        elif skill_meta.source == SkillSource.USER:
            badge_type = "user"
        elif skill_meta.source == SkillSource.PROJECT:
            badge_type = "project"

        # Build actions based on source
        actions = []
        if skill_meta.source != SkillSource.BUILTIN:
            actions.append({"name": "edit", "label": "Edit", "icon": "fa5s.edit"})

        self._preview_panel.set_item({
            "name": full_skill.name,
            "description": full_skill.description,
            "content": full_skill.instructions,
            "badge": skill_meta.source.value,
            "badge_type": badge_type,
            "actions": actions,
        })

    def _on_add_skill(self) -> None:
        """Handle add skill button click."""
        # TODO: Implement skill creation dialog
        print("Add skill clicked")

    def _on_action_clicked(self, action: str, item: Optional[dict]) -> None:
        """Handle action button clicks."""
        if action == "edit" and item:
            # TODO: Implement skill editing
            print(f"Editing skill: {item.get('name')}")

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update theme."""
        self._is_dark = is_dark
        self._preview_panel.set_dark_theme(is_dark)

    def refresh(self) -> None:
        """Refresh the skills list."""
        # Clear cache to get fresh data
        from src.skills.registry import clear_skill_cache

        clear_skill_cache()
        self._load_skills()
