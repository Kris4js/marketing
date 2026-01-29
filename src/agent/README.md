# Agent Module

Multi-phase agent system with tool execution capabilities. Uses a phase-based workflow (understand → plan → execute → reflect → answer) with a dedicated `ToolExecutor` for managing tool operations.

## Architecture

```
src/agent/
├── __init__.py           # Module exports
├── state.py              # Pydantic models for agent state (Task, ToolCall, etc.)
├── tool_executor.py      # Tool selection and execution (CURRENT DESIGN)
├── prompts.py            # System prompts for each phase
└── types.py              # Agent configuration types
```

## Current Design: Separate ToolExecutor

`tool_executor.py` is a dedicated class that handles all tool-related operations:

```python
class ToolExecutor:
    def __init__(self, options: ToolExecutorOptions)
    async def execute_tools(task, query_id, callbacks) -> bool
    async def select_tools(task, understanding) -> list[ToolCallStatus]
    def _format_tool_descriptions() -> str
    def _extract_tool_calls(response) -> list[ToolCall]
```

### Responsibilities

| Method | Purpose |
|--------|---------|
| `execute_tools()` | Execute tool calls with cancellation support |
| `select_tools()` | LLM-based tool selection for a task |
| `format_tool()` | Format single tool for LLM consumption |
| `_format_tool_descriptions()` | Format all tools for system prompt |
| `_extract_tool_calls()` | Parse tool calls from LLM response |

### Key Features

1. **Cancellation Support** - Three checkpoint strategy for graceful cancellation
2. **Context Management** - Integrates with `ToolContextManager` for persistence
3. **Callback Protocol** - `ToolExecutorCallbacks` for real-time status updates
4. **Error Handling** - Continues execution on individual tool failures
5. **Parallel Execution** - Uses `asyncio.gather()` for concurrent tool calls

### Design Rationale

Keeping `ToolExecutor` separate provides:
- **Single Responsibility** - Agent orchestrates phases, Executor handles tools
- **Testability** - Can test tool execution in isolation
- **Reusability** - Can be used by different agent implementations
- **Extensibility** - Easy to add new tool-related features

## State Models (`state.py`)

| Class | Purpose |
|-------|---------|
| `Phase` | Enum: UNDERSTAND, PLAN, EXECUTE, REFLECT, ANSWER, COMPLETE |
| `TaskStatus` | Enum: PENDING, IN_PROGRESS, COMPLETED, FAILED |
| `TaskType` | Enum: USE_TOOLS, REASON |
| `Task` | Dataclass: id, description, status, taskType, toolCalls, dependsOn |
| `ToolCall` | Dataclass: tool, args |
| `ToolCallStatus` | ToolCall + status, output, error |
| `Understanding` | Dataclass: intent, entities |

## Usage Example

```python
from src.agent.tool_executor import ToolExecutor, ToolExecutorOptions, ToolExecutorCallbacks
from src.tools import get_tools
from src.utils.context import ToolContextManager

class MyCallbacks(ToolExecutorCallbacks):
    def on_tool_call_update(self, task_id, tool_index, status, output=None, error=None):
        print(f"Tool {tool_index}: {status}")

# Setup
tools = get_tools(model="gpt-4o")
context_manager = ToolContextManager()
options = ToolExecutorOptions(tools=tools, context_manager=context_manager)
executor = ToolExecutor(options=options)

# Execute
task = Task(id="task-1", description="Search for AAPL news", ...)
success = await executor.execute_tools(task, query_id="query-1", callbacks=MyCallbacks())
```

---

## Future Refactor Plan

Following the original [dexter](https://github.com/virattt/dexter) architecture, the tool execution functionality can be absorbed directly into the `Agent` class.

### Motivation

The original author removed `tool_executor.ts` because:
- **Reduced indirection** - Agent can directly call `tool.invoke()`
- **Simpler architecture** - Fewer classes to manage
- **Tighter integration** - Tool execution is coupled with scratchpad/agent state

### Refactor Steps

#### Phase 1: Add Tool Methods to Agent

```python
class Agent:
    def __init__(self, tools: list[StructuredTool]):
        self.tools = tools
        self.tool_map = {t.name: t for t in tools}

    async def execute_tool_call(
        self,
        tool_name: str,
        tool_args: dict,
        query: str,
        scratchpad: Scratchpad,
    ) -> None:
        """Execute a single tool and add result to scratchpad."""
        tool = self.tool_map.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")

        result = await tool.ainvoke(tool_args)
        summary = await self.summarize_tool_result(query, tool_name, tool_args, result)
        scratchpad.add_tool_result(tool_name, tool_args, result, summary)

    async def execute_tool_calls(
        self,
        response: AIMessage,
        query: str,
        scratchpad: Scratchpad,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute all tool calls from LLM response."""
        for tool_call in response.tool_calls:
            yield {"type": "tool_start", "tool": tool_call.name}
            try:
                await self.execute_tool_call(tool_call.name, tool_call.args, query, scratchpad)
                yield {"type": "tool_end", "tool": tool_call.name}
            except Exception as e:
                yield {"type": "tool_error", "error": str(e)}
```

#### Phase 2: Update Imports

```python
# Before
from src.agent.tool_executor import ToolExecutor

# After (remove tool_executor dependency)
# Tools managed directly in Agent
```

#### Phase 3: Deprecate ToolExecutor

1. Mark `tool_executor.py` as deprecated
2. Move `select_tools()` logic into Agent if needed
3. Keep context management separate (still use `ToolContextManager`)

### Migration Path

| Step | Action | Breaking Change |
|------|--------|-----------------|
| 1 | Add tool methods to `Agent` class | No |
| 2 | Update callers to use `Agent.execute_tool_calls()` | No |
| 3 | Remove `ToolExecutor` imports | Yes |
| 4 | Delete `tool_executor.py` | Yes |

### Trade-offs

| Current (ToolExecutor) | Refactored (Agent-only) |
|------------------------|-------------------------|
| Clear separation of concerns | More cohesive but less modular |
| Easier to test in isolation | Testing requires Agent setup |
| Can swap implementations | Tightly coupled to Agent |
| More files/boilerplate | Simpler, less indirection |

### Recommendation

**Keep current design** if:
- You plan to have multiple agent types with different tool strategies
- You want to test tool execution independently
- You value modularity over simplicity

**Refactor to Agent-only** if:
- You only need one agent implementation
- You prefer simpler architecture
- You want to match the original dexter design

---

## Dependencies

- `langchain-core` - Tool abstractions
- `pydantic` - Data validation
- `asyncio` - Async tool execution
- `src/tools` - Tool registry
- `src/utils.context` - Context management
- `src.utils.logger` - Logging
