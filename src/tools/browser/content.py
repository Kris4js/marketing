"""
Browser content tool - extract content from page elements.
"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from src.tools.types import format_tool_result
from src.utils.logger import get_logger

logger = get_logger("browser_content")


class GetContentInput(BaseModel):
    """Input for browser_get_content tool."""

    selector: str = Field(
        ...,
        description="CSS selector for the element (e.g., 'div.content', '#main', 'article')",
    )
    attribute: Optional[str] = Field(
        None,
        description="Optional attribute to retrieve (e.g., 'href', 'src'). If not provided, returns text content.",
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional session ID (uses current session if not provided)",
    )


def _get_session_manager():
    """Get the global session manager."""
    from src.tools.browser.session import get_session_manager

    return get_session_manager()


@tool(args_schema=GetContentInput)
async def browser_get_content(
    selector: str,
    attribute: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """Get content from a specific element in the web page.

    Use this to extract text or attributes from elements identified via browser_snapshot.

    Examples:
        - Get text: selector="article"
        - Get link: selector="a.link", attribute="href"
        - Get image: selector="img", attribute="src"

    Args:
        selector: CSS selector for the element
        attribute: Optional attribute name. If None, returns text content.
        session_id: Optional session ID (uses current session if not provided)

    Returns:
        JSON string with the element's content
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

    try:
        if attribute:
            content = await session.page.get_attribute(selector, attribute)
            result = {
                "success": True,
                "selector": selector,
                "attribute": attribute,
                "content": content,
            }
        else:
            content = await session.page.inner_text(selector)
            result = {
                "success": True,
                "selector": selector,
                "content": content,
            }
    except Exception as e:
        logger.error(f"Failed to get content from {selector}: {e}")
        result = {
            "success": False,
            "error": str(e),
            "selector": selector,
        }

    return format_tool_result(data=result)
