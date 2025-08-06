# Tidy Extension for Orchestra - Revised Plan

## Overview

The Tidy extension is an automated code quality checker for Orchestra that leverages IDE diagnostics through MCP (Model Context Protocol) to ensure code meets project standards. It integrates with Claude Code's hooks to automatically check for issues after code modifications and prompts Claude to fix them when needed.

## Goals

1. **Simplicity**: Use existing IDE diagnostics rather than complex tool detection
2. **Non-intrusive**: Only notify when issues are found, stay silent on success
3. **Claude-powered fixes**: Let Claude handle fixing issues using its knowledge
4. **Universal support**: Works with any language/project that has IDE diagnostics

## Scope and Constraints

### In Scope
- Monitor code changes via Stop and SubagentStop hooks
- Retrieve diagnostics via MCP's getDiagnostics tool
- Prompt Claude to fix issues when found
- Filter diagnostics by severity and type
- Store minimal configuration state

### Out of Scope
- Direct tool execution (ruff, eslint, etc.)
- Complex project type detection
- Auto-fix without Claude involvement
- Custom rule definitions

### Dependencies
- MCP server with getDiagnostics capability
- claude_invoker for prompting Claude
- Orchestra hook system

## Architecture

### Directory Structure

```
src/orchestra/extensions/tidy/
├── __init__.py               # Extension registration
└── tidy_monitor.py           # Main extension class with hooks
```

### State Management

Minimal state in `.orchestra/tidy-state.json`:

```json
{
  "enabled": true,
  "severity_filter": "warning",
  "ignore_patterns": ["*_test.py", "migrations/*"],
  "last_check": {
    "timestamp": "2024-01-20T10:30:00Z",
    "files_checked": ["src/main.py"],
    "issues_found": 3,
    "issues_fixed": 2
  }
}
```

## Implementation Details

### 1. Core Flow

```python
class TidyMonitor:
    def on_stop_hook(self, context):
        # 1. Get list of modified files from context
        modified_files = context.get_modified_files()

        # 2. Call MCP getDiagnostics for each file
        diagnostics = self.get_diagnostics(modified_files)

        # 3. Filter by severity and patterns
        relevant_issues = self.filter_diagnostics(diagnostics)

        # 4. If issues found, prompt Claude
        if relevant_issues:
            self.prompt_claude_to_fix(relevant_issues)
```

### 2. Diagnostics Retrieval

```python
def get_diagnostics(self, files):
    """Get IDE diagnostics via MCP"""
    diagnostics = []
    for file in files:
        result = mcp_client.call("getDiagnostics", {"uri": file})
        diagnostics.extend(result.get("diagnostics", []))
    return diagnostics
```

### 3. Claude Prompting

```python
def prompt_claude_to_fix(self, issues):
    """Prompt Claude to fix issues"""
    prompt = self.format_issues_prompt(issues)
    response = claude_invoker.invoke(prompt)
    return response
```

## File Modifications

### Files to Create

1. **src/orchestra/extensions/tidy/__init__.py**
   - Extension registration
   - Export TidyMonitor class

2. **src/orchestra/extensions/tidy/tidy_monitor.py**
   - Main TidyMonitor class
   - Hook implementations (on_stop, on_subagent_stop)
   - MCP getDiagnostics integration
   - Claude prompting logic
   - Diagnostic filtering

### Files to Modify

1. **src/orchestra/core.py**
   - Register tidy extension in extension list

2. **pyproject.toml** (if needed)
   - Add any new dependencies

## Testing Strategy

### Unit Tests

**File**: `tests/test_tidy_monitor.py`

1. **Test diagnostic retrieval**
   - Mock MCP client
   - Verify getDiagnostics called correctly
   - Handle empty diagnostics

2. **Test filtering**
   - Filter by severity levels
   - Apply ignore patterns
   - Handle various diagnostic formats

3. **Test Claude prompting**
   - Mock claude_invoker
   - Verify prompt formatting
   - Handle prompt failures

### Integration Tests

**File**: `tests/test_tidy_integration.py`

1. **Test hook integration**
   - Simulate Stop hook with modified files
   - Verify full flow execution
   - Check state updates

2. **Test with real diagnostics**
   - Use sample diagnostic data
   - Verify correct issues identified
   - Test Claude response handling

### Manual Testing

1. Modify Python file with known issues
2. Trigger Stop hook
3. Verify diagnostics retrieved
4. Confirm Claude prompted to fix
5. Check fixes applied correctly

## Slash Commands

### `/tidy status`
Show current configuration and last check results

### `/tidy check`
Manually run diagnostics check on current files

### `/tidy toggle`
Enable/disable automatic checking

### `/tidy severity <level>`
Set minimum severity level (error, warning, info)

## Success Metrics

- Successfully retrieves IDE diagnostics
- Correctly filters relevant issues
- Claude fixes issues when prompted
- Minimal false positives
- Fast execution (< 2 seconds for check)

## Alternatives Considered

1. **Complex tool detection system** (original plan)
   - Pros: Direct tool control, more features
   - Cons: Complex implementation, maintenance burden
   - Decision: Too complex for initial version

2. **Git pre-commit hooks**
   - Pros: Prevents bad commits
   - Cons: Outside Claude's control flow
   - Decision: Better suited for separate tool

3. **Direct file watching**
   - Pros: Real-time feedback
   - Cons: Performance overhead, complexity
   - Decision: Hook-based approach is simpler

## Future Enhancements

1. **Caching**: Cache diagnostics to avoid redundant checks
2. **Batch fixing**: Group related issues for Claude
3. **Learning**: Track which issues Claude commonly introduces
4. **Metrics**: Track fix success rate over time
5. **Custom rules**: Allow project-specific diagnostic filters

## Implementation Timeline

1. **Phase 1** (Current): Basic diagnostic retrieval and Claude prompting
2. **Phase 2**: Add slash commands and configuration
3. **Phase 3**: Implement caching and metrics
4. **Phase 4**: Advanced features and learning system
undefined
>