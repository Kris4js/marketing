import asyncio
from typing import Dict, List, Optional, Protocol

from src.agent.state import Task, Plan, TaskResult, TaskStatus, Understanding
from src.agent.tool_executor import ToolExecutor, ToolExecutorCallbacks
from src.agent.phases.execute import ExecutePhase
from src.utils.context import ToolContextManager
from src.utils.logger import logger


# ======================================================================
## Task Executor Callbacks
# ======================================================================


class TaskExecutorCallbacks(Protocol):
    """Callbacks for task executor events."""

    def on_task_start(self, task_id: str) -> None:
        """Called when a task starts execution."""
        ...

    def on_task_complete(self, task_id: str, output: str) -> None:
        """Called when a task completes successfully."""
        ...

    def on_task_failed(self, task_id: str, error: str) -> None:
        """Called when a task fails."""
        ...


# ======================================================================
## Task Executor Options
# ======================================================================


class TaskExecutorOptions:
    """Options for the task executor."""

    def __init__(
        self,
        tool_executor: ToolExecutor,
        execute_phase: ExecutePhase,
        context_manager: ToolContextManager,
    ):
        self.tool_executor = tool_executor
        self.execute_phase = execute_phase
        self.context_manager = context_manager


# ======================================================================
## Task Executor Implementation
# ======================================================================


class TaskExecutor:
    """
    Executes tasks with dependency awareness.

    Manages the scheduling and execution of tasks based on their dependencies.
    Tasks are executed in parallel when possible, respecting the dependency chain.
    """

    def __init__(
        self,
        options: TaskExecutorOptions,
    ):
        self.tool_executor = options.tool_executor
        self.execute_phase = options.execute_phase
        self.context_manager = options.context_manager

    async def execute_tasks(
        self,
        plan: Plan,
        query: str,
        understanding: Understanding,
        query_id: str,
        task_executor_callbacks: Optional[TaskExecutorCallbacks] = None,
        tool_executor_callbacks: Optional[ToolExecutorCallbacks] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> Dict[str, TaskResult]:
        """Execute all tasks in the plan respecting dependencies.

        Args:
            plan (Plan): The plan containing tasks to execute
            query (str): The original user query
            understanding (Understanding): The understanding from the understand phase
            query_id (str): The query ID for context management
            task_executor_callbacks (Optional[TaskExecutorCallbacks]): Callbacks for task events
            tool_executor_callbacks (Optional[ToolExecutorCallbacks]): Callbacks for tool events
            cancellation_token (Optional[asyncio.Event]): Token for cancelling execution

        Returns:
            Dict[str, TaskResult]: Map of task IDs to their results
        """
        logger.info(f"TaskExecutor: Starting execution of {len(plan.tasks)} tasks")

        task_results: Dict[str, TaskResult] = {}
        task_map = {task.id: task for task in plan.tasks}

        # Track task states
        completed_tasks = set()
        running_tasks = set()

        while len(completed_tasks) < len(plan.tasks):
            # Check for cancellation
            if cancellation_token and cancellation_token.is_set():
                logger.info("TaskExecutor: Execution cancelled")
                raise asyncio.CancelledError("Task execution cancelled")

            # Get tasks that are ready to execute
            ready_tasks = self._get_ready_tasks(
                task_map=task_map,
                completed_tasks=completed_tasks,
                running_tasks=running_tasks,
            )

            if not ready_tasks:
                # No tasks ready and not all completed - likely a dependency cycle
                if len(completed_tasks) < len(plan.tasks):
                    logger.error(
                        "TaskExecutor: No ready tasks available, possible dependency cycle"
                    )
                    break
                else:
                    # All tasks completed
                    break

            # Execute ready tasks in parallel
            logger.info(
                f"TaskExecutor: Executing {len(ready_tasks)} tasks in parallel"
            )

            execution_tasks = [
                self.execute_task(
                    task=task,
                    query=query,
                    understanding=understanding,
                    query_id=query_id,
                    task_results=task_results,
                    task_executor_callbacks=task_executor_callbacks,
                    tool_executor_callbacks=tool_executor_callbacks,
                    cancellation_token=cancellation_token,
                )
                for task in ready_tasks
            ]

            # Wait for all tasks to complete
            results = await asyncio.gather(*execution_tasks, return_exceptions=True)

            # Process results
            for task, result in zip(ready_tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"TaskExecutor: Task {task.id} failed: {result}")
                    task.status = TaskStatus.FAILED
                    completed_tasks.add(task.id)

                    if task_executor_callbacks:
                        task_executor_callbacks.on_task_failed(
                            task.id, str(result)
                        )
                else:
                    task_results[result.taskId] = result
                    task.status = TaskStatus.COMPLETED
                    completed_tasks.add(task.id)
                    logger.info(
                        f"TaskExecutor: Task {task.id} completed successfully"
                    )

                    if task_executor_callbacks:
                        task_executor_callbacks.on_task_complete(
                            task.id, result.output
                        )

        logger.info(
            f"TaskExecutor: Completed {len(task_results)}/{len(plan.tasks)} tasks"
        )

        return task_results

    def _get_ready_tasks(
        self,
        task_map: Dict[str, Task],
        completed_tasks: set[str],
        running_tasks: set[str],
    ) -> List[Task]:
        """Get tasks whose dependencies have all completed.

        Args:
            task_map (Dict[str, Task]): Map of task IDs to tasks
            completed_tasks (set[str]): Set of completed task IDs
            running_tasks (set[str]): Set of currently running task IDs

        Returns:
            List[Task]: List of tasks ready to execute
        """
        ready_tasks = []

        for task in task_map.values():
            # Skip if already completed or running
            if task.id in completed_tasks or task.id in running_tasks:
                continue

            # Check if all dependencies are completed
            dependencies_met = all(
                dep_id in completed_tasks for dep_id in task.dependencies
            )

            if dependencies_met:
                ready_tasks.append(task)

        return ready_tasks

    async def execute_task(
        self,
        task: Task,
        query: str,
        understanding: Understanding,
        query_id: str,
        task_results: Dict[str, TaskResult],
        task_executor_callbacks: Optional[TaskExecutorCallbacks] = None,
        tool_executor_callbacks: Optional[ToolExecutorCallbacks] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> TaskResult:
        """Execute a single task.

        Args:
            task (Task): The task to execute
            query (str): The original user query
            understanding (Understanding): The understanding from the understand phase
            query_id (str): The query ID for context management
            task_results (Dict[str, TaskResult]): Results from previous tasks
            task_executor_callbacks (Optional[TaskExecutorCallbacks]): Callbacks for task events
            tool_executor_callbacks (Optional[ToolExecutorCallbacks]): Callbacks for tool events
            cancellation_token (Optional[asyncio.Event]): Token for cancelling execution

        Returns:
            TaskResult: The result of the task execution
        """
        logger.info(f"TaskExecutor: Executing task {task.id} ({task.type})")

        if task_executor_callbacks:
            task_executor_callbacks.on_task_start(task.id)

        if task.type == "tool":
            # Select tools for the task
            tool_calls = await self.tool_executor.select_tools(
                task=task,
                understanding=understanding,
            )

            # Attach tool calls to the task
            task.toolCalls = tool_calls

            # Execute tools
            await self.tool_executor.execute_tools(
                task=task,
                query_id=query_id,
                callbacks=tool_executor_callbacks,
                cancellation_token=cancellation_token,
            )

            # Format output from tool results
            output_parts = []
            for tc in tool_calls:
                if tc.status == TaskStatus.COMPLETED:
                    output_parts.append(f"Tool: {tc.tool}\nResult: {tc.output}")
                elif tc.status == TaskStatus.FAILED:
                    output_parts.append(f"Tool: {tc.tool}\nError: {tc.error}")

            output = "\n\n".join(output_parts)

        elif task.type == "reasoning":
            # Build context data from previous task results
            context_data = self._build_context_data(
                task=task,
                task_results=task_results,
                query_id=query_id,
            )

            # Execute reasoning using ExecutePhase
            from src.agent.state import ExecuteInput

            result = await self.execute_phase.run(
                input=ExecuteInput(
                    query=query,
                    task=task,
                    contextData=context_data,
                )
            )

            output = result.output

        else:
            raise ValueError(f"Unknown task type: {task.type}")

        return TaskResult(
            taskId=task.id,
            output=output,
        )

    def _build_context_data(
        self,
        task: Task,
        task_results: Dict[str, TaskResult],
        query_id: str,
    ) -> str:
        """Build context data from task results and stored context.

        Args:
            task (Task): The current task
            task_results (Dict[str, TaskResult]): Results from previous tasks
            query_id (str): The query ID

        Returns:
            str: Formatted context data
        """
        context_parts = []

        # Add results from dependent tasks
        for dep_id in task.dependencies:
            if dep_id in task_results:
                result = task_results[dep_id]
                context_parts.append(f"Task {dep_id}:\n{result.output}")

        # Add context from context manager
        stored_context = self.context_manager.get_all_context(query_id)
        if stored_context:
            context_parts.append(f"\nStored Context:\n{stored_context}")

        return "\n\n".join(context_parts)
