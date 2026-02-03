"""
Tool registry for managing and discovering available tools.

This module provides:
- RegisteredTool: A Pydantic model for tools with metadata
- get_tool_registry: Get all registered tools with descriptions
- get_tools: Get just the tool instances for LLM binding
- build_tool_descriptions: Format tool descriptions for system prompt
"""

import os
from typing import Any

from pydantic import BaseModel, Field

from src.skills import discover_skills
from src.tools.search import tavily_search
from src.tools.skill import skill_tool, SKILL_TOOL_DESCRIPTION
from src.tools.description import (
    WEB_SEARCH_DESCRIPTION,
    BROWSER_AUTOMATION_DESCRIPTION,
    FILE_READ_DESCRIPTION,
    FILE_WRITE_DESCRIPTION,
    FILE_EDIT_DESCRIPTION,
    EXEC_DESCRIPTION,
    LIST_DESCRIPTION,
    GREP_DESCRIPTION,
)
from src.tools.buildin import (
    read_tool,
    write_tool,
    edit_tool,
    exec_tool,
    list_tool,
    grep_tool,
)


class RegisteredTool(BaseModel):
    """A registered tool with its rich description for system prompt injection."""

    name: str = Field(
        ..., description="Tool name (must match the tool's name property)"
    )
    tool: Any = Field(..., description="The actual tool instance (StructuredTool)")
    description: str = Field(
        ...,
        description="Rich description for system prompt (includes when to use, when not to use, etc.)",
    )


def get_tool_registry(model: str) -> list[RegisteredTool]:
    """
    Get all registered tools with their descriptions.
    Conditionally includes tools based on environment configuration.

    Args:
        model: The model name (needed for tools that require model-specific configuration)

    Returns:
        Array of registered tools
    """
    tools: list[RegisteredTool] = []

    # ============== Built-in Tools (always available) ==============
    tools.extend(
        [
            RegisteredTool(
                name="read_tool",
                tool=read_tool,
                description=FILE_READ_DESCRIPTION,
            ),
            RegisteredTool(
                name="write_tool",
                tool=write_tool,
                description=FILE_WRITE_DESCRIPTION,
            ),
            RegisteredTool(
                name="edit_tool",
                tool=edit_tool,
                description=FILE_EDIT_DESCRIPTION,
            ),
            RegisteredTool(
                name="exec_tool",
                tool=exec_tool,
                description=EXEC_DESCRIPTION,
            ),
            RegisteredTool(
                name="list_tool",
                tool=list_tool,
                description=LIST_DESCRIPTION,
            ),
            RegisteredTool(
                name="grep_tool",
                tool=grep_tool,
                description=GREP_DESCRIPTION,
            ),
        ]
    )

    # ============== Optional Tools ==============

    # Include web_search if Exa or Tavily API key is configured (Exa preferred)
    if os.getenv("TAVILY_API_KEY"):
        tools.append(
            RegisteredTool(
                name="web_search",
                tool=tavily_search,
                description=WEB_SEARCH_DESCRIPTION,
            )
        )

    # Include browser automation tools (always available if Playwright is installed)
    try:
        from src.tools.browser import get_browser_tools

        browser_tools = get_browser_tools()
        for browser_tool in browser_tools:
            tools.append(
                RegisteredTool(
                    name=browser_tool.name,
                    tool=browser_tool,
                    description=BROWSER_AUTOMATION_DESCRIPTION,
                )
            )
    except ImportError:
        # Playwright not installed, skip browser tools
        pass

    # Include skill tool if any skills are available
    available_skills = discover_skills()
    if len(available_skills) > 0:
        tools.append(
            RegisteredTool(
                name="skill",
                tool=skill_tool,
                description=SKILL_TOOL_DESCRIPTION,
            )
        )

    return tools


def get_tools(model: str) -> list[Any]:
    """
    Get just the tool instances for binding to the LLM.

    Args:
        model: The model name

    Returns:
        Array of tool instances
    """
    return [t.tool for t in get_tool_registry(model)]


def build_tool_descriptions(model: str) -> str:
    """
    Build the tool descriptions section for the system prompt.
    Formats each tool's rich description with a header.

    Args:
        model: The model name

    Returns:
        Formatted string with all tool descriptions
    """
    return "\n\n".join(
        f"### {t.name}\n\n{t.description}" for t in get_tool_registry(model)
    )
