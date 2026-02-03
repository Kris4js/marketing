"""Settings dialog for configuring the application."""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QTabWidget,
    QWidget,
)
from PySide6.QtCore import Signal


class SettingsDialog(QDialog):
    """Settings dialog for application configuration."""

    settings_changed = Signal(dict)
    theme_changed = Signal(bool)  # True for dark, False for light

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)

        self._settings = self._load_settings()
        self._setup_ui()
        self._populate_fields()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Tab widget for different setting categories
        tabs = QTabWidget()

        # Model settings tab
        model_tab = QWidget()
        model_layout = QVBoxLayout(model_tab)

        model_group = QGroupBox("Model Configuration")
        model_form = QFormLayout(model_group)

        # Provider selection
        self._provider_combo = QComboBox()
        self._provider_combo.addItems([
            "openrouter",
            "openai",
            "anthropic",
            "azure",
        ])
        model_form.addRow("Provider:", self._provider_combo)

        # Model name
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("e.g., google/gemini-3-flash-preview")
        model_form.addRow("Model:", self._model_input)

        # Fast model (for summaries)
        self._fast_model_input = QLineEdit()
        self._fast_model_input.setPlaceholderText("Optional, defaults to main model")
        model_form.addRow("Fast Model:", self._fast_model_input)

        # Max iterations
        self._max_iterations_spin = QSpinBox()
        self._max_iterations_spin.setRange(1, 50)
        self._max_iterations_spin.setValue(10)
        model_form.addRow("Max Iterations:", self._max_iterations_spin)

        model_layout.addWidget(model_group)
        model_layout.addStretch()
        tabs.addTab(model_tab, "Model")

        # API Keys tab
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)

        api_group = QGroupBox("API Keys")
        api_form = QFormLayout(api_group)

        # OpenRouter API key
        self._openrouter_key = QLineEdit()
        self._openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openrouter_key.setPlaceholderText("sk-or-...")
        api_form.addRow("OpenRouter:", self._openrouter_key)

        # OpenAI API key
        self._openai_key = QLineEdit()
        self._openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_key.setPlaceholderText("sk-...")
        api_form.addRow("OpenAI:", self._openai_key)

        # Anthropic API key
        self._anthropic_key = QLineEdit()
        self._anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._anthropic_key.setPlaceholderText("sk-ant-...")
        api_form.addRow("Anthropic:", self._anthropic_key)

        # Tavily API key (for web search)
        self._tavily_key = QLineEdit()
        self._tavily_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._tavily_key.setPlaceholderText("tvly-...")
        api_form.addRow("Tavily:", self._tavily_key)

        api_layout.addWidget(api_group)

        # Note about API keys
        note = QLabel(
            "Note: API keys are stored in environment variables.\n"
            "Changes here will only persist for the current session."
        )
        note.setObjectName("subtleText")
        note.setWordWrap(True)
        api_layout.addWidget(note)

        api_layout.addStretch()
        tabs.addTab(api_tab, "API Keys")

        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)

        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout(theme_group)

        self._dark_mode_check = QCheckBox("Dark Mode")
        self._dark_mode_check.toggled.connect(self._on_theme_toggled)
        theme_layout.addWidget(self._dark_mode_check)

        appearance_layout.addWidget(theme_group)
        appearance_layout.addStretch()
        tabs.addTab(appearance_tab, "Appearance")

        layout.addWidget(tabs)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _load_settings(self) -> dict:
        """Load current settings from environment and defaults."""
        return {
            "provider": os.getenv("MODEL_PROVIDER", "openrouter"),
            "model": os.getenv("MODEL_NAME", "google/gemini-3-flash-preview"),
            "fast_model": os.getenv("FAST_MODEL_NAME", ""),
            "max_iterations": int(os.getenv("MAX_ITERATIONS", "10")),
            "openrouter_key": os.getenv("OPENROUTER_API_KEY", ""),
            "openai_key": os.getenv("OPENAI_API_KEY", ""),
            "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
            "tavily_key": os.getenv("TAVILY_API_KEY", ""),
            "dark_mode": os.getenv("THEME", "light") == "dark",
        }

    def _populate_fields(self) -> None:
        """Populate form fields with current settings."""
        self._provider_combo.setCurrentText(self._settings.get("provider", "openrouter"))
        self._model_input.setText(self._settings.get("model", ""))
        self._fast_model_input.setText(self._settings.get("fast_model", ""))
        self._max_iterations_spin.setValue(self._settings.get("max_iterations", 10))

        self._openrouter_key.setText(self._settings.get("openrouter_key", ""))
        self._openai_key.setText(self._settings.get("openai_key", ""))
        self._anthropic_key.setText(self._settings.get("anthropic_key", ""))
        self._tavily_key.setText(self._settings.get("tavily_key", ""))

        self._dark_mode_check.setChecked(self._settings.get("dark_mode", False))

    def _on_theme_toggled(self, is_dark: bool) -> None:
        """Handle theme toggle - apply immediately."""
        self.theme_changed.emit(is_dark)

    def _on_save(self) -> None:
        """Save settings and close dialog."""
        settings = {
            "provider": self._provider_combo.currentText(),
            "model": self._model_input.text().strip(),
            "fast_model": self._fast_model_input.text().strip(),
            "max_iterations": self._max_iterations_spin.value(),
            "openrouter_key": self._openrouter_key.text().strip(),
            "openai_key": self._openai_key.text().strip(),
            "anthropic_key": self._anthropic_key.text().strip(),
            "tavily_key": self._tavily_key.text().strip(),
            "dark_mode": self._dark_mode_check.isChecked(),
        }

        # Update environment variables
        if settings["openrouter_key"]:
            os.environ["OPENROUTER_API_KEY"] = settings["openrouter_key"]
        if settings["openai_key"]:
            os.environ["OPENAI_API_KEY"] = settings["openai_key"]
        if settings["anthropic_key"]:
            os.environ["ANTHROPIC_API_KEY"] = settings["anthropic_key"]
        if settings["tavily_key"]:
            os.environ["TAVILY_API_KEY"] = settings["tavily_key"]

        os.environ["MODEL_PROVIDER"] = settings["provider"]
        os.environ["MODEL_NAME"] = settings["model"]
        if settings["fast_model"]:
            os.environ["FAST_MODEL_NAME"] = settings["fast_model"]
        os.environ["MAX_ITERATIONS"] = str(settings["max_iterations"])
        os.environ["THEME"] = "dark" if settings["dark_mode"] else "light"

        self.settings_changed.emit(settings)
        self.accept()

    def get_settings(self) -> dict:
        """Get current settings."""
        return {
            "provider": self._provider_combo.currentText(),
            "model": self._model_input.text().strip(),
            "fast_model": self._fast_model_input.text().strip(),
            "max_iterations": self._max_iterations_spin.value(),
            "dark_mode": self._dark_mode_check.isChecked(),
        }

    def set_dark_mode(self, is_dark: bool) -> None:
        """Set dark mode state from external source."""
        self._dark_mode_check.setChecked(is_dark)
