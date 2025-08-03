"""
Unit tests for TesterAnalyzeCommand

Tests the core functionality of the test analysis command
without external dependencies.
"""

import json
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from orchestra.extensions.tester.commands.analyze import TesterAnalyzeCommand
from orchestra.common.claude_cli_wrapper import ClaudeResponse


class TestTesterAnalyzeCommand:
    """Test suite for TesterAnalyzeCommand"""
    
    def test_validates_required_input(self):
        """Test input validation for required fields"""
        command = TesterAnalyzeCommand()
        
        # Missing required fields
        assert not command.validate_input({"code_changes": {}})
        assert not command.validate_input({"test_context": {}})
        assert not command.validate_input({
            "code_changes": {},
            "test_context": {}
            # Missing calibration_data
        })
        
        # Valid input
        assert command.validate_input({
            "code_changes": {"files": [], "diff": ""},
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        })
    
    def test_validates_nested_structures(self):
        """Test validation of nested data structures"""
        command = TesterAnalyzeCommand()
        
        # Invalid code_changes structure
        assert not command.validate_input({
            "code_changes": {"files": []},  # Missing diff
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        })
        
        # Invalid test_context - missing framework
        assert not command.validate_input({
            "code_changes": {"files": [], "diff": ""},
            "test_context": {"coverage_requirements": 0.8},
            "calibration_data": {}
        })
        
        # Valid with all optional fields
        assert command.validate_input({
            "code_changes": {
                "files": ["app.py", "utils.py"],
                "diff": "+def new_function():\n+    pass"
            },
            "test_context": {
                "framework": "jest",
                "test_patterns": ["*.test.js"],
                "coverage_requirements": 0.9
            },
            "calibration_data": {
                "test_commands": {"unit": "npm test"},
                "test_file_patterns": ["__tests__/*.js"],
                "assertion_style": "expect"
            }
        })
    
    def test_builds_analysis_prompt(self):
        """Test building prompt for test analysis"""
        command = TesterAnalyzeCommand()
        
        input_data = {
            "code_changes": {
                "files": ["calculator.py"],
                "diff": "+def add(a, b):\n+    return a + b"
            },
            "test_context": {
                "framework": "pytest",
                "test_patterns": ["test_*.py"],
                "coverage_requirements": 0.8
            },
            "calibration_data": {}
        }
        
        prompt = command.build_prompt(input_data)
        
        assert "calculator.py" in prompt
        assert "def add(a, b):" in prompt
        assert "test" in prompt.lower()
        assert "analyze" in prompt.lower()
    
    def test_builds_focused_system_prompt(self):
        """Test system prompt includes framework details"""
        command = TesterAnalyzeCommand()
        
        input_data = {
            "code_changes": {"files": [], "diff": ""},
            "test_context": {
                "framework": "jest",
                "test_patterns": ["*.spec.js"],
                "coverage_requirements": 0.95
            },
            "calibration_data": {
                "test_commands": {"unit": "npm test", "e2e": "npm run e2e"},
                "assertion_style": "expect"
            }
        }
        
        system_prompt = command.build_system_prompt(input_data)
        
        assert "test requirement analyzer" in system_prompt.lower()
        assert "jest" in system_prompt
        assert "95%" in system_prompt or "0.95" in system_prompt
        assert "expect" in system_prompt
        assert "JSON" in system_prompt
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_identifies_unit_tests_needed(self, mock_invoke):
        """Test identification of unit tests needed"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "tests_needed": [
                {
                    "file": "test_calculator.py",
                    "test_name": "test_add_positive_numbers",
                    "test_type": "unit",
                    "reason": "Test basic addition functionality"
                },
                {
                    "file": "test_calculator.py",
                    "test_name": "test_add_negative_numbers",
                    "test_type": "unit",
                    "reason": "Test edge case with negative numbers"
                }
            ],
            "suggested_commands": ["pytest test_calculator.py"],
            "coverage_gaps": ["No tests for overflow conditions"],
            "existing_tests_to_update": []
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "code_changes": {
                "files": ["calculator.py"],
                "diff": "+def add(a, b):\n+    return a + b"
            },
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        })
        
        assert result["success"] is True
        assert len(result["tests_needed"]) == 2
        assert result["tests_needed"][0]["test_type"] == "unit"
        assert "pytest" in result["suggested_commands"][0]
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_identifies_integration_tests(self, mock_invoke):
        """Test identification of integration tests"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "tests_needed": [
                {
                    "file": "test_api_integration.py",
                    "test_name": "test_user_registration_flow",
                    "test_type": "integration",
                    "reason": "Test full registration process with database"
                }
            ],
            "suggested_commands": ["pytest -m integration"],
            "coverage_gaps": ["Database rollback scenarios"],
            "existing_tests_to_update": ["test_user_model.py"]
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "code_changes": {
                "files": ["api/users.py", "models/user.py"],
                "diff": "+async def register_user(data):\n+    user = User(**data)\n+    await user.save()"
            },
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        })
        
        assert result["tests_needed"][0]["test_type"] == "integration"
        assert "test_user_model.py" in result["existing_tests_to_update"]
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_respects_calibration_data(self, mock_invoke):
        """Test that calibration data influences suggestions"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "tests_needed": [{
                "file": "__tests__/calculator.test.js",
                "test_name": "should add numbers correctly",
                "test_type": "unit",
                "reason": "Test add function"
            }],
            "suggested_commands": ["npm run test:unit"],
            "coverage_gaps": [],
            "existing_tests_to_update": []
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "code_changes": {
                "files": ["src/calculator.js"],
                "diff": "+export const add = (a, b) => a + b;"
            },
            "test_context": {"framework": "jest"},
            "calibration_data": {
                "test_commands": {"unit": "npm run test:unit"},
                "test_file_patterns": ["__tests__/*.test.js"],
                "assertion_style": "expect"
            }
        })
        
        # Should use calibrated test command
        assert "npm run test:unit" in result["suggested_commands"]
        # Should follow calibrated file pattern
        assert "__tests__" in result["tests_needed"][0]["file"]
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_no_tests_needed(self, mock_invoke):
        """Test when no new tests are needed"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "tests_needed": [],
            "suggested_commands": [],
            "coverage_gaps": [],
            "existing_tests_to_update": []
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "code_changes": {
                "files": ["README.md"],
                "diff": "+# Documentation update"
            },
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        })
        
        assert result["success"] is True
        assert len(result["tests_needed"]) == 0
        assert len(result["suggested_commands"]) == 0
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_handles_claude_failure(self, mock_invoke):
        """Test handling of Claude invocation failure"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = False
        mock_response.error = "Connection timeout"
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "code_changes": {"files": [], "diff": ""},
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        })
        
        assert result["success"] is False
        assert "Claude invocation failed" in result["error"]
    
    def test_parse_response_with_partial_data(self):
        """Test parsing response with missing optional fields"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.content = json.dumps({
            "tests_needed": [{
                "file": "test_app.py",
                "test_name": "test_feature",
                "test_type": "unit",
                "reason": "New feature"
            }]
            # Missing other fields
        })
        
        result = command.parse_response(mock_response)
        
        assert len(result["tests_needed"]) == 1
        assert result["suggested_commands"] == []
        assert result["coverage_gaps"] == []
        assert result["existing_tests_to_update"] == []
    
    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON response"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.content = "Not valid JSON"
        
        result = command.parse_response(mock_response)
        
        assert result["tests_needed"] == []
        assert "error" in result
    
    def test_handles_multiple_file_changes(self):
        """Test analysis of multiple file changes"""
        command = TesterAnalyzeCommand()
        
        input_data = {
            "code_changes": {
                "files": ["api.py", "models.py", "utils.py"],
                "diff": """
+# api.py
+def create_user(data):
+    user = User(data)
+    return user.save()
+
+# models.py  
+class User:
+    def save(self):
+        pass
+
+# utils.py
+def validate_email(email):
+    return '@' in email
"""
            },
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        }
        
        prompt = command.build_prompt(input_data)
        
        assert "api.py" in prompt
        assert "models.py" in prompt
        assert "utils.py" in prompt
        assert "create_user" in prompt
        assert "validate_email" in prompt
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_identifies_e2e_tests(self, mock_invoke):
        """Test identification of end-to-end tests"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "tests_needed": [{
                "file": "e2e/checkout.spec.js",
                "test_name": "complete checkout flow",
                "test_type": "e2e",
                "reason": "Test full user journey from cart to payment"
            }],
            "suggested_commands": ["npm run cypress"],
            "coverage_gaps": ["Mobile viewport testing"],
            "existing_tests_to_update": []
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "code_changes": {
                "files": ["checkout.js"],
                "diff": "+function processCheckout() {}"
            },
            "test_context": {"framework": "cypress"},
            "calibration_data": {}
        })
        
        assert result["tests_needed"][0]["test_type"] == "e2e"
        assert "cypress" in result["suggested_commands"][0]
    
    def test_truncates_large_diffs(self):
        """Test that large diffs are truncated"""
        command = TesterAnalyzeCommand()
        
        # Create a very large diff
        large_diff = "+def func():\n" * 5000
        
        input_data = {
            "code_changes": {
                "files": ["large_file.py"],
                "diff": large_diff
            },
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        }
        
        prompt = command.build_prompt(input_data)
        
        # Should be truncated
        assert len(prompt) < 15000
        assert "truncated" in prompt
    
    def test_system_prompt_includes_all_calibration(self):
        """Test system prompt includes all calibration details"""
        command = TesterAnalyzeCommand()
        
        input_data = {
            "code_changes": {"files": [], "diff": ""},
            "test_context": {
                "framework": "mocha",
                "test_patterns": ["*.spec.ts", "*.test.ts"],
                "coverage_requirements": 0.85
            },
            "calibration_data": {
                "test_commands": {
                    "unit": "npm run test:unit",
                    "integration": "npm run test:integration",
                    "e2e": "npm run test:e2e"
                },
                "test_file_patterns": ["src/**/*.spec.ts"],
                "assertion_style": "chai"
            }
        }
        
        system_prompt = command.build_system_prompt(input_data)
        
        assert "mocha" in system_prompt
        assert "85%" in system_prompt
        assert "chai" in system_prompt
        assert all(cmd in system_prompt for cmd in 
                  ["test:unit", "test:integration", "test:e2e"])
    
    @patch('orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke')
    def test_suggests_test_updates(self, mock_invoke):
        """Test identification of existing tests that need updates"""
        command = TesterAnalyzeCommand()
        
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps({
            "tests_needed": [],
            "suggested_commands": ["pytest -xvs"],
            "coverage_gaps": [],
            "existing_tests_to_update": [
                "test_user.py",  # Signature changed
                "test_api.py"    # New parameter added
            ]
        })
        mock_invoke.return_value = mock_response
        
        result = command.execute({
            "code_changes": {
                "files": ["user.py"],
                "diff": "-def create_user(name):\n+def create_user(name, email):"
            },
            "test_context": {"framework": "pytest"},
            "calibration_data": {}
        })
        
        assert len(result["existing_tests_to_update"]) == 2
        assert "test_user.py" in result["existing_tests_to_update"]