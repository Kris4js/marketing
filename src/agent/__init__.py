"""
Agent module - Generic agent framework with persistence.

Core components:
- Agent: Main agent class with tool execution loop
- Scratchpad: In-memory state management for agent work
- Types: Event types for UI updates
- Prompts: Customization layer (swap for different agent types)

Integrated utilities (from src.utils):
- SessionManager: Conversation persistence (JSONL)
- ToolContextManager: Tool result disk persistence
- MemoryManager: Long-term memory with keyword search
- Logger: Structured logging with loguru

Usage:
    from src.agent import Agent, AgentConfig

    agent = Agent.create(AgentConfig(model="your-model"))
    async for event in agent.run("Your query", session_key="user123"):
        print(event)
"""

from src.agent.agent import Agent
from src.agent.scratchpad import Scratchpad
from src.agent.types import (
    AgentConfig,
    AgentEvent,
    ThinkingEvent,
    ToolStartEvent,
    ToolEndEvent,
    ToolErrorEvent,
    ToolLimitEvent,
    AnswerStartEvent,
    DoneEvent,
    ToolCallRecord,
)

__all__ = [
    "Agent",
    "AgentConfig",
    "Scratchpad",
    "AgentEvent",
    "ThinkingEvent",
    "ToolStartEvent",
    "ToolEndEvent",
    "ToolErrorEvent",
    "ToolLimitEvent",
    "AnswerStartEvent",
    "DoneEvent",
    "ToolCallRecord",
]
