# Agent Documentation

## Overview

This project implements a CLI documentation agent that connects to an LLM (Large Language Model) and answers questions by reading project files. The agent has **tools** (`read_file`, `list_files`) and an **agentic loop** that allows it to discover information, reason about results, and provide sourced answers.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌──────────────┐     ┌──────────────────────────────────────┐  │
│  │  agent.py    │────▶│  LLM Provider (Qwen Code API)        │  │
│  │  (CLI)       │◀────│  OpenAI-compatible API + tools       │  │
│  └──────┬───────┘     └──────────────────────────────────────┘  │
│         │                                                        │
│         │ tool calls                                             │
│         ├──────────▶ read_file(path) ──▶ file contents          │
│         ├──────────▶ list_files(dir) ──▶ directory listing       │
│         │                                                        │
│  ┌──────┴───────┐                                                │
│  │  .env.agent  │  Configuration file                            │
│  │  .secret     │  (API key, base URL, model)                    │
│  └──────────────┘                                                │
└──────────────────────────────────────────────────────────────────┘
```

## Components

### 1. agent.py

Main CLI entry point that:
- Parses command-line arguments (question)
- Loads configuration from `.env.agent.secret`
- Runs the **agentic loop**:
  1. Send question + tool definitions to LLM
  2. If LLM returns tool calls → execute tools, append results, repeat
  3. If LLM returns answer → output JSON and exit
- Returns structured JSON with `answer`, `source`, and `tool_calls`

### 2. Tools

#### `read_file(path)`

Read the contents of a file from the project repository.

**Parameters:**
- `path` (string): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message

**Security:**
- Validates path to prevent directory traversal (`..` not allowed)
- Only allows files within project root

#### `list_files(path)`

List files and directories at a given path.

**Parameters:**
- `path` (string): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entry names, or error message

**Security:**
- Validates path to prevent directory traversal
- Only allows directories within project root

### 3. Agentic Loop

The agent follows this loop:

```
1. Initialize messages with system prompt + user question
2. For up to 10 iterations:
   a. Call LLM with messages and tool definitions
   b. If LLM returns tool_calls:
      - Execute each tool
      - Append results as "tool" role messages
      - Continue to next iteration
   c. If LLM returns text answer:
      - Extract answer and source
      - Break loop and output JSON
3. Return result with answer, source, and tool_calls log
```

**Maximum iterations:** 10 tool calls per question

### 4. System Prompt

The system prompt guides the LLM:

```
You are a documentation assistant for a software engineering project.
You have access to the project wiki and source code files.

Available tools:
- list_files(path): List files and directories at a given path
- read_file(path): Read the contents of a file

When answering questions:
1. First use list_files to discover relevant files in the wiki/ directory
2. Then use read_file to read specific files and find the answer
3. Include a source reference in your answer (file path with section anchor if applicable)
4. Format source as: "wiki/filename.md#section-anchor"

Always provide accurate answers based on the file contents.
Maximum 10 tool calls per question.
```

### 5. Configuration (.env.agent.secret)

Environment file containing:
- `LLM_API_KEY` — API key for authentication
- `LLM_API_BASE` — Base URL of the LLM API endpoint
- `LLM_MODEL` — Model name to use (e.g., `qwen3-coder-plus`)

### 6. LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)
**Model:** `qwen3-coder-plus`

The API follows the OpenAI-compatible format with tool calling:
- Endpoint: `POST /v1/chat/completions`
- Authentication: Bearer token in `Authorization` header
- Tool definitions in `tools` parameter
- Tool results returned via `tool` role messages

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output Format

The agent outputs JSON to stdout:

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

**Fields:**
- `answer` (string): The LLM's final answer
- `source` (string): Wiki file path with optional section anchor
- `tool_calls` (array): Log of all tool calls with args and results

### Error Handling

- Debug/progress output goes to stderr (iterations, tool calls)
- Exit code 0 on success
- Non-zero exit code on errors (missing config, API failure, etc.)
- 60-second timeout per LLM call
- Maximum 10 tool call iterations

## Setup

### Prerequisites

1. Python 3.14.2
2. `uv` package manager
3. Access to Qwen Code API (or alternative LLM provider)

### Configuration

1. Copy the example environment file:
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Edit `.env.agent.secret` and fill in:
   - `LLM_API_KEY`: Your API key
   - `LLM_API_BASE`: API base URL (e.g., `http://<vm-ip>:8080/v1`)
   - `LLM_MODEL`: Model name (default: `qwen3-coder-plus`)

### Running Tests

```bash
uv run pytest tests/test_agent_task2.py -v
```

## File Structure

```
se-toolkit-lab-6/
├── agent.py                 # Main CLI agent with tools + loop
├── AGENT.md                 # This documentation
├── .env.agent.example       # Example environment file
├── .env.agent.secret        # Actual configuration (gitignored)
├── plans/
│   ├── task-1.md           # Task 1 implementation plan
│   └── task-2.md           # Task 2 implementation plan
├── tests/
│   ├── __init__.py
│   ├── test_agent_task1.py  # Task 1 regression tests
│   └── test_agent_task2.py  # Task 2 regression tests
└── wiki/                    # Project documentation
    ├── git-workflow.md
    └── ...
```

## Dependencies

- `httpx`: HTTP client for API calls
- `python-dotenv`: Environment variable loading
- `typing`: Type hints for Python

## Security

### Path Validation

Both tools validate paths to prevent directory traversal:

1. Check for `..` in path string
2. Resolve to absolute path
3. Verify path is within project root
4. Return error message if validation fails

### Example Attack Prevention

```bash
# This will be rejected:
uv run agent.py "Read ../../../etc/passwd"

# Error: Path traversal (..) not allowed
```

## Task 1 vs Task 2

| Feature | Task 1 | Task 2 |
|---------|--------|--------|
| Tools | None | `read_file`, `list_files` |
| Agentic loop | No | Yes (max 10 iterations) |
| Output fields | `answer`, `tool_calls` | `answer`, `source`, `tool_calls` |
| Source reference | N/A | Wiki file path + anchor |

## Future Enhancements (Task 3)

- **Task 3:** Add `query_api` tool to query backend HTTP API
- Support for more complex multi-step reasoning
- Improved source extraction with section anchors
