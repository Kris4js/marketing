"""
Session Manager

Core design decisions:

1. Why JSONL instead of single JSON file?
   - JSONL (JSON Lines) writes one message per line, append-only
   - Pros: Write is O(1), no need to read entire file before writing
   - Pros: File corruption only affects single line, better fault tolerance
   - Pros: Can use `tail -f` for real-time monitoring

2. Why memory cache + disk persistence (dual-write)?
   - Memory cache: Avoids disk read on every get(), better performance
   - Disk persistence: Can recover context after agent restart
   - Write to both simultaneously to maintain consistency

3. Session key security handling
   - Users might pass malicious sessionKey (e.g., "../../../etc/passwd")
   - Must sanitize to safe filename
"""

import json
import re
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import quote, unquote

import aiofiles
from pydantic import BaseModel, Field


# =============================================================================
# Session Key Utilities
# =============================================================================
#
# Session Key Specification (Simplified)
#
# OpenClaw's sessionKey is the core for routing and isolation.
# The key structure is: agent:<agentId>:<mainKey>
#
# Design goals:
# 1. Unified session naming to avoid state confusion between agents
# 2. Support explicit sessionKey and auto-complete from sessionId
# 3. Provide minimal "system-level" session domain structure
# =============================================================================

DEFAULT_AGENT_ID = "main"
DEFAULT_MAIN_KEY = "main"

VALID_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$", re.IGNORECASE)
INVALID_CHARS_RE = re.compile(r"[^a-z0-9_-]+")
LEADING_DASH_RE = re.compile(r"^-+")
TRAILING_DASH_RE = re.compile(r"-+$")


class ParsedSessionKey(NamedTuple):
    """Parsed agent session key."""

    agent_id: str
    rest: str


def _normalize_token(value: str | None) -> str:
    """Normalize a token value to lowercase trimmed string."""
    return (value or "").strip().lower()


def normalize_agent_id(value: str | None) -> str:
    """
    Normalize agent ID to a valid identifier.

    - Empty/None returns DEFAULT_AGENT_ID
    - Valid IDs are returned lowercased
    - Invalid characters are replaced with dashes
    """
    trimmed = (value or "").strip()
    if not trimmed:
        return DEFAULT_AGENT_ID
    if VALID_ID_RE.match(trimmed):
        return trimmed.lower()
    # Sanitize invalid characters
    normalized = trimmed.lower()
    normalized = INVALID_CHARS_RE.sub("-", normalized)
    normalized = LEADING_DASH_RE.sub("", normalized)
    normalized = TRAILING_DASH_RE.sub("", normalized)
    normalized = normalized[:64]
    return normalized or DEFAULT_AGENT_ID


def normalize_main_key(value: str | None) -> str:
    """Normalize main key, defaulting to DEFAULT_MAIN_KEY if empty."""
    trimmed = (value or "").strip()
    return trimmed.lower() if trimmed else DEFAULT_MAIN_KEY


def build_agent_main_session_key(
    agent_id: str,
    main_key: str | None = None,
) -> str:
    """
    Build the main session key for an agent.

    Returns: "agent:<agent_id>:<main_key>"
    """
    agent_id = normalize_agent_id(agent_id)
    main_key = normalize_main_key(main_key)
    return f"agent:{agent_id}:{main_key}"


def parse_agent_session_key(session_key: str | None) -> ParsedSessionKey | None:
    """
    Parse a session key into agent_id and rest components.

    Expected format: "agent:<agent_id>:<rest>"
    Returns None if format is invalid.
    """
    raw = (session_key or "").strip()
    if not raw:
        return None
    parts = [p for p in raw.split(":") if p]
    if len(parts) < 3 or parts[0].lower() != "agent":
        return None
    agent_id = normalize_agent_id(parts[1])
    rest = ":".join(parts[2:]).strip()
    if not rest:
        return None
    return ParsedSessionKey(agent_id=agent_id, rest=rest)


def is_subagent_session_key(session_key: str | None) -> bool:
    """Check if session key belongs to a subagent."""
    parsed = parse_agent_session_key(session_key)
    if not parsed or not parsed.rest:
        return False
    return parsed.rest.strip().lower().startswith("subagent:")


def resolve_agent_id_from_session_key(session_key: str | None) -> str:
    """Extract and normalize agent ID from session key."""
    parsed = parse_agent_session_key(session_key)
    return normalize_agent_id(parsed.agent_id if parsed else DEFAULT_AGENT_ID)


def to_agent_store_session_key(
    agent_id: str,
    request_key: str | None,
    main_key: str | None = None,
) -> str:
    """
    Convert a request key to a full agent store session key.

    - Empty/default keys return the main session key
    - Keys starting with "agent:" are returned as-is (lowercased)
    - Other keys are prefixed with "agent:<agent_id>:"
    """
    raw = (request_key or "").strip()
    if not raw or _normalize_token(raw) == DEFAULT_MAIN_KEY:
        return build_agent_main_session_key(agent_id, main_key)
    lowered = raw.lower()
    if lowered.startswith("agent:"):
        return lowered
    return f"agent:{normalize_agent_id(agent_id)}:{lowered}"


def resolve_session_key(
    agent_id: str | None = None,
    session_id: str | None = None,
    session_key: str | None = None,
) -> str:
    """
    Unified entry point: resolve sessionId/sessionKey to a normalized sessionKey.

    Priority:
    1. Explicit session_key if provided
    2. session_id converted to session_key
    3. Default main session key
    """
    agent_id = normalize_agent_id(agent_id or DEFAULT_AGENT_ID)
    explicit = (session_key or "").strip()
    if explicit:
        return to_agent_store_session_key(agent_id, explicit)
    session_id = (session_id or "").strip()
    if session_id:
        return to_agent_store_session_key(agent_id, session_id)
    return build_agent_main_session_key(agent_id, DEFAULT_MAIN_KEY)


class ContentBlock(BaseModel):
    """
    Content block structure.
    Supports text, tool_use, and tool_result types.
    """

    type: str = Field(..., description="Type: text, tool_use, or tool_result")
    text: str | None = Field(default=None, description="Text content (when type=text)")
    id: str | None = Field(
        default=None, description="Tool call ID (generated by API when type=tool_use)"
    )
    name: str | None = Field(default=None, description="Tool name (when type=tool_use)")
    input: dict[str, Any] | None = Field(
        default=None, description="Tool input parameters (when type=tool_use)"
    )
    tool_use_id: str | None = Field(
        default=None, description="Associated tool call ID (when type=tool_result)"
    )
    content: str | None = Field(
        default=None, description="Tool execution result (when type=tool_result)"
    )


class Message(BaseModel):
    """
    Message structure.
    Compatible with Anthropic API's MessageParam.
    """

    role: str = Field(..., description="Role: user or assistant")
    content: str | list[ContentBlock] = Field(
        ...,
        description="Content: plain text or list of content blocks (including tool calls)",
    )
    timestamp: int = Field(..., description="Timestamp for sorting and debugging")


class SessionManager:
    """
    Session manager with memory cache and JSONL persistence.
    """

    def __init__(self, base_dir: str = "./.mini-agent/sessions") -> None:
        self.base_dir: Path = Path(base_dir)
        self._cache: dict[str, list[Message]] = {}

    def _get_path(self, session_key: str) -> Path:
        """
        Get session file path.

        Security: Uses URL encoding for session_key.
        Prevents path injection attacks (e.g., session_key = "../../../etc/passwd")
        """
        safe_id = quote(session_key, safe="")
        return self.base_dir / f"{safe_id}.jsonl"

    def _get_legacy_path(self, session_key: str) -> Path:
        """Get legacy path (underscore replacement) for backwards compatibility."""
        import re

        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", session_key)
        return self.base_dir / f"{safe_id}.jsonl"

    async def load(self, session_key: str) -> list[Message]:
        """
        Load session history.

        Reads from memory cache first, loads from disk on cache miss.
        This is the typical Cache-Aside pattern.
        """
        # 1. Check cache
        if session_key in self._cache:
            return self._cache[session_key]

        # 2. Load JSONL file from disk
        file_path = self._get_path(session_key)
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                messages = [
                    Message(**json.loads(line))
                    for line in content.split("\n")
                    if line.strip()  # Skip empty lines
                ]
                # 3. Write to cache
                self._cache[session_key] = messages
                return messages
        except FileNotFoundError:
            # Try legacy path (underscore replacement)
            try:
                legacy_path = self._get_legacy_path(session_key)
                async with aiofiles.open(legacy_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    messages = [
                        Message(**json.loads(line))
                        for line in content.split("\n")
                        if line.strip()
                    ]
                    self._cache[session_key] = messages
                    return messages
            except FileNotFoundError:
                # File doesn't exist, return empty list
                self._cache[session_key] = []
                return []

    async def append(self, session_key: str, message: Message) -> None:
        """
        Append message.

        Dual-write strategy:
        1. Update memory cache first (ensures subsequent get() reads immediately)
        2. Then append to disk (ensures persistence)

        Why appendFile instead of writeFile?
        - appendFile is append-only, no need to read entire file
        - Write is O(1), regardless of file size
        """
        # 1. Update memory cache
        if session_key not in self._cache:
            self._cache[session_key] = []
        self._cache[session_key].append(message)

        # 2. Append to disk
        file_path = self._get_path(session_key)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
            await f.write(message.model_dump_json() + "\n")

    def get(self, session_key: str) -> list[Message]:
        """
        Get session messages (memory only).
        For fast reads without disk IO.
        """
        return self._cache.get(session_key, [])

    async def clear(self, session_key: str) -> None:
        """
        Clear session.
        Clears both memory cache and disk file.
        """
        self._cache.pop(session_key, None)

        file_path = self._get_path(session_key)
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass

        # Also try to remove legacy file
        legacy_path = self._get_legacy_path(session_key)
        if legacy_path != file_path:
            try:
                legacy_path.unlink()
            except FileNotFoundError:
                pass

    async def list_sessions(self) -> list[str]:
        """
        List all sessions.
        Scans directory for .jsonl files.
        """
        try:
            files = list(self.base_dir.iterdir())
            return [unquote(f.stem) for f in files if f.suffix == ".jsonl"]
        except FileNotFoundError:
            return []
