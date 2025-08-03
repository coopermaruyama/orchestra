"""
Unit tests for TidyFixCommand

Tests the core functionality of the code fixing command
without external dependencies.
"""

import json
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from orchestra.extensions.tidy.commands.fix import TidyFixCommand
from orchestra.common.claude_cli_wrapper import ClaudeResponse


class TestTidyFixCommand:
    """Test suite for TidyFixCommand"""
    
    def test_validates_required_input(self):
        """Test input validation for required fields"""
        command = TidyFixCommand()
        
        # Missing required fields
        assert not command.validate_input({"file_content": "test"})
        assert not command.validate_input({"file_path": "/test.py"})
        assert not command.validate_input({
            "file_content": "test",
            "file_path": "/test.py"
            # Missing project_rules
        })
        
        # All required fields present
        assert command.validate_input({
            "file_content": "test code",
            "file_path": "/test.py",
            "project_rules": {"linter": "ruff"},
            "file_type": "python"
        })
    
    def test_validates_project_rules_structure(self):
        """Test validation of project_rules structure"""
        command = TidyFixCommand()
        
        # Empty project_rules is valid (uses defaults)
        assert command.validate_input({
            "file_content": "test",
            "file_path": "/test.py",
            "project_rules": {},
            "file_type": "python"
        })
        
        # Full project_rules
        assert command.validate_input({
            "file_content": "test",
            "file_path": "/test.py",
            "project_rules": {
                "linter": "ruff",
                "formatter": "black",
                "type_checker": "mypy",
                "custom_rules": ["no print statements", "use type hints"]
            },
            "file_type": "python"
        })
    
    def test_builds_fix_prompt(self):
        """Test prompt building for code fixes"""
        command = TidyFixCommand()
        
        input_data = {
            "file_content": "def hello( ):\n  print('hi')",
            "file_path": "/hello.py",
            "project_rules": {"formatter": "black"},
            "file_type": "python"
        }
        
        prompt = command.build_prompt(input_data)
        
        # Should include the code and request complete fix
        assert "def hello( ):" in prompt
        assert "print('hi')" in prompt
        assert "python" in prompt.lower()
        assert "complete fixed file" in prompt.lower()
    
    def test_builds_minimal_system_prompt(self):
        """Test system prompt focuses on fixing"""
        command = TidyFixCommand()
        
        input_data = {
            "file_content": "test",
            "file_path": "/test.js",
            "project_rules": {
                "linter": "eslint",
                "formatter": "prettier",
                "type_checker": "typescript",
                "custom_rules": ["use const", "no var"]
            },
            "file_type": "javascript"
        }
        
        system_prompt = command.build_system_prompt(input_data)
        
        assert "code fixer" in system_prompt.lower()
        assert "eslint" in system_prompt
        assert "prettier" in system_prompt
        assert "typescript" in system_prompt
        assert "use const" in system_prompt
        assert "ONLY the fixed code" in system_prompt
        assert len(system_prompt) < 500  # Keep it focused
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_fixes_formatting_issues(self, mock_invoke):
        """Test fixing formatting issues"""
        command = TidyFixCommand()
        
        # Mock Claude fixing the code
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """def hello():
    print('hi')"""
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "file_content": "def hello( ):\n  print('hi')",
            "file_path": "/test.py",
            "project_rules": {"formatter": "black"},
            "file_type": "python"
        })
        
        assert result["success"] is True
        assert result["fixed"] is True
        assert result["fixed_content"] == "def hello():\n    print('hi')"
        assert len(result["changes_made"]) > 0
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_fixes_linting_issues(self, mock_invoke):
        """Test fixing linting issues"""
        command = TidyFixCommand()
        
        # Mock response with linting fixes
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """import os
import sys

def process_data(data):
    if data is None:
        return []
    return data"""
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "file_content": "import os, sys\n\ndef process_data(data):\n    if data == None:\n        return []\n    return data",
            "file_path": "/test.py",
            "project_rules": {"linter": "ruff"},
            "file_type": "python"
        })
        
        assert result["fixed"] is True
        assert "is None" in result["fixed_content"]
        assert "import os\nimport sys" in result["fixed_content"]
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_fixes_type_issues(self, mock_invoke):
        """Test fixing type checking issues"""
        command = TidyFixCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """from typing import List, Optional

def process_items(items: List[str]) -> Optional[str]:
    if not items:
        return None
    return items[0]"""
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "file_content": "def process_items(items):\n    if not items:\n        return None\n    return items[0]",
            "file_path": "/test.py",
            "project_rules": {"type_checker": "mypy"},
            "file_type": "python"
        })
        
        assert result["fixed"] is True
        assert "List[str]" in result["fixed_content"]
        assert "Optional[str]" in result["fixed_content"]
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_no_changes_needed(self, mock_invoke):
        """Test when code is already clean"""
        command = TidyFixCommand()
        
        clean_code = """def hello():
    print('Hello, world!')"""
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = clean_code  # Same as input
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "file_content": clean_code,
            "file_path": "/test.py",
            "project_rules": {"formatter": "black", "linter": "ruff"},
            "file_type": "python"
        })
        
        assert result["success"] is True
        assert result["fixed"] is False
        assert result["fixed_content"] == clean_code
        assert len(result["changes_made"]) == 0
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_handles_claude_failure(self, mock_invoke):
        """Test handling of Claude invocation failure"""
        command = TidyFixCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = False
        mock_response.error = "API rate limit exceeded"
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "file_content": "test",
            "file_path": "/test.py",
            "project_rules": {},
            "file_type": "python"
        })
        
        assert result["success"] is False
        assert "Claude invocation failed" in result["error"]
        assert "rate limit" in result["error"]
    
    def test_parse_response_extracts_code(self):
        """Test extraction of code from various response formats"""
        command = TidyFixCommand()
        
        # Test with code block
        response1 = Mock(spec=ClaudeResponse)
        response1.content = """Here's the fixed code:

```python
def hello():
    print('fixed')
```"""
        
        result1 = command.parse_response(response1, "def hello( ):\n  print('fixed')")
        assert result1["fixed_content"] == "def hello():\n    print('fixed')"
        
        # Test with direct code
        response2 = Mock(spec=ClaudeResponse)
        response2.content = "def hello():\n    print('fixed')"
        
        result2 = command.parse_response(response2, "def hello( ):\n  print('fixed')")
        assert result2["fixed_content"] == "def hello():\n    print('fixed')"
    
    def test_detects_changes_made(self):
        """Test detection of specific changes"""
        command = TidyFixCommand()
        
        original = """def hello( ):
  print('hi')
x=1"""
        
        fixed = """def hello():
    print('hi')
x = 1"""
        
        changes = command._detect_changes(original, fixed)
        
        assert len(changes) >= 2
        # Should detect spacing and indentation changes
        assert any("spacing" in change["issue"].lower() or 
                  "indentation" in change["issue"].lower() 
                  for change in changes)
    
    def test_handles_javascript_files(self):
        """Test handling of JavaScript files"""
        command = TidyFixCommand()
        
        input_data = {
            "file_content": "const x=1;function f(){console.log(x)}",
            "file_path": "/test.js",
            "project_rules": {
                "linter": "eslint",
                "formatter": "prettier"
            },
            "file_type": "javascript"
        }
        
        prompt = command.build_prompt(input_data)
        assert "javascript" in prompt.lower()
        assert "const x=1" in prompt
    
    def test_handles_custom_rules(self):
        """Test that custom rules are included in prompts"""
        command = TidyFixCommand()
        
        input_data = {
            "file_content": "print('debug')",
            "file_path": "/test.py",
            "project_rules": {
                "custom_rules": [
                    "No print statements in production code",
                    "Use logging instead of print",
                    "All functions must have docstrings"
                ]
            },
            "file_type": "python"
        }
        
        system_prompt = command.build_system_prompt(input_data)
        
        assert "No print statements" in system_prompt
        assert "Use logging" in system_prompt
        assert "docstrings" in system_prompt
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_preserves_code_logic(self, mock_invoke):
        """Test that fixes preserve code logic"""
        command = TidyFixCommand()
        
        # Mock response that fixes style but preserves logic
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """def calculate_sum(numbers: list[int]) -> int:
    if not numbers:
        return 0
    total = 0
    for num in numbers:
        total += num
    return total"""
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "file_content": "def calculate_sum(numbers):\n    if not numbers: return 0\n    total=0\n    for num in numbers: total+=num\n    return total",
            "file_path": "/calc.py",
            "project_rules": {"formatter": "black", "type_checker": "mypy"},
            "file_type": "python"
        })
        
        assert result["fixed"] is True
        # Check that logic is preserved
        assert "return 0" in result["fixed_content"]
        assert "total += num" in result["fixed_content"]
        # But style is fixed
        assert ": list[int]" in result["fixed_content"]
        assert "-> int:" in result["fixed_content"]
    
    def test_handles_empty_file(self):
        """Test handling of empty files"""
        command = TidyFixCommand()
        
        assert command.validate_input({
            "file_content": "",
            "file_path": "/empty.py",
            "project_rules": {},
            "file_type": "python"
        })
        
        prompt = command.build_prompt({
            "file_content": "",
            "file_path": "/empty.py", 
            "project_rules": {},
            "file_type": "python"
        })
        
        assert "python" in prompt.lower()
    
    def test_file_type_inference(self):
        """Test file type inference from path"""
        command = TidyFixCommand()
        
        # Test Python file
        file_type = command._infer_file_type("/path/to/script.py")
        assert file_type == "python"
        
        # Test JavaScript file
        file_type = command._infer_file_type("/app.js")
        assert file_type == "javascript"
        
        # Test TypeScript file
        file_type = command._infer_file_type("/component.tsx")
        assert file_type == "typescript"
        
        # Test unknown file
        file_type = command._infer_file_type("/data.txt")
        assert file_type == "text"