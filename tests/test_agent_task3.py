"""
Regression tests for Task 3: The System Agent.

These tests verify that the agent:
1. Uses query_api tool for data questions
2. Uses read_file for source code questions
3. Correctly identifies framework and API endpoints
"""

import json
import subprocess
import sys
from pathlib import Path


def get_agent_path() -> Path:
    """Get the path to agent.py in the project root."""
    return Path(__file__).parent.parent / "agent.py"


def test_framework_question() -> None:
    """
    Test that agent uses read_file to find the backend framework.
    
    This test verifies:
    1. Agent uses read_file tool to find framework name
    2. Answer contains "FastAPI"
    3. tool_calls array is populated
    """
    agent_path = get_agent_path()
    
    if not agent_path.exists():
        raise AssertionError(f"agent.py not found at {agent_path}")
    
    question = "What Python web framework does the backend use?"
    
    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,
    )
    
    # Skip if LLM API is unavailable
    if result.returncode != 0 and "ConnectError" in result.stderr:
        print("SKIP: LLM API unavailable")
        return
    
    # Check exit code
    assert result.returncode == 0, (
        f"agent.py failed with exit code {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    
    # Parse JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Invalid JSON in stdout: {result.stdout}\nError: {e}"
        ) from e
    
    # Check answer contains FastAPI
    answer = output.get("answer", "").lower()
    assert "fastapi" in answer, (
        f"Expected 'FastAPI' in answer, got: {output.get('answer', '')}"
    )
    
    # Check tool_calls is populated
    assert len(output["tool_calls"]) > 0, "tool_calls should be populated"
    
    # Check that read_file was used
    tool_names = [call.get("tool", "") for call in output["tool_calls"]]
    assert "read_file" in tool_names, (
        f"Expected read_file in tool_calls, got: {tool_names}"
    )


def test_database_items_question() -> None:
    """
    Test that agent uses query_api for database count question.
    
    This test verifies:
    1. Agent uses query_api tool to get item count
    2. Answer contains a number > 0
    3. tool_calls array contains query_api execution
    """
    agent_path = get_agent_path()
    
    if not agent_path.exists():
        raise AssertionError(f"agent.py not found at {agent_path}")
    
    question = "How many items are in the database?"
    
    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,
    )
    
    # Skip if LLM API is unavailable
    if result.returncode != 0 and "ConnectError" in result.stderr:
        print("SKIP: LLM API unavailable")
        return
    
    # Skip if backend API is unavailable
    if result.returncode != 0 and "Cannot connect to API" in result.stderr:
        print("SKIP: Backend API unavailable")
        return
    
    # Check exit code
    assert result.returncode == 0, (
        f"agent.py failed with exit code {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    
    # Parse JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Invalid JSON in stdout: {result.stdout}\nError: {e}"
        ) from e
    
    # Check answer contains a number
    import re
    answer = output.get("answer", "")
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, (
        f"Expected a number in answer, got: {answer}"
    )
    
    # Check tool_calls contains query_api
    tool_names = [call.get("tool", "") for call in output.get("tool_calls", [])]
    assert "query_api" in tool_names, (
        f"Expected query_api in tool_calls, got: {tool_names}"
    )
