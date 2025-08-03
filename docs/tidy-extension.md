# Tidy Extension Documentation

The Tidy extension for Orchestra is an automated code quality checker that ensures code meets project standards. It integrates with Claude Code's hooks to automatically run linters, formatters, and type checkers after code modifications.

## Overview

Tidy helps maintain code quality by:
- Automatically detecting your project type and available tools
- Running checks after Claude modifies files
- Providing immediate feedback on code quality issues
- Learning project conventions over time
- Supporting auto-fix capabilities where available

## Installation

```bash
# Install Orchestra if not already installed
pip install --user orchestra

# Enable the tidy extension globally
orchestra enable tidy

# Or enable for current project only
orchestra enable tidy --project
```

## Configuration

### Automatic Configuration

When you first use Tidy, it will automatically detect:
- Project type (Python, JavaScript, TypeScript, Rust, etc.)
- Package manager (pip, npm, yarn, cargo, etc.)
- Available tools (linters, formatters, type checkers)

### Manual Configuration

Use `/tidy init` to run the interactive setup wizard:

```
/tidy init
```

This will:
1. Re-detect your project configuration
2. Show detected tools
3. Let you configure settings like auto-fix and parallel execution
4. Allow adding custom commands
5. Run an initial check

### Configuration File

Tidy stores its configuration in `.claude/orchestra/tidy.json`:

```json
{
  "project_info": {
    "type": "python",
    "package_manager": "pip",
    "config_files": ["pyproject.toml"],
    "source_files": ["src/main.py", "src/utils.py"]
  },
  "detected_tools": {
    "linter": {
      "name": "ruff",
      "command": "ruff check .",
      "fix_command": "ruff check . --fix",
      "is_available": true
    },
    "formatter": {
      "name": "black",
      "command": "black . --check",
      "fix_command": "black .",
      "is_available": true
    }
  },
  "settings": {
    "auto_fix": false,
    "strict_mode": true,
    "parallel_execution": true,
    "ignore_patterns": ["*_test.py", "migrations/*", "node_modules/*"]
  }
}
```

## Commands

### /tidy init
Interactive setup wizard to configure code quality tools. Re-runs detection and allows customization of settings.

### /tidy check [files...]
Run code quality checks on all or specified files.

```
/tidy check                    # Check all files
/tidy check src/main.py       # Check specific file
/tidy check src/*.py          # Check multiple files
```

### /tidy fix [files...]
Auto-fix code quality issues where possible.

```
/tidy fix                     # Fix all files
/tidy fix src/main.py        # Fix specific file
```

### /tidy status
Show current configuration and last check results.

### /tidy learn <do|dont> <example>
Add examples to help Claude learn project conventions.

```
/tidy learn do Use descriptive variable names
/tidy learn dont Use single-letter variables except in loops
```

## Hook Integration

Tidy integrates with Claude Code hooks to run automatically:

### Stop Hook
Runs after Claude finishes responding. If files were modified, runs checks and shows issues.

### SubagentStop Hook
Runs after a subagent completes. Similar to Stop but for subagent context.

### PostToolUse Hook
Tracks file modifications when Edit, Write, or MultiEdit tools are used.

### PreCompact Hook
Saves Tidy state before conversation compaction.

## Supported Languages and Tools

### Python
- **Linters**: ruff, flake8, pylint
- **Formatters**: black, autopep8, yapf
- **Type Checkers**: mypy, pyright, pyre
- **Security**: bandit

### JavaScript/TypeScript
- **Linters**: eslint, standard
- **Formatters**: prettier
- **Type Checkers**: tsc (TypeScript)

### Rust
- **Formatter**: rustfmt
- **Linter**: clippy

### Go
- **Formatter**: gofmt
- **Linters**: golint, go vet

### Custom Tools
Tidy can detect custom commands from:
- package.json scripts (npm/yarn/pnpm)
- Makefile targets
- Custom shell commands

## Learning System

Tidy learns from your project over time:

1. **Pattern Recognition**: Tracks common issues Claude introduces
2. **Convention Learning**: Builds understanding of project style
3. **Do/Don't Examples**: Explicit examples you provide
4. **Integration with CLAUDE.md**: Can export learnings to project memory

## Performance Optimization

- **Parallel Execution**: Run multiple tools simultaneously
- **Incremental Checking**: Only check modified files
- **Smart Caching**: Skip unchanged files
- **Configurable Timeouts**: Prevent hanging on slow tools

## Troubleshooting

### Tools Not Detected
- Ensure tools are installed and in PATH
- Check tool configuration files exist
- Try running tool commands manually

### False Positives
- Update ignore patterns in settings
- Configure tool-specific rules
- Use `/tidy learn` to teach exceptions

### Performance Issues
- Enable parallel execution
- Reduce number of files checked
- Increase timeout settings
- Disable expensive tools

## Best Practices

1. **Run `/tidy init` first** to ensure proper configuration
2. **Use `/tidy learn`** to teach project-specific conventions
3. **Keep tools updated** for best compatibility
4. **Configure ignore patterns** for generated/vendor code
5. **Enable auto-fix** for teams with consistent style

## Integration with Other Extensions

Tidy works well with other Orchestra extensions:

- **Task Monitor**: Respects task boundaries and requirements
- **TimeMachine**: Code quality preserved in checkpoints

## Example Workflow

```bash
# Start a new feature
/task start

# Claude writes some code...
# Tidy automatically checks it

# If issues found, Claude is prompted to fix them
# You can also manually check
/tidy check

# Auto-fix formatting issues
/tidy fix

# Teach Claude a convention
/tidy learn do Use async/await instead of promises

# Check current status
/tidy status
```

## Subagents

Tidy includes specialized subagents:

### code-quality-analyzer
Analyzes code for quality issues, explaining why they matter and how to fix them.

### fix-suggester
Provides specific fixes for linting and formatting errors when auto-fix isn't available.