"""Chat page - main chat interface with agent integration."""

import uuid
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLineEdit,
    QPushButton,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

from app.components.message_bubble import MessageBubble
from app.bridge.agent_bridge import AgentBridge


class ChatPage(QWidget):
    """Main chat interface page."""

    new_chat_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_dark = False
        self._messages: list[MessageBubble] = []
        self._session_key = str(uuid.uuid4())

        # Agent bridge
        self._agent_bridge = AgentBridge(self)
        self._agent_bridge.initialize()
        self._agent_bridge.set_session_key(self._session_key)

        # Connect agent signals
        self._agent_bridge.thinking.connect(self._on_thinking)
        self._agent_bridge.tool_start.connect(self._on_tool_start)
        self._agent_bridge.tool_end.connect(self._on_tool_end)
        self._agent_bridge.tool_error.connect(self._on_tool_error)
        self._agent_bridge.answer_start.connect(self._on_answer_start)
        self._agent_bridge.done.connect(self._on_done)
        self._agent_bridge.error.connect(self._on_error)
        self._agent_bridge.busy_changed.connect(self._on_busy_changed)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Chat header
        header = QFrame()
        header.setObjectName("chatHeader")
        header.setStyleSheet("""
            QFrame#chatHeader {
                background-color: #ffffff;
                border-bottom: 1px solid #e2e8f0;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Chat")
        title.setObjectName("sectionTitle")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # New chat button
        new_chat_btn = QPushButton()
        new_chat_btn.setObjectName("iconButton")
        new_chat_btn.setIcon(qta.icon("fa5s.plus"))
        new_chat_btn.setToolTip("New chat")
        new_chat_btn.clicked.connect(self._on_new_chat)
        header_layout.addWidget(new_chat_btn)

        layout.addWidget(header)

        # Messages area
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("messageArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Container for messages
        self._messages_container = QWidget()
        self._messages_container.setObjectName("chatContainer")
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(16, 16, 16, 16)
        self._messages_layout.setSpacing(8)
        self._messages_layout.addStretch()

        self._scroll_area.setWidget(self._messages_container)
        layout.addWidget(self._scroll_area, 1)

        # Input area
        input_container = QFrame()
        input_container.setObjectName("inputContainer")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(16, 16, 16, 16)
        input_layout.setSpacing(12)

        self._input_field = QLineEdit()
        self._input_field.setObjectName("messageInput")
        self._input_field.setPlaceholderText("Type your message...")
        self._input_field.returnPressed.connect(self._on_send)
        input_layout.addWidget(self._input_field, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setIcon(qta.icon("fa5s.paper-plane"))
        self._send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self._send_btn)

        layout.addWidget(input_container)

        # Show welcome message
        self._show_welcome()

    def _show_welcome(self) -> None:
        """Show welcome message."""
        welcome = QLabel(
            "Welcome to Wild Goose Agent!\n\n"
            "Type a message below to start chatting."
        )
        welcome.setObjectName("subtleText")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setWordWrap(True)

        # Insert before the stretch
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, welcome
        )
        self._welcome_label = welcome

    def _add_message(
        self,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        duration: Optional[int] = None,
    ) -> MessageBubble:
        """Add a message bubble to the chat."""
        # Remove welcome message on first real message
        if hasattr(self, "_welcome_label") and self._welcome_label:
            self._welcome_label.deleteLater()
            self._welcome_label = None

        bubble = MessageBubble(
            role=role,
            content=content,
            tool_name=tool_name,
            duration=duration,
        )
        bubble.set_dark_theme(self._is_dark)

        # Insert before the stretch
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, bubble
        )
        self._messages.append(bubble)

        # Scroll to bottom
        self._scroll_to_bottom()

        return bubble

    def _scroll_to_bottom(self) -> None:
        """Scroll the message area to the bottom."""
        # Use a timer to ensure layout is updated
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, lambda: self._scroll_area.verticalScrollBar().setValue(
            self._scroll_area.verticalScrollBar().maximum()
        ))

    def _on_send(self) -> None:
        """Handle send button click."""
        text = self._input_field.text().strip()
        if not text:
            return

        # Clear input
        self._input_field.clear()

        # Add user message
        self._add_message("user", text)

        # Run query
        if not self._agent_bridge.run_query(text):
            self._add_message(
                "tool_error",
                "Agent is busy. Please wait for the current query to complete.",
                tool_name="system",
            )

    def _on_thinking(self, message: str) -> None:
        """Handle thinking event."""
        self._add_message("thinking", message)

    def _on_tool_start(self, tool_name: str, args: dict) -> None:
        """Handle tool start event."""
        args_str = ", ".join(f"{k}={v}" for k, v in list(args.items())[:2])
        self._add_message(
            "tool",
            f"Starting: {tool_name}({args_str})" if args_str else f"Starting: {tool_name}",
            tool_name=tool_name,
        )

    def _on_tool_end(
        self, tool_name: str, args: dict, result: str, duration: int
    ) -> None:
        """Handle tool end event."""
        # Show truncated result
        display_result = result[:300] + "..." if len(result) > 300 else result
        self._add_message(
            "tool",
            display_result,
            tool_name=tool_name,
            duration=duration,
        )

    def _on_tool_error(self, tool_name: str, error: str) -> None:
        """Handle tool error event."""
        self._add_message("tool_error", error, tool_name=tool_name)

    def _on_answer_start(self) -> None:
        """Handle answer start event."""
        # Could show a typing indicator here
        pass

    def _on_done(self, answer: str, tool_calls: list, iterations: int) -> None:
        """Handle completion event."""
        self._add_message("assistant", answer)

    def _on_error(self, error_msg: str) -> None:
        """Handle error event."""
        self._add_message("tool_error", f"Error: {error_msg}", tool_name="system")

    def _on_busy_changed(self, is_busy: bool) -> None:
        """Handle busy state change."""
        self._input_field.setEnabled(not is_busy)
        self._send_btn.setEnabled(not is_busy)

        if is_busy:
            self._send_btn.setText("Processing...")
        else:
            self._send_btn.setText("Send")

    def _on_new_chat(self) -> None:
        """Handle new chat button click."""
        # Clear messages
        for bubble in self._messages:
            bubble.deleteLater()
        self._messages.clear()

        # Generate new session key
        self._session_key = str(uuid.uuid4())
        self._agent_bridge.set_session_key(self._session_key)

        # Reset the agent session
        self._agent_bridge.reset_session()

        # Show welcome again
        self._show_welcome()

        self.new_chat_requested.emit()

    def set_dark_theme(self, is_dark: bool) -> None:
        """Update theme."""
        self._is_dark = is_dark

        # Update existing messages
        for bubble in self._messages:
            bubble.set_dark_theme(is_dark)

        # Update container styles
        if is_dark:
            self._messages_container.setStyleSheet("""
                QWidget#chatContainer { background-color: #161625; }
            """)
            self.findChild(QFrame, "chatHeader").setStyleSheet("""
                QFrame#chatHeader {
                    background-color: #0f0f1a;
                    border-bottom: 1px solid #1e293b;
                }
            """)
        else:
            self._messages_container.setStyleSheet("""
                QWidget#chatContainer { background-color: #f8fafc; }
            """)
            self.findChild(QFrame, "chatHeader").setStyleSheet("""
                QFrame#chatHeader {
                    background-color: #ffffff;
                    border-bottom: 1px solid #e2e8f0;
                }
            """)

    def set_model(self, model: str, provider: str) -> None:
        """Update the model configuration."""
        self._agent_bridge.initialize(model=model, model_provider=provider)
        self._agent_bridge.set_session_key(self._session_key)
