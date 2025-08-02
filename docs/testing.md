# Testing

>  Scenarios for the task monitor and git integration

## Task Monitor Testing

```bash
# Set up a test git repository
mkdir test_project && cd test_project && git init
git config user.email "test@example.com" && git config user.name "Test
User"
echo "# Test Project" > README.md && git add . && git commit -m "Initial
commit"

# Initialize a task with git integration
orchestra task-monitor init "Fix login bug" "Reproduce issue" "Debug code" "Implement fix" "Add tests"

# Check that a git branch was created
git branch -a   # Should show task-monitor/[task-id]

# Make some code changes and commit
echo "def login():" > auth.py && git add . && git commit -m "Add login
function"

# Test stop hook behavior
echo '{"session_id": "test", "transcript_path": "/tmp/test",
"hook_event_name": "Stop", "stop_hook_active": false}' | python
path/to/task_monitor.py hook Stop

# Complete requirements and test again
python path/to/task_monitor.py complete  # Repeat until all done
```

2. Automated Testing

The integration tests in tests/test_task_monitor_integration.py cover the
core functionality:

```bash
# Run all task monitor tests
python -m pytest tests/test_task_monitor_integration.py -v

# Run specific test
python -m pytest tests/test_task_monitor_integration.py -k
test_hook_command_json_input -v
```

3. Git Integration Testing

```python
# Test script to verify git functionality
from orchestra.common import GitTaskManager, SubagentRunner
import tempfile
import subprocess

def test_git_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmpdir)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'],
  cwd=tmpdir)
        subprocess.run(['git', 'config', 'user.name', 'Test User'],
cwd=tmpdir)

        # Create initial commit
        with open(f"{tmpdir}/README.md", 'w') as f:
            f.write("# Test Project")
        subprocess.run(['git', 'add', '.'], cwd=tmpdir)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'],
cwd=tmpdir)

        # Test GitTaskManager
        git_manager = GitTaskManager(tmpdir)
        task_state = git_manager.create_task_branch(
            task_description="Test task"
        )

        print(f"Created branch: {task_state.branch_name}")
        print(f"Base SHA: {task_state.base_sha}")

        # Make changes and test diff
        with open(f"{tmpdir}/test.py", 'w') as f:
            f.write("print('Hello, World!')")
        subprocess.run(['git', 'add', '.'], cwd=tmpdir)
        subprocess.run(['git', 'commit', '-m', 'Add test file'],
cwd=tmpdir)

        # Get diff
        diff = git_manager.get_task_diff(task_state)
        print(f"Task diff:\n{diff}")
```

4. Subagent Testing

```python
# Test subagent invocation
from orchestra.common import SubagentRunner, GitTaskManager

def test_subagent():
    git_manager = GitTaskManager()
    subagent_runner = SubagentRunner(git_manager)

    # Check available subagents
    agents = subagent_runner.get_available_subagents()
    print("Available subagents:", agents)

    # Validate environment
    validation = subagent_runner.validate_subagent_environment()
    print("Environment validation:", validation)
```

5. Claude Code Integration Testing

To test the actual Claude Code integration:

1. Set up a project with the task monitor installed
2. Use Claude Code interactively and run /task init "Your task" "Req 1"
"Req 2"
3. Do some development work and make git commits
4. Try to exit Claude Code - the stop hook should intervene if requirements
  aren't complete
5. Complete requirements using /task complete and try again

6. Hook Testing

```bash
# Test different hook scenarios
echo '{"session_id": "test", "transcript_path": "/tmp/test",
"hook_event_name": "Stop", "stop_hook_active": false}' | python
task_monitor.py hook Stop

# Test recursion prevention
echo '{"session_id": "test", "transcript_path": "/tmp/test",
"hook_event_name": "Stop", "stop_hook_active": true}' | python
task_monitor.py hook
```