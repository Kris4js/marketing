"""
Core Agent implementation.

This is the generic agent engine. It handles:
- The main agent loop (query → tools → answer)
- Tool execution and result tracking
- Context compaction with LLM summaries
- Event yielding for UI updates
- Session persistence (via SessionManager)
- Tool context disk persistence (via ToolContextManager)
- Long-term memory search (via MemoryManager)

Customize behavior by modifying prompts.py - this file stays unchanged.
"""

import json
import time
from typing import AsyncGenerator, Any, Optional

from langchain_core.messages import AIMessage

from src.model.llm import llm_call
from src.tools.registry import get_tools

from src.agent.scratchpad import Scratchpad, ToolContextWithSummary
from src.agent.types import (
    AgentConfig,
    AgentEvent,
    ThinkingEvent,
    ToolStartEvent,
    ToolEndEvent,
    ToolErrorEvent,
    ToolLimitEvent,
    AnswerStartEvent,
    DoneEvent,
)
from src.agent.prompts import (
    SYSTEM_PROMPT,
    build_iteration_prompt,
    build_final_answer_prompt,
    build_tool_summary_prompt,
    build_context_selection_prompt,
    get_tool_description,
)

# Utility integrations
from src.utils.logger import get_logger
from src.utils.session import SessionManager, Message, resolve_session_key
from src.utils.context import ToolContextManager
from src.utils.memory import MemoryManager

log = get_logger(__name__)


# Token budget for final answer context
TOKEN_BUDGET = 8000


def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token)."""
    return len(text) // 4


def extract_text_content(response: AIMessage) -> str:
    """Extract text content from AIMessage."""
    if isinstance(response.content, str):
        return response.content
    if isinstance(response.content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response.content
        )
    return ""


def has_tool_calls(response: AIMessage) -> bool:
    """Check if response has tool calls."""
    return bool(response.tool_calls)


class Agent:
    """
    Core agent that handles the agent loop and tool execution.

    Integrates:
    - SessionManager: Conversation history persistence (JSONL)
    - ToolContextManager: Tool result disk persistence
    - MemoryManager: Long-term memory search

    Usage:
        agent = Agent.create()
        async for event in agent.run("What is the weather?", session_key="user123"):
            print(event)
    """

    def __init__(
        self,
        config: AgentConfig,
        tools: list[Any],
        system_prompt: str,
        session_manager: SessionManager,
        context_manager: ToolContextManager,
        memory_manager: MemoryManager,
    ):
        self.model = config.model
        self.fast_model = config.fast_model or config.model
        self.max_iterations = config.max_iterations
        self.tools = tools
        self.tool_map = {t.name: t for t in tools}
        self.system_prompt = system_prompt

        # Utility managers
        self.session_manager = session_manager
        self.context_manager = context_manager
        self.memory_manager = memory_manager

        log.info(
            f"Agent initialized with model={self.model}, max_iterations={self.max_iterations}"
        )

    @classmethod
    def create(
        cls,
        config: Optional[AgentConfig] = None,
        base_dir: str = ".mini-agent",
    ) -> "Agent":
        """
        Create a new Agent instance with tools and utilities.

        Args:
            config: Agent configuration (model, max_iterations, etc.)
            base_dir: Base directory for persistence (.mini-agent by default)
        """
        config = config or AgentConfig()
        tools = get_tools(config.model)

        # Initialize utility managers
        session_manager = SessionManager(base_dir=f"{base_dir}/sessions")
        context_manager = ToolContextManager(
            context_dir=f"{base_dir}/context", model=config.model
        )
        memory_manager = MemoryManager(base_dir=f"{base_dir}/memory")

        log.debug(f"Created utility managers at base_dir={base_dir}")

        return cls(
            config,
            tools,
            SYSTEM_PROMPT,
            session_manager,
            context_manager,
            memory_manager,
        )

    async def run(
        self,
        query: str,
        session_key: Optional[str] = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Run the agent and yield events for real-time UI updates.

        Args:
            query: The user's query
            session_key: Optional session key for conversation persistence.
                         If provided, loads history and saves new messages.

        Yields:
            AgentEvent objects for UI updates
        """
        # Normalize session key for consistent storage
        if session_key:
            session_key = resolve_session_key(session_id=session_key)

        log.info(
            f"Starting agent run: query='{query[:50]}...' session_key={session_key}"
        )

        if not self.tools:
            log.warning("No tools available")
            yield DoneEvent(
                answer="No tools available. Please check your configuration.",
                tool_calls=[],
                iterations=0,
            )
            return

        # Generate query_id for context tracking
        query_id = self.context_manager.hash_query(query)
        log.debug(f"Generated query_id={query_id}")

        # Create scratchpad - single source of truth for this query
        scratchpad = Scratchpad(query)

        # Load session history and build initial prompt
        session_messages = await self._load_session(session_key) if session_key else []
        memory_context = await self._search_memory(query)
        current_prompt = self._build_initial_prompt(
            query, session_messages, memory_context
        )

        # Save user message to session
        if session_key:
            await self._save_user_message(session_key, query)

        iteration = 0

        # Main agent loop
        while iteration < self.max_iterations:
            iteration += 1
            log.debug(f"Iteration {iteration}/{self.max_iterations}")

            # Call LLM
            response = await self._call_model(current_prompt, use_tools=True)

            # Handle non-AIMessage response
            if isinstance(response, str):
                log.debug("Received string response from LLM")
                yield AnswerStartEvent()
                await self._finalize_run(session_key, query, response, scratchpad)
                yield DoneEvent(
                    answer=response,
                    tool_calls=scratchpad.get_tool_call_records(),
                    iterations=iteration,
                )
                return

            response_text = extract_text_content(response)

            # Emit thinking if there are also tool calls
            if response_text and has_tool_calls(response):
                scratchpad.add_thinking(response_text)
                yield ThinkingEvent(message=response_text)

            # No tool calls = ready to answer
            if not has_tool_calls(response):
                # Direct response (greetings, simple questions)
                if not scratchpad.has_tool_results() and response_text:
                    log.debug("Direct response (no tool results)")
                    yield AnswerStartEvent()
                    await self._finalize_run(
                        session_key, query, response_text, scratchpad
                    )
                    yield DoneEvent(
                        answer=response_text,
                        tool_calls=[],
                        iterations=iteration,
                    )
                    return

                # Generate final answer with full context
                log.debug("Generating final answer with tool context")
                full_context = await self._build_full_context(query, scratchpad)
                final_prompt = build_final_answer_prompt(query, full_context)

                yield AnswerStartEvent()
                final_response = await self._call_model(final_prompt, use_tools=False)
                answer = (
                    final_response
                    if isinstance(final_response, str)
                    else extract_text_content(final_response)
                )

                await self._finalize_run(session_key, query, answer, scratchpad)
                yield DoneEvent(
                    answer=answer,
                    tool_calls=scratchpad.get_tool_call_records(),
                    iterations=iteration,
                )
                return

            # Execute tools and yield events
            async for event in self._execute_tool_calls(
                response, query, query_id, scratchpad
            ):
                yield event

            # Build iteration prompt with summaries
            current_prompt = build_iteration_prompt(
                query,
                scratchpad.get_tool_summaries(),
                scratchpad.format_tool_usage_for_prompt(),
            )

        # Max iterations reached - still generate answer
        log.warning(f"Max iterations ({self.max_iterations}) reached")
        full_context = await self._build_full_context(query, scratchpad)
        final_prompt = build_final_answer_prompt(query, full_context)

        yield AnswerStartEvent()
        final_response = await self._call_model(final_prompt, use_tools=False)
        answer = (
            final_response
            if isinstance(final_response, str)
            else extract_text_content(final_response)
        )

        await self._finalize_run(session_key, query, answer or "", scratchpad)
        yield DoneEvent(
            answer=answer or f"Reached maximum iterations ({self.max_iterations}).",
            tool_calls=scratchpad.get_tool_call_records(),
            iterations=iteration,
        )

    async def _call_model(
        self,
        prompt: str,
        use_tools: bool = True,
    ) -> AIMessage | str:
        """Call the LLM with the current prompt."""
        log.debug(f"Calling LLM: use_tools={use_tools}, prompt_len={len(prompt)}")
        return await llm_call(
            prompt=prompt,
            system_prompt=self.system_prompt,
            model=self.model,
            tools=self.tools if use_tools else None,
        )

    # ========================================================================
    # Session & Memory Methods
    # ========================================================================

    async def _load_session(self, session_key: str) -> list[Message]:
        """Load conversation history from session."""
        messages = await self.session_manager.load(session_key)
        log.debug(f"Loaded {len(messages)} messages from session={session_key}")
        return messages

    async def _save_user_message(self, session_key: str, query: str) -> None:
        """Save user message to session."""
        message = Message(
            role="user",
            content=query,
            timestamp=int(time.time() * 1000),
        )
        await self.session_manager.append(session_key, message)
        log.debug(f"Saved user message to session={session_key}")

    async def _save_assistant_message(self, session_key: str, answer: str) -> None:
        """Save assistant message to session."""
        message = Message(
            role="assistant",
            content=answer,
            timestamp=int(time.time() * 1000),
        )
        await self.session_manager.append(session_key, message)
        log.debug(f"Saved assistant message to session={session_key}")

    async def _search_memory(self, query: str, limit: int = 3) -> list[str]:
        """Search long-term memory for relevant context."""
        try:
            results = await self.memory_manager.search(query, limit=limit)
            if results:
                log.debug(f"Found {len(results)} memory results for query")
                return [r.snippet for r in results]
        except Exception as e:
            log.warning(f"Memory search failed: {e}")
        return []

    async def _save_to_memory(
        self,
        query: str,
        answer: str,
        scratchpad: Scratchpad,
    ) -> None:
        """Save important information to long-term memory."""
        # Save the Q&A pair as a memory entry
        if answer and len(answer) > 50:  # Skip trivial responses
            content = f"Q: {query}\nA: {answer[:500]}"
            tags = ["qa", "conversation"]

            # Add tool names as tags
            tool_records = scratchpad.get_tool_call_records()
            for record in tool_records[:5]:
                tags.append(f"tool:{record.tool}")

            await self.memory_manager.add(content, source="agent", tags=tags)
            log.debug(f"Saved Q&A to memory with tags={tags}")

    async def _finalize_run(
        self,
        session_key: Optional[str],
        query: str,
        answer: str,
        scratchpad: Scratchpad,
    ) -> None:
        """Finalize the run: save session and memory."""
        if session_key:
            await self._save_assistant_message(session_key, answer)

        # Save to long-term memory (only meaningful responses)
        if scratchpad.has_tool_results():
            await self._save_to_memory(query, answer, scratchpad)

        log.info(f"Run completed: answer_len={len(answer)}")

    async def _summarize_tool_result(
        self,
        query: str,
        tool_name: str,
        tool_args: dict[str, Any],
        result: str,
    ) -> str:
        """Generate LLM summary of a tool result for context compaction."""
        log.debug(f"Summarizing {tool_name} result (len={len(result)})")
        prompt = build_tool_summary_prompt(query, tool_name, tool_args, result)
        response = await llm_call(
            prompt=prompt,
            system_prompt="You are a concise data summarizer.",
            model=self.fast_model,
        )
        return str(response.content) if hasattr(response, "content") else str(response)

    async def _execute_tool_calls(
        self,
        response: AIMessage,
        query: str,
        query_id: str,
        scratchpad: Scratchpad,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute all tool calls from an LLM response."""
        log.debug(f"Executing {len(response.tool_calls)} tool calls")
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})

            # Deduplicate skill calls
            if tool_name == "skill":
                skill_name = tool_args.get("skill", "")
                if scratchpad.has_executed_skill(skill_name):
                    log.debug(f"Skipping duplicate skill call: {skill_name}")
                    continue

            async for event in self._execute_single_tool(
                tool_name, tool_args, query, query_id, scratchpad
            ):
                yield event

    async def _execute_single_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        query: str,
        query_id: str,
        scratchpad: Scratchpad,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute a single tool call and add result to scratchpad."""
        # Extract query for similarity detection
        tool_query = self._extract_query_from_args(tool_args)

        # Check tool limits
        limit_check = scratchpad.can_call_tool(tool_name, tool_query)
        if limit_check.warning:
            log.warning(
                f"Tool limit warning for {tool_name}: {limit_check.warning[:100]}"
            )
            yield ToolLimitEvent(
                tool=tool_name,
                warning=limit_check.warning,
                blocked=False,
            )

        log.info(f"Executing tool: {tool_name}")
        yield ToolStartEvent(tool=tool_name, args=tool_args)
        start_time = time.time()

        try:
            tool = self.tool_map.get(tool_name)
            if not tool:
                raise ValueError(f"Tool '{tool_name}' not found")

            raw_result = await tool.ainvoke(tool_args)
            result = (
                raw_result if isinstance(raw_result, str) else json.dumps(raw_result)
            )
            duration = int((time.time() - start_time) * 1000)

            log.info(
                f"Tool {tool_name} completed in {duration}ms (result_len={len(result)})"
            )

            yield ToolEndEvent(
                tool=tool_name,
                args=tool_args,
                result=result,
                duration=duration,
            )

            # Persist tool result to disk via ToolContextManager
            self.context_manager.save_context(
                tool_name=tool_name,
                args=tool_args,
                result=result,
                query_id=query_id,
            )

            # Record and summarize
            scratchpad.record_tool_call(tool_name, tool_query)
            llm_summary = await self._summarize_tool_result(
                query, tool_name, tool_args, result
            )
            scratchpad.add_tool_result(tool_name, tool_args, result, llm_summary)

        except Exception as e:
            error_message = str(e)
            log.error(f"Tool {tool_name} failed: {error_message}")
            yield ToolErrorEvent(tool=tool_name, error=error_message)

            scratchpad.record_tool_call(tool_name, tool_query)
            description = get_tool_description(tool_name, tool_args)
            error_summary = f"{description} [FAILED]: {error_message}"
            scratchpad.add_tool_result(
                tool_name, tool_args, f"Error: {error_message}", error_summary
            )

    def _extract_query_from_args(self, args: dict[str, Any]) -> Optional[str]:
        """Extract query string from tool arguments."""
        query_keys = ["query", "search", "question", "q", "text", "input"]
        for key in query_keys:
            if isinstance(args.get(key), str):
                return args[key]
        return None

    def _build_initial_prompt(
        self,
        query: str,
        session_messages: Optional[list[Message]] = None,
        memory_context: Optional[list[str]] = None,
    ) -> str:
        """Build initial prompt with conversation history and memory context."""
        parts = [f"Query: {query}"]

        # Add session history (last 5 exchanges)
        if session_messages:
            recent = session_messages[-10:]  # Last 10 messages (5 exchanges)
            if recent:
                history_lines = []
                for msg in recent:
                    role = "User" if msg.role == "user" else "Assistant"
                    content = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    history_lines.append(f"{role}: {content[:200]}...")
                parts.append("\n## Conversation History\n" + "\n".join(history_lines))

        # Add memory context (relevant past information)
        if memory_context:
            memory_text = "\n".join(f"- {m}" for m in memory_context)
            parts.append(f"\n## Relevant Context from Memory\n{memory_text}")

        return "\n".join(parts)

    async def _build_full_context(
        self,
        query: str,
        scratchpad: Scratchpad,
    ) -> str:
        """Build full context data for final answer generation."""
        contexts = scratchpad.get_full_contexts_with_summaries()

        if not contexts:
            return "No data was gathered."

        # Filter errors
        valid = [c for c in contexts if not c.result.startswith("Error:")]
        if not valid:
            return "No data was successfully gathered."

        # Check token budget
        total_tokens = sum(estimate_tokens(c.result) for c in valid)

        if total_tokens <= TOKEN_BUDGET:
            return self._format_full_contexts(valid)

        # Over budget - use LLM selection
        try:
            return await self._build_llm_selected_context(query, valid)
        except Exception:
            return self._format_summaries_only(valid)

    async def _build_llm_selected_context(
        self,
        query: str,
        contexts: list[ToolContextWithSummary],
    ) -> str:
        """Use LLM to select which tool results need full data."""
        summaries = [
            {
                "index": c.index,
                "tool_name": c.tool_name,
                "summary": c.llm_summary,
                "token_cost": estimate_tokens(c.result),
            }
            for c in contexts
        ]

        prompt = build_context_selection_prompt(query, summaries)
        response = await llm_call(
            prompt=prompt,
            system_prompt="Return only valid JSON array.",
            model=self.fast_model,
        )

        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )
        selected = set(json.loads(response_text))

        # Build mixed context
        used_tokens = 0
        full_results = []
        summary_results = []

        for ctx in contexts:
            tokens = estimate_tokens(ctx.result)
            if ctx.index in selected and used_tokens + tokens <= TOKEN_BUDGET:
                full_results.append(self._format_single_context(ctx, use_full=True))
                used_tokens += tokens
            else:
                summary_results.append(self._format_single_context(ctx, use_full=False))

        return self._combine_context_sections(full_results, summary_results)

    def _format_full_contexts(self, contexts: list[ToolContextWithSummary]) -> str:
        """Format all contexts with full data."""
        return "\n\n".join(
            self._format_single_context(c, use_full=True) for c in contexts
        )

    def _format_summaries_only(self, contexts: list[ToolContextWithSummary]) -> str:
        """Format all contexts with summaries only."""
        formatted = [self._format_single_context(c, use_full=False) for c in contexts]
        return "## Data Summaries\n\n" + "\n\n".join(formatted)

    def _format_single_context(
        self,
        ctx: ToolContextWithSummary,
        use_full: bool,
    ) -> str:
        """Format a single context entry."""
        description = get_tool_description(ctx.tool_name, ctx.args)
        if use_full:
            try:
                formatted = json.dumps(json.loads(ctx.result), indent=2)
                return f"### {description}\n```json\n{formatted}\n```"
            except (json.JSONDecodeError, TypeError):
                return f"### {description}\n{ctx.result}"
        else:
            return f"### {description}\n{ctx.llm_summary}"

    def _combine_context_sections(
        self,
        full_results: list[str],
        summary_results: list[str],
    ) -> str:
        """Combine full data and summary sections."""
        output = ""
        if full_results:
            output += "## Full Data\n\n" + "\n\n".join(full_results)
        if summary_results:
            if output:
                output += "\n\n"
            output += "## Summary Data\n\n" + "\n\n".join(summary_results)
        return output

    async def reset(self, session_id_or_key: str) -> list[Message]:
        """Reset the session data for a given session key."""
        session_key = self.resolve_id_or_key(session_id_or_key)
        messages = await self.session_manager.load(session_key)
        await self.session_manager.clear(session_key)
        log.info(f"Reset session={session_key}, cleared {len(messages)} messages")
        return messages

    def resolve_id_or_key(self, session_id_or_key: str) -> str:
        """Resolve session ID or key to a session key."""
        return resolve_session_key(session_id=session_id_or_key)
