"""
Type definitions and utility functions for tool execution results.

This module provides:
- ToolResult: A Pydantic model for structured tool outputs
- format_tool_result: Serializes tool results to JSON strings
- parse_search_results: Parses and normalizes search provider responses,
  extracting URLs from multiple response formats (Exa, Tavily, etc.)
"""

import json

from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    data: Any = Field(..., description="The result data from the tool execution.")
    source_urls: Optional[list[str]] = Field(
        None,
        description="Optional list of source URLs related to the result.",
    )


def format_tool_result(data: Any, source_urls: Optional[list[str]] = None) -> str:
    """Format tool result as JSON string."""
    result: ToolResult = ToolResult(data=data, source_urls=source_urls)
    return result.model_dump_json()


def parse_search_results(result: Any) -> dict[str, Any]:
    """
    Parse search results from a search provider response.
    Handles both string and object responses, extracting URLs from results.
    Supports multiple response shapes from different providers.

    Args:
        result: The raw result from a search provider

    Returns:
        A dict with 'parsed' (the parsed result) and 'urls' (list of extracted URLs)
    """
    # Safely parse JSON strings
    if isinstance(result, str):
        try:
            parsed: Any = json.loads(result)
        except json.JSONDecodeError:
            # If parsing fails, treat the string as the result itself
            parsed = result
    else:
        parsed = result

    # Extract URLs from multiple possible response shapes
    urls: list[str] = []

    # Shape 1: { results: [{ url: string }] } (Exa format)
    if isinstance(parsed, dict) and "results" in parsed:
        results = parsed.get("results")
        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict) and "url" in r:
                    url = r.get("url")
                    if isinstance(url, str) and url:
                        urls.append(url)
    # Shape 2: [{ url: string }] (direct array, Tavily format)
    elif isinstance(parsed, list):
        for r in parsed:
            if isinstance(r, dict) and "url" in r:
                url = r.get("url")
                if isinstance(url, str) and url:
                    urls.append(url)

    return {
        "parsed": parsed,
        "urls": urls,
    }
