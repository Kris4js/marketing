# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wild Goose Agent is an AI agent system with a PySide6 desktop UI. The agent uses LangChain/LangGraph for LLM orchestration and supports tools, skills, and long-term memory.

## Commands

### Environment Setup
```bash
# Install dependencies (uses uv package manager)
uv sync

# Install Playwright browsers (for browser automation tools)
playwright install
```

### Development
```bash
# Run the desktop UI application
python -m app.main

# Run basic agent example
python examples/basic_use.py

# Lint code
ruff check

# Format code
ruff format

# Run tests
pytest
pytest tests/unit/test_file.py::test_function  # Single test
```

## Architecture

### Core Agent System (`src/agent/`)

The agent uses an async generator pattern that yields events for real-time UI updates:

- **Agent** (`agent.py`): Main agent loop. Calls LLM iteratively, executes tools, and yields `AgentEvent` objects. Handles context compaction when over token budget.
- **Scratchpad** (`scratchpad.py`): Single source of truth for a query's execution. Tracks tool calls, thinking, enforces soft limits (warnings, not blocks) on tool usage.
- **Types** (`types.py`): Event types (`ThinkingEvent`, `ToolStartEvent`, `ToolEndEvent`, `DoneEvent`, etc.) and `AgentConfig`.

### Tool System (`src/tools/`)

- **Registry** (`registry.py`): Returns `RegisteredTool` objects containing tool instances + rich descriptions for system prompt injection. Conditionally includes tools based on environment (e.g., Tavily API key for `web_search`).
- **Built-in tools** (`buildin.py`): File operations (read, write, edit, list, grep, exec).
- **Skill tool** (`skill.py`): Dynamically loads and executes user-defined skills.
- **Browser tools** (`browser/`): Playwright-based browser automation.

### Skill System (`src/skills/`)

Skills are markdown files with frontmatter metadata. Discovered from three locations (later overrides earlier):
1. Builtin: `src/skills/`
2. User: `~/.dexter/skills/`
3. Project: `.dexter/skills/`

Each skill is a directory containing `SKILL.md` with YAML frontmatter (name, description).

### Utilities (`src/utils/`)

- **SessionManager** (`session.py`): Conversation persistence using JSONL format (append-only, fault-tolerant). Sanitizes session keys to prevent path traversal.
- **ToolContextManager** (`context.py`): Persists tool results to disk as JSON, stores lightweight pointers in memory. Enables large tool outputs without context bloat.
- **MemoryManager** (`memory.py`): Long-term memory using file-based keyword search + time decay scoring. Stores Q&A pairs with tags for retrieval.

### Desktop UI (`app/`)

PySide6 application with Cherry Studio-style theming:

- **AgentBridge** (`bridge/agent_bridge.py`): Qt signals/slots wrapper around async Agent. Runs agent queries in QThread, emits signals for each event type.
- **Pages**: Chat (message bubbles with streaming), Resources (Tools/Skills/Prompts sub-tabs), Settings dialog.
- **Components**: Reusable `ListPanel` (searchable list), `PreviewPanel` (markdown detail view), `MessageBubble`, `MarkdownViewer`.
- **Themes**: QSS files in `themes/` (light/dark).

### Prompts (`src/agent/prompts.py`)

Customization layer. Modify `SYSTEM_PROMPT` to change agent personality. Build functions for iteration, final answer, tool summary.

## Data Flow

1. Query → Agent creates Scratchpad
2. Load session history (SessionManager) + search memory (MemoryManager)
3. LLM call → if tool calls: execute via tool_map
4. Tool results persisted to disk (ToolContextManager), summarized via LLM
5. Scratchpad records tool calls with summaries
6. Repeat until no more tool calls or max_iterations
7. Generate final answer with optionally-selected full contexts
8. Save messages to session, save Q&A to memory

## Key Patterns

- **Event streaming**: Agent yields events; UI subscribes via AgentBridge signals
- **Disk persistence**: JSONL for sessions (append-only), JSON for tool contexts
- **Graceful degradation**: Tool limits warn but don't block; missing tools are skipped
- **Skill override**: Project > User > Builtin precedence for skill discovery
