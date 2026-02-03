"""
Type definitions for the Agent system.

Includes:
- AgentEvent types for real-time UI updates
- AgentConfig for agent configuration
- ToolCallRecord for tracking tool calls
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Literal
from pydantic import BaseModel


# ============================================================================
# Agent Configuration
# ============================================================================


class AgentConfig(BaseModel):
    """Configuration options for the Agent."""

    model: str = "google/gemini-3-flash-preview"
    model_provider: str = "openrouter"
    fast_model: Optional[str] = None  # For tool summaries, defaults to model
    max_iterations: int = 10


# ============================================================================
# Tool Call Records
# ============================================================================


@dataclass
class ToolCallRecord:
    """Record of a tool call for external consumers."""

    tool: str
    args: dict[str, Any]
    result: str


# ============================================================================
# Agent Events (for async generator yielding)
# ============================================================================


@dataclass
class ThinkingEvent:
    """Emitted when the agent has thinking/reasoning text."""

    type: Literal["thinking"] = "thinking"
    message: str = ""


@dataclass
class ToolStartEvent:
    """Emitted when a tool execution starts."""

    type: Literal["tool_start"] = "tool_start"
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolEndEvent:
    """Emitted when a tool execution completes successfully."""

    type: Literal["tool_end"] = "tool_end"
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    duration: int = 0  # milliseconds


@dataclass
class ToolErrorEvent:
    """Emitted when a tool execution fails."""

    type: Literal["tool_error"] = "tool_error"
    tool: str = ""
    error: str = ""


@dataclass
class ToolLimitEvent:
    """Emitted when a tool is approaching or over its call limit."""

    type: Literal["tool_limit"] = "tool_limit"
    tool: str = ""
    warning: str = ""
    blocked: bool = False


@dataclass
class AnswerStartEvent:
    """Emitted when the agent starts generating the final answer."""

    type: Literal["answer_start"] = "answer_start"


@dataclass
class DoneEvent:
    """Emitted when the agent has completed its work."""

    type: Literal["done"] = "done"
    answer: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 0


# Union type for all events
AgentEvent = (
    ThinkingEvent
    | ToolStartEvent
    | ToolEndEvent
    | ToolErrorEvent
    | ToolLimitEvent
    | AnswerStartEvent
    | DoneEvent
)
