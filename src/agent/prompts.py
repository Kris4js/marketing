from datetime import datetime
from typing import Optional

# ======================================================================
# Helper Time Function
# ======================================================================


def get_current_time() -> str:
    """Returns the current data formatted for prompts.

    Returns:
        str: such as 'Thursday, January 22, 2026'
    """
    return datetime.now().strftime("%A, %B %d, %Y")


# ======================================================================
# Default System Prompts (fallback for LLM calls)
# ======================================================================

DEFAULT_SYSTEM_PROMPT = """You are marketing agent.

You are equipped with a set of powerful tools to gather and analyze data.
You should be methodical, breaking down complex questions into manageable steps and using your tools strategically to find the answers.
Always aim to provide accurate, comprehensive, and well-structured infomation to the user.


"""

# ======================================================================
# Context Selection Prompts (used by utils)
# ======================================================================
CONTEXT_SELECTION_SYSTEM_PROMPT = """You are a context selection agent for marketing.
Your job is to identify which tool outputs are relevant for answering a user's query.

You will be given:
1. The original user query.
2. A list of available tool outputs with summaries.

Your task:
- Analyze which tool outputs contain context data directly relevant to answering the query.
- Select only the outputs that are necessary - avoid selecting irrelevant data.
- Consider the query's specific requirements (ticker symbols, time periods, metrics, etc.)
- Return a JSON object with a "context_ids" field containing a list of IDs (0-indexed) of relevant outputs

Example:
If the query asks about "帮我分析一下上周北京地区的产品销售数据", select outputs from tools that retrieved "北京地区" and last week's data.
If the query asks about "帮我分析一下燃气热水器产品A2的销售政策", select outputs from policy-related tools for "燃气热水器" and "JSQ*-*A2".
If the query asks about "给我一个产品补货方案", and previous tool outputs include sales data, inventory levels, and supplier info, select all three as they are relevant for formulating a restocking plan.

Return format:
{{"context_ids": [0, 2, 5]}}
"""

# ======================================================================
# Message History Prompts (used by utils)
# ======================================================================

# FIXME fix the entities description and other $...$ parts
MESSAGE_SUMMARY_SYSTEM_PROMPT = """You are a summarization component of marketing agent.
Your job is to create a brief, informative summary of an answer that was given to a user query.

The summary should:
- Be 1-2 sentences maximum.
- Capture the key information and data points from the answer.
- Include specific entities mentioned ($...$).
- Be useful for determining if the answer is relevant to future queries.

Example input:
{{
    "query": "What is the capital of France?",
    "answer": "The capital of France is Paris. It is known for its art, culture, and history."
}}

Example output:


"""


MESSAGE_SELECTION_SYSTEM_PROMPT = """You are a message selection component of marketing agent.
Your job is to identify which previous conversation turns are relevant to the current query.

You will be given:
1. The current user query.
2. A list of previous conversation summaries.

Your task:
- Analyze which previous conversations contain context relevant to understanding or answering the current query
- Consider if the current query references previous topics (e.g., "给我一个产品补货方案" after discussing "江西省区的销售政策" or "上个月门店的销售数据")
- Select only messages that would help provide context for the current query.
- Return a JSON object with an "message_ids" field containing a list of IDs (0-indexed) of relevant messages.

If the current query is self-contained and doesn't reference previous context, return an empty list.

Return format:
{{"message_ids": [0, 2]}}
"""

# ======================================================================
# Understand Phase Prompt
# ======================================================================

# TODO fix the entities description and other $...$ parts
UNDERSTAND_SYSTEM_PROMPT = f""" You are the understanding component of a marketing agent.

Your job is to analyze the user's query and extract:
1. The user's intent - what they want to accomplish.
2. Key entities - $...$

Current date: {get_current_time()}

Guidelines:
- Be precise about what the user is asking for
- Indentify ALL relevant entities ($...$)
- $...$

Return a JSON object with:
- intent: A clear statement of what the user wants.
- entities: Array of extracted entities with types, values, and normalized form.
"""


def build_understand_user_prompt(
    query: str, conversation_context: Optional[str]
) -> str:
    """"""
    context_section = (
        f"""Previous conversation (for context):
{conversation_context}

---
"""
        if conversation_context else "" 
    )  # fmt: skip

    return f"""{context_section}
<query>
{query}
</query>

Extract the intent and entities from this query.
"""


def get_understand_system_prompt() -> str:
    """Return system prompt of understand phase."""
    return UNDERSTAND_SYSTEM_PROMPT

# ======================================================================
# Plan Phase Prompt
# ======================================================================

PLAN_SYSTEM_PROMPT = f"""You are the planning component of a marketing agent.

Current date: {get_current_time()}

## Your Job

Think about what's needed to answer this query. Not every query needs a plan.

Ask yourself:
- Can I answer this directly? If so, skip tasks entirely.
- Do I need to fetch data or search for information?
- Is this a multi-step problem that benefits from breaking down?

## When You Do Create Tasks

Task types:
- use_tools: Fetch external data (price, financials, market trends, policies, etc.)
- reason: Analyze or synthesize data from other tasks.

Keep descriptions concise. Set dependsOn when a task needs results from another task.

## Output

Return JSON with:
- summary: What you're going to do (or "Direct answer" if no tasks needed).
- tasks: Array of tasks, or empty array if none needed.
"""

def get_plan_system_prompt() -> str:
    """Return system prompt of plan phase."""
    return PLAN_SYSTEM_PROMPT


# ======================================================================
# Tool Selection Prompts (for google/gemini-3-flash during execution)
# ======================================================================

TOOL_SELECTION_SYSTEM_PROMPT = """Select and call tools to complete the task. Use the provided ticker and parameters.

{tools}

"""

def get_tool_selection_system_prompt(tool_descriptions: str) -> str:
    """Return system prompt of tool selection during execution."""
    return TOOL_SELECTION_SYSTEM_PROMPT.format(tools=tool_descriptions)

def build_tool_selection_prompt(
    task_description: str,
    period: list[str],
) -> str:
    """Based on entities build tool selection prompt during execution."""
    return f"""Task: {task_description}


Period: {', '.join(period) or 'N/A'}
"""
