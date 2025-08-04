# ruff: noqa: SLF001
"""Unit tests for TimeMachine state persistence"""

import os
import tempfile
from unittest.mock import patch

import pytest

from orchestra.extensions.timemachine.timemachine_monitor import TimeMachineMonitor


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def monitor(temp_dir):
    """Create a TimeMachine monitor instance"""
    config_path = os.path.join(temp_dir, ".claude", "orchestra", "timemachine.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # Set working directory in environment
    os.environ["CLAUDE_WORKING_DIR"] = temp_dir

    monitor = TimeMachineMonitor(config_path)
    return monitor


def test_prompt_persistence_across_hooks(monitor):
    """Test that prompt captured in UserPromptSubmit is available in Stop hook"""
    session_id = "test-session-123"
    transcript_path = "/path/to/transcript-456.jsonl"
    test_prompt = "Test user prompt for checkpoint"

    # Context for UserPromptSubmit hook
    prompt_context = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "prompt": test_prompt,
        "hook_event_name": "UserPromptSubmit",
    }

    # Handle UserPromptSubmit - should capture the prompt
    response = monitor.handle_hook("UserPromptSubmit", prompt_context)
    assert response.get("decision") == "approve"

    # Verify state was persisted
    state = monitor.get_session_state(prompt_context)
    assert state.get("current_prompt") == test_prompt
    assert state.get("session_id") == session_id
    assert state.get("tools_used_this_turn") == []
    assert state.get("files_modified_this_turn") == []

    # Context for Stop hook (different invocation)
    stop_context = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "hook_event_name": "Stop",
    }

    # Mock git operations
    with patch.object(
        monitor.git_manager, "_is_git_repo", return_value=True
    ), patch.object(monitor, "_create_checkpoint") as mock_create:

        mock_create.return_value = "checkpoint-0"

        # Handle Stop hook - should use persisted prompt
        response = monitor.handle_hook("Stop", stop_context)
        assert response.get("decision") == "approve"

        # Verify checkpoint was created with context
        mock_create.assert_called_once_with(stop_context)

    # Verify state was cleared after checkpoint
    state = monitor.get_session_state(stop_context)
    assert state == {}


def test_tool_tracking_persistence(monitor):
    """Test that tool usage is tracked across hook invocations"""
    session_id = "test-session-123"
    transcript_path = "/path/to/transcript-456.jsonl"

    # First set up a prompt
    prompt_context = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "prompt": "Test prompt",
        "hook_event_name": "UserPromptSubmit",
    }
    monitor.handle_hook("UserPromptSubmit", prompt_context)

    # Track tool usage
    tool_context = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "tool_name": "Edit",
        "hook_event_name": "PreToolUse",
    }

    # First tool
    monitor.handle_hook("PreToolUse", tool_context)

    # Second tool (different invocation)
    tool_context["tool_name"] = "Write"
    monitor.handle_hook("PreToolUse", tool_context)

    # Duplicate tool (should not be added again)
    tool_context["tool_name"] = "Edit"
    monitor.handle_hook("PreToolUse", tool_context)

    # Verify tools are tracked
    state = monitor.get_session_state(tool_context)
    tools_used = state.get("tools_used_this_turn", [])
    assert len(tools_used) == 2
    assert "Edit" in tools_used
    assert "Write" in tools_used


def test_file_modification_tracking(monitor):
    """Test that file modifications are tracked across hook invocations"""
    session_id = "test-session-123"
    transcript_path = "/path/to/transcript-456.jsonl"

    # Set up initial prompt
    prompt_context = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "prompt": "Test prompt",
        "hook_event_name": "UserPromptSubmit",
    }
    monitor.handle_hook("UserPromptSubmit", prompt_context)

    # Track file modifications
    post_tool_context = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "tool_name": "Edit",
        "tool_input": {"file_path": "/path/to/file1.py"},
        "hook_event_name": "PostToolUse",
    }

    # First file
    monitor.handle_hook("PostToolUse", post_tool_context)

    # Second file (different invocation)
    post_tool_context["tool_input"]["file_path"] = "/path/to/file2.py"
    monitor.handle_hook("PostToolUse", post_tool_context)

    # Duplicate file (should not be added again)
    post_tool_context["tool_input"]["file_path"] = "/path/to/file1.py"
    monitor.handle_hook("PostToolUse", post_tool_context)

    # Verify files are tracked
    state = monitor.get_session_state(post_tool_context)
    files_modified = state.get("files_modified_this_turn", [])
    assert len(files_modified) == 2
    assert "/path/to/file1.py" in files_modified
    assert "/path/to/file2.py" in files_modified


def test_no_checkpoint_without_prompt(monitor):
    """Test that no checkpoint is created if no prompt was captured"""
    session_id = "test-session-123"
    transcript_path = "/path/to/transcript-456.jsonl"

    # Make sure there's no leftover state by clearing it first
    stop_context = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "hook_event_name": "Stop",
    }
    monitor.clear_session_state(stop_context)

    # Stop hook without prior UserPromptSubmit
    with patch.object(monitor, "_create_checkpoint") as mock_create:
        response = monitor.handle_hook("Stop", stop_context)
        assert response.get("decision") == "approve"

        # Should not create checkpoint
        mock_create.assert_not_called()


def test_session_isolation(monitor):
    """Test that different sessions have isolated state"""
    transcript_path = "/path/to/transcript-456.jsonl"

    # Session 1
    context1 = {
        "session_id": "session-1",
        "transcript_path": transcript_path,
        "prompt": "Prompt for session 1",
        "hook_event_name": "UserPromptSubmit",
    }
    monitor.handle_hook("UserPromptSubmit", context1)

    # Session 2
    context2 = {
        "session_id": "session-2",
        "transcript_path": transcript_path,
        "prompt": "Prompt for session 2",
        "hook_event_name": "UserPromptSubmit",
    }
    monitor.handle_hook("UserPromptSubmit", context2)

    # Verify isolation
    state1 = monitor.get_session_state(context1)
    state2 = monitor.get_session_state(context2)

    assert state1.get("current_prompt") == "Prompt for session 1"
    assert state2.get("current_prompt") == "Prompt for session 2"
