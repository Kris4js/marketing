import sys
import asyncio

from loguru import logger
from typing import Optional, Any, Protocol
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_core.messages import AIMessage

from src.model.llm import llm_call
from src.utils.context import ToolContextManager
from src.utils.logger import get_logger
from src.agent.prompts import (
    get_tool_selection_system_prompt,
    build_tool_selection_prompt,
)
from src.agent.state import (
    Task,
    ToolCall,
    ToolCallStatus,
    TaskStatus,
    TaskType,
    Understanding,
)

logger = get_logger(__name__)

STANDARD_TOOL_MODEL = "google/gemini-2.5-flash-lite-preview-09-2025"


# ======================================================================
## Tool Executor Options
# ======================================================================


class ToolExecutorOptions(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    tools: list[StructuredTool] = Field(
        ..., description="List of available tools."
    )
    context_manager: ToolContextManager = Field(
        ...,
        description="Manages tool execution context storage and retrieval.",
    )


# ======================================================================
## Tool Executor Callbacks
# ======================================================================


class ToolExecutorCallbacks(Protocol):
    """Callbacks for tool executor events."""

    def on_tool_call_update(
        self,
        task_id: str,
        tool_index: int,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Called when a tool starts execution."""
        


# ======================================================================
## Tool Executor Implementation
# ======================================================================


# Handles tool selection and execution for tasks.
# Uses standard, fast model (google/gemini-2.5-flash-lite-preview-09-2025) for tool selection.
class ToolExecutor:
    def __init__(
        self,
        options: ToolExecutorOptions,
    ) -> None:
        self.tools: list[StructuredTool] = options.tools
        self.tool_map: dict[str, StructuredTool] = {
            tool.name: tool for tool in options.tools
        }
        self.context_manager: ToolContextManager = options.context_manager

    def format_tool(self, tool: StructuredTool) -> str:
        """
        class StructuredTool(BaseTool):
            description: str = ""
            args_schema: Annotated[ArgsSchema, SkipValidation()] = Field(
                ..., description="The tool schema."
            )

            name: str
        """
        schema = tool.args_schema
        args_description = ""

        if schema and hasattr(schema, "shape"):
            shape: dict[str, Optional[str]] = schema.shape
            if hasattr(shape, "_defs"):
                # fmt: off
                """
                key: tool.args_schema.shape._defs.keys()
                value: tool.args_schema.shape._defs[key]._schema.description
                """
                args = []
                for key, value in shape._defs.items():
                    if hasattr(value, '_schema') and hasattr(value._schema, 'description'):
                        description = value._schema.description or "No description"
                        args.append(f"- {key}: {description}")
                # fmt: on
                if args:
                    args_description = "\n Arguments:\n" + "\n".join(args)

        return f"""- {tool.name}: {tool.description}{args_description}"""

    def _format_tool_descriptions(self) -> str:
        """生成一个包含工具及其参数和描述的格式化列表字符串"""
        return "\n\n".join(
            self.format_tool(tool=tool) for tool in self.tools
        )

    def _extract_tool_calls(
        self,
        response: Any,
    ) -> list[ToolCall]:
        """从 LLM 响应中提取工具调用列表"""
        if response is None or not isinstance(response, dict):
            return []

        message: AIMessage = response
        tool_calls = message.get("tool_calls")
        if not tool_calls or not isinstance(tool_calls, list):
            return []

        return [
            ToolCall(
                tool=tc.get("name"),
                args=tc.get("args", {}),
            )
            for tc in tool_calls
        ]

    async def execute_tools(
        self,
        task: Task,
        query_id: str,
        callbacks: Optional[ToolExecutorCallbacks],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> bool:
        """支持取消的异步执行工具调用

        Args:
            task (Task): Task object containing tool calls
            query_id (str): Query ID
            callbacks (Optional[ToolExecutorCallbacks]): Callbacks for tool execution events
            cancellation_token(Optional[asyncio.Event], optional): Check if cancel the event.

        Returns:
            bool: True if all tool calls succeeded, False otherwise.
        """
        if task.toolCalls is None:
            return True

        # 1. Check point 1: overall pre-check
        if cancellation_token and cancellation_token.is_set():
            raise asyncio.CancelledError("Tool execution cancelled.")

        all_succeeded = True

        async def execute_single_tool(
            tool_call: ToolCallStatus,
            index: int,
        ) -> None:
            """执行单个工具调用并更新其状态

            Args:
                tool_call (ToolCallStatus): 工具调用状态对象

                ```python
                class ToolCall:
                    tool: str
                    args: dict[str, Any]

                class ToolCallStatus(ToolCall):
                    status: TaskStatus
                ```

                index (int): 工具调用在任务中的索引

            """
            nonlocal all_succeeded

            # 2. Check point 2: before each tool execution
            if cancellation_token and cancellation_token.is_set():
                raise asyncio.CancelledError("Tool execution cancelled.")

            callbacks.on_tool_call_update(
                task.id, index, TaskStatus.IN_PROGRESS
            )

            try:
                tool = self.tool_map.get(tool_call.tool)
                if tool is None:
                    raise ValueError(f"Tool {tool_call.tool} not found.")

                # Atomic operation execution of the tool
                # 原子操作执行工具
                result = await tool.ainvoke(tool_call.args)

                # 3. Check point 3: after tool execution before saving context
                if cancellation_token and cancellation_token.is_set():
                    raise asyncio.CancelledError(
                        "Tool execution cancelled."
                    )

                # 保存上下文
                context_path = self.context_manager.save_context(
                    tool_name=tool.name,
                    args=tool_call.args,
                    result=result,
                    task_id=None,
                    query_id=query_id,
                )

                output = result if isinstance(result, str) else str(result)
                tool_call.status = TaskStatus.COMPLETED
                tool_call.output = output
                callbacks.on_tool_call_update(
                    task.id, index, TaskStatus.COMPLETED, output=output
                )

                callbacks.on_tool_call_update(
                    task.id,
                    index,
                    "succeeded",
                    output=f"Result saved at {context_path}",
                )

            except asyncio.CancelledError:
                # !!! AbortError: 用户取消操作, 立即中止所有操作
                raise
            except Exception as e:
                # !!! Mark as failed but do not interrupt other tasks
                all_succeeded = False
                error_msg = str(e)
                tool_call.status = TaskStatus.FAILED
                tool_call.error = error_msg
                callbacks.on_tool_call_update(
                    task.id, index, TaskStatus.FAILED, error=error_msg
                )

        # fmt: off
        tasks = [
            execute_single_tool(tool_call, idx) for idx, tool_call in enumerate(task.toolCalls)
        ]
        # fmt: on

        try:
            # gather() 会等待所有任务完成，即使其中一些任务引发异常
            # 如果有任务引发 CancelledError，则整个 gather() 调用会引发该异常
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            # User cancelled the operation, re-raise to propagate
            raise

        return all_succeeded

    async def select_tools(
        self,
        task: Task,
        understanding: Understanding,
    ) -> list[ToolCallStatus]:
        """_summary_

        Args:
            task (Task): _description_
            understanding (Understanding): _description_

        Returns:
            list[ToolCallStatus]: _description_
        """
        periods = understanding.entities.get("periods", [])

        prompt = build_tool_selection_prompt(
            task_description=task.description,
            period=periods,
        )

        system_prompt = get_tool_selection_system_prompt(
            self._format_tool_descriptions()
        )

        response = await llm_call(
            model=STANDARD_TOOL_MODEL,
            prompt=prompt,
            system_prompt=system_prompt,
            tools=self.tools,
        )

        tool_calls = self._extract_tool_calls(response)
        return [
            ToolCallStatus(
                tool=tc.tool,
                args=tc.args,
                status=TaskStatus.PENDING,
            )
            for tc in tool_calls
        ]


# ======================================================================
## Examples
# ======================================================================


async def example_1_basic_initialization() -> None:
    """Example 1: Basic initialization and tool formatting"""
    class SearchArgs(BaseModel):
        query: str = Field(description="Search query")

    async def search_func(query: str) -> str:
        return f"Results for: {query}"

    search_tool = StructuredTool(
        name="search",
        description="Search the web",
        func=search_func,
        coroutine=search_func,
        args_schema=SearchArgs,
    )

    options = ToolExecutorOptions(
        tools=[search_tool],
        context_manager=ToolContextManager(),
    )
    executor = ToolExecutor(options)

    # Format and display tool descriptions
    formatted = executor._format_tool_descriptions()
    logger.info(formatted)


async def example_2_mock_tool_execution() -> None:
    """Example 2: Execute tools with mock (no API key needed)"""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class CalculatorArgs(BaseModel):
        a: int = Field(description="First number")
        b: int = Field(description="Second number")

    async def add_func(a: int, b: int) -> str:
        return str(a + b)

    calc_tool = StructuredTool(
        name="add",
        description="Add two numbers",
        func=add_func,
        coroutine=add_func,
        args_schema=CalculatorArgs,
    )

    # Create a simple callback
    class SimpleCallback(ToolExecutorCallbacks):
        def __init__(self):
            self.updates = []

        def on_tool_call_update(
            self,
            task_id: str,
            tool_index: int,
            status: str,
            output: Optional[str] = None,
            error: Optional[str] = None,
        ) -> None:
            self.updates.append({"status": status, "output": output})
            logger.info(f"[Task {task_id}] Tool {tool_index}: {status}")

    options = ToolExecutorOptions(
        tools=[calc_tool],
        context_manager=ToolContextManager(),
    )
    executor = ToolExecutor(options)
    callback = SimpleCallback()

    # Create a task with tool calls
    task = Task(
        id="task-1",
        description="Add 5 and 3",
        status=TaskStatus.PENDING,
        taskType=TaskType.USE_TOOLS,
        toolCalls=[
            ToolCallStatus(
                tool="add",
                args={"a": 5, "b": 3},
                status=TaskStatus.PENDING,
            )
        ],
    )

    # Execute tools (mock, no API key needed)
    success = await executor.execute_tools(
        task=task,
        query_id="query-1",
        callbacks=callback,
    )
    logger.info(f"Execution succeeded: {success}")
    logger.info(f"Result: {task.toolCalls[0].output}")


async def example_3_tool_selection_mock() -> None:
    """Example 3: Tool selection (requires API key)"""
    from unittest.mock import AsyncMock, patch

    # Mock tool
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class WeatherArgs(BaseModel):
        city: str = Field(description="City name")

    async def get_weather(city: str) -> str:
        return f"Weather in {city}: 22°C, Sunny"

    weather_tool = StructuredTool(
        name="get_weather",
        description="Get weather for a city",
        func=get_weather,
        coroutine=get_weather,
        args_schema=WeatherArgs,
    )

    # Mock LLM response
    mock_response = {
        "tool_calls": [
            {
                "name": "get_weather",
                "args": {"city": "Tokyo"},
            }
        ]
    }

    options = ToolExecutorOptions(
        tools=[weather_tool],
        context_manager=ToolContextManager(),
    )
    executor = ToolExecutor(options)

    with patch("src.tools.tool_executor.llm_call", new=AsyncMock(return_value=mock_response)):
        task = Task(
            id="task-2",
            description="What's the weather in Tokyo?",
            status=TaskStatus.PENDING,
            taskType=TaskType.USE_TOOLS,
        )
        understanding = Understanding(
            intent="get_weather",
            entities={"periods": []},
        )

        tool_calls = await executor.select_tools(task, understanding)
        logger.info(f"Selected {len(tool_calls)} tool(s)")
        logger.info(f"Tool: {tool_calls[0].tool}, Args: {tool_calls[0].args}")


async def example_4_real_api_execution() -> None:
    """Example 4: Execute tools with real API (requires OPENROUTER_API_KEY in .env)"""
    import os
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    # Check if API key is available
    if not os.getenv("OPENROUTER_API_KEY"):
        logger.warning("Skipping: OPENROUTER_API_KEY not found in environment")
        return

    class SearchArgs(BaseModel):
        query: str = Field(description="Search query")

    async def search_func(query: str) -> str:
        return f"Search results for: {query}"

    search_tool = StructuredTool(
        name="search",
        description="Search the web",
        func=search_func,
        coroutine=search_func,
        args_schema=SearchArgs,
    )

    class SimpleCallback(ToolExecutorCallbacks):
        def on_tool_call_update(
            self,
            task_id: str,
            tool_index: int,
            status: str,
            output: Optional[str] = None,
            error: Optional[str] = None,
        ) -> None:
            logger.info(f"[{status}] Tool {tool_index}: {output or ''}")

    options = ToolExecutorOptions(
        tools=[search_tool],
        context_manager=ToolContextManager(),
    )
    executor = ToolExecutor(options)
    callback = SimpleCallback()

    task = Task(
        id="task-3",
        description="Search for Python tutorials",
        status=TaskStatus.PENDING,
        taskType=TaskType.USE_TOOLS,
        toolCalls=[
            ToolCallStatus(
                tool="search",
                args={"query": "Python tutorials"},
                status=TaskStatus.PENDING,
            )
        ],
    )

    success = await executor.execute_tools(
        task=task,
        query_id="query-2",
        callbacks=callback,
    )
    logger.info(f"Execution with real API succeeded: {success}")


async def example_5_cancellation_handling() -> None:
    """Example 5: Handle tool execution cancellation"""
    import asyncio
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class SlowTaskArgs(BaseModel):
        duration: int = Field(description="Duration in seconds")

    async def slow_task(duration: int) -> str:
        await asyncio.sleep(duration)
        return f"Completed after {duration}s"

    slow_tool = StructuredTool(
        name="slow_task",
        description="A task that takes time",
        func=slow_task,
        coroutine=slow_task,
        args_schema=SlowTaskArgs,
    )

    class SimpleCallback(ToolExecutorCallbacks):
        def on_tool_call_update(
            self,
            task_id: str,
            tool_index: int,
            status: str,
            output: Optional[str] = None,
            error: Optional[str] = None,
        ) -> None:
            logger.info(f"Tool {tool_index}: {status}")

    options = ToolExecutorOptions(
        tools=[slow_tool],
        context_manager=ToolContextManager(),
    )
    executor = ToolExecutor(options)
    callback = SimpleCallback()

    task = Task(
        id="task-4",
        description="Run slow task",
        status=TaskStatus.PENDING,
        taskType=TaskType.USE_TOOLS,
        toolCalls=[
            ToolCallStatus(
                tool="slow_task",
                args={"duration": 5},
                status=TaskStatus.PENDING,
            )
        ],
    )

    # Create cancellation token
    cancel_event = asyncio.Event()

    async def run_and_cancel():
        # Cancel after 1 second
        await asyncio.sleep(1)
        cancel_event.set()
        logger.info("Cancellation requested!")

    # Run execution and cancellation in parallel
    try:
        await asyncio.gather(
            executor.execute_tools(
                task=task,
                query_id="query-3",
                callbacks=callback,
                cancellation_token=cancel_event,
            ),
            run_and_cancel(),
        )
    except asyncio.CancelledError:
        logger.info("Tool execution was cancelled successfully")


if __name__ == "__main__":
    logger.info("=== Example 1: Basic Initialization ===")
    asyncio.run(example_1_basic_initialization())

    # logger.info("\n=== Example 2: Mock Tool Execution ===")
    # asyncio.run(example_2_mock_tool_execution())

    # logger.info("\n=== Example 3: Tool Selection (Mock) ===")
    # asyncio.run(example_3_tool_selection_mock())

    # logger.info("\n=== Example 4: Real API Execution ===")
    # asyncio.run(example_4_real_api_execution())

    # logger.info("\n=== Example 5: Cancellation Handling ===")
    # asyncio.run(example_5_cancellation_handling())
