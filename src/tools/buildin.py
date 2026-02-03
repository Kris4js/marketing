import asyncio
import os
import re

import aiofiles
from pydantic import BaseModel, Field
from langchain_core.tools import tool


class ReadToolInput(BaseModel):
    """Input for read_tool."""

    filepath: str = Field(
        ...,
        description="Path to the file to read",
    )
    limit: int = Field(
        500,
        description="Maximum number of lines to read from the file",
    )


class WriteToolInput(BaseModel):
    """Input for write_tool."""

    filepath: str = Field(
        ...,
        description="Path to the file to write",
    )
    content: str = Field(
        ...,
        description="Content to write to the file",
    )


class EditToolInput(BaseModel):
    """Input for edit_tool."""

    filepath: str = Field(
        ...,
        description="Path to the file to edit",
    )
    old_string: str = Field(
        ...,
        description="Old string to be replaced (exact match, including whitespace)",
    )
    new_string: str = Field(
        ...,
        description="New string to replace with",
    )


class ExecToolInput(BaseModel):
    """Input for exec_tool."""

    command: str = Field(
        ...,
        description="Shell command to execute",
    )
    timeout: int = Field(
        30000,
        description="Timeout in milliseconds, default 30000 (30 seconds)",
    )


class ListToolInput(BaseModel):
    """Input for list_tool."""

    path: str = Field(
        ".",
        description="Directory path, default current directory",
    )
    pattern: str = Field(
        None,
        description="Filter pattern like *.py or *.ts",
    )


class GrepToolInput(BaseModel):
    """Input for grep_tool."""

    pattern: str = Field(
        ...,
        description="Regular expression to search for",
    )
    path: str = Field(
        ".",
        description="Search path, default current directory",
    )


class MemorySearchInput(BaseModel):
    """Input for memory_search_tool."""

    query: str = Field(
        ...,
        description="Search query or keywords",
    )
    limit: int = Field(
        5,
        description="Number of results to return, default 5",
    )


class MemoryGetInput(BaseModel):
    """Input for memory_get_tool."""

    id: str = Field(
        ...,
        description="Memory ID from memory_search results",
    )


class SessionsSpawnInput(BaseModel):
    """Input for sessions_spawn_tool."""

    task: str = Field(
        ...,
        description="Task description for sub-agent",
    )
    label: str = Field(
        None,
        description="Optional label for the session",
    )
    cleanup: str = Field(
        None,
        description="Whether to cleanup session after completion: keep|delete",
    )


# ============== File Tools ==============


@tool(
    args_schema=ReadToolInput,
    description="Read file contents and return as text with line numbers.",
)
async def read_tool(filepath: str, limit: int = 500) -> str:
    """Read the contents of a file and return as text with line numbers.

    Why limit to 500 lines?
    - LLM context window is limited (Claude ~200K tokens)
    - Too much content consumes valuable context space
    - 500 lines is usually enough to understand file structure
    - LLM can call multiple times with offset if needed

    Why add line numbers?
    - Helps LLM reference specific locations ("fix line 42")
    - Helps edit tool pinpoint exact location
    """
    # Safe: resolve path to ensure it's within workspace
    filepath = os.path.abspath(filepath)
    limit = limit if limit > 0 else 500

    try:
        async with aiofiles.open(filepath, mode="r", encoding="utf-8") as f:
            content = await f.read()

        lines = content.split("\n")[:limit]
        # Format: "line_number\tcontent" for easy LLM parsing
        return "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(lines))
    except Exception as e:
        return f"Error: {e}"


@tool(
    args_schema=WriteToolInput,
    description="Write text content to a specified file (overwrites existing).",
)
async def write_tool(filepath: str, content: str) -> str:
    """Write text content to a specified file.

    Why overwrite instead of append?
    - Code files usually need complete replacement
    - Append operations can be done with edit tool
    - Overwrite matches "write new file" semantics

    Safety:
    - Automatically creates parent directories (recursive: true)
    - Path based on workspace, prevents writing outside workspace
    """
    # Safe: resolve path to ensure it's within workspace
    filepath = os.path.abspath(filepath)

    try:
        # Create parent directory if not exists
        dir_path = os.path.dirname(filepath)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        async with aiofiles.open(filepath, mode="w", encoding="utf-8") as f:
            await f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error: {e}"


@tool(
    args_schema=EditToolInput,
    description="Edit a file by replacing exact text match (only first occurrence).",
)
async def edit_tool(filepath: str, old_string: str, new_string: str) -> str:
    """Edit a file by replacing exact text match.

    Why string replacement instead of regex?
    - String replacement is more predictable, no regex escaping issues
    - LLM-generated regex may have syntax errors
    - For code editing, exact match is safer than fuzzy match

    Why replace() instead of replaceAll()?
    - Only replace first match, more controllable
    - If need to replace all, LLM can call multiple times

    Typical usage:
    - LLM first reads file, sees issue at line 42
    - Then edit replaces that line's content
    """
    # Safe: resolve path to ensure it's within workspace
    filepath = os.path.abspath(filepath)

    try:
        async with aiofiles.open(filepath, mode="r", encoding="utf-8") as f:
            content = await f.read()

        # Check if the text to replace exists
        if old_string not in content:
            return "Error: Text to replace not found (ensure old_string matches file content exactly, including spaces and newlines)"

        # Only replace first match
        new_content = content.replace(old_string, new_string, 1)

        async with aiofiles.open(filepath, mode="w", encoding="utf-8") as f:
            await f.write(new_content)

        return f"Successfully edited {filepath}"
    except Exception as e:
        return f"Error: {e}"


# ============== Command Execution ==============


@tool(
    args_schema=ExecToolInput,
    description="Execute shell command.",
)
async def exec_tool(command: str, timeout: int = 30000) -> str:
    """Execute shell command.

    Why default timeout 30 seconds?
    - Most commands (npm install, tsc, pytest) complete within 30s
    - Timeout prevents Agent from waiting indefinitely on stuck commands
    - If need more time, LLM can specify timeout parameter

    Why limit output to 30KB (30000 chars)?
    - Command output can be very large (like npm install logs)
    - Too much output consumes LLM context, affects subsequent reasoning
    - 30KB is enough for error messages and key logs

    Why maxBuffer 1MB?
    - subprocess default is usually limited
    - We截取 first 30KB for LLM, but allow command to produce more output
    - Avoids command failure due to output size limit

    Safety:
    - cwd set to workspace, command executes in workspace
    - But this doesn't prevent malicious commands entirely
    - Production should use Docker sandbox
    """
    timeout_sec = timeout / 1000  # Convert ms to seconds

    try:
        # Run command with timeout
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Error: Command timed out after {timeout}ms"

        result = stdout.decode("utf-8", errors="replace")
        if stderr:
            result += f"\n[STDERR]\n{stderr.decode('utf-8', errors='replace')}"

        # Limit to 30KB to prevent excessive context usage
        return result[:30000]
    except Exception as e:
        return f"Error: {e}"


# ============== Directory Listing ==============


@tool(
    args_schema=ListToolInput,
    description="List directory contents.",
)
async def list_tool(path: str = ".", pattern: str = None) -> str:
    """List directory contents.

    Why limit to 100 entries?
    - Directory may contain thousands of files (like node_modules)
    - 100 entries is enough to understand directory structure
    - If need more, LLM can enter subdirectory to view

    Why use 📁 📄 icons?
    - Helps LLM quickly distinguish files and directories
    - More visually clear
    """
    dir_path = os.path.abspath(path)

    try:
        entries = os.listdir(dir_path)

        # Simple wildcard to regex conversion
        regex_pattern = None
        if pattern:
            regex_pattern = re.compile(pattern.replace("*", ".*"))

        result = []
        count = 0
        for entry in entries:
            if count >= 100:
                break

            if regex_pattern and not regex_pattern.match(entry):
                continue

            entry_path = os.path.join(dir_path, entry)
            icon = "📁" if os.path.isdir(entry_path) else "📄"
            result.append(f"{icon} {entry}")
            count += 1

        return "\n".join(result) if result else "Directory is empty"
    except Exception as e:
        return f"Error: {e}"


# ============== File Search ==============


@tool(
    args_schema=GrepToolInput,
    description="Search for text in files (supports regex).",
)
async def grep_tool(pattern: str, path: str = ".") -> str:
    """Search for text in files.

    Why use grep instead of custom implementation?
    - grep is a tool optimized over decades, extremely fast
    - Supports regex expressions
    - Automatically outputs filename and line numbers

    Why limit file types?
    - Only search .ts .js .json .md .py and other text files
    - Avoid searching binary files, images
    - Avoid searching large files in node_modules (grep -r is recursive)

    Why head -50?
    - Search results may have thousands of matches
    - 50 results is enough for LLM to locate the issue
    - If need more, can narrow search scope

    Why timeout 10 seconds?
    - Searching large projects can be slow
    - 10 seconds is enough for most projects
    - Timeout is better than hanging
    """
    search_path = os.path.abspath(path)

    try:
        # grep parameters:
        # -r: recursive search
        # -n: show line numbers
        # --include: only search files with specified extensions
        # head -50: only return first 50 results
        cmd = (
            f'grep -rn --include="*.py" --include="*.ts" --include="*.js" '
            f'--include="*.json" --include="*.md" --include="*.txt" '
            f'"{pattern}" "{search_path}" | head -50'
        )

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10,  # 10 second timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return "Error: Search timed out after 10 seconds"

        result = stdout.decode("utf-8", errors="replace")
        return result if result.strip() else "No matches found"
    except Exception:
        # grep returns non-zero exit code when no matches found, this is not an error
        return "No matches found"


# ============== Memory Tools ==============


@tool(
    args_schema=MemorySearchInput,
    description="Search long-term memory index, returns list of relevant memory summaries.",
)
async def memory_search_tool(query: str, limit: int = 5) -> str:
    """Search long-term memory index.

    Design goals:
    - Let LLM proactively call memory search, not auto-inject
    - Control context size: search first, then pull on demand
    """
    # TODO: Implement memory system
    return "Memory system not enabled"


@tool(
    args_schema=MemoryGetInput,
    description="Read complete content of a memory by ID.",
)
async def memory_get_tool(id: str) -> str:
    """Read complete content of a memory by ID.

    Used after memory_search to precisely pull a memory's full text.
    """
    # TODO: Implement memory system
    return f"Memory system not enabled (requested ID: {id})"


# ============== Sub-agent Tool ==============


@tool(
    args_schema=SessionsSpawnInput,
    description="Launch sub-agent to execute background task and return summary.",
)
async def sessions_spawn_tool(task: str, label: str = None, cleanup: str = None) -> str:
    """Launch sub-agent for background task execution (minimal version).

    Design goals:
    - Allow main agent to split tasks to background sub-agents
    - Sub-agent returns summary via event stream when complete
    """
    # TODO: Implement sub-agent system
    cleanup_info = f", cleanup={cleanup}" if cleanup else ""
    label_info = f", label={label}" if label else ""
    return f"Sub-agent system not enabled (task: {task}{label_info}{cleanup_info})"


# ============== Export All Built-in Tools ==============

"""
All built-in tools

These 9 tools cover Agent's core capabilities:
- Perception: read, list, grep
- Action: write, edit, exec
- Memory: memory_search, memory_get
- Orchestration: sessions_spawn

OpenClaw has 50+ tools, including:
- Browser automation (Playwright/Puppeteer)
- Git operations
- Database queries
- API calls
- etc...

But these 9 are the most fundamental - understanding these means understanding
the essence of the tool system.
"""

builtin_tools = [
    read_tool,
    write_tool,
    edit_tool,
    exec_tool,
    list_tool,
    grep_tool,
    memory_search_tool,
    memory_get_tool,
    sessions_spawn_tool,
]
