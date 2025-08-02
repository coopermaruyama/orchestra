# TimeMachine Extension

## Overview

The TimeMachine extension will create automatic git checkpoints for every user prompt, allowing users to view their conversation history and rollback to any previous state. Unlike the task extension which focuses on task management, TimeMachine focuses on conversation-driven version control.

## Key Differences from Task Extension

- Checkpoint on every prompt (not just task-related actions)
- Store conversation metadata in commit messages (user prompt, task info, transcript UUID)
- Provide conversation-aware navigation (list by prompts, not just git commits)
- Direct integration with transcript files for viewing full prompts

## Implementation Plan

### 1. Create Extension Structure

```
src/orchestra/extensions/timemachine/
├── __init__.py
├── timemachine_monitor.py    # Main extension class
└── checkpoint_manager.py      # Git checkpoint management
```

### 2. TimeMachineMonitor Class

- Inherit from GitAwareExtension
- State file: `.claude-timemachine.json`
- Track checkpoint history with metadata

### 3. Hook Implementation

**PreToolUse Hook:**
- Create a WIP checkpoint before any tool execution
- Store current prompt and context

**PostToolUse Hook:**
- Update checkpoint with tool results
- Track which files were modified

**Stop Hook:**
- Finalize the checkpoint for this conversation turn
- Store complete metadata in commit message

### 4. Checkpoint Metadata Format

Commit messages will contain structured JSON:

```json
{
  "user_prompt": "Add error handling to the login function",
  "task_id": "task-monitor-123abc",
  "task_description": "Implement user authentication",
  "transcript_id": "00893aaf-19fa-41d2-8238-13269b9b3ca0",
  "timestamp": "2024-01-20T10:30:00Z",
  "tools_used": ["Edit", "Read", "Bash"],
  "files_modified": ["src/auth.py", "tests/test_auth.py"]
}
```

### 5. Commands Implementation

**`orchestra timemachine list`:**
- Parse WIP branch commits
- Extract and display user prompts
- Show relative timestamps
- Format: `[n turns ago] <timestamp> <prompt preview>`

**`orchestra timemachine checkout [id]`:**
- Checkout the specific WIP commit
- Restore working directory to that state
- Show what changed since then

**`orchestra timemachine view [id]`:**
- Read transcript file from commit metadata
- Display full user prompt
- Show context (task, files modified)

**`orchestra timemachine rollback n`:**
- Go back n conversation turns
- Equivalent to checkout but using relative numbering

### 6. State Management (`.claude-timemachine.json`)

```json
{
  "enabled": true,
  "current_session": "session-123",
  "checkpoints": [
    {
      "id": "checkpoint-1",
      "commit_sha": "abc123",
      "prompt_preview": "Add error handling...",
      "timestamp": "2024-01-20T10:30:00Z"
    }
  ],
  "settings": {
    "max_checkpoints": 100,
    "auto_cleanup": true,
    "include_untracked": false
  }
}
```

### 7. Integration with Orchestra Registry

- Add "timemachine" to extensions dictionary
- Configure hooks for PreToolUse, PostToolUse, and Stop
- Create slash commands for interactive use

### 8. Advanced Features

- **Checkpoint compression:** Squash multiple small changes
- **Branch management:** Clean up old WIP branches
- **Diff viewing:** Show what changed between checkpoints
- **Search:** Find checkpoints by prompt content

## Benefits

1. **Perfect undo:** Rollback to any previous conversation state
2. **Conversation history:** See what you asked Claude and when
3. **Debugging aid:** Trace when issues were introduced
4. **Learning tool:** Review how problems were solved
5. **Safety net:** Never lose work due to mistakes

## Technical Considerations

- Use same git-wip script as task extension
- Ensure compatibility with existing WIP branches
- Handle large repositories efficiently
- Manage checkpoint storage (auto-cleanup old ones)
- Work well with task extension (share branch namespace)

## Slash Commands for Claude Code

Optional slash commands to make it easier:
- `/timemachine` - Show recent checkpoints
- `/timemachine:rollback` - Interactive rollback
- `/timemachine:diff` - Show changes since checkpoint