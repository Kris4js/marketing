from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from src.agent.state import PlanInput, Task, Plan, TaskType, TaskStatus
from src.agent.prompts import (
    get_plan_system_prompt,
    build_plan_user_prompt,
)
from src.model.llm import llm_call
from src.utils.logger import logger


class TaskSchema(BaseModel):
    """Schema for a task as returned by the LLM."""

    description: str
    taskType: str  # "use_tools" or "reason"
    dependsOn: List[str] = []  # List of task IDs this task depends on

    class Config:
        frozen = True


class PlanResponse(BaseModel):
    """Schema for the plan response from the LLM."""

    summary: str
    tasks: List[TaskSchema]

    class Config:
        frozen = True


class PlanPhase:
    """Plan phase that creates task lists without selecting tools.

    This phase analyzes the query and creates a list of tasks with
    dependencies to accomplish the goal.
    """

    def __init__(
        self,
        model: str = "google/gemini-2.5-pro-preview-09-2025",
    ):
        self.model = model

    async def run(
        self,
        input: PlanInput,
    ) -> Plan:
        """Create a plan with tasks to accomplish the query.

        Args:
            input (PlanInput): Contains query, understanding, prior plans,
                             and optional guidance

        Returns:
            Plan: A plan with tasks and their dependencies
        """
        logger.info("Plan phase: Starting planning iteration")

        system_prompt = get_plan_system_prompt()
        user_prompt = build_plan_user_prompt(
            query=input.query,
            understanding=input.understanding,
            guidanceFromReflection=input.guidanceFromReflection,
            format_prior_work=self._format_prior_work(input.priorPlans),
        )

        # Call LLM with schema for structured output
        response = await llm_call(
            model=self.model,
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format=PlanResponse,
        )

        # Parse the response into PlanResponse
        if isinstance(response, PlanResponse):
            plan_response = response
        elif hasattr(response, "parsed"):
            plan_response = response.parsed
        else:
            # Fallback: parse manually
            logger.warning(f"Unexpected response type: {type(response)}")
            plan_response = PlanResponse(summary="Failed to generate plan", tasks=[])

        # Convert TaskSchema to Task objects
        tasks: List[Task] = []

        for idx, task_schema in enumerate(plan_response.tasks):
            # Map string to TaskType enum
            task_type = (
                TaskType.USE_TOOLS
                if task_schema.taskType == "use_tools"
                else TaskType.REASON
            )

            task = Task()
            task.id = f"task_{idx}"
            task.description = task_schema.description
            task.status = TaskStatus.PENDING
            task.taskType = task_type
            task.dependsOn = task_schema.dependsOn if task_schema.dependsOn else None
            task.toolCalls = None
            tasks.append(task)

        plan = Plan()
        plan.summary = plan_response.summary
        plan.tasks = tasks

        logger.info(
            f"Plan phase: Created plan with {len(tasks)} tasks: {plan.summary}"
        )

        return plan

    def _format_prior_work(self, prior_plans: Optional[List[Plan]]) -> str:
        """Format prior planning iterations into a summary string.

        Args:
            prior_plans: List of previously completed plans

        Returns:
            str: Formatted summary of prior work
        """
        if not prior_plans:
            return ""

        summary_parts = []

        for idx, plan in enumerate(prior_plans, start=1):
            pass_num = idx
            task_summaries = []

            for task in plan.tasks:
                status_symbol = "✓" if task.status == TaskStatus.COMPLETED else "✗"
                task_summaries.append(
                    f"{status_symbol} {task.description} [{task.id}]"
                )

            tasks_str = "\n    ".join(task_summaries)
            summary_parts.append(f"Pass {pass_num}:\n    {tasks_str}")

        return "\n\n".join(summary_parts)
