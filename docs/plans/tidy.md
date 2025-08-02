# Tidy Extension for Orchestra

## Overview

The Tidy extension is an automated code quality checker for Orchestra that ensures code meets project standards without manual intervention. It integrates with Claude Code's Stop and SubagentStop hooks to automatically run linters, formatters, and type checkers after code modifications.

## Goals

1. **Zero-config setup**: Automatically detect project type and available tools
2. **Non-intrusive**: Only notify when issues are found, stay silent on success
3. **Learning system**: Remember project-specific patterns and preferences
4. **Multi-language support**: Work with Python, JavaScript/TypeScript, and more
5. **Claude-aware**: Help Claude learn and follow project conventions

## Architecture

### Extension Structure

```
src/orchestra/extensions/tidy/
├── __init__.py
├── tidy_monitor.py          # Main extension class
├── project_detector.py      # Project type and tool detection
├── tool_runners.py          # Wrapper classes for various tools
└── agents/                  # Subagents for code quality analysis
    ├── code-quality-analyzer.md
    └── fix-suggester.md
```

### State Management

The extension maintains state in `.claude-tidy.json`:

```json
{
  "project_type": "python",
  "detected_tools": {
    "linter": {
      "name": "ruff",
      "command": "uv run ruff check .",
      "fix_command": "uv run ruff check . --fix",
      "config_file": "pyproject.toml"
    },
    "formatter": {
      "name": "black", 
      "command": "uv run black . --check",
      "fix_command": "uv run black .",
      "config_file": "pyproject.toml"
    },
    "type_checker": {
      "name": "mypy",
      "command": "uv run mypy src/",
      "config_file": "pyproject.toml"
    }
  },
  "custom_commands": [],
  "do_examples": [
    "Use type hints for all function parameters",
    "Follow PEP 8 naming conventions",
    "Write docstrings for public functions"
  ],
  "dont_examples": [
    "Use print() for debugging - use logging instead",
    "Commit commented-out code",
    "Use mutable default arguments"
  ],
  "last_check": {
    "timestamp": "2024-01-20T10:30:00Z",
    "results": {
      "linter": {"passed": true, "issues": 0},
      "formatter": {"passed": false, "issues": 3},
      "type_checker": {"passed": true, "issues": 0}
    }
  },
  "settings": {
    "auto_fix": false,
    "strict_mode": true,
    "check_on_file_change": true,
    "ignore_patterns": ["*_test.py", "migrations/*"]
  }
}
```

## Implementation Details

### 1. Project Detection (`project_detector.py`)

The detector examines the project structure to identify:

- **Language**: Based on file extensions and configuration files
- **Package manager**: pip/uv, npm/yarn/pnpm, cargo, etc.
- **Available tools**: Check for installed linters/formatters
- **Configuration files**: pyproject.toml, package.json, .eslintrc, etc.

Detection priority:
1. Check for explicit configuration files
2. Look for lock files (poetry.lock, package-lock.json)
3. Examine source file extensions
4. Check for tool-specific configs (.flake8, .prettierrc)

### 2. Tool Runners (`tool_runners.py`)

Abstract base class for tool runners:

```python
class ToolRunner(ABC):
    @abstractmethod
    def check(self) -> ToolResult:
        """Run the tool in check mode"""
        
    @abstractmethod
    def fix(self) -> ToolResult:
        """Run the tool in fix mode"""
        
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the tool is available"""
```

Implementations for each tool type:
- `RuffRunner`, `BlackRunner`, `MypyRunner` (Python)
- `ESLintRunner`, `PrettierRunner`, `TSCRunner` (JS/TS)
- `RustfmtRunner`, `ClippyRunner` (Rust)
- etc.

### 3. Hook Integration

#### Stop Hook Behavior

1. Check if any files were modified during the session
2. Run all configured checks in parallel
3. Aggregate results
4. If issues found:
   - Show concise summary
   - Offer to fix automatically (if auto_fix enabled)
   - Or prompt Claude to fix the issues

#### SubagentStop Hook Behavior

Similar to Stop hook but:
- Only check files modified by the subagent
- Results are reported back to the main Claude instance

### 4. Slash Commands

#### `/tidy init`
Interactive setup wizard:
1. Detect project type
2. Find available tools
3. Run sample checks
4. Let user customize configuration
5. Save to `.claude-tidy.json`

#### `/tidy check`
Manual check command:
- Run all configured tools
- Show detailed results
- Update last_check in state

#### `/tidy fix`
Auto-fix command:
- Run tools in fix mode
- Show what was changed
- Optionally create a commit

#### `/tidy status`
Show current configuration:
- Detected project type
- Configured tools
- Last check results
- Current settings

#### `/tidy learn <do|dont> <example>`
Add examples of good/bad patterns:
- Updates do_examples or dont_examples
- Helps Claude understand project conventions

## Language Support

### Python Projects

Detected by: `pyproject.toml`, `setup.py`, `requirements.txt`, `*.py` files

Supported tools:
- **Linters**: ruff, flake8, pylint
- **Formatters**: black, autopep8, yapf
- **Type checkers**: mypy, pyright, pyre
- **Security**: bandit
- **Complexity**: radon, mccabe

### JavaScript/TypeScript Projects

Detected by: `package.json`, `tsconfig.json`, `*.js/*.ts` files

Supported tools:
- **Linters**: eslint, tslint (deprecated), standard
- **Formatters**: prettier, standardjs
- **Type checkers**: tsc, flow
- **Security**: npm audit, snyk

### Other Languages

Extensible system for:
- **Rust**: rustfmt, clippy
- **Go**: gofmt, golint, go vet
- **Ruby**: rubocop, standard
- **Java**: checkstyle, spotbugs
- **C/C++**: clang-format, clang-tidy

## Advanced Features

### 1. Smart Issue Detection

- Understand which issues are auto-fixable
- Prioritize issues by severity
- Group related issues together
- Skip issues in generated code

### 2. Learning System

- Track which issues Claude commonly introduces
- Build project-specific patterns over time
- Suggest additions to do/dont examples
- Integrate with CLAUDE.md for persistent memory

### 3. Performance Optimization

- Incremental checking (only modified files)
- Parallel execution of tools
- Caching of results
- Smart skipping of unchanged files

### 4. Integration with Task Monitor

- Respect task boundaries
- Don't interrupt critical operations
- Coordinate with task requirements
- Share context between extensions

## Configuration Examples

### Minimal Python Project

```json
{
  "project_type": "python",
  "detected_tools": {
    "formatter": {
      "name": "black",
      "command": "black . --check"
    }
  }
}
```

### Strict TypeScript Project

```json
{
  "project_type": "typescript",
  "detected_tools": {
    "linter": {
      "name": "eslint",
      "command": "npm run lint",
      "fix_command": "npm run lint:fix"
    },
    "formatter": {
      "name": "prettier",
      "command": "npm run prettier:check",
      "fix_command": "npm run prettier:write"
    },
    "type_checker": {
      "name": "tsc",
      "command": "npm run typecheck"
    }
  },
  "settings": {
    "strict_mode": true,
    "auto_fix": true
  }
}
```

### Multi-Language Monorepo

```json
{
  "project_type": "monorepo",
  "detected_tools": {
    "python": {
      "path": "backend/",
      "linter": {"name": "ruff", "command": "cd backend && ruff check ."}
    },
    "typescript": {
      "path": "frontend/",
      "linter": {"name": "eslint", "command": "cd frontend && npm run lint"}
    }
  }
}
```

## Future Enhancements

1. **IDE Integration**: Send diagnostics to IDE extensions
2. **Git Hooks**: Optionally install pre-commit hooks
3. **CI/CD Templates**: Generate GitHub Actions or similar
4. **Custom Rules**: Define project-specific lint rules
5. **AI-Powered Suggestions**: Use Claude to suggest style improvements
6. **Team Sharing**: Share tidy configurations across team
7. **Metrics Dashboard**: Track code quality over time

## Success Metrics

- Reduction in style-related feedback cycles
- Increased consistency in generated code
- Faster development iteration
- Better Claude adaptation to project conventions
- Minimal false positives in checks