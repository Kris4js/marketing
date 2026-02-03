"""
Browser automation tools.

Tools:
- browser_navigate: Navigate to a URL
- browser_snapshot: Capture page structure
- browser_get_content: Extract content from elements
"""

from src.tools.browser.navigate import browser_navigate
from src.tools.browser.snapshot import browser_snapshot
from src.tools.browser.content import browser_get_content
from src.tools.browser.session import BrowserSessionManager


def get_browser_tools() -> list:
    """Get all browser tools."""
    return [
        browser_navigate,
        browser_snapshot,
        browser_get_content,
    ]


__all__ = [
    "browser_navigate",
    "browser_snapshot",
    "browser_get_content",
    "get_browser_tools",
    "BrowserSessionManager",
]
