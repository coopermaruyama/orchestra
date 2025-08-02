# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Since this is an extension for Claude Code, important documentation references are included at:

@docs/claude-docs/configuration-reference.md
@docs/claude-docs/slash-commands-reference.md
@docs/claude-docs/hooks-reference.md
@docs/claude-docs/subagents-reference.md
@docs/claude-docs/tool-reference.md

## Project Overview

Orchestra is a lightweight extension manager for Claude Code that helps developers stay focused and productive. It consists of:

1. **Orchestra CLI** (`orchestra.py`) - Extension installer and manager with built-in log viewer
2. **Task Monitor Extension** (`extensions/task/task_monitor.py`) - Prevents scope creep and tracks progress
3. **TimeMachine Extension** (`extensions/timemachine/timemachine_monitor.py`) - Automatic git checkpointing for every conversation turn

## Development Commands

### Testing and Code Quality
```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=orchestra --cov-report=term-missing

# Code formatting
uv run black .

# Linting
uv run ruff check .

# Type checking
uv run mypy src/
```

### Building and Installation
```bash
# Install locally for development
uv pip install -e .

# Build wheel and source distribution
uv build

# Install dependencies (handled automatically by uv)
uv sync

# Install specific dependency groups
uv sync --extra dev
```

### Running Orchestra
```bash
# Make executable and run
chmod +x orchestra.py
./orchestra.py

# Enable task-monitor extension locally
./orchestra.py enable task-monitor

# Enable globally for all projects
./orchestra.py enable task-monitor --global

# List enabled extensions
./orchestra.py list

# View extension logs
./orchestra.py logs              # View all logs
./orchestra.py logs task         # View task monitor logs only
./orchestra.py logs --tail       # Follow logs in real-time
./orchestra.py logs --clear      # Clear all logs
```

## Architecture

### Orchestra CLI (orchestra.py)
- **Extension Management**: Installs extensions to `.claude/commands/` (local) or `~/.claude/commands/` (global)
- **Configuration**: Auto-configures Claude Code hooks in `.claude/settings.json`
- **Current Extensions**: Only `task-monitor` is implemented

### Task Monitor Extension (task_monitor.py)
- **Hook Integration**: Uses Claude Code's pre-command, post-command, prompt, and file-change hooks
- **Deviation Detection**: Identifies scope creep, over-engineering, and off-topic commands
- **Progress Tracking**: Monitors requirement completion and provides focus guidance
- **Interactive Setup**: `/task start` provides intelligent task setup based on task type (bug fix, feature, refactor, etc.)

### Key Data Structures
```python
@dataclass
class TaskRequirement:
    id: str
    description: str
    priority: int  # 1-5, where 1 is highest
    completed: bool = False

class DeviationType(Enum):
    SCOPE_CREEP = "scope_creep"
    OFF_TOPIC = "off_topic"
    OVER_ENGINEERING = "over_engineering"
    MISSING_REQUIREMENT = "missing_requirement"
    UNNECESSARY_WORK = "unnecessary_work"
```

### Configuration Files
- `.claude-task.json` - Task state and progress (created by task monitor)
- `.claude/settings.json` - Claude Code settings including hook configurations
- `claude-slash-commands.json` - Claude Code slash command definitions (legacy)
- `claude-hooks.json` - Claude Code hook configurations (legacy)

## Task Monitor Usage

### Slash Commands
- `/task:start` - Interactive task setup with type-specific questions
- `/task:status` - Show current progress and requirements
- `/task:next` - Display next priority action
- `/task:complete` - Mark current requirement as complete
- `/focus` - Quick focus reminder

### Hook Behaviors
- **Pre-command**: Analyzes commands for deviations, blocks/warns based on severity
- **Post-command**: Updates requirement completion, shows progress
- **Prompt**: Enhances prompts with task context and current focus
- **File-change**: Warns about creating unnecessary files before core requirements

## Extension Development

Extensions are Python scripts that integrate with Claude Code's hooks and slash commands. The task-monitor serves as a reference implementation showing:

1. Hook handling (`handle_hook` method)
2. Slash command configuration
3. State persistence (JSON config files)
4. Interactive CLI interfaces
5. Integration with Claude Code's workflow

## File Structure

```
orchestra/
├── orchestra.py                    # Main extension manager CLI
├── extensions/task-monitor/
│   └── task_monitor.py            # Task alignment and focus extension
├── pyproject.toml                 # Build configuration and dev dependencies
├── requirements.txt               # Runtime dependencies
└── README.md                      # User documentation
```