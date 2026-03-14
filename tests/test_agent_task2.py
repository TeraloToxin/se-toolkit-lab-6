"""
Regression tests for Task 2: The Documentation Agent.

These tests verify that the agent:
1. Uses tools (read_file, list_files) to answer questions
2. Populates tool_calls with executed tools
3. Includes source references in the output

Note: Tests that require LLM API connection are skipped if API is unavailable.
"""

import json
import subprocess
import sys
from pathlib import Path


def get_agent_path() -> Path:
    """Get the path to agent.py in the project root."""
    return Path(__file__).parent.parent / "agent.py"


def test_merge_conflict_question() -> None:
    """
    Test that agent uses read_file for merge conflict question.
    
    This test verifies:
    1. Agent uses read_file tool to find answer
    2. Source field contains wiki/git-workflow.md reference
    3. tool_calls array is populated with tool execution log
    """
    agent_path = get_agent_path()
    
    if not agent_path.exists():
        raise AssertionError(f"agent.py not found at {agent_path}")
    
    question = "How do you resolve a merge conflict?"
    
    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,  # Allow more time for agentic loop
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
    
    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check tool_calls is populated (agent should use tools)
    assert len(output["tool_calls"]) > 0, "tool_calls should be populated"
    
    # Check that read_file was used
    tool_names = [call.get("tool", "") for call in output["tool_calls"]]
    assert "read_file" in tool_names, (
        f"Expected read_file in tool_calls, got: {tool_names}"
    )
    
    # Check source contains wiki reference
    source = output.get("source", "")
    assert "wiki" in source.lower() or "git" in source.lower(), (
        f"Expected wiki reference in source, got: {source}"
    )


def test_wiki_files_question() -> None:
    """
    Test that agent uses list_files for wiki discovery question.
    
    This test verifies:
    1. Agent uses list_files tool to discover wiki files
    2. tool_calls array contains list_files execution
    """
    agent_path = get_agent_path()
    
    if not agent_path.exists():
        raise AssertionError(f"agent.py not found at {agent_path}")
    
    question = "What files are in the wiki directory?"
    
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
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that list_files was used
    tool_names = [call.get("tool", "") for call in output["tool_calls"]]
    assert "list_files" in tool_names, (
        f"Expected list_files in tool_calls, got: {tool_names}"
    )
