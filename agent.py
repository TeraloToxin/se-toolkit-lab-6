#!/usr/bin/env python3
"""
CLI Documentation Agent with tools and agentic loop.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source', and 'tool_calls' fields to stdout.
    Debug/progress output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Maximum tool calls per question
MAX_ITERATIONS = 10

# Project root directory (where agent.py is located)
PROJECT_ROOT = Path(__file__).parent.resolve()


def load_env() -> dict[str, str]:
    """Load environment variables from .env.agent.secret."""
    env_path = Path(__file__).parent / ".env.agent.secret"
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        print(
            "Copy .env.agent.example to .env.agent.secret and fill in your credentials",
            file=sys.stderr,
        )
        sys.exit(1)

    load_dotenv(env_path)

    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key or api_key == "your-llm-api-key-here":
        print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    if not api_base or "<your-vm-ip>" in api_base:
        print("Error: LLM_API_BASE not set in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_base": api_base.rstrip("/"),
        "model": model,
    }


def validate_path(user_path: str) -> Path:
    """
    Validate and resolve a user-provided path.
    
    Security: prevents directory traversal attacks.
    
    Args:
        user_path: Relative path from project root
        
    Returns:
        Resolved absolute Path
        
    Raises:
        ValueError: If path is outside project root or contains ..
    """
    if ".." in user_path:
        raise ValueError("Path traversal (..) not allowed")
    
    full_path = (PROJECT_ROOT / user_path).resolve()
    
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        raise ValueError("Path outside project directory not allowed")
    
    return full_path


def read_file(path: str) -> str:
    """
    Read the contents of a file.
    
    Args:
        path: Relative path from project root
        
    Returns:
        File contents as string, or error message
    """
    try:
        validated_path = validate_path(path)
        
        if not validated_path.exists():
            return f"Error: File not found: {path}"
        
        if not validated_path.is_file():
            return f"Error: Not a file: {path}"
        
        return validated_path.read_text(encoding="utf-8")
        
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        
    Returns:
        Newline-separated listing, or error message
    """
    try:
        validated_path = validate_path(path)
        
        if not validated_path.exists():
            return f"Error: Path not found: {path}"
        
        if not validated_path.is_dir():
            return f"Error: Not a directory: {path}"
        
        entries = sorted([e.name for e in validated_path.iterdir()])
        return "\n".join(entries)
        
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


# Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path in the project",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation assistant for a software engineering project.
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
If you cannot find the answer in the files, say so honestly."""


def execute_tool(name: str, args: dict[str, Any]) -> str:
    """
    Execute a tool and return the result.
    
    Args:
        name: Tool name (read_file or list_files)
        args: Tool arguments
        
    Returns:
        Tool result as string
    """
    if name == "read_file":
        path = args.get("path", "")
        return read_file(path)
    elif name == "list_files":
        path = args.get("path", "")
        return list_files(path)
    else:
        return f"Error: Unknown tool: {name}"


def call_llm(messages: list[dict[str, Any]], config: dict[str, str]) -> dict[str, Any]:
    """
    Call the LLM API with messages and tool definitions.
    
    Args:
        messages: List of message dicts (role, content, optional tool_call_id)
        config: Configuration dict with api_key, api_base, model
        
    Returns:
        Response dict with content and/or tool_calls
    """
    url = f"{config['api_base']}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }
    
    payload = {
        "model": config["model"],
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("choices"):
            return {"content": "Error: No response from LLM", "tool_calls": []}

        message = data["choices"][0]["message"]

        content: str = message.get("content", "") or ""
        tool_calls_list: list[dict[str, str]] = []

        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                tool_calls_list.append({
                    "id": tc.get("id", "") or "",
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                })

        return {"content": content, "tool_calls": tool_calls_list}


def extract_source(tool_calls_log: list[dict[str, Any]]) -> str:
    """
    Extract source reference from tool calls.
    
    Args:
        tool_calls_log: List of executed tool calls with args and results
        
    Returns:
        Source string (file path with optional anchor)
    """
    # Find the last read_file call
    for call in reversed(tool_calls_log):
        if call["tool"] == "read_file":
            path = call["args"].get("path", "")
            return path
    
    # Fallback to first file listed
    for call in tool_calls_log:
        if call["tool"] == "read_file":
            return call["args"].get("path", "unknown")
    
    return ""


def run_agentic_loop(question: str, config: dict[str, str]) -> dict[str, Any]:
    """
    Run the agentic loop: LLM → tool calls → execute → repeat until answer.
    
    Args:
        question: User's question
        config: Configuration dict
        
    Returns:
        Result dict with answer, source, and tool_calls
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    tool_calls_log: list[dict[str, Any]] = []
    
    for iteration in range(MAX_ITERATIONS):
        print(f"Iteration {iteration + 1}/{MAX_ITERATIONS}...", file=sys.stderr)
        
        response = call_llm(messages, config)
        
        if response["tool_calls"]:
            # Execute tool calls
            for tool_call in response["tool_calls"]:
                name = tool_call["name"]
                try:
                    args = json.loads(tool_call["arguments"])
                except json.JSONDecodeError:
                    args = {"path": tool_call["arguments"]}
                
                print(f"  Calling {name}({args})...", file=sys.stderr)
                
                result = execute_tool(name, args)
                
                tool_calls_log.append({
                    "tool": name,
                    "args": args,
                    "result": result,
                })
                
                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                })
            
            # Continue loop - LLM will reason about results
            continue
        else:
            # No tool calls - LLM provided final answer
            answer = response["content"]
            source = extract_source(tool_calls_log)
            
            return {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_log,
            }
    
    # Max iterations reached
    print("Max iterations reached", file=sys.stderr)
    
    # Return whatever answer we have
    if tool_calls_log:
        # Try to extract answer from last read_file result
        for call in reversed(tool_calls_log):
            if call["tool"] == "read_file":
                return {
                    "answer": f"Based on {call['args'].get('path', 'the files')}: {call['result'][:500]}...",
                    "source": call["args"].get("path", ""),
                    "tool_calls": tool_calls_log,
                }
    
    return {
        "answer": "Unable to find answer within maximum iterations",
        "source": "",
        "tool_calls": tool_calls_log,
    }


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    if not question.strip():
        print("Error: Question cannot be empty", file=sys.stderr)
        sys.exit(1)
    
    print(f"Question: {question}", file=sys.stderr)
    
    config = load_env()
    print(f"Using model: {config['model']}", file=sys.stderr)
    
    result = run_agentic_loop(question, config)
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
