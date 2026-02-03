"""
Append-only scratchpad for tracking agent work on a query.

Uses JSONL format (newline-delimited JSON) for resilient appending.
Files are persisted in tmp/scratchpad/ for debugging/history.

This is the single source of truth for all agent work on a query.

Includes soft limit warnings to guide the LLM:
- Tool call counting with suggested limits (warnings, not blocks)
- Query similarity detection to help prevent retry loops
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

from .types import ToolCallRecord


# ============================================================================
# Data Types
# ============================================================================


@dataclass
class ToolContext:
    """Full context data for final answer generation."""

    tool_name: str
    args: dict[str, Any]
    result: str


@dataclass
class ToolContextWithSummary(ToolContext):
    """Tool context with LLM summary for selective inclusion."""

    llm_summary: str = ""
    index: int = 0  # For LLM to reference when selecting


@dataclass
class ScratchpadEntry:
    """A single entry in the scratchpad."""

    type: str  # 'init' | 'tool_result' | 'thinking'
    timestamp: str
    content: Optional[str] = None
    tool_name: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    result: Optional[Any] = None
    llm_summary: Optional[str] = None


@dataclass
class ToolLimitConfig:
    """Tool call limit configuration."""

    max_calls_per_tool: int = 3
    similarity_threshold: float = 0.7


@dataclass
class ToolUsageStatus:
    """Status of tool usage for graceful exit mechanism."""

    tool_name: str
    call_count: int
    max_calls: int
    remaining_calls: int
    recent_queries: list[str] = field(default_factory=list)
    is_blocked: bool = False
    block_reason: Optional[str] = None


@dataclass
class ToolLimitCheck:
    """Result of checking if a tool call can proceed."""

    allowed: bool = True
    warning: Optional[str] = None


# ============================================================================
# Scratchpad Implementation
# ============================================================================


class Scratchpad:
    """
    Append-only scratchpad for tracking agent work on a query.

    Uses JSONL format for resilient appending. Files are persisted
    in tmp/scratchpad/ for debugging/history.
    """

    def __init__(
        self,
        query: str,
        scratchpad_dir: str = "tmp/scratchpad",
        limit_config: Optional[ToolLimitConfig] = None,
    ):
        self.scratchpad_dir = scratchpad_dir
        self.limit_config = limit_config or ToolLimitConfig()

        # In-memory tracking for tool limits
        self.tool_call_counts: dict[str, int] = {}
        self.tool_queries: dict[str, list[str]] = {}

        # Ensure directory exists
        Path(self.scratchpad_dir).mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        query_hash = hashlib.md5(query.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.filepath = os.path.join(
            self.scratchpad_dir, f"{timestamp}_{query_hash}.jsonl"
        )

        # Write initial entry with the query
        self._append(
            ScratchpadEntry(
                type="init",
                timestamp=datetime.now().isoformat(),
                content=query,
            )
        )

    # ========================================================================
    # Core Methods
    # ========================================================================

    def add_tool_result(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: str,
        llm_summary: str,
    ) -> None:
        """Add a complete tool result with full data and LLM summary."""
        self._append(
            ScratchpadEntry(
                type="tool_result",
                timestamp=datetime.now().isoformat(),
                tool_name=tool_name,
                args=args,
                result=self._parse_result_safely(result),
                llm_summary=llm_summary,
            )
        )

    def add_thinking(self, thought: str) -> None:
        """Append thinking/reasoning."""
        self._append(
            ScratchpadEntry(
                type="thinking",
                timestamp=datetime.now().isoformat(),
                content=thought,
            )
        )

    # ========================================================================
    # Tool Limit / Graceful Exit Methods
    # ========================================================================

    def can_call_tool(
        self, tool_name: str, query: Optional[str] = None
    ) -> ToolLimitCheck:
        """
        Check if a tool call can proceed. Returns status with warning if limits exceeded.
        Note: Always allows the call but provides warnings to guide the LLM.
        """
        current_count = self.tool_call_counts.get(tool_name, 0)
        max_calls = self.limit_config.max_calls_per_tool

        # Check if over the suggested limit - warn but allow
        if current_count >= max_calls:
            return ToolLimitCheck(
                allowed=True,
                warning=(
                    f"Tool '{tool_name}' has been called {current_count} times "
                    f"(suggested limit: {max_calls}). If previous calls didn't return "
                    f"the needed data, consider: (1) trying a different tool, "
                    f"(2) using different search terms, or (3) proceeding with what "
                    f"you have and noting any data gaps to the user."
                ),
            )

        # Check query similarity if query provided
        if query:
            previous_queries = self.tool_queries.get(tool_name, [])
            similar_query = self._find_similar_query(query, previous_queries)

            if similar_query:
                remaining = max_calls - current_count
                return ToolLimitCheck(
                    allowed=True,
                    warning=(
                        f"This query is very similar to a previous '{tool_name}' call. "
                        f"You have {remaining} attempt(s) before reaching the suggested limit. "
                        f"If the tool isn't returning useful results, consider: "
                        f"(1) trying a different tool, (2) using different search terms, or "
                        f"(3) acknowledging the data limitation to the user."
                    ),
                )

        # Check if approaching limit (1 call remaining)
        if current_count == max_calls - 1:
            return ToolLimitCheck(
                allowed=True,
                warning=(
                    f"You are approaching the suggested limit for '{tool_name}' "
                    f"({current_count + 1}/{max_calls}). If this doesn't return "
                    f"the needed data, consider trying a different approach."
                ),
            )

        return ToolLimitCheck(allowed=True)

    def record_tool_call(self, tool_name: str, query: Optional[str] = None) -> None:
        """Record a tool call attempt. Call this AFTER the tool executes."""
        # Update call count
        current_count = self.tool_call_counts.get(tool_name, 0)
        self.tool_call_counts[tool_name] = current_count + 1

        # Track query if provided
        if query:
            if tool_name not in self.tool_queries:
                self.tool_queries[tool_name] = []
            self.tool_queries[tool_name].append(query)

    def get_tool_usage_status(self) -> list[ToolUsageStatus]:
        """Get usage status for all tools that have been called."""
        statuses: list[ToolUsageStatus] = []

        for tool_name, call_count in self.tool_call_counts.items():
            max_calls = self.limit_config.max_calls_per_tool
            remaining_calls = max(0, max_calls - call_count)
            recent_queries = self.tool_queries.get(tool_name, [])
            over_limit = call_count >= max_calls

            statuses.append(
                ToolUsageStatus(
                    tool_name=tool_name,
                    call_count=call_count,
                    max_calls=max_calls,
                    remaining_calls=remaining_calls,
                    recent_queries=recent_queries[-3:],  # Last 3 queries
                    is_blocked=False,  # Never block, just warn
                    block_reason=(
                        f"Over suggested limit of {max_calls} calls"
                        if over_limit
                        else None
                    ),
                )
            )

        return statuses

    def format_tool_usage_for_prompt(self) -> Optional[str]:
        """Format tool usage status for injection into prompts."""
        statuses = self.get_tool_usage_status()

        if not statuses:
            return None

        lines = []
        for s in statuses:
            if s.call_count >= s.max_calls:
                status = f"{s.call_count} calls (over suggested limit of {s.max_calls})"
            else:
                status = f"{s.call_count}/{s.max_calls} calls"
            lines.append(f"- {s.tool_name}: {status}")

        return (
            "## Tool Usage This Query\n\n"
            + "\n".join(lines)
            + "\n\nNote: If a tool isn't returning useful results after several "
            "attempts, consider trying a different tool/approach."
        )

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_tool_summaries(self) -> list[str]:
        """Get all LLM summaries for building the iteration prompt.

        Returns formatted strings like "tool_name(arg=val): summary"
        so the LLM knows which tools were already called.
        """
        summaries = []
        for e in self._read_entries():
            if e.type == "tool_result" and e.llm_summary and e.tool_name:
                # Format: "tool_name(args): summary"
                args_str = ""
                if e.args:
                    args_str = ", ".join(f"{k}={v}" for k, v in list(e.args.items())[:2])
                tool_desc = f"{e.tool_name}({args_str})" if args_str else e.tool_name
                summaries.append(f"{tool_desc}: {e.llm_summary}")
        return summaries

    def get_tool_call_records(self) -> list[ToolCallRecord]:
        """Get tool call records for DoneEvent."""
        return [
            ToolCallRecord(
                tool=e.tool_name,
                args=e.args or {},
                result=self._stringify_result(e.result),
            )
            for e in self._read_entries()
            if e.type == "tool_result" and e.tool_name
        ]

    def get_full_contexts(self) -> list[ToolContext]:
        """Get full contexts for final answer generation."""
        return [
            ToolContext(
                tool_name=e.tool_name,
                args=e.args or {},
                result=self._stringify_result(e.result),
            )
            for e in self._read_entries()
            if e.type == "tool_result" and e.tool_name and e.result
        ]

    def get_full_contexts_with_summaries(self) -> list[ToolContextWithSummary]:
        """Get full contexts with LLM summaries for selective inclusion."""
        contexts = []
        for i, e in enumerate(self._read_entries()):
            if e.type == "tool_result" and e.tool_name and e.result:
                contexts.append(
                    ToolContextWithSummary(
                        tool_name=e.tool_name,
                        args=e.args or {},
                        result=self._stringify_result(e.result),
                        llm_summary=e.llm_summary or "",
                        index=i,
                    )
                )
        return contexts

    def has_tool_results(self) -> bool:
        """Check if any tool results have been recorded."""
        return any(e.type == "tool_result" for e in self._read_entries())

    def has_executed_skill(self, skill_name: str) -> bool:
        """Check if a skill has already been executed in this query."""
        return any(
            e.type == "tool_result"
            and e.tool_name == "skill"
            and e.args
            and e.args.get("skill") == skill_name
            for e in self._read_entries()
        )

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _append(self, entry: ScratchpadEntry) -> None:
        """Append-only write."""
        data = {
            "type": entry.type,
            "timestamp": entry.timestamp,
        }
        if entry.content is not None:
            data["content"] = entry.content
        if entry.tool_name is not None:
            data["toolName"] = entry.tool_name
        if entry.args is not None:
            data["args"] = entry.args
        if entry.result is not None:
            data["result"] = entry.result
        if entry.llm_summary is not None:
            data["llmSummary"] = entry.llm_summary

        with open(self.filepath, "a") as f:
            f.write(json.dumps(data) + "\n")

    def _read_entries(self) -> list[ScratchpadEntry]:
        """Read all entries from the log."""
        if not os.path.exists(self.filepath):
            return []

        entries = []
        with open(self.filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    entries.append(
                        ScratchpadEntry(
                            type=data.get("type", ""),
                            timestamp=data.get("timestamp", ""),
                            content=data.get("content"),
                            tool_name=data.get("toolName"),
                            args=data.get("args"),
                            result=data.get("result"),
                            llm_summary=data.get("llmSummary"),
                        )
                    )
        return entries

    def _parse_result_safely(self, result: str) -> Any:
        """Safely parse a result string as JSON if possible."""
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result

    def _stringify_result(self, result: Any) -> str:
        """Convert a result back to string."""
        if isinstance(result, str):
            return result
        return json.dumps(result)

    def _find_similar_query(
        self, new_query: str, previous_queries: list[str]
    ) -> Optional[str]:
        """Check if a query is too similar to previous queries."""
        new_words = self._tokenize(new_query)

        for prev_query in previous_queries:
            prev_words = self._tokenize(prev_query)

            # Check for exact match first (highest similarity)
            if new_query == prev_query:
                return prev_query

            similarity = self._calculate_similarity(new_words, prev_words)

            if similarity >= self.limit_config.similarity_threshold:
                return prev_query

        return None

    def _tokenize(self, query: str) -> set[str]:
        """Tokenize a query into normalized words for similarity comparison."""
        import re

        # Use Unicode-aware pattern that works with Chinese characters
        words = re.sub(r"[^\w\s]", " ", query.lower(), flags=re.UNICODE).split()
        return {
            w for w in words if len(w) > 1
        }  # Reduced from 2 to 1 for Chinese support

    def _calculate_similarity(self, set1: set[str], set2: set[str]) -> float:
        """Calculate word overlap similarity (Jaccard)."""
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0
