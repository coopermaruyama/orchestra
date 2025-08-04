"""Unit tests for SessionStateManager"""

import pytest

from orchestra.common.base_extension import SessionStateManager


@pytest.fixture
def state_manager():
    """Create a test state manager"""
    return SessionStateManager("test_extension")


@pytest.fixture
def test_context():
    """Create a test hook context"""
    return {
        "session_id": "test-session-123",
        "transcript_path": "/path/to/transcript-456.jsonl",
    }


def test_state_persistence(state_manager, test_context):
    """Test that state persists between get/set calls"""
    session_id = "test-session-123"
    transcript_id = "transcript-456"

    # Set some state
    test_state = {
        "prompt": "Test prompt",
        "tools_used": ["Edit", "Write"],
        "custom_field": 42,
    }
    state_manager.set_state(session_id, transcript_id, test_state)

    # Get the state back
    retrieved_state = state_manager.get_state(session_id, transcript_id)

    # Verify all fields except _last_updated
    assert retrieved_state["prompt"] == test_state["prompt"]
    assert retrieved_state["tools_used"] == test_state["tools_used"]
    assert retrieved_state["custom_field"] == test_state["custom_field"]
    assert "_last_updated" in retrieved_state


def test_update_state(state_manager):
    """Test updating specific fields in state"""
    session_id = "test-session-123"
    transcript_id = "transcript-456"

    # Set initial state
    initial_state = {"field1": "value1", "field2": "value2"}
    state_manager.set_state(session_id, transcript_id, initial_state)

    # Update specific fields
    state_manager.update_state(
        session_id, transcript_id, {"field2": "updated_value", "field3": "new_value"}
    )

    # Verify updates
    state = state_manager.get_state(session_id, transcript_id)
    assert state["field1"] == "value1"  # Unchanged
    assert state["field2"] == "updated_value"  # Updated
    assert state["field3"] == "new_value"  # New field


def test_clear_state(state_manager):
    """Test clearing state"""
    session_id = "test-session-123"
    transcript_id = "transcript-456"

    # Set and then clear state
    state_manager.set_state(session_id, transcript_id, {"data": "test"})
    state_manager.clear_state(session_id, transcript_id)

    # Should return empty dict
    state = state_manager.get_state(session_id, transcript_id)
    assert state == {}


def test_state_isolation(state_manager):
    """Test that states are isolated by session/transcript"""
    # Set state for different sessions
    state_manager.set_state("session1", "transcript1", {"data": "session1"})
    state_manager.set_state("session2", "transcript1", {"data": "session2"})
    state_manager.set_state("session1", "transcript2", {"data": "transcript2"})

    # Verify isolation
    assert state_manager.get_state("session1", "transcript1")["data"] == "session1"
    assert state_manager.get_state("session2", "transcript1")["data"] == "session2"
    assert state_manager.get_state("session1", "transcript2")["data"] == "transcript2"


def test_corrupted_state_file(state_manager):
    """Test handling of corrupted state files"""
    session_id = "test-session"
    transcript_id = "test-transcript"

    # Create a corrupted state file
    state_path = state_manager._get_state_path(session_id, transcript_id)
    state_path.parent.mkdir(exist_ok=True)
    with open(state_path, "w") as f:
        f.write("invalid json {")

    # Should return empty dict instead of crashing
    state = state_manager.get_state(session_id, transcript_id)
    assert state == {}


def test_atomic_writes(state_manager):
    """Test that writes are atomic using temp files"""
    session_id = "test-session"
    transcript_id = "test-transcript"

    # Set state and verify temp file is not left behind
    state_manager.set_state(session_id, transcript_id, {"test": "data"})

    state_dir = state_manager.state_dir
    temp_files = list(state_dir.glob("*.tmp"))
    assert len(temp_files) == 0, "Temp files should be cleaned up"
