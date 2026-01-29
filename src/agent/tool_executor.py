import asyncio

from typing import Optional, Any, Protocol
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

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
        ...


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
        if response is None:
            return []

        # AIMessage has tool_calls as an attribute, not a dict key
        if hasattr(response, "tool_calls"):
            tool_calls = response.tool_calls
        elif isinstance(response, dict):
            tool_calls = response.get("tool_calls")
        else:
            return []

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

