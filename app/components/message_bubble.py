"""Chat message bubble component."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt

from app.components.markdown_viewer import MarkdownViewer


class MessageBubble(QWidget):
    """A chat message bubble widget."""

    def __init__(
        self,
        role: str,  # 'user', 'assistant', 'thinking', 'tool'
        content: str,
        tool_name: Optional[str] = None,
        duration: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._role = role
        self._content = content
        self._tool_name = tool_name
        self._duration = duration
        self._is_dark = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        # Create bubble container
        bubble = QFrame()
        bubble.setObjectName(f"{self._role}Bubble")

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        bubble_layout.setSpacing(8)

        # Style based on role
        if self._role == "user":
            bubble.setStyleSheet("""
                QFrame#userBubble {
                    background-color: #6366f1;
                    border-radius: 16px 16px 4px 16px;
                }
            """)
            layout.setAlignment(Qt.AlignmentFlag.AlignRight)

            # User messages are plain text
            content_label = QLabel(self._content)
            content_label.setWordWrap(True)
            content_label.setStyleSheet("color: #ffffff;")
            bubble_layout.addWidget(content_label)

        elif self._role == "assistant":
            bubble.setStyleSheet("""
                QFrame#assistantBubble {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 16px 16px 16px 4px;
                }
            """)
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            # Assistant messages support markdown
            content_viewer = MarkdownViewer()
            content_viewer.setStyleSheet("background: transparent; border: none;")
            content_viewer.set_markdown(self._content)
            bubble_layout.addWidget(content_viewer)

        elif self._role == "thinking":
            bubble.setStyleSheet("""
                QFrame#thinkingBubble {
                    background-color: #fef3c7;
                    border-radius: 8px;
                }
            """)
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            # Thinking indicator
            header = QHBoxLayout()
            icon_label = QLabel("🤔")
            header.addWidget(icon_label)
            thinking_label = QLabel("Thinking...")
            thinking_label.setStyleSheet("color: #92400e; font-style: italic;")
            header.addWidget(thinking_label)
            header.addStretch()
            bubble_layout.addLayout(header)

            if self._content:
                content_label = QLabel(self._content)
                content_label.setWordWrap(True)
                content_label.setStyleSheet("color: #92400e;")
                bubble_layout.addWidget(content_label)

        elif self._role == "tool":
            bubble.setStyleSheet("""
                QFrame#toolBubble {
                    background-color: #ecfdf5;
                    border-radius: 8px;
                }
            """)
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            # Tool header with name and duration
            header = QHBoxLayout()
            icon_label = QLabel("🔧")
            header.addWidget(icon_label)

            tool_label = QLabel(f"Using: {self._tool_name or 'tool'}")
            tool_label.setStyleSheet("color: #065f46; font-weight: 500;")
            header.addWidget(tool_label)

            if self._duration is not None:
                duration_label = QLabel(f"({self._duration}ms)")
                duration_label.setStyleSheet("color: #059669; font-size: 12px;")
                header.addWidget(duration_label)

            header.addStretch()
            bubble_layout.addLayout(header)

            # Tool result (truncated)
            if self._content:
                display_content = self._content
                if len(display_content) > 200:
                    display_content = display_content[:200] + "..."

                content_label = QLabel(display_content)
                content_label.setWordWrap(True)
                content_label.setStyleSheet(
                    "color: #065f46; font-family: monospace; font-size: 12px;"
                )
                bubble_layout.addWidget(content_label)

        elif self._role == "tool_error":
            bubble.setStyleSheet("""
                QFrame#tool_errorBubble {
                    background-color: #fef2f2;
                    border-radius: 8px;
                }
            """)
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            header = QHBoxLayout()
            icon_label = QLabel("❌")
            header.addWidget(icon_label)

            error_label = QLabel(f"Error in: {self._tool_name or 'tool'}")
            error_label.setStyleSheet("color: #dc2626; font-weight: 500;")
            header.addWidget(error_label)
            header.addStretch()
            bubble_layout.addLayout(header)

            if self._content:
                content_label = QLabel(self._content)
                content_label.setWordWrap(True)
                content_label.setStyleSheet("color: #dc2626;")
                bubble_layout.addWidget(content_label)

        layout.addWidget(bubble)

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update theme for the message bubble."""
        self._is_dark = is_dark
        # Re-apply styles for dark theme
        bubble = self.findChild(QFrame)
        if not bubble:
            return

        if self._role == "user":
            bubble.setStyleSheet("""
                QFrame#userBubble {
                    background-color: #6366f1;
                    border-radius: 16px 16px 4px 16px;
                }
            """)

        elif self._role == "assistant":
            if is_dark:
                bubble.setStyleSheet("""
                    QFrame#assistantBubble {
                        background-color: #1e1e2e;
                        border: 1px solid #2d2d44;
                        border-radius: 16px 16px 16px 4px;
                    }
                """)
            else:
                bubble.setStyleSheet("""
                    QFrame#assistantBubble {
                        background-color: #f8fafc;
                        border: 1px solid #e2e8f0;
                        border-radius: 16px 16px 16px 4px;
                    }
                """)

        elif self._role == "thinking":
            if is_dark:
                bubble.setStyleSheet("""
                    QFrame#thinkingBubble {
                        background-color: #422006;
                        border-radius: 8px;
                    }
                """)
            else:
                bubble.setStyleSheet("""
                    QFrame#thinkingBubble {
                        background-color: #fef3c7;
                        border-radius: 8px;
                    }
                """)

        elif self._role == "tool":
            if is_dark:
                bubble.setStyleSheet("""
                    QFrame#toolBubble {
                        background-color: #064e3b;
                        border-radius: 8px;
                    }
                """)
            else:
                bubble.setStyleSheet("""
                    QFrame#toolBubble {
                        background-color: #ecfdf5;
                        border-radius: 8px;
                    }
                """)
