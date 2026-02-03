"""
Browser snapshot tool - capture page structure and elements.
"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from src.tools.types import format_tool_result


class SnapshotInput(BaseModel):
    """Input for browser_snapshot tool."""

    session_id: Optional[str] = Field(
        None,
        description="Optional session ID (uses current session if not provided)",
    )


def _get_session_manager():
    """Get the global session manager."""
    from src.tools.browser.session import get_session_manager

    return get_session_manager()


@tool(args_schema=SnapshotInput)
async def browser_snapshot(session_id: Optional[str] = None) -> str:
    """Recognize and get all elements in the current web page.

    Returns the page structure with accessibility information, including all interactive elements.
    Use this to understand what's on the page before getting content from specific elements.

    Args:
        session_id: Optional session ID (uses current session if not provided)

    Returns:
        JSON string with page structure showing all recognized elements
    """
    manager = _get_session_manager()

    # Try specified session, or fall back to current session
    session = None
    if session_id:
        session = await manager.get_session(session_id)
    if not session:
        session = await manager.get_current_session()

    if not session:
        return format_tool_result(
            data={
                "success": False,
                "error": "No active session. Navigate to a URL first.",
            }
        )

    result = await session.snapshot()
    return format_tool_result(data=result)
