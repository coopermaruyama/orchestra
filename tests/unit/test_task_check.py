"""
Unit tests for TaskCheckCommand

Tests the core functionality of the task deviation checking command
without external dependencies.
"""

import json
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from orchestra.extensions.task.commands.check import TaskCheckCommand
from orchestra.common.claude_cli_wrapper import ClaudeResponse


class TestTaskCheckCommand:
    """Test suite for TaskCheckCommand"""
    
    def test_validates_required_input(self):
        """Test input validation for required fields"""
        command = TaskCheckCommand()
        
        # Missing required field
        assert not command.validate_input({"transcript": "test"})
        assert not command.validate_input({"diff": "test diff"})
        assert not command.validate_input({"transcript": "test", "diff": "diff"})
        
        # All fields present
        assert command.validate_input({
            "transcript": "test",
            "diff": "diff", 
            "memory": {"task": "test task"}
        })
    
    def test_validates_memory_structure(self):
        """Test validation of memory field structure"""
        command = TaskCheckCommand()
        
        # Missing task in memory
        assert not command.validate_input({
            "transcript": "test",
            "diff": "diff",
            "memory": {"requirements": []}
        })
        
        # Valid memory with optional fields
        assert command.validate_input({
            "transcript": "test",
            "diff": "diff",
            "memory": {
                "task": "Fix login bug",
                "requirements": ["Fix 500 error"],
                "forbidden_patterns": ["new features"]
            }
        })
    
    def test_builds_minimal_prompt(self):
        """Test prompt building with minimal context"""
        command = TaskCheckCommand()
        input_data = {
            "transcript": "User: Add OAuth integration",
            "diff": "+OAuth implementation code",
            "memory": {"task": "Fix login bug"}
        }
        
        prompt = command.build_prompt(input_data)
        assert "Add OAuth integration" in prompt
        assert "OAuth implementation code" in prompt
        assert "task deviations" in prompt.lower()
        assert len(prompt) < 1000  # Ensure prompt is minimal
    
    def test_builds_focused_system_prompt(self):
        """Test system prompt building"""
        command = TaskCheckCommand()
        input_data = {
            "transcript": "test",
            "diff": "diff",
            "memory": {
                "task": "Fix login bug", 
                "requirements": ["Fix 500 error", "Add logging"],
                "forbidden_patterns": ["new features", "refactoring"]
            }
        }
        
        system_prompt = command.build_system_prompt(input_data)
        assert "task deviation analyzer" in system_prompt.lower()
        assert "Fix login bug" in system_prompt
        assert "Fix 500 error" in system_prompt
        assert "Output JSON" in system_prompt
        assert len(system_prompt) < 500  # Keep it focused
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_detects_scope_creep(self, mock_invoke):
        """Test detection of scope creep"""
        command = TaskCheckCommand()
        
        # Mock successful Claude response
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "deviation_detected": True,
            "deviation_type": "scope_creep",
            "severity": "high",
            "recommendation": "Focus on bug fix first",
            "specific_issues": ["Adding OAuth is beyond scope"]
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "transcript": "Add OAuth",
            "diff": "+OAuth code",
            "memory": {"task": "Fix bug", "requirements": []}
        })
        
        assert result["success"] is True
        assert result["deviation_detected"] is True
        assert result["deviation_type"] == "scope_creep"
        assert result["severity"] == "high"
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_no_deviation_detected(self, mock_invoke):
        """Test when no deviation is detected"""
        command = TaskCheckCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "deviation_detected": False,
            "deviation_type": None,
            "severity": "low",
            "recommendation": "Continue with current approach",
            "specific_issues": []
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "transcript": "Fix login error handling",
            "diff": "+error handling code",
            "memory": {"task": "Fix login bug"}
        })
        
        assert result["success"] is True
        assert result["deviation_detected"] is False
        assert result["deviation_type"] is None
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_detects_over_engineering(self, mock_invoke):
        """Test detection of over-engineering"""
        command = TaskCheckCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "deviation_detected": True,
            "deviation_type": "over_engineering",
            "severity": "medium",
            "recommendation": "Simplify the implementation",
            "specific_issues": [
                "Complex factory pattern for simple error handling",
                "Unnecessary abstraction layers"
            ]
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "transcript": "Create ErrorHandlerFactory",
            "diff": "+abstract factory pattern",
            "memory": {"task": "Fix simple error"}
        })
        
        assert result["success"] is True
        assert result["deviation_type"] == "over_engineering"
        assert len(result["specific_issues"]) == 2
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_handles_claude_failure(self, mock_invoke):
        """Test handling of Claude invocation failure"""
        command = TaskCheckCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = False
        mock_response.error = "Timeout waiting for response"
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "transcript": "test",
            "diff": "diff",
            "memory": {"task": "test"}
        })
        
        assert result["success"] is False
        assert "Claude invocation failed" in result["error"]
        assert "Timeout" in result["error"]
    
    def test_parse_response_with_json_block(self):
        """Test parsing response with JSON in markdown block"""
        command = TaskCheckCommand()
        
        response_content = """
        Here's the analysis:
        
        ```json
        {
            "deviation_detected": true,
            "deviation_type": "off_topic",
            "severity": "high",
            "recommendation": "Return to main task"
        }
        ```
        """
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.content = response_content
        
        result = command.parse_response(mock_response)
        assert result["deviation_detected"] is True
        assert result["deviation_type"] == "off_topic"
    
    def test_parse_response_invalid_json(self):
        """Test parsing response with invalid JSON"""
        command = TaskCheckCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.content = "This is not JSON"
        
        result = command.parse_response(mock_response)
        assert result["deviation_detected"] is False
        assert "error" in result
        assert "parse" in result["error"].lower()
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_uses_correct_claude_options(self, mock_invoke):
        """Test that correct Claude CLI options are used"""
        command = TaskCheckCommand()
        
        # Setup mock
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = '{"deviation_detected": false}'
        mock_invoke.return_value = mock_response
        
        # Execute command
        command.execute({
            "transcript": "test",
            "diff": "diff", 
            "memory": {"task": "test"}
        })
        
        # Verify invoke was called with correct parameters
        mock_invoke.assert_called_once()
        call_args = mock_invoke.call_args
        
        assert call_args.kwargs["output_format"].value == "stream-json"
        assert call_args.kwargs["timeout"] == 120
        assert call_args.kwargs["verbose"] is True
    
    def test_handles_all_deviation_types(self):
        """Test that all deviation types are properly handled"""
        command = TaskCheckCommand()
        
        deviation_types = ["scope_creep", "over_engineering", "off_topic"]
        
        for deviation_type in deviation_types:
            with patch.object(command.claude, 'invoke') as mock_invoke:
                mock_response = Mock(spec=ClaudeResponse)
                mock_response.success = True
                mock_response.content = json.dumps({
                    "deviation_detected": True,
                    "deviation_type": deviation_type,
                    "severity": "medium",
                    "recommendation": f"Fix {deviation_type}"
                })
                mock_invoke.return_value = mock_response
                
                result = command.execute({
                    "transcript": "test",
                    "diff": "diff",
                    "memory": {"task": "test"}
                })
                
                assert result["deviation_type"] == deviation_type
    
    def test_empty_transcript_and_diff(self):
        """Test handling of empty transcript and diff"""
        command = TaskCheckCommand()
        
        # Empty strings should still be valid
        assert command.validate_input({
            "transcript": "",
            "diff": "",
            "memory": {"task": "test"}
        })
        
        prompt = command.build_prompt({
            "transcript": "",
            "diff": "",
            "memory": {"task": "test"}
        })
        
        assert "TRANSCRIPT:" in prompt
        assert "GIT DIFF:" in prompt