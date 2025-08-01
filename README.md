# Orchestra 🎼

> Orchestrate your Claude Code workflow with focused extensions

## Quick Start

```bash
# Clone and install Orchestra system-wide
git clone git@github.com:coopermaruyama/orchestra.git
cd orchestra
pip install --user .

# Install task-monitor extension (local to current project)
orchestra install task-monitor

# Or install globally for all projects
orchestra install task-monitor --global

# Use it in Claude Code
/task start
```

> Note: Extensions include a bootstrap script that allows team members to use commands even without Orchestra installed. They'll get friendly installation instructions on first use.


## What is Orchestra?

Orchestra is a lightweight extension manager for Claude Code that helps you stay focused and productive. Extensions are installed to `.claude/commands/` (local) or `~/.claude/commands/` (global).

## Available Extensions

### task-monitor
Keep Claude focused on your task requirements. No scope creep, no over-engineering.

**Commands:**
- `/task start` - Interactive task setup with intelligent questions
- `/task status` - Check your progress
- `/task next` - See what to work on next
- `/task complete` - Mark current item done
- `/focus` - Quick focus reminder

**Features:**
- Blocks off-topic commands
- Warns about scope creep
- Tracks progress automatically
- Guides you through requirements

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

### Install Extensions

```bash
# Local install (current project only)
orchestra install task-monitor

# Global install (all projects)
orchestra install task-monitor --global

# List installed extensions
orchestra list

# Uninstall
orchestra uninstall task-monitor
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

When you install Orchestra extensions in a project, team members can use the commands immediately:

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

### Run Tests

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test types
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m deviation_detection  # Deviation detection tests

# Run tests verbosely
pytest -v
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy src/

# Run all quality checks
black . && ruff check . && mypy src/
```

### Manual Testing

```bash
# Test Orchestra CLI directly
orchestra --help
orchestra list
orchestra install task-monitor

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
