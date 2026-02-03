"""Markdown rendering widget using QTextBrowser."""

import markdown
from PySide6.QtWidgets import QTextBrowser
from PySide6.QtCore import Qt


class MarkdownViewer(QTextBrowser):
    """A widget that renders markdown content as HTML."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )

        # Configure markdown processor with extensions
        self._md = markdown.Markdown(
            extensions=[
                "fenced_code",
                "tables",
                "nl2br",
                "sane_lists",
            ]
        )

        # Base CSS for markdown rendering
        self._base_css = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 14px;
                line-height: 1.6;
                padding: 0;
                margin: 0;
            }
            h1 { font-size: 1.5em; font-weight: 600; margin: 0.5em 0; }
            h2 { font-size: 1.25em; font-weight: 600; margin: 0.5em 0; }
            h3 { font-size: 1.1em; font-weight: 600; margin: 0.5em 0; }
            p { margin: 0.5em 0; }
            code {
                font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
                font-size: 0.9em;
                padding: 2px 6px;
                border-radius: 4px;
            }
            pre {
                padding: 12px;
                border-radius: 8px;
                overflow-x: auto;
                font-size: 0.9em;
            }
            pre code {
                padding: 0;
                background: none;
            }
            ul, ol {
                margin: 0.5em 0;
                padding-left: 1.5em;
            }
            li { margin: 0.25em 0; }
            blockquote {
                margin: 0.5em 0;
                padding-left: 1em;
                border-left: 3px solid #6366f1;
                color: #64748b;
            }
            table {
                border-collapse: collapse;
                margin: 0.5em 0;
            }
            th, td {
                border: 1px solid #e2e8f0;
                padding: 8px 12px;
                text-align: left;
            }
            th {
                font-weight: 600;
            }
            a { color: #6366f1; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
        """

        self._light_theme_css = """
        <style>
            body { color: #1a1a2e; }
            code { background-color: #f1f5f9; }
            pre { background-color: #f8fafc; border: 1px solid #e2e8f0; }
            th { background-color: #f8fafc; }
        </style>
        """

        self._dark_theme_css = """
        <style>
            body { color: #e2e8f0; }
            code { background-color: #1e1e2e; }
            pre { background-color: #1e1e2e; border: 1px solid #2d2d44; }
            th { background-color: #1e1e2e; }
            th, td { border-color: #2d2d44; }
            blockquote { color: #94a3b8; }
        </style>
        """

        self._is_dark = False

    def set_markdown(self, text: str) -> None:
        """Set markdown content to display."""
        if not text:
            self.setHtml("")
            return

        # Reset markdown processor state
        self._md.reset()

        # Convert markdown to HTML
        html_content = self._md.convert(text)

        # Combine CSS and content
        theme_css = self._dark_theme_css if self._is_dark else self._light_theme_css
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            {self._base_css}
            {theme_css}
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        self.setHtml(full_html)

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update the theme for markdown rendering."""
        self._is_dark = is_dark
        # Re-render current content with new theme
        current = self.toPlainText()
        if current:
            self.set_markdown(current)

    def clear_content(self) -> None:
        """Clear the viewer content."""
        self.setHtml("")
