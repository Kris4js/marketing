"""
Browser navigation tool.
"""

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from src.tools.types import format_tool_result


class NavigateInput(BaseModel):
    """Input for browser_navigate tool."""

    url: str = Field(..., description="The URL to navigate to")
    wait_until: str = Field(
        "load",
        description="When to consider navigation succeeded: 'load', 'domcontentloaded', 'networkidle'",
    )


def _get_session_manager():
    """Get the global session manager."""
    from src.tools.browser.session import get_session_manager

    return get_session_manager()


@tool(args_schema=NavigateInput)
async def browser_navigate(url: str, wait_until: str = "load") -> str:
    """Navigate to a URL in the browser.

    Use this tool to open a webpage. Returns the page title and URL after navigation.

    Args:
        url: The URL to navigate to
        wait_until: When to consider navigation succeeded

    Returns:
        JSON string with navigation result including page title and URL
    """
    manager = _get_session_manager()
    session = await manager.create_session()

    result = await session.navigate(url, wait_until=wait_until)
    return format_tool_result(
        data=result,
        source_urls=[url] if result.get("success") else None,
    )
