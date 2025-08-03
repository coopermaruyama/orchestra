# Orchestra Architecture Redesign Plan

## Overview

This document outlines a comprehensive redesign of the Orchestra extension architecture, moving from a multi-command CLI approach to a test-driven design where extensions use focused commands that spawn separate Claude instances with minimal context. The goal is to have multiple specialized agents with small memories, each handling one responsibility, rather than feeding huge context blocks to a single instance.

## Current Architecture Problems

1. **Complex Command Structure**: Each extension has multiple commands (init, status, hook, etc.) making testing difficult
2. **Tight Coupling**: Business logic mixed with CLI handling and state management
3. **Indirect Claude Integration**: Multiple abstraction layers between extensions and Claude
4. **Hard to Test**: Current structure makes unit testing core functionality challenging
5. **Stateful Operations**: Extensions maintain complex state that complicates testing

## New Architecture Philosophy

### Core Principles

1. **Single Responsibility**: Each command does ONE thing well (extensions can have multiple commands)
2. **Small Context Windows**: Each Claude call gets minimal, focused context
3. **External Claude Instances**: Each command spawns a separate Claude process
4. **Test-First Development**: Every command has comprehensive tests before implementation
5. **Clear Separation**: Separate specialized agents rather than monolithic extensions

## Redesigned Extension Commands

### 1. Task Monitor: `check`

**Purpose**: Analyze work for deviations from task requirements

**Input Structure**:
```python
{
    "transcript": str,      # Recent conversation/commands
    "diff": str,           # Git diff of changes
    "memory": {            # Task context and rules
        "task": str,
        "requirements": List[str],
        "forbidden_patterns": List[str]
    }
}
```

**Output Structure**:
```python
{
    "deviation_detected": bool,
    "deviation_type": "scope_creep" | "over_engineering" | "off_topic" | None,
    "severity": "low" | "medium" | "high",
    "recommendation": str,
    "specific_issues": List[str]
}
```

**Claude CLI Call**:
```bash
claude --print --output-format stream-json --verbose \
  --model haiku \
  -p "Analyze the following transcript and git diff for deviations from the task requirements. 
      Check for scope creep, over-engineering, and off-topic work." \
  --append-system-prompt "Task: ${task}\nRequirements: ${requirements}\nForbidden: ${forbidden_patterns}"
```

### 2. Tester: `analyze`

**Purpose**: Determine what tests are needed for code changes

**Input Structure**:
```python
{
    "code_changes": {
        "files": List[str],
        "diff": str
    },
    "test_context": {
        "framework": str,       # pytest, jest, etc.
        "test_patterns": List[str],
        "coverage_requirements": float
    },
    "calibration_data": {      # Learned from calibration
        "test_commands": Dict[str, str],
        "test_file_patterns": List[str],
        "assertion_style": str
    }
}
```

**Output Structure**:
```python
{
    "tests_needed": List[{
        "file": str,
        "test_name": str,
        "test_type": "unit" | "integration" | "e2e",
        "reason": str
    }],
    "suggested_commands": List[str],
    "coverage_gaps": List[str],
    "existing_tests_to_update": List[str]
}
```

**Claude CLI Call**:
```bash
claude --print --output-format stream-json --verbose \
  --model haiku \
  -p "Analyze code changes and determine required tests based on the test framework and patterns" \
  --append-system-prompt "Framework: ${framework}\nPatterns: ${test_patterns}\nCalibration: ${calibration}"
```

### 3. Tidy: `fix`

**Purpose**: Automatically fix code quality issues

**Input Structure**:
```python
{
    "file_content": str,
    "file_path": str,
    "project_rules": {
        "linter": str,          # ruff, eslint, etc.
        "formatter": str,       # black, prettier, etc.
        "type_checker": str,    # mypy, tsc, etc.
        "custom_rules": List[str]
    },
    "file_type": str           # python, javascript, etc.
}
```

**Output Structure**:
```python
{
    "fixed": bool,
    "fixed_content": str,  # The entire fixed file content
    "changes_made": List[{
        "line": int,
        "issue": str,
        "fix_applied": str
    }],
    "unfixable_issues": List[{
        "line": int,
        "issue": str,
        "reason": str
    }]
}
```

**Claude CLI Call**:
```bash
claude --print --output-format stream-json --verbose \
  --model haiku \
  -p "Fix all code quality issues in this file. Return the complete fixed file content." \
  --append-system-prompt "Linter: ${linter}\nFormatter: ${formatter}\nRules: ${custom_rules}\nIMPORTANT: Return the entire fixed file, not just suggestions."
```

### 4. TimeMachine

**No changes needed** - TimeMachine works well with its current implementation and should remain unchanged.

## Implementation Architecture

### Base Classes

```python
# src/orchestra/common/core_command.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from orchestra.common.claude_cli_wrapper import ClaudeCLIWrapper, OutputFormat

class CoreCommand(ABC):
    """Base class for all extension core commands"""
    
    def __init__(self, model: str = "haiku"):
        self.claude = ClaudeCLIWrapper(default_model=model)
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input structure"""
        pass
    
    @abstractmethod
    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build Claude prompt from input"""
        pass
    
    @abstractmethod
    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build system prompt with context"""
        pass
    
    @abstractmethod
    def parse_response(self, claude_response: str) -> Dict[str, Any]:
        """Parse Claude's response into structured output"""
        pass
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command via Claude CLI"""
        if not self.validate_input(input_data):
            return {"error": "Invalid input structure"}
        
        prompt = self.build_prompt(input_data)
        system_prompt = self.build_system_prompt(input_data)
        
        # Call Claude CLI wrapper
        response = self.claude.invoke(
            prompt=prompt,
            system_prompt=system_prompt,
            output_format=OutputFormat.STREAM_JSON,
            timeout=120
        )
        
        if response.success:
            return self.parse_response(response.content)
        else:
            return {"error": f"Claude invocation failed: {response.error}"}
```

### Extension Structure

```python
# src/orchestra/extensions/task/commands/check.py
from orchestra.common.core_command import CoreCommand
from typing import Dict, Any, List

class TaskCheckCommand(CoreCommand):
    """Check for task deviations using external Claude instance"""
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        required = ["transcript", "diff", "memory"]
        return all(key in input_data for key in required)
    
    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        # Minimal context - just what's needed for analysis
        return f"""
        Analyze the following for task deviations:
        
        TRANSCRIPT:
        {input_data['transcript']}
        
        GIT DIFF:
        {input_data['diff']}
        
        Identify any scope creep, over-engineering, or off-topic work.
        """
    
    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:
        memory = input_data['memory']
        # Keep system prompt focused and minimal
        return f"""
        You are a task deviation analyzer.
        Current task: {memory['task']}
        Requirements: {', '.join(memory['requirements'])}
        
        Output JSON with: deviation_detected, deviation_type, severity, recommendation
        """
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        # Parse Claude's JSON response
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "deviation_detected": False,
                "error": "Failed to parse response"
            }
```

### Tidy Fix Command Example

```python
# src/orchestra/extensions/tidy/commands/fix.py
class TidyFixCommand(CoreCommand):
    """Fix code quality issues using external Claude instance"""
    
    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        # Send only the file content to fix
        return f"""
        Fix all code quality issues in this {input_data['file_type']} file:
        
        ```{input_data['file_type']}
        {input_data['file_content']}
        ```
        
        Return the complete fixed file content.
        """
    
    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:
        rules = input_data['project_rules']
        # Minimal context about rules
        return f"""
        You are a code fixer. Fix issues based on:
        - Linter: {rules['linter']}
        - Formatter: {rules['formatter']}
        - Type checker: {rules['type_checker']}
        
        Return ONLY the fixed code, no explanations.
        """
```

## Test Structure

### Test Organization

```
tests/
├── unit/
│   ├── test_task_check.py
│   ├── test_tester_analyze.py
│   └── test_tidy_fix.py
├── integration/
│   ├── test_task_check_integration.py
│   ├── test_tester_analyze_integration.py
│   └── test_tidy_fix_integration.py
└── e2e/
    ├── test_task_check_e2e.py
    ├── test_tester_analyze_e2e.py
    └── test_tidy_fix_e2e.py
```

### Test Example

```python
# tests/unit/test_task_check.py
import pytest
from unittest.mock import Mock, patch
from orchestra.extensions.task.commands.check import TaskCheckCommand

class TestTaskCheck:
    def test_validates_required_input(self):
        command = TaskCheckCommand()
        
        # Missing required field
        assert not command.validate_input({"transcript": "test"})
        
        # All fields present
        assert command.validate_input({
            "transcript": "test",
            "diff": "diff",
            "memory": {"task": "test"}
        })
    
    def test_builds_correct_prompt(self):
        command = TaskCheckCommand()
        input_data = {
            "transcript": "User: Add OAuth",
            "diff": "+OAuth implementation",
            "memory": {"task": "Fix login bug"}
        }
        
        prompt = command.build_prompt(input_data)
        assert "Add OAuth" in prompt
        assert "OAuth implementation" in prompt
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_detects_scope_creep(self, mock_invoke):
        command = TaskCheckCommand()
        
        # Mock successful Claude response
        mock_response = Mock()
        mock_response.success = True
        mock_response.content = json.dumps({
            "deviation_detected": True,
            "deviation_type": "scope_creep",
            "severity": "high",
            "recommendation": "Focus on bug fix first"
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "transcript": "Add OAuth",
            "diff": "+OAuth code",
            "memory": {"task": "Fix bug", "requirements": []}
        })
        
        assert result["deviation_detected"] is True
        assert result["deviation_type"] == "scope_creep"
```

### E2E Test Example

```python
# tests/e2e/test_task_check_e2e.py
import pytest
import os
from orchestra.extensions.task.commands.check import TaskCheckCommand

@pytest.mark.skipif(
    not os.environ.get("CLAUDECODE"),
    reason="E2E tests require Claude Code environment"
)
class TestTaskCheckE2E:
    def test_real_scope_creep_detection(self):
        """Test actual Claude detection of scope creep"""
        command = TaskCheckCommand()
        
        input_data = {
            "transcript": """
            User: I need to fix the login bug where users get 500 errors
            Assistant: I'll help fix the login bug. Let me add OAuth integration too.
            """,
            "diff": """
            +import oauth2
            +class OAuthProvider:
            +    def authenticate(self):
            +        # New OAuth logic
            """,
            "memory": {
                "task": "Fix login 500 error bug",
                "requirements": ["Fix 500 error", "Add error logging"],
                "forbidden_patterns": ["new features", "refactoring"]
            }
        }
        
        result = command.execute(input_data)
        
        # Claude should detect scope creep
        assert result["deviation_detected"] is True
        assert result["deviation_type"] == "scope_creep"
        assert "oauth" in result["recommendation"].lower()
```

## Migration Strategy

### Phase 1: Infrastructure (Week 1)
1. Create `CoreCommand` base class
2. Enhance `claude_cli_wrapper.py` for better structured responses
3. Set up new test directory structure
4. Create test utilities and fixtures
5. Document new patterns and conventions

### Phase 2: Task Monitor (Week 2)
1. Write comprehensive unit tests for `check` command
2. Implement `TaskCheckCommand` class
3. Create adapter to integrate with existing hook system
4. Write integration tests
5. Validate with E2E tests against real Claude

### Phase 3: Other Extensions (Weeks 3-4)
1. **Tester Extension**:
   - Write tests for `analyze` command
   - Implement `TesterAnalyzeCommand`
   - Integrate with calibration system
   
2. **Tidy Extension**:
   - Write tests for `fix` command
   - Implement `TidyFixCommand`
   - Support multiple linters/formatters
   - Ensure atomic file updates
   
3. **TimeMachine Extension**:
   - No changes needed - keep current implementation

### Phase 4: Integration (Week 5)
1. Update hook handlers to use new commands
2. Create backward compatibility layer
3. Update Orchestra CLI to support new architecture
4. Performance testing and optimization
5. Update all documentation

### Phase 5: Deprecation (Week 6+)
1. Mark old command structure as deprecated
2. Provide migration guide for users
3. Remove old code in next major version

## Benefits

1. **Separation of Concerns**: Each Claude instance handles one specific task with minimal context
2. **Testability**: Focused commands with clear inputs/outputs are easy to test
3. **Maintainability**: Single responsibility makes code easier to understand and modify
4. **Debuggability**: External Claude calls can be replayed and debugged independently
5. **Scalability**: Multiple small agents scale better than one large context
6. **Reliability**: Isolated failures don't affect other components
7. **Performance**: Smaller context windows mean faster Claude responses

## Success Metrics

1. **Test Coverage**: 
   - Unit tests: >95% coverage
   - Integration tests: All command paths covered
   - E2E tests: Key scenarios validated

2. **Performance**:
   - Command execution: <2s overhead (excluding Claude API time)
   - Memory usage: <50MB per extension
   - Startup time: <100ms

3. **Code Quality**:
   - All tests passing
   - Type checking clean (mypy)
   - Linting clean (ruff/black)
   - Zero security vulnerabilities

4. **Developer Experience**:
   - New extension creation: <1 day
   - Test writing: Clear patterns and examples
   - Debugging: Clear error messages and logs

5. **User Experience**:
   - Error rate: <1% command failures
   - Response clarity: Structured, actionable output
   - Integration: Seamless with existing Claude Code

## Example Implementation Timeline

### Week 1: Foundation
- Monday: Create CoreCommand base class and tests
- Tuesday: Enhance claude_cli_wrapper for structured responses
- Wednesday: Set up test infrastructure
- Thursday: Create test utilities and fixtures
- Friday: Documentation and code review

### Week 2: Task Monitor
- Monday: Write TaskCheckCommand tests (TDD)
- Tuesday: Implement TaskCheckCommand
- Wednesday: Create hook adapter
- Thursday: Integration testing
- Friday: E2E testing and refinement

### Week 3-4: Remaining Extensions
- Each extension gets 2-3 days:
  - Day 1: Write tests
  - Day 2: Implementation
  - Day 3: Integration and testing

### Week 5: Integration and Polish
- Monday-Tuesday: Update Orchestra CLI
- Wednesday: Performance testing
- Thursday: Documentation update
- Friday: Release preparation

## Next Steps

1. **Review and Approve**: Team review of this architecture
2. **Create Tickets**: Break down into implementation tasks
3. **Prototype**: Build TaskCheckCommand as proof of concept
4. **Iterate**: Refine based on prototype learnings
5. **Execute**: Follow the migration strategy

## Key Philosophy Changes

1. **From Monolithic to Distributed**: Instead of one Claude instance with massive context, use multiple focused instances
2. **From Suggesting to Doing**: Tidy now fixes code directly rather than suggesting changes
3. **From Complex State to Simple Functions**: Each command is stateless with minimal context
4. **Keep What Works**: TimeMachine remains unchanged as it already works well

## Conclusion

This redesign transforms Orchestra to embrace the principle of multiple specialized agents with small memories. By using separate Claude instances for each task, we avoid the problems of feeding huge context blocks to a single instance. Each agent has one clear responsibility and minimal context, making the system more scalable, testable, and maintainable.

The key insight is that smaller, focused agents working independently are more effective than one large agent trying to handle everything. This architecture better aligns with how Claude performs best - with clear, focused tasks and minimal context.