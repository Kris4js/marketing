"""Descriptions for built-in tools."""

# ============== File Operation Tools ==============

FILE_READ_DESCRIPTION: str = """
Read file contents from the local filesystem.

## When to Use

- Reading source code files to understand implementation
- Reading configuration files (.env, .json, .yaml)
- Reading documentation files (.md, .txt)
- Examining log files
- Any time you need to see the actual contents of a file

## When NOT to Use

- Don't use for listing directories (use list_tool instead)
- Don't use for searching within files (use grep_tool instead)
- Don't try to read binary files (images, executables, etc.)

## Usage Notes

- Returns content with line numbers for easy reference
- Limited to 500 lines by default to conserve context
- Can specify offset/limit for reading large files in chunks
- Line numbers help with precise editing later
""".strip()


FILE_WRITE_DESCRIPTION: str = """
Write text content to a file (overwrites existing content).

## When to Use

- Creating new files (source code, config, documentation)
- Completely replacing a file's contents
- Writing generated code or content
- Saving results to a file

## When NOT to Use

- Don't use for small edits to existing files (use edit_tool instead)
- Don't use for appending to files (not supported)
- Don't use for binary data

## Usage Notes

- Overwrites any existing content in the file
- Automatically creates parent directories if needed
- Use for complete file rewrites or new file creation
- For partial edits, use edit_tool instead
""".strip()


FILE_EDIT_DESCRIPTION: str = """
Edit a file by replacing exact text match (string replacement).

## When to Use

- Making small, targeted changes to existing files
- Fixing bugs by replacing specific lines
- Updating configuration values
- Any situation where you know the exact text to replace

## When NOT to Use

- Don't use when you need to replace all occurrences (call multiple times)
- Don't use for regex patterns (use exact string match only)
- Don't use for complete file rewrites (use write_tool instead)

## Usage Notes

- Only replaces the FIRST occurrence of the exact string
- String must match EXACTLY (including whitespace)
- More predictable than regex for code editing
- Use read_tool first to see the exact content you want to replace
""".strip()


# ============== Command Execution Tools ==============

EXEC_DESCRIPTION: str = """
Execute shell commands in the current working directory.

## When to Use

- Running build commands (npm, make, cargo, etc.)
- Running tests (pytest, npm test, etc.)
- Installing dependencies (npm install, pip install, etc.)
- Git operations (git status, git log, etc.)
- Any terminal command that needs to be executed

## When NOT to Use

- Don't use for interactive commands (will hang)
- Don't use for commands requiring user input
- Don't use for very long-running commands without increasing timeout

## Usage Notes

- Default timeout is 30 seconds (adjustable)
- Output limited to 30KB to prevent context overflow
- Returns both stdout and stderr
- Commands run in the current working directory
- For security, consider using Docker isolation in production
""".strip()


# ============== Directory & Search Tools ==============

LIST_DESCRIPTION: str = """
List directory contents with file type indicators.

## When to Use

- Exploring directory structure
- Finding what files exist in a directory
- Understanding project layout
- Checking if files/folders exist

## When NOT to Use

- Don't use for reading file contents (use read_tool instead)
- Don't use for searching files (use grep_tool instead)

## Usage Notes

- Shows folders with 📁 icon
- Shows files with 📄 icon
- Limited to 100 entries to prevent overwhelming output
- Supports wildcard patterns (*.py, *.ts, etc.)
""".strip()


GREP_DESCRIPTION: str = """
Search for text patterns in files using regex.

## When to Use

- Finding where a function/class is defined
- Searching for usage of a variable or function
- Finding all occurrences of a string in codebase
- Searching log files for specific patterns
- Code navigation and exploration

## When NOT to Use

- Don't use for simple file listing (use list_tool instead)
- Don't use for reading specific files (use read_tool instead)

## Usage Notes

- Supports regular expression patterns
- Searches recursively through directories
- Limited to text files (.py, .ts, .js, .json, .md, .txt)
- Returns up to 50 matches with line numbers
- Has 10-second timeout to prevent hanging
- Excludes node_modules and large binary files automatically
""".strip()


__all__ = [
    "FILE_READ_DESCRIPTION",
    "FILE_WRITE_DESCRIPTION",
    "FILE_EDIT_DESCRIPTION",
    "EXEC_DESCRIPTION",
    "LIST_DESCRIPTION",
    "GREP_DESCRIPTION",
]
