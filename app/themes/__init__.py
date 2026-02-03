"""Theme management for the application."""

from pathlib import Path

THEMES_DIR = Path(__file__).parent


def load_theme(theme_name: str) -> str:
    """Load a QSS theme file by name."""
    theme_file = THEMES_DIR / f"{theme_name}.qss"
    if theme_file.exists():
        return theme_file.read_text()
    return ""


def get_available_themes() -> list[str]:
    """Get list of available theme names."""
    return [f.stem for f in THEMES_DIR.glob("*.qss")]
