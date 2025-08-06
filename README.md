# Orchestra 🎼

> Orchestrate your Claude Code workflow with focused extensions

Orchestra is a collection of custom subagents, hooks, and slash commands designed to enhance your Claude Code experience.

It also includes utilities to help you work with claude in a "controlled" way, where your workflow involves prompt engineering rather than fixing claude's mistakes.

Currently includes:
- **🕰️ TimeMachine**: Automatic git checkpointing for every conversation turn. Travel back in time to any previous state.
- **🔍 Plancheck**: Validates your plans and prompts before execution, ensuring they align with your goals and constraints.
- **🛑 Neveragain**: Detects when you correct Claude's mistakes and prevents similar issues in the future. Automatically generates memory entries which can be fed into Claude on subsequent runs.
- **🎯 Task Monitor**: Keep Claude focused on your task requirements. No scope creep, no over-engineering.
- **🧹 Tidy**: Automated code quality checker that ensures code meets project standards. Runs linters, formatters, and type checkers in parallel while Claude modifies files
- **🧪 Tester**: Implements a calibration process to make sure claude knows exactly how tests should be run, what frameworks are used, and how to write new tests.

## Quick Start

### One-liner Install

```bash
# Using python
curl -sSL https://raw.githubusercontent.com/coopermaruyama/orchestra/main/get-orchestra.py | python3

# Using sh
curl -sSL https://raw.githubusercontent.com/coopermaruyama/orchestra/main/install.sh | sh
```

Once installed, run `orchestra enable` in a project to enable extensions for that project.

### Manual Install

```bash
# Clone repository
git clone https://github.com/coopermaruyama/orchestra.git
cd orchestra

# Install with pipx (recommended)
pipx install .

# Or install with pip
pip install --user .
```

### Enable Extensions

```bash
# Enable all extensions at once
orchestra enable

# Or enable specific extensions
orchestra enable task      # Task focus and tracking
orchestra enable tidy      # Code quality checking

# Or enable to current project only
orchestra enable task --project

# Use in Claude Code
/task start               # Start a new task
/tidy init               # Configure code quality tools
```

> Note: Extensions include a bootstrap script that allows team members to use commands even without Orchestra installed. They'll get friendly installation instructions on first use.


## Orchestra in Action

### Task Monitor: Preventing Scope Creep

```
🔹 Human: Can you help me fix the login bug where users get a 500 error?

[Claude starts writing unrelated code e.g. OAuth integration]

⚠️ Orchestra Task Monitor: SCOPE CREEP DETECTED
This request deviates from your current task: "Fix login 500 error bug"
Adding OAuth is a significant feature addition, not a bug fix.

Options:
1. Continue with original bug fix only
2. Create a new task for OAuth refactoring after this bug is fixed
3. Override and expand current task scope

🤖 Claude: The task monitor is right - let's focus on fixing the 500 error first. Once that's resolved, we can create a separate task for OAuth implementation.
```

### Tidy: Async Quality Checks

```
🔹 Human: Please add a helper function to calculate user statistics

🤖 Claude: I'll add a helper function for calculating user statistics.

[Claude writes the function]

🧹 Orchestra Tidy: Code quality check triggered
Running: ruff check, mypy, black --check

Issues found:
- src/utils/stats.py:15: Missing return type annotation
- src/utils/stats.py:23: Line too long (95 > 88 characters)
- src/utils/stats.py:30: Undefined variable 'total_users'

🤖 Claude: Let me fix those issues before continuing...

[Claude fixes the issues]

✅ Orchestra Tidy: All checks passed!
```

### TimeMachine: Easy Rollback When Things Go Wrong

```
🔹 Human: Update the database schema to add user preferences

🤖 Claude: I'll update the database schema to add user preferences.

[Claude makes several changes to models and migrations]

🔹 Human: Actually, this is breaking our tests. Can we go back?

🤖 Claude: I'll use TimeMachine to rollback to before the schema changes.

🕐 Orchestra TimeMachine: Available checkpoints:
1. "Update database schema to add user preferences" (3 minutes ago)
2. "Fix login 500 error bug" (15 minutes ago)
3. "Add input validation to user form" (22 minutes ago)

Rolling back to checkpoint 2...

✅ Restored to: "Fix login 500 error bug"
- Reverted 5 file changes
- Current branch: main
- All changes have been undone
```

### Tester: Calibrated Test Runner

```
🔹 Human: /tester:calibrate

🤖 Claude: Let's calibrate the test runner to understand your project's testing setup.
I'll ask you a few questions to learn about your test framework and patterns.

1. What testing framework are you using? (e.g. pytest, unittest)
2. How are your tests organized? (e.g. by feature, by type)
3. Do you have any specific testing patterns or practices you follow? (e.g. AAA, BDD)
4. Are there any browser tests that need to be automated?

🔹 Human: [Answers to questions]

🤖 Claude: Great! I've learned the following about your testing setup:
```

Tester will then save this configuration in `.claude/orchestra/tester/calibration.json` and use it to run tests automatically in future interactions.

### Preventing Over-Engineering

```
🔹 Human: I need to add a simple contact form to the website

🤖 Claude: I'll help you add a contact form. Let me start by creating a form component.

[Claude starts writing code with Redux, custom hooks, and complex state management]

🛑 Orchestra Task Monitor: OVER-ENGINEERING DETECTED
You're implementing:
- Redux store for a simple form
- Custom validation framework
- Abstract form builder pattern

For a basic contact form, consider:
- Simple React component with useState
- Basic HTML5 validation
- Direct API call on submit

🤖 Claude: You're right, I was over-complicating this. Let me create a simple, straightforward contact form instead.
```

Each extension is implemented via claude hooks which allows us to run python scripts inside of a session and implement advanced functionality. All extensions can be used standalone, for example `orchestra timemachine rollback 2` to go back to the state 2 turns ago.






















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

### tidy
Automated code quality checker that ensures code meets project standards. Runs linters, formatters, and type checkers after Claude modifies files.

**Commands:**
- `/tidy:init` - Interactive setup wizard to configure tools
- `/tidy:check` - Run code quality checks manually
- `/tidy:fix` - Auto-fix issues where possible
- `/tidy:status` - Show configuration and last results
- `/tidy:learn` - Add do/don't examples for Claude

**Features:**
- Auto-detects project type and available tools
- Runs checks automatically after code modifications
- Supports Python, JavaScript/TypeScript, Rust, Go, and more
- Parallel execution for performance
- Learns project conventions over time
- Zero-config setup with smart defaults

## Installation

### Prerequisites
- Python 3.8+
- pipx (recommended) or pip

#### Why pipx?
pipx installs Python applications in isolated environments, preventing dependency conflicts. The installers will automatically use pipx if available, otherwise fall back to pip.

To install pipx:
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

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
