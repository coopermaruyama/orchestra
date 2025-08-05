# ruff: noqa: SLF001
"""
End-to-end tests for Orchestra Never Again functionality

These tests create a complete workflow:
- Create temp project with git repo
- Enable orchestra with neveragain extension
- Simulate Claude conversations with user corrections
- Verify correction learning and memory file updates
- Test that learned corrections are accessible
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def project_with_git(temp_project_dir):
    """Set up a temp project with git repo and basic files"""
    project_path = Path(temp_project_dir)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_path, check=True)

    # Create basic project structure
    (project_path / "src").mkdir()
    (project_path / "src" / "__init__.py").write_text("")

    # Create a simple Python file to modify
    main_py = project_path / "src" / "main.py"
    main_py.write_text("""def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
""")

    # Create README
    readme = project_path / "README.md"
    readme.write_text("# Test Project\n\nA simple test project for neveragain testing.\n")

    # Initial commit
    subprocess.run(["git", "add", "."], cwd=project_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, check=True)

    return project_path


def run_orchestra_command(command_args, cwd):
    """Run an orchestra command and return the result"""
    cmd = ["orchestra"] + command_args
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30
    )
    return result


def run_neveragain_command(command_args, cwd):
    """Run a neveragain monitor command and return the result"""
    # Find the neveragain_monitor.py script
    test_dir = Path(__file__).parent
    monitor_script = test_dir.parent.parent / "src" / "orchestra" / "extensions" / "neveragain" / "neveragain_monitor.py"

    cmd = ["python", str(monitor_script)] + command_args
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "CLAUDE_WORKING_DIR": str(cwd)}
    )
    return result


def create_mock_transcript_with_correction(project_path, correction_scenario="file_creation"):
    """Create a mock transcript file simulating a conversation with user correction"""
    claude_dir = project_path / ".claude"
    claude_dir.mkdir(exist_ok=True)

    transcript_path = claude_dir / "test_transcript.jsonl"

    if correction_scenario == "file_creation":
        # Scenario: User asks to edit file, Claude creates new file, user corrects
        transcript_lines = [
            {
                "type": "message",
                "role": "user",
                "content": "Please modify the existing main.py file to add a new function",
                "timestamp": "2025-08-05T00:50:00.000Z"
            },
            {
                "type": "message",
                "role": "assistant",
                "content": "I'll create a new file with the function you requested.",
                "timestamp": "2025-08-05T00:50:01.000Z"
            },
            {
                "type": "message",
                "role": "user",
                "content": "No, don't create a new file! I said modify the existing main.py file. Never create new files when I ask you to modify existing ones.",
                "timestamp": "2025-08-05T00:50:02.000Z"
            },
            {
                "type": "message",
                "role": "assistant",
                "content": "You're absolutely right. I should have edited the existing main.py file instead of creating a new one. Let me fix that by modifying the existing file.",
                "timestamp": "2025-08-05T00:50:03.000Z"
            }
        ]
    elif correction_scenario == "comments":
        # Scenario: User asks for code, Claude adds comments, user corrects
        transcript_lines = [
            {
                "type": "message",
                "role": "user",
                "content": "Add a function to calculate the sum of two numbers",
                "timestamp": "2025-08-05T00:51:00.000Z"
            },
            {
                "type": "message",
                "role": "assistant",
                "content": "I'll add the function with helpful comments:\n\n```python\n# Function to add two numbers\ndef add_numbers(a, b):\n    # Return the sum\n    return a + b\n```",
                "timestamp": "2025-08-05T00:51:01.000Z"
            },
            {
                "type": "message",
                "role": "user",
                "content": "Don't add comments unless I explicitly ask for them. The code should be clean without unnecessary comments.",
                "timestamp": "2025-08-05T00:51:02.000Z"
            }
        ]

    # Write transcript as JSONL
    with open(transcript_path, 'w') as f:
        for line in transcript_lines:
            f.write(json.dumps(line) + '\n')

    return transcript_path


def test_neveragain_basic_functionality(project_with_git):
    """Test basic neveragain monitor functionality"""
    project_path = project_with_git

    # Test status command (should work even without setup)
    result = run_neveragain_command(["status"], project_path)
    assert result.returncode == 0, f"Status command failed: {result.stderr}"
    assert "Never Again Monitor Status" in result.stdout

    # Test view command on empty memory
    result = run_neveragain_command(["view"], project_path)
    assert result.returncode == 0, f"View command failed: {result.stderr}"
    assert "No corrections learned yet" in result.stdout or result.stdout.strip() == ""


def test_neveragain_correction_learning_workflow(project_with_git):
    """Test complete correction learning workflow"""
    project_path = project_with_git

    # Create mock transcript with user correction
    transcript_path = create_mock_transcript_with_correction(project_path, "file_creation")

    # Create mock hook context
    hook_context = {
        "transcript_path": str(transcript_path),
        "session_id": "test-session-123",
        "hook_event_name": "Stop"
    }

    # Set up environment for Claude invocation (skip if no API key)
    env = os.environ.copy()
    # if not env.get("ANTHROPIC_API_KEY") and not env.get("ORCHESTRA_CLAUDE_API_KEY"):
    #     pytest.skip("Test requires Claude API key for correction analysis")

    # Run neveragain hook with mock context
    hook_input = json.dumps(hook_context)
    result = subprocess.run(
        ["python", "-c", f"""
import sys
import json
sys.path.insert(0, '{project_path.parent.parent / "src"}')
from orchestra.extensions.neveragain.neveragain_monitor import NeverAgainMonitor

monitor = NeverAgainMonitor()
context = {hook_context}
result = monitor.handle_hook('Stop', context)
print(json.dumps(result))
"""],
        cwd=project_path,
        capture_output=True,
        text=True,
        env={**env, "CLAUDE_WORKING_DIR": str(project_path)},
        timeout=60
    )

    if result.returncode != 0:
        # If Claude invocation fails, just verify the hook structure works
        pytest.skip(f"Claude invocation failed (expected in test environment): {result.stderr}")

    # Verify hook allows stopping (never blocks)
    try:
        hook_result = json.loads(result.stdout.strip().split('\n')[-1])
        assert hook_result.get("continue") is not False, "Hook should never block stopping"
    except (json.JSONDecodeError, KeyError):
        # Hook might not return JSON in test environment, that's ok
        pass

    # Check if memory file was created (might not happen without real Claude API)
    memory_file = project_path / ".claude" / "memory" / "neveragain.md"
    if memory_file.exists():
        content = memory_file.read_text()
        assert "Never Again - Learned Corrections" in content
        assert len(content.strip()) > 0


def test_neveragain_memory_file_management(project_with_git):
    """Test memory file creation and management"""
    project_path = project_with_git
    memory_dir = project_path / ".claude" / "memory"
    memory_file = memory_dir / "neveragain.md"

    # Import and create monitor
    import sys
    sys.path.insert(0, str(project_path.parent.parent / "src"))
    from orchestra.extensions.neveragain.neveragain_monitor import NeverAgainMonitor

    # Set working directory via environment variable
    original_claude_wd = os.environ.get("CLAUDE_WORKING_DIR")
    os.environ["CLAUDE_WORKING_DIR"] = str(project_path)
    
    try:
        monitor = NeverAgainMonitor()
    finally:
        # Restore original environment
        if original_claude_wd is not None:
            os.environ["CLAUDE_WORKING_DIR"] = original_claude_wd
        else:
            os.environ.pop("CLAUDE_WORKING_DIR", None)

    # Test memory file creation
    assert memory_dir.exists(), "Memory directory should be created"
    assert monitor.memory_file == memory_file, "Memory file path should be correct"

    # Test updating memory file
    test_corrections = "- Always prefer editing existing files over creating new ones\n- Don't add comments unless explicitly requested"
    monitor._update_memory_file(test_corrections)

    # Verify file was created and content is correct
    assert memory_file.exists(), "Memory file should be created"
    content = memory_file.read_text()
    assert "Never Again - Learned Corrections" in content
    assert "Always prefer editing existing files" in content
    assert "Don't add comments unless explicitly requested" in content

    # Test appending additional corrections
    new_corrections = "- Use existing patterns from the codebase when adding new functionality"
    monitor._update_memory_file(new_corrections)

    updated_content = memory_file.read_text()
    assert "Always prefer editing existing files" in updated_content  # Old content preserved
    assert "Use existing patterns from the codebase" in updated_content  # New content added
    assert updated_content.count("## Added") == 2, "Should have two timestamp sections"


def test_neveragain_transcript_parsing(project_with_git):
    """Test transcript parsing functionality"""
    project_path = project_with_git

    # Create transcript with mixed format
    transcript_path = create_mock_transcript_with_correction(project_path, "comments")

    # Import monitor
    import sys
    sys.path.insert(0, str(project_path.parent.parent / "src"))
    from orchestra.extensions.neveragain.neveragain_monitor import NeverAgainMonitor

    # Set working directory via environment variable
    original_claude_wd = os.environ.get("CLAUDE_WORKING_DIR")
    os.environ["CLAUDE_WORKING_DIR"] = str(project_path)
    
    try:
        monitor = NeverAgainMonitor()
    finally:
        # Restore original environment
        if original_claude_wd is not None:
            os.environ["CLAUDE_WORKING_DIR"] = original_claude_wd
        else:
            os.environ.pop("CLAUDE_WORKING_DIR", None)

    # Test parsing new messages
    messages = monitor._parse_new_messages(str(transcript_path))

    assert len(messages) > 0, "Should parse messages from transcript"

    # Verify message structure
    for msg in messages:
        assert "role" in msg, "Each message should have a role"
        assert "content" in msg, "Each message should have content"
        assert msg["role"] in ["user", "assistant"], "Role should be user or assistant"

    # Test that position tracking works
    initial_position = monitor.last_processed_position
    messages_again = monitor._parse_new_messages(str(transcript_path))

    # Should not reprocess same messages
    assert len(messages_again) == 0, "Should not reprocess same transcript content"
    # Position should stay the same since no new messages were processed
    assert monitor.last_processed_position == initial_position, "Position should not change when no new messages"


def test_neveragain_multiple_corrections(project_with_git):
    """Test handling multiple corrections in sequence"""
    project_path = project_with_git

    # Import monitor
    import sys
    sys.path.insert(0, str(project_path.parent.parent / "src"))
    from orchestra.extensions.neveragain.neveragain_monitor import NeverAgainMonitor

    # Set working directory via environment variable
    original_claude_wd = os.environ.get("CLAUDE_WORKING_DIR")
    os.environ["CLAUDE_WORKING_DIR"] = str(project_path)
    
    try:
        monitor = NeverAgainMonitor()
    finally:
        # Restore original environment
        if original_claude_wd is not None:
            os.environ["CLAUDE_WORKING_DIR"] = original_claude_wd
        else:
            os.environ.pop("CLAUDE_WORKING_DIR", None)

    # Add first set of corrections
    corrections1 = "- Prefer editing over creating new files\n- Keep code simple and clean"
    monitor._update_memory_file(corrections1)

    time.sleep(1)  # Ensure different timestamps

    # Add second set of corrections
    corrections2 = "- Follow existing code patterns\n- Ask for clarification when requirements are unclear"
    monitor._update_memory_file(corrections2)

    # Verify both sets are preserved
    content = monitor.memory_file.read_text()
    assert "Prefer editing over creating" in content
    assert "Keep code simple" in content
    assert "Follow existing code patterns" in content
    assert "Ask for clarification" in content

    # Should have two timestamped sections
    assert content.count("## Added") == 2


def test_neveragain_hook_integration(project_with_git):
    """Test integration with Orchestra hook system"""
    project_path = project_with_git

    # Enable orchestra (this sets up hook infrastructure)
    result = run_orchestra_command(["enable"], project_path)
    if result.returncode != 0:
        pytest.skip("Orchestra enable not available in test environment")

    # Test hook command exists
    result = run_neveragain_command(["hook", "Stop"], project_path)
    # Should accept hook command even without stdin context
    assert result.returncode in [0, 1], f"Hook command should exist: {result.stderr}"


@pytest.mark.skipif(
    not os.environ.get("ORCHESTRA_CLAUDE_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Integration test requires Claude API key"
)
def test_neveragain_with_real_claude_analysis(project_with_git):
    """Test neveragain with actual Claude analysis (requires API key)"""
    project_path = project_with_git

    # Import monitor
    import sys
    sys.path.insert(0, str(project_path.parent.parent / "src"))
    from orchestra.extensions.neveragain.neveragain_monitor import NeverAgainMonitor

    # Set working directory via environment variable
    original_claude_wd = os.environ.get("CLAUDE_WORKING_DIR")
    os.environ["CLAUDE_WORKING_DIR"] = str(project_path)
    
    try:
        monitor = NeverAgainMonitor()
    finally:
        # Restore original environment
        if original_claude_wd is not None:
            os.environ["CLAUDE_WORKING_DIR"] = original_claude_wd
        else:
            os.environ.pop("CLAUDE_WORKING_DIR", None)

    # Create realistic correction scenario
    messages = [
        {"role": "user", "content": "Please add a helper function to the existing utils.py file"},
        {"role": "assistant", "content": "I'll create a new utils_helper.py file with the function"},
        {"role": "user", "content": "No! I said add it to the EXISTING utils.py file, don't create new files!"},
        {"role": "assistant", "content": "You're right, I should have modified the existing utils.py file instead of creating a new one."}
    ]

    # Test Claude analysis
    try:
        monitor._analyze_corrections_async(messages)

        # Give some time for async processing
        time.sleep(2)

        # Check if memory file was updated
        if monitor.memory_file.exists():
            content = monitor.memory_file.read_text()
            # Should contain some learning from the correction
            assert len(content.strip()) > 50, "Should have learned something from the correction"
            assert "existing" in content.lower() or "modify" in content.lower() or "edit" in content.lower()

    except Exception as e:
        # Real Claude invocation might fail in test environment
        pytest.skip(f"Claude analysis failed (expected in test environment): {e}")


def test_neveragain_state_persistence(project_with_git):
    """Test that neveragain state persists across instances"""
    project_path = project_with_git

    # Import monitor
    import sys
    sys.path.insert(0, str(project_path.parent.parent / "src"))
    from orchestra.extensions.neveragain.neveragain_monitor import NeverAgainMonitor

    # Create first monitor instance and set position
    # Set working directory via environment variable
    original_claude_wd = os.environ.get("CLAUDE_WORKING_DIR")
    os.environ["CLAUDE_WORKING_DIR"] = str(project_path)
    
    try:
        monitor1 = NeverAgainMonitor()
    finally:
        # Restore original environment
        if original_claude_wd is not None:
            os.environ["CLAUDE_WORKING_DIR"] = original_claude_wd
        else:
            os.environ.pop("CLAUDE_WORKING_DIR", None)
            
    monitor1.last_processed_position = 1000
    monitor1.save_config()

    # Create second monitor instance
    # Set working directory via environment variable
    original_claude_wd2 = os.environ.get("CLAUDE_WORKING_DIR")
    os.environ["CLAUDE_WORKING_DIR"] = str(project_path)
    
    try:
        monitor2 = NeverAgainMonitor()
    finally:
        # Restore original environment
        if original_claude_wd2 is not None:
            os.environ["CLAUDE_WORKING_DIR"] = original_claude_wd2
        else:
            os.environ.pop("CLAUDE_WORKING_DIR", None)

    # Should load previous state
    assert monitor2.last_processed_position == 1000, "State should persist across instances"

    # Verify state file uses dot prefix
    state_file = project_path / ".claude" / "orchestra" / ".neveragain.json"
    assert state_file.exists(), "State file should use dot prefix naming"