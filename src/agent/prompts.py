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


def build_plan_user_prompt(
    query: str,
    understanding: object,
    guidanceFromReflection: Optional[str] = None,
    format_prior_work: str = "",
) -> str:
    """Build user prompt for plan phase."""
    guidance_section = (
        f"\nGuidance from reflection:\n{guidanceFromReflection}\n"
        if guidanceFromReflection
        else ""
    )
    prior_work_section = (
        f"\nPrevious work:\n{format_prior_work}\n" if format_prior_work else ""
    )

    return f"""Query:
{query}

Understanding:
{understanding.intent}
{prior_work_section}
{guidance_section}

Create a plan to answer this query.
"""


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


# ======================================================================
# Execute Phase Prompt
# ======================================================================

EXECUTE_SYSTEM_PROMPT = """You are the execution component of a marketing agent.

Your job is to complete reasoning tasks by analyzing data and providing insights.

You will be given:
1. The user's original query
2. A specific task to complete
3. Context data from previous tasks and tool executions

Your task:
- Analyze the context data thoroughly
- Provide a comprehensive response that addresses the specific task
- Use the data available to support your analysis
- If data is insufficient, clearly state what additional information would be helpful

Guidelines:
- Be thorough and analytical
- Reference specific data points when available
- Provide actionable insights
- Structure your response clearly with sections when appropriate
"""


def get_execute_system_prompt() -> str:
    """Return system prompt of execute phase."""
    return EXECUTE_SYSTEM_PROMPT


def build_execute_user_prompt(
    query: str,
    task_description: str,
    context_data: str,
) -> str:
    """Build user prompt for execute phase."""
    return f"""Original Query:
{query}

Task:
{task_description}

Context Data:
{context_data}

Please complete this task based on the provided context data.
"""


# ======================================================================
# Reflect Phase Prompt
# ======================================================================

REFLECT_SYSTEM_PROMPT = f"""You are the reflection component of a marketing agent.

Current date: {get_current_time()}

Your job is to evaluate whether enough information has been gathered to answer the user's query.

You will be given:
1. The user's original query
2. The current plan with task completion status
3. All task results obtained so far
4. A summary of all planning iterations

Your task:
- Evaluate if the gathered information is sufficient to answer the query
- Consider whether the results directly address the user's needs
- Identify any gaps or missing information
- If complete, provide clear reasoning for why it's sufficient
- If incomplete, provide specific guidance on what additional information is needed

Output format:
- isComplete: true if sufficient information has been gathered, false otherwise
- reason: Clear explanation of your assessment
- guidance: If incomplete, specific guidance on what to do next (optional)

Guidelines:
- Be thorough in your evaluation
- Consider the user's original intent
- Don't mark as complete if there are obvious gaps
- Provide actionable guidance when incomplete
"""


def get_reflect_system_prompt() -> str:
    """Return system prompt of reflect phase."""
    return REFLECT_SYSTEM_PROMPT


def build_reflect_user_prompt(
    query: str,
    understanding: object,
    completedPlans: list,
    taskResults: dict,
    iteration: int,
) -> str:
    """Build user prompt for reflect phase."""
    # Format current plan with task statuses
    current_plan = completedPlans[-1] if completedPlans else None
    plan_summary = []
    if current_plan:
        for task in current_plan.tasks:
            status_symbol = "✓" if task.status.value == "completed" else "✗"
            plan_summary.append(
                f"{status_symbol} {task.description} [{task.id}] - {task.status.value}"
            )
    plan_str = "\n".join(plan_summary) if plan_summary else "No tasks in current plan"

    # Format task results
    results_summary = []
    for task_id, result in taskResults.items():
        results_summary.append(f"Task {task_id}:\n{result.output}")
    results_str = "\n\n".join(results_summary) if results_summary else "No task results yet"

    # Format all completed plans
    all_plans_summary = []
    for idx, completed_plan in enumerate(completedPlans, start=1):
        pass_summary = [f"Pass {idx}:"]
        for task in completed_plan.tasks:
            status_symbol = "✓" if task.status.value == "completed" else "✗"
            pass_summary.append(f"  {status_symbol} {task.description} [{task.id}]")
        all_plans_summary.append("\n".join(pass_summary))
    all_plans_str = "\n\n".join(all_plans_summary) if all_plans_summary else "No completed plans"

    return f"""Original Query:
{query}

Understanding:
{understanding.intent}

Iteration: {iteration}

Current Plan:
{plan_str}

Task Results:
{results_str}

All Planning Iterations:
{all_plans_str}

Evaluate whether the gathered information is sufficient to answer the query.
"""


# ======================================================================
# Answer Phase Prompt
# ======================================================================

ANSWER_SYSTEM_PROMPT = f"""You are the answer component of a marketing agent.

Current date: {get_current_time()}

Your job is to synthesize all gathered information into a comprehensive, well-structured answer to the user's query.

You will be given:
1. The user's original query
2. All completed planning iterations
3. All task results from tool executions and reasoning tasks

Your task:
- Synthesize information from all sources into a coherent answer
- Structure your response clearly with appropriate sections
- Highlight key findings and insights
- Support your answer with specific data from the task results
- Make the answer actionable and practical

Guidelines:
- Be comprehensive but concise
- Use clear headings and bullet points when appropriate
- Reference specific data points and findings
- Provide actionable recommendations when relevant
- Ensure the answer directly addresses the user's question
- If there are limitations in the data, acknowledge them
"""


def get_answer_system_prompt() -> str:
    """Return system prompt of answer phase."""
    return ANSWER_SYSTEM_PROMPT


def build_answer_user_prompt(
    query: str,
    completedPlans: list,
    taskResults: dict,
) -> str:
    """Build user prompt for answer phase."""
    # Format completed plans
    plans_summary = []
    for idx, plan in enumerate(completedPlans, start=1):
        pass_summary = [f"Planning Pass {idx}:"]
        for task in plan.tasks:
            status_symbol = "✓" if task.status.value == "completed" else "✗"
            pass_summary.append(f"  {status_symbol} {task.description} [{task.id}]")
        plans_summary.append("\n".join(pass_summary))
    plans_str = "\n\n".join(plans_summary) if plans_summary else "No completed plans"

    # Format task results
    results_summary = []
    for task_id, result in taskResults.items():
        results_summary.append(f"Task {task_id}:\n{result.output}")
    results_str = "\n\n".join(results_summary) if results_summary else "No task results"

    return f"""Original Query:
{query}

Completed Planning Iterations:
{plans_str}

All Task Results:
{results_str}

Based on all the information gathered above, provide a comprehensive answer to the user's query.
"""
