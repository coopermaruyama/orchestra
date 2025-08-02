# Orchestra 🎼

> Orchestrate your Claude Code workflow with focused extensions

## Quick Start

```bash
# Clone and install Orchestra system-wide
git clone git@github.com:coopermaruyama/orchestra.git
cd orchestra
pip install --user .

# Enable task-monitor extension (globally by default)
orchestra enable task-monitor

# Or enable to current project only
orchestra enable task-monitor --project

# Use it in Claude Code
/task start
```

> Note: Extensions include a bootstrap script that allows team members to use commands even without Orchestra installed. They'll get friendly installation instructions on first use.


## What is Orchestra?

Orchestra is a lightweight extension manager for Claude Code that helps you stay focused and productive. Extensions are enabled in `~/.claude/commands/` (global by default) or `.claude/commands/` (project-specific with `--project` flag).

> **⚠️ Important**: Claude Code does not support conflicts between user and project level commands. We recommend using global enablement (default) unless you specifically need project-specific commands.

## Available Extensions

### task
Keep Claude focused on your task requirements. No scope creep, no over-engineering.

**Commands:**
- `/task:start` - Interactive task setup with intelligent questions
- `/task:status` - Check your progress
- `/task:next` - See what to work on next
- `/task:complete` - Mark current item done
- `/focus` - Quick focus reminder

**Features:**
- Blocks off-topic commands
- Warns about scope creep
- Tracks progress automatically
- Guides you through requirements
- Git integration for task isolation

### timemachine
Automatic git checkpointing for every conversation turn. Travel back in time to any previous state.

**Commands:**
- `/timemachine:list` - View conversation checkpoints
- `/timemachine:checkout` - Checkout a specific checkpoint
- `/timemachine:view` - View full checkpoint details
- `/timemachine:rollback` - Go back n conversation turns

**Features:**
- Checkpoint every user prompt automatically
- Store full conversation metadata
- Track tools used and files modified
- Easy rollback to any previous state
- Works alongside task monitor

## Installation

### Prerequisites
- Python 3.8+
- pip (for `--user` install) or pipx (recommended for isolated install)

### Install Orchestra

**Option 1: System-wide installation (Recommended for CLI usage)**

```bash
# Clone the repository
git clone https://github.com/your-org/orchestra.git
cd orchestra

# Install system-wide (makes 'orchestra' available in PATH)
pip install --user .

# Or install with pipx (manages virtual environment automatically)
pipx install .

# with uv
uv tool install dist/orchestra-0.5.0-py3-none-any.whl
```

**Option 2: Development installation**

```bash
# Clone the repository
git clone https://github.com/your-org/orchestra.git
cd orchestra

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

**Verify Installation**

```bash
# Check that orchestra is available in PATH
which orchestra
orchestra --help
```

### Enable Extensions

```bash
# Enable task monitor (recommended)
orchestra enable task

# Enable timemachine (optional)
orchestra enable timemachine

# Project-specific enablement (current project only)
orchestra enable task --project

# List enabled extensions
orchestra list

# View logs
orchestra logs              # View all logs
orchestra logs task         # View task monitor logs only
orchestra logs --tail       # Follow logs in real-time
orchestra logs --clear      # Clear all logs

# Disable extensions
orchestra disable task
orchestra disable timemachine
```

### Quick Usage

**In Claude Code:**
```
/task:start        # Start a new task
/focus             # Quick focus reminder
/timemachine:list  # View checkpoints
```

**From CLI:**
```bash
orchestra task start
orchestra task status
orchestra timemachine list
```

## Direct Command Usage

You can run task commands directly from the command line without entering Claude Code:

```bash
# Start a new task interactively
./orchestra.py task start

# Check task status
./orchestra.py task status

# See what to work on next
./orchestra.py task next

# Mark current requirement as complete
./orchestra.py task complete

# Get a quick focus reminder
./orchestra.py task focus
```

## Team Collaboration

When you enable Orchestra extensions in a project, team members can use the commands immediately:

1. **With Orchestra installed**: Commands work directly through the `orchestra` CLI
2. **Without Orchestra**: The bootstrap script shows one-time installation instructions

The bootstrap approach means:
- No duplicate code in version control
- Always uses the latest Orchestra version
- Graceful degradation for team members
- Commands in `.claude/commands/` are automatically available

## How It Works

Orchestra uses a bootstrap architecture:
- Commands: `.claude/commands/task/*.md` (slash commands)
- Bootstrap: `.claude/orchestra/bootstrap.py` (checks for Orchestra)
- Settings: Updates `.claude/settings.json` for hooks

The bootstrap script:
1. Checks if `orchestra` is in PATH
2. If yes: Executes the command
3. If no: Shows installation instructions (once per session)

## Project Structure

```
orchestra/
├── orchestra.py           # Main CLI
├── extensions/
│   └── task-monitor/
│       └── task_monitor.py
└── README.md
```

## Future Extensions

Ideas for future Orchestra extensions:
- `test-runner` - Run tests automatically on file changes
- `doc-writer` - Generate documentation as you code
- `pr-ready` - Ensure code is PR-ready with checks
- `time-tracker` - Track time spent on tasks

## Development & Testing

### Setup Development Environment

```bash
# Development setup
uv sync --extra dev
```

### Run Tests

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=orchestra --cov-report=term-missing

# Run specific test types
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests only
uv run pytest -m deviation_detection  # Deviation detection tests

# Run tests verbosely
uv run pytest -v
```

### Testing Documentation

- **[Testing Guide](docs/testing-guide.md)** - Comprehensive testing instructions
- **[Quick Test Reference](docs/quick-test-reference.md)** - Quick commands for testing
- **[Testing Scenarios](docs/testing.md)** - Detailed test scenarios

### Code Quality

```bash
# Format code
uv run black .

# Lint code
uv run ruff check .

# Type checking
uv run mypy src/

# Run all quality checks
uv run black . && uv run ruff check . && uv run mypy src/


## Build
```bash
# Build the package
uv  build

```

### Manual Testing

```bash
# Test Orchestra CLI directly
orchestra --help
orchestra list
orchestra enable task-monitor

# Test task monitor commands
orchestra task start
orchestra task status
orchestra task next
orchestra task complete
```

## Contributing

Have an idea for an extension? Extensions are just Python scripts that integrate with Claude Code's hooks and slash commands. See the task-monitor source for an example.

## License

MIT
