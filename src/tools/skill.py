"""
Skill tool for executing specialized instructions.

This module provides:
- SKILL_TOOL_DESCRIPTION: Rich description for system prompt
- skill_tool: LangChain tool for invoking skills
"""

from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.skills import discover_skills, get_skill


SKILL_TOOL_DESCRIPTION: str = """
Execute a skill to get specialized instructions for complex tasks.

## When to Use

- When the user's query matches an available skill's description
- For complex workflows that benefit from structured guidance (e.g., DCF valuation, financial reports)
- When you need step-by-step instructions for a specialized task

## When NOT to Use

- For simple queries that don't require specialized workflows
- When no available skill matches the task
- If you've already invoked the skill for this query (don't invoke twice)

## Usage Notes

- Invoke the skill IMMEDIATELY when relevant, as your first action
- The skill returns instructions that you should follow to complete the task
- Use the skill name exactly as listed in Available Skills
- Pass any relevant arguments (like ticker symbols) via the args parameter
""".strip()


class SkillToolInput(BaseModel):
    """Input schema for the skill tool."""

    skill: str = Field(..., description='Name of the skill to invoke (e.g., "dcf")')
    args: Optional[str] = Field(
        None,
        description="Optional arguments for the skill (e.g., ticker symbol)",
    )


@tool(args_schema=SkillToolInput)
def skill_tool(skill: str, args: Optional[str] = None) -> str:
    """
    Execute a skill and return its instructions.

    Args:
        skill: Name of the skill to invoke
        args: Optional arguments for the skill

    Returns:
        Formatted skill instructions
    """
    skill_def = get_skill(skill)

    if not skill_def:
        available = ", ".join(s.name for s in discover_skills())
        return (
            f'Error: Skill "{skill}" not found. Available skills: {available or "none"}'
        )

    # Return instructions with optional args context
    result = f"## Skill: {skill_def.name}\n\n"

    if args:
        result += f"**Arguments provided:** {args}\n\n"

    result += skill_def.instructions

    return result
