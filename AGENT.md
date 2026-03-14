# Agent Documentation

## Overview

This project implements a CLI system agent that connects to an LLM (Large Language Model) and answers questions by reading project files, discovering directory structures, and querying the live backend API. The agent has **three tools** (`read_file`, `list_files`, `query_api`) and an **agentic loop** that allows it to discover information, reason about results, and provide sourced answers.

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
│         ├──────────▶ query_api(method, path) ──▶ API response   │
│         │                                                        │
│  ┌──────┴───────┐                                                │
│  │  .env.agent  │  Configuration file                            │
│  │  .secret     │  (LLM key, backend key, URLs)                  │
│  └──────────────┘                                                │
└──────────────────────────────────────────────────────────────────┘
```

## Components

### 1. agent.py

Main CLI entry point that:
- Parses command-line arguments (question)
- Loads configuration from `.env.agent.secret` and `.env.docker.secret`
- Runs the **agentic loop**:
  1. Send question + tool definitions to LLM
  2. If LLM returns tool calls → execute tools, append results, repeat
  3. If LLM returns answer → output JSON and exit
- Returns structured JSON with `answer`, `source` (optional), and `tool_calls`

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

#### `query_api(method, path, body?)`

Query the deployed backend API to get live data or check system status.

**Parameters:**
- `method` (string): HTTP method (GET, POST, PUT, DELETE)
- `path` (string): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body`, or error message

**Authentication:**
- Uses `LMS_API_KEY` from `.env.docker.secret`
- Adds `Authorization: Bearer <LMS_API_KEY>` header to requests

**Security:**
- Validates path to prevent traversal attacks
- 30-second timeout for API requests

### 3. Agentic Loop

The agent follows this loop:

```
1. Initialize messages with system prompt + user question
2. For up to 10 iterations:
   a. Call LLM with messages and tool definitions
   b. If LLM returns tool_calls:
      - Execute each tool (read_file, list_files, or query_api)
      - Append results as "tool" role messages
      - Continue to next iteration
   c. If LLM returns text answer:
      - Extract answer and source
      - Break loop and output JSON
3. Return result with answer, source, and tool_calls log
```

**Maximum iterations:** 10 tool calls per question

### 4. System Prompt

The system prompt guides the LLM to choose the right tool:

```
You are a documentation and system assistant for a software engineering project.
You have access to the project wiki, source code files, and the live backend API.

Available tools:
- list_files(path): List files and directories at a given path
- read_file(path): Read the contents of a file
- query_api(method, path, body?): Query the live backend API

When answering questions:
1. For wiki/documentation questions → use list_files to discover files, then read_file
2. For source code questions → use read_file on backend/ or other source files
3. For live data questions (counts, status codes, analytics) → use query_api
4. For bug diagnosis → use query_api to see the error, then read_file to find the bug
5. Include a source reference when applicable (file path with section anchor)
6. Format source as: "wiki/filename.md#section-anchor" or "backend/path/file.py"

Always provide accurate answers based on file contents or API responses.
Maximum 10 tool calls per question.
```

### 5. Configuration

The agent reads configuration from two environment files:

#### `.env.agent.secret` (LLM configuration)

```
LLM_API_KEY=<your-qwen-api-key>
LLM_API_BASE=http://<vm-ip>:8080/v1
LLM_MODEL=qwen3-coder-plus
```

#### `.env.docker.secret` (Backend configuration)

```
LMS_API_KEY=<backend-api-key>
AGENT_API_BASE_URL=http://localhost:42002  # optional, defaults to localhost
```

**Important:** Two distinct keys:
- `LLM_API_KEY` — authenticates with LLM provider (Qwen Code)
- `LMS_API_KEY` — protects backend LMS endpoints (Authorization header)

The agent reads ALL configuration from environment variables, not hardcoded values. This allows the autochecker to inject different credentials during evaluation.

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
- `source` (string, optional): Wiki file path with optional section anchor
- `tool_calls` (array): Log of all tool calls with args and results

### Error Handling

- Debug/progress output goes to stderr (iterations, tool calls)
- Exit code 0 on success
- Non-zero exit code on errors (missing config, API failure, etc.)
- 60-second timeout per LLM call
- 30-second timeout per API call
- Maximum 10 tool call iterations

## Setup

### Prerequisites

1. Python 3.14.2
2. `uv` package manager
3. Access to Qwen Code API (or alternative LLM provider)
4. Running backend API (for `query_api` tool)

### Configuration

1. Copy environment files:
   ```bash
   cp .env.agent.example .env.agent.secret
   cp .env.docker.example .env.docker.secret
   ```

2. Edit `.env.agent.secret`:
   - `LLM_API_KEY`: Your Qwen API key
   - `LLM_API_BASE`: API base URL (e.g., `http://<vm-ip>:8080/v1`)
   - `LLM_MODEL`: Model name (default: `qwen3-coder-plus`)

3. Edit `.env.docker.secret`:
   - `LMS_API_KEY`: Backend API key
   - `AGENT_API_BASE_URL`: Backend URL (optional, defaults to `http://localhost:42002`)

### Running Tests

```bash
uv run pytest tests/test_agent_task3.py -v
```

### Running Benchmark

```bash
uv run run_eval.py
```

This runs 10 evaluation questions covering:
- Wiki lookups (branch protection, SSH connection)
- Source code analysis (framework, router modules)
- Live API queries (item count, status codes)
- Bug diagnosis (ZeroDivisionError, TypeError)
- Reasoning questions (request lifecycle, ETL idempotency)

## File Structure

```
se-toolkit-lab-6/
├── agent.py                 # Main CLI agent with tools + loop
├── AGENT.md                 # This documentation
├── .env.agent.example       # Example LLM config
├── .env.agent.secret        # LLM configuration (gitignored)
├── .env.docker.example      # Example backend config
├── .env.docker.secret       # Backend configuration (gitignored)
├── plans/
│   ├── task-1.md           # Task 1: Call an LLM
│   ├── task-2.md           # Task 2: Documentation Agent
│   └── task-3.md           # Task 3: System Agent
├── tests/
│   ├── test_agent_task1.py  # Task 1 tests
│   ├── test_agent_task2.py  # Task 2 tests
│   └── test_agent_task3.py  # Task 3 tests
├── wiki/                    # Project documentation
│   └── ...
└── backend/                 # Backend source code
    └── ...
```

## Dependencies

- `httpx`: HTTP client for API calls (LLM and backend)
- `python-dotenv`: Environment variable loading
- `typing`: Type hints for Python

## Security

### Path Validation

Both `read_file` and `list_files` validate paths:

1. Check for `..` in path string
2. Resolve to absolute path
3. Verify path is within project root
4. Return error message if validation fails

### API Authentication

The `query_api` tool:
- Reads `LMS_API_KEY` from environment (never hardcoded)
- Adds `Authorization: Bearer <LMS_API_KEY>` header
- Uses 30-second timeout to prevent hanging
- Validates paths to prevent traversal attacks

### Example Attack Prevention

```bash
# Path traversal rejected:
uv run agent.py "Read ../../../etc/passwd"
# Error: Path traversal (..) not allowed

# API without auth returns 401:
uv run agent.py "Query /items/ without auth"
# Returns 401 Unauthorized
```

## Task Evolution

| Feature | Task 1 | Task 2 | Task 3 |
|---------|--------|--------|--------|
| Tools | None | `read_file`, `list_files` | + `query_api` |
| Agentic loop | No | Yes (max 10) | Yes (max 10) |
| Output fields | `answer`, `tool_calls` | + `source` | `source` optional |
| Config | LLM only | LLM only | LLM + Backend |
| Questions | Simple chat | Wiki lookup | Wiki + Source + API |

## Lessons Learned

### Benchmark Iteration

During development of Task 3, several iterations were needed to pass all 10 benchmark questions:

1. **Initial failure: Agent didn't call `query_api` for data questions**
   - **Cause:** Tool description was too vague
   - **Fix:** Updated description to explicitly mention "live data", "counts", "status codes"

2. **API returns 401 Unauthorized**
   - **Cause:** `LMS_API_KEY` not loaded from `.env.docker.secret`
   - **Fix:** Added loading of both `.env.agent.secret` and `.env.docker.secret` in `load_env()`

3. **Agent crashes on null content**
   - **Cause:** `msg.get("content", "")` returns `None` when field exists but is null
   - **Fix:** Changed to `(msg.get("content") or "")` pattern

4. **Wrong tool for bug diagnosis**
   - **Cause:** Agent tried to read wiki for API errors
   - **Fix:** Updated system prompt: "For bug diagnosis → use query_api to see the error, then read_file to find the bug"

5. **Timeout on multi-step questions**
   - **Cause:** Agent read entire docker-compose.yml line by line
   - **Fix:** System prompt now guides to read specific files for specific questions

### Key Insights

- **Tool descriptions matter:** The LLM relies entirely on tool descriptions to decide which tool to use. Vague descriptions lead to wrong tool choices.

- **Environment separation is critical:** Keeping `LLM_API_KEY` and `LMS_API_KEY` in separate files prevents accidental exposure and matches the deployment model.

- **Source is optional:** For API queries, there's no wiki source. The `source` field should be optional, not required.

- **Error messages help debugging:** Returning descriptive error messages from tools (instead of crashing) helps the LLM understand what went wrong and try again.

### Final Evaluation Score

After iteration, the agent passes all 10 local benchmark questions:
- ✓ Wiki questions (branch protection, SSH)
- ✓ Source code questions (FastAPI framework, router modules)
- ✓ API questions (item count, 401 status code)
- ✓ Bug diagnosis (ZeroDivisionError, TypeError)
- ✓ Reasoning questions (request lifecycle, ETL idempotency)

Note: The autochecker bot tests additional hidden questions and uses LLM-based judging for open-ended reasoning questions.

## Future Enhancements

- Add `search_file(pattern)` tool to find files by name pattern
- Add `grep_file(pattern, path)` tool to search file contents
- Implement content truncation for large files (currently returns full content)
- Add caching for repeated API calls
- Support streaming responses for long answers
