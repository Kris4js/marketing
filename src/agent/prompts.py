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

DEFAULT_SYSTEM_PROMPT = """


"""

# ======================================================================
# Message History Prompts (used by utils)
# ======================================================================

# FIXME fix the entities description and other $...$ parts
MESSAGE_SUMMARY_SYSTEM_PROMPT = """You are a summarization component for $...$, a marketing agent.
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


MESSAGE_SELECTION_SYSTEM_PROMPT = """You are a message selection component for $...$, a marketing agent.
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
UNDERSTAND_SYSTEM_PROMPT = f""" You are the understanding component for $...$, a marketing agent.

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
