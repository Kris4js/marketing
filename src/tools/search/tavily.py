import json

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from src.tools.types import format_tool_result

load_dotenv()

tavily_client = TavilySearch(max_results=5)


class TavilySearchInput(BaseModel):
    query: str = Field(..., description="The search query to look up on the web.")


@tool(args_schema=TavilySearchInput)
async def tavily_search(query: str) -> str:
    """Search the web for current information on any topic.

    Args:
        query (str): The search query to look up on the web.
    """
    result = await tavily_client.ainvoke(query)

    parsed = json.loads(result) if isinstance(result, str) else result
    urls = [
        r.get("url") if isinstance(r, dict) and r.get("url") else ""
        for r in parsed.get("results", [])
    ]

    return format_tool_result(data=parsed, source_urls=urls)
