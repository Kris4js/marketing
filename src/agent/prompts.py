"""
Prompts for the Agent system.

This is the customization layer - swap this file to create different agent types.
The agent core (agent.py, scratchpad.py) remains unchanged.

To create a specialized agent:
1. Copy this file
2. Customize SYSTEM_PROMPT for your agent's personality
3. Adjust other prompts as needed
"""

from typing import Optional, Any


# ============================================================================
# System Prompt - Define your agent's personality here
# ============================================================================

SYSTEM_PROMPT = """You are a helpful assistant with access to tools.

## Tool Usage Guidelines

1. **Use tools efficiently**: Call tools only when you genuinely need information you don't have
2. **Do NOT repeat tool calls**: If you've already called a tool with the same parameters, do NOT call it again
3. **Stop when you have enough data**: Once a tool returns relevant information, proceed to answer the user
4. **No tool needed for simple questions**: If you can answer from your knowledge, respond directly

## Warning Messages Matter

When you receive a warning about tool usage limits:
- STOP calling that tool
- Work with the data you already have
- Acknowledge any limitations to the user

## Good Answer = Useful, Not Perfect

You don't need perfect information to help. Answer with what you have, and note any gaps.
"""


# ============================================================================
# Iteration Prompt - Shows progress during the agent loop
# ============================================================================


def build_iteration_prompt(
    query: str,
    tool_summaries: list[str],
    tool_usage_status: Optional[str] = None,
) -> str:
    """Build prompt for each iteration with gathered data."""

    summaries_text = ""
    if tool_summaries:
        summaries_text = "\n\nData gathered:\n" + "\n".join(
            f"- {s}" for s in tool_summaries
        )

    usage_text = f"\n\n{tool_usage_status}" if tool_usage_status else ""

    return f"""Query: {query}{summaries_text}{usage_text}

Do you have enough information to answer? If yes, provide your answer. If not, use tools to gather more data."""


# ============================================================================
# Final Answer Prompt - For synthesizing the response
# ============================================================================


def build_final_answer_prompt(query: str, full_context: str) -> str:
    """Build prompt for generating the final answer."""

    return f"""Query: {query}

Gathered data:
{full_context}

Provide a comprehensive answer based on the data above."""


# ============================================================================
# Tool Summary Prompt - For compressing tool results
# ============================================================================


def build_tool_summary_prompt(
    query: str,
    tool_name: str,
    tool_args: dict[str, Any],
    result: str,
) -> str:
    """Build prompt for summarizing a tool result."""

    return f"""Summarize this tool result in 1-2 sentences. Focus on information relevant to: {query}

Tool: {tool_name}
Result: {result[:3000]}

Summary:"""


# ============================================================================
# Context Selection Prompt - When over token budget
# ============================================================================


def build_context_selection_prompt(
    query: str,
    summaries: list[dict[str, Any]],
) -> str:
    """Build prompt for selecting relevant contexts."""

    items = "\n".join(
        f"[{s['index']}] {s['tool_name']}: {s['summary']}" for s in summaries
    )

    return f"""Query: {query}

Available data:
{items}

Return JSON array of indices most relevant to the query. Example: [0, 2]"""


# ============================================================================
# Helper
# ============================================================================


def get_tool_description(tool_name: str, args: dict[str, Any]) -> str:
    """Generate human-readable tool call description."""
    args_str = ", ".join(f"{k}={v}" for k, v in list(args.items())[:2])
    return f"{tool_name}({args_str})" if args_str else tool_name


# ============================================================================
# Legacy Prompts (for backward compatibility with utils)
# ============================================================================

CONTEXT_SELECTION_SYSTEM_PROMPT = """You are a context selection assistant.
Your job is to identify which tool outputs are relevant for answering a user's query.

Return a JSON object with a "context_ids" field containing a list of IDs (0-indexed) of relevant outputs.

Return format:
{"context_ids": [0, 2, 5]}
"""

MESSAGE_SUMMARY_SYSTEM_PROMPT = """You are a summarization assistant.
Create a brief, informative summary of an answer (1-2 sentences max).
"""

MESSAGE_SELECTION_SYSTEM_PROMPT = """You are a message selection assistant.
Identify which previous conversation turns are relevant to the current query.

Return format:
{"message_ids": [0, 2]}
"""
