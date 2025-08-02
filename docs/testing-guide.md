# Orchestra Testing Guide

This guide provides comprehensive instructions for testing Orchestra extensions, including both manual testing and automated test procedures.

## Prerequisites

Before testing, ensure you have:

1. **Python 3.8+** installed
2. **Git** installed and initialized in your project
3. **uv** (recommended) or pip for package management
4. Orchestra installed: `pip install -e .` or `uv pip install -e .`

## Testing Task Monitor Extension

### Installation Test

```bash
# Install the task monitor extension
orchestra install task

# Verify installation
orchestra list

# Check that commands were created
ls ~/.claude/commands/task/
# Should show: start.md, progress.md, next.md, complete.md

ls ~/.claude/commands/focus.md
# Should exist
```

### Basic Functionality Test

1. **Start a new task**:
   ```bash
   orchestra task start
   # Follow the interactive prompts
   # Choose a task type (e.g., "bug")
   # Enter task description
   # Add requirements
   ```

2. **Check task status**:
   ```bash
   orchestra task status
   # Should show current task and requirements
   ```

3. **View next action**:
   ```bash
   orchestra task next
   # Should show the highest priority incomplete requirement
   ```

4. **Complete a requirement**:
   ```bash
   orchestra task complete
   # Should mark current requirement as done
   ```

### Hook Testing

1. **Create a test file** to trigger hooks:
   ```bash
   echo "test content" > test_file.txt
   ```

2. **Check hook configuration**:
   ```bash
   cat ~/.claude/settings.json | grep -A 10 "hooks"
   # Should show PreToolUse, PostToolUse, UserPromptSubmit, Stop, SubagentStop
   ```

3. **Verify state persistence**:
   ```bash
   cat .claude/orchestra/task.json
   # Should show task configuration and progress
   ```

### Git Integration Test

1. **Check git task state**:
   ```bash
   git branch | grep task-monitor
   # Should show task branch if git integration is active
   ```

2. **View WIP snapshots**:
   ```bash
   git show-ref | grep wip
   # Should show WIP references
   ```

## Testing TimeMachine Extension

### Installation Test

```bash
# Install the timemachine extension
orchestra install timemachine

# Verify installation
orchestra list

# Check that commands were created
ls ~/.claude/commands/timemachine/
# Should show: list.md, checkout.md, view.md, rollback.md
```

### Basic Functionality Test

1. **List checkpoints** (initially empty):
   ```bash
   orchestra timemachine list
   # Should show "No checkpoints found." initially
   ```

2. **Create test checkpoints**:
   ```python
   # Create a test script: test_checkpoint.py
   #!/usr/bin/env python3
   import json
   import sys
   import os
   
   sys.path.insert(0, os.path.expanduser("~/.claude/orchestra/timemachine"))
   from timemachine_monitor import TimeMachineMonitor
   
   monitor = TimeMachineMonitor()
   
   # Simulate UserPromptSubmit
   monitor.handle_hook("UserPromptSubmit", {
       "prompt": "Test prompt for checkpoint",
       "session_id": "test-123",
       "transcript_path": "/tmp/test.jsonl"
   })
   
   # Simulate Stop to create checkpoint
   monitor.handle_hook("Stop", {
       "session_id": "test-123",
       "stop_hook_active": False
   })
   
   # List checkpoints
   monitor.list_checkpoints()
   ```

3. **Run the test**:
   ```bash
   python test_checkpoint.py
   # Should create a checkpoint if in a git repo
   ```

4. **View checkpoint details**:
   ```bash
   orchestra timemachine view checkpoint-0
   # Should show checkpoint metadata
   ```

5. **Test rollback** (be careful in real projects!):
   ```bash
   # First, make a change
   echo "new content" >> test_file.txt
   
   # Rollback to previous state
   orchestra timemachine rollback 1
   
   # Verify the change was reverted
   cat test_file.txt
   ```

### State Persistence Test

```bash
# Check config file
cat .claude/orchestra/timemachine.json
# Should show checkpoints array and settings

# Verify checkpoints persist across sessions
orchestra timemachine list
# Should still show previously created checkpoints
```

## Testing Multiple Extensions Together

1. **Install both extensions**:
   ```bash
   orchestra install task
   orchestra install timemachine
   ```

2. **Verify they don't conflict**:
   ```bash
   # Check bootstrap script handles both
   cat ~/.claude/orchestra/bootstrap.sh | grep -E "task|timemachine"
   
   # Check both config files exist
   ls .claude/orchestra/
   # Should show: task.json, timemachine.json (after use)
   ```

3. **Test hook execution order**:
   - Both extensions use the same hooks
   - Bootstrap script determines which runs based on installed scripts
   - Only one extension's hooks run per installation

## Automated Testing

### Running Unit Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=orchestra --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_orchestra.py

# Run tests with markers
uv run pytest -m "unit"
uv run pytest -m "integration"
```

### Code Quality Checks

```bash
# Format code
uv run black .

# Lint code
uv run ruff check .

# Type checking
uv run mypy src/
```

## Testing Hook Behavior

### Manual Hook Testing

1. **Create a hook test script**:
   ```bash
   cat > test_hook.sh << 'EOF'
   #!/bin/bash
   echo "Hook Input:" >&2
   cat | jq . >&2
   echo '{"decision": "approve"}'
   EOF
   chmod +x test_hook.sh
   ```

2. **Test with the script**:
   ```bash
   echo '{"hook_event_name": "Stop", "session_id": "test"}' | \
     sh ~/.claude/orchestra/bootstrap.sh hook Stop
   ```

### Testing Error Scenarios

1. **Test missing git repo**:
   ```bash
   cd /tmp
   mkdir no-git-test && cd no-git-test
   orchestra timemachine list
   # Should handle gracefully
   ```

2. **Test invalid config**:
   ```bash
   echo "invalid json" > .claude/orchestra/task.json
   orchestra task status
   # Should handle error gracefully
   ```

## Debugging Tips

### Enable Debug Logging

1. **Check log files**:
   ```bash
   # Easy way - use Orchestra's logs command
   orchestra logs              # View all logs
   orchestra logs task         # Just task monitor logs
   orchestra logs timemachine  # Just timemachine logs
   orchestra logs --tail       # Follow logs in real-time
   orchestra logs --clear      # Clear all logs
   
   # Manual way - find and tail logs
   find /var/folders -name "task_monitor.log" 2>/dev/null | xargs tail -f
   find /var/folders -name "timemachine.log" 2>/dev/null | xargs tail -f
   ```

2. **Add debug output**:
   ```python
   # In your extension code
   self.logger.debug(f"Debug info: {variable}")
   ```

### Common Issues and Solutions

1. **"No monitor script found" error**:
   - Check enablement: `ls ~/.claude/orchestra/*/`
   - Re-enable extension: `orchestra disable <ext> && orchestra enable <ext>`

2. **Hooks not firing**:
   - Check settings.json has correct hook configuration
   - Verify bootstrap.sh is executable: `ls -la ~/.claude/orchestra/`

3. **Config not saving**:
   - Check permissions: `ls -la .claude/orchestra/`
   - Ensure directory exists: `mkdir -p .claude/orchestra`

## Testing in Different Environments

### Testing with Claude Code

1. **Enable extension in Claude Code session**:
   ```
   /bash orchestra enable task
   /bash orchestra enable timemachine
   ```

2. **Test slash commands**:
   ```
   /task:start
   /task:status
   /timemachine:list
   ```

3. **Verify hooks fire on actions**:
   - Edit a file
   - Run a command
   - Check logs to see hook execution

### Testing in CI/CD

Example GitHub Actions workflow:

```yaml
name: Test Orchestra
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e .
          uv pip install -e ".[dev]"
      
      - name: Run tests
        run: |
          uv run pytest --cov=orchestra
          uv run black --check .
          uv run ruff check .
          uv run mypy src/
```

## Performance Testing

### Measure Hook Execution Time

```python
# Add to your test script
import time

start = time.time()
monitor.handle_hook("Stop", context)
end = time.time()
print(f"Hook execution time: {end - start:.3f}s")
```

### Test with Large Repositories

1. Create many files:
   ```bash
   for i in {1..1000}; do echo "test" > "test_$i.txt"; done
   ```

2. Test checkpoint creation speed:
   ```bash
   time orchestra timemachine list
   ```

## Best Practices for Testing

1. **Always test in a separate directory** or branch to avoid data loss
2. **Back up important work** before testing rollback features
3. **Check git status** before and after tests
4. **Review logs** when something unexpected happens
5. **Test incrementally** - verify each step before proceeding

## Reporting Issues

When reporting issues, include:

1. **Orchestra version**: `orchestra version`
2. **Python version**: `python --version`
3. **Git version**: `git --version`
4. **Error messages** from logs
5. **Steps to reproduce** the issue
6. **Expected vs actual** behavior

## Contributing Tests

When adding new features:

1. **Write unit tests** in `tests/`
2. **Add integration tests** for end-to-end workflows
3. **Document test procedures** in this guide
4. **Include test commands** in docstrings
5. **Add CI checks** for new functionality