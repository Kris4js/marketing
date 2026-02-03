"""Bridge between UI and agent backend using Qt signals."""

from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread

from src.agent.agent import Agent
from src.agent.types import (
    AgentConfig,
    AgentEvent,
    ThinkingEvent,
    ToolStartEvent,
    ToolEndEvent,
    ToolErrorEvent,
    AnswerStartEvent,
    DoneEvent,
)


class AgentWorker(QThread):
    """Worker thread for running agent queries."""

    # Signals for different event types
    thinking = Signal(str)
    tool_start = Signal(str, dict)  # tool_name, args
    tool_end = Signal(str, dict, str, int)  # tool_name, args, result, duration
    tool_error = Signal(str, str)  # tool_name, error
    answer_start = Signal()
    done = Signal(str, list, int)  # answer, tool_calls, iterations
    error = Signal(str)  # error message

    def __init__(
        self,
        agent: Agent,
        query: str,
        session_key: Optional[str] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._agent = agent
        self._query = query
        self._session_key = session_key

    def run(self) -> None:
        """Execute the agent query in a background thread."""
        import asyncio

        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(self._run_agent())
            finally:
                loop.close()

        except Exception as e:
            self.error.emit(str(e))

    async def _run_agent(self) -> None:
        """Run the agent and emit signals for each event."""
        async for event in self._agent.run(self._query, self._session_key):
            self._emit_event(event)

    def _emit_event(self, event: AgentEvent) -> None:
        """Emit the appropriate signal for an agent event."""
        if isinstance(event, ThinkingEvent):
            self.thinking.emit(event.message)

        elif isinstance(event, ToolStartEvent):
            self.tool_start.emit(event.tool, event.args)

        elif isinstance(event, ToolEndEvent):
            self.tool_end.emit(event.tool, event.args, event.result, event.duration)

        elif isinstance(event, ToolErrorEvent):
            self.tool_error.emit(event.tool, event.error)

        elif isinstance(event, AnswerStartEvent):
            self.answer_start.emit()

        elif isinstance(event, DoneEvent):
            tool_calls = [
                {"tool": tc.tool, "args": tc.args, "result": tc.result}
                for tc in event.tool_calls
            ]
            self.done.emit(event.answer, tool_calls, event.iterations)


class AgentBridge(QObject):
    """
    Bridge between the UI and the agent backend.

    Provides a Qt-friendly interface for running agent queries
    with proper signal/slot communication.
    """

    # Signals forwarded from worker
    thinking = Signal(str)
    tool_start = Signal(str, dict)
    tool_end = Signal(str, dict, str, int)
    tool_error = Signal(str, str)
    answer_start = Signal()
    done = Signal(str, list, int)
    error = Signal(str)

    # State signals
    busy_changed = Signal(bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._agent: Optional[Agent] = None
        self._worker: Optional[AgentWorker] = None
        self._session_key: Optional[str] = None
        self._is_busy = False

    def initialize(
        self,
        model: str = "google/gemini-3-flash-preview",
        model_provider: str = "openrouter",
        max_iterations: int = 10,
    ) -> None:
        """Initialize the agent with configuration."""
        config = AgentConfig(
            model=model,
            model_provider=model_provider,
            max_iterations=max_iterations,
        )
        self._agent = Agent.create(config)

    def set_session_key(self, session_key: Optional[str]) -> None:
        """Set the session key for conversation persistence."""
        self._session_key = session_key

    def run_query(self, query: str) -> bool:
        """
        Run a query through the agent.

        Returns False if already busy, True if query started.
        """
        if self._is_busy:
            return False

        if not self._agent:
            self.error.emit("Agent not initialized")
            return False

        self._set_busy(True)

        # Create and connect worker
        self._worker = AgentWorker(
            self._agent,
            query,
            self._session_key,
            parent=self,
        )

        # Connect worker signals to bridge signals
        self._worker.thinking.connect(self.thinking.emit)
        self._worker.tool_start.connect(self.tool_start.emit)
        self._worker.tool_end.connect(self.tool_end.emit)
        self._worker.tool_error.connect(self.tool_error.emit)
        self._worker.answer_start.connect(self.answer_start.emit)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)

        # Start the worker
        self._worker.start()
        return True

    def _set_busy(self, busy: bool) -> None:
        """Update busy state and emit signal."""
        if self._is_busy != busy:
            self._is_busy = busy
            self.busy_changed.emit(busy)

    def _on_done(self, answer: str, tool_calls: list, iterations: int) -> None:
        """Handle completion."""
        self.done.emit(answer, tool_calls, iterations)

    def _on_error(self, error_msg: str) -> None:
        """Handle error."""
        self.error.emit(error_msg)

    def _on_worker_finished(self) -> None:
        """Clean up after worker finishes."""
        self._set_busy(False)
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def is_busy(self) -> bool:
        """Check if the agent is currently processing."""
        return self._is_busy

    def reset_session(self) -> None:
        """Reset the current session."""
        if self._agent and self._session_key:
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._agent.reset(self._session_key))
            finally:
                loop.close()
