# ruff: noqa: SLF001
"""
Integration tests for TaskCheckCommand

Tests the command with mocked Claude responses but real data structures
and error conditions.
"""

import json
import logging
from unittest.mock import Mock, patch

import pytest

from orchestra.common.claude_cli_wrapper import ClaudeResponse
from orchestra.extensions.task.commands.check import TaskCheckCommand


class TestTaskCheckIntegration:
    """Integration tests for TaskCheckCommand"""

    @pytest.fixture
    def command(self):
        """Create command instance with custom logger"""
        logger = logging.getLogger("test_task_check")
        return TaskCheckCommand(model="haiku", logger=logger)

    @pytest.fixture
    def real_world_input(self):
        """Real-world example input data"""
        return {
            "transcript": """
            User: I need to fix the login bug where users get 500 errors
            Assistant: I'll help fix the login bug. Let me start by examining the error logs.
            User: Great, also while you're at it, can you add OAuth support?
            Assistant: I'll add OAuth integration as well.
            """,
            "diff": """
            diff --git a/auth.py b/auth.py
            index 1234567..abcdefg 100644
            --- a/auth.py
            +++ b/auth.py
            @@ -1,5 +1,20 @@
             import logging
            +import oauth2
            +from oauth2.provider import OAuthProvider
             
             def login(username, password):
                 # Fix for 500 error
                 if not username or not password:
                     return {"error": "Missing credentials"}, 400
            +
            +class OAuthIntegration:
            +    def __init__(self):
            +        self.provider = OAuthProvider()
            +    
            +    def authenticate(self, token):
            +        return self.provider.validate(token)
            """,
            "memory": {
                "task": "Fix login 500 error bug",
                "requirements": [
                    "Identify root cause of 500 errors",
                    "Add proper error handling",
                    "Add logging for debugging",
                ],
                "forbidden_patterns": ["new features", "major refactoring"],
            },
        }

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_real_world_scope_creep(self, mock_invoke, command, real_world_input):
        """Test detection of real-world scope creep scenario"""
        # Mock Claude detecting scope creep
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "deviation_detected": True,
                "deviation_type": "scope_creep",
                "severity": "high",
                "recommendation": "Focus on fixing the 500 error first. OAuth is a new feature that should be implemented separately.",
                "specific_issues": [
                    "OAuth integration is not part of the bug fix",
                    "Adding new authentication method while fixing existing one",
                    "Violates 'no new features' constraint",
                ],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(real_world_input)

        assert result["success"] is True
        assert result["deviation_detected"] is True
        assert result["deviation_type"] == "scope_creep"
        assert result["severity"] == "high"
        assert len(result["specific_issues"]) == 3
        assert "OAuth" in result["recommendation"]

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_complex_over_engineering(self, mock_invoke, command):
        """Test detection of over-engineering in complex scenario"""
        input_data = {
            "transcript": """
            User: Fix the null pointer exception in user profile
            Assistant: I'll create a comprehensive error handling framework
            """,
            "diff": """
            +class ErrorHandlerFactory:
            +    @staticmethod
            +    def create_handler(error_type):
            +        if error_type == "null_pointer":
            +            return NullPointerHandler()
            +
            +class AbstractErrorHandler(ABC):
            +    @abstractmethod
            +    def handle(self, error):
            +        pass
            +
            +class NullPointerHandler(AbstractErrorHandler):
            +    def handle(self, error):
            +        # 50 lines of complex handling
            """,
            "memory": {
                "task": "Fix null pointer exception in user profile",
                "requirements": ["Add null check before accessing profile data"],
            },
        }

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "deviation_detected": True,
                "deviation_type": "over_engineering",
                "severity": "high",
                "recommendation": "A simple null check would suffice. The factory pattern is unnecessary.",
                "specific_issues": [
                    "Factory pattern for single error type",
                    "Abstract base class with one implementation",
                    "50+ lines for a simple null check",
                ],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        assert result["deviation_type"] == "over_engineering"
        assert "factory pattern" in result["recommendation"].lower()

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_multiple_deviations(self, mock_invoke, command):
        """Test when multiple types of deviations are present"""
        input_data = {
            "transcript": "Implement machine learning model for login",
            "diff": "+import tensorflow\n+class LoginMLModel",
            "memory": {
                "task": "Fix login timeout issue",
                "requirements": ["Increase timeout to 30 seconds"],
            },
        }

        # Claude might detect both off-topic and over-engineering
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "deviation_detected": True,
                "deviation_type": "off_topic",  # Primary deviation
                "severity": "high",
                "recommendation": "ML is unrelated to timeout fix. Focus on configuration change.",
                "specific_issues": [
                    "Machine learning is unrelated to timeout issue",
                    "Introduces unnecessary complexity",
                    "Does not address the actual requirement",
                ],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        assert result["deviation_type"] == "off_topic"
        assert len(result["specific_issues"]) >= 2

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_edge_case_minimal_diff(self, mock_invoke, command):
        """Test with minimal or no changes"""
        input_data = {
            "transcript": "Fix typo in comment",
            "diff": "-# Lgging system\n+# Logging system",
            "memory": {
                "task": "Implement comprehensive logging system",
                "requirements": ["Add structured logging", "Include request IDs"],
            },
        }

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "deviation_detected": True,
                "deviation_type": "scope_creep",
                "severity": "low",
                "recommendation": "Typo fix is fine but doesn't address main requirements",
                "specific_issues": ["Not implementing required logging system"],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        assert result["severity"] == "low"

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_progressive_work(self, mock_invoke, command):
        """Test when work is progressing correctly"""
        input_data = {
            "transcript": """
            User: Add error handling to the payment processor
            Assistant: I'll add try-catch blocks and proper error messages
            """,
            "diff": """
            +try:
            +    process_payment(amount)
            +except PaymentError as e:
            +    logger.error(f"Payment failed: {e}")
            +    return {"error": str(e)}, 400
            """,
            "memory": {
                "task": "Add error handling to payment processor",
                "requirements": ["Handle payment failures gracefully", "Log errors"],
            },
        }

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "deviation_detected": False,
                "deviation_type": None,
                "severity": "low",
                "recommendation": "Good progress. Consider adding retry logic next.",
                "specific_issues": [],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        assert result["deviation_detected"] is False
        assert "progress" in result["recommendation"].lower()

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_timeout_handling(self, mock_invoke, command):
        """Test handling of timeouts"""
        import subprocess

        mock_invoke.side_effect = subprocess.TimeoutExpired("claude", 120)

        result = command.execute(
            {
                "transcript": "Long analysis",
                "diff": "Huge diff" * 1000,
                "memory": {"task": "test"},
            }
        )

        assert result["success"] is False
        assert "error" in result

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_malformed_claude_response(self, mock_invoke, command):
        """Test handling of malformed Claude responses"""
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """
        I think there's scope creep here because...
        {invalid json}
        """
        mock_invoke.return_value = mock_response

        result = command.execute(
            {"transcript": "test", "diff": "test", "memory": {"task": "test"}}
        )

        # Should handle gracefully
        assert result["success"] is True
        assert result["deviation_detected"] is False
        assert "error" in result

    def test_prompt_size_limits(self, command):
        """Test that prompts stay within reasonable size limits"""
        huge_transcript = "A" * 10000
        huge_diff = "B" * 50000

        input_data = {
            "transcript": huge_transcript,
            "diff": huge_diff,
            "memory": {
                "task": "test",
                "requirements": ["req" * 100 for _ in range(50)],
            },
        }

        # Should truncate appropriately
        prompt = command.build_prompt(input_data)
        system_prompt = command.build_system_prompt(input_data)

        # Verify prompts are truncated to reasonable sizes
        assert len(prompt) < 100000  # Some reasonable limit
        assert len(system_prompt) < 5000

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_forbidden_patterns_enforcement(self, mock_invoke, command):
        """Test that forbidden patterns are properly communicated"""
        input_data = {
            "transcript": "Let's refactor the entire codebase",
            "diff": "+# Major refactoring",
            "memory": {
                "task": "Fix button color",
                "requirements": ["Change button from blue to green"],
                "forbidden_patterns": [
                    "refactoring",
                    "architecture changes",
                    "new dependencies",
                ],
            },
        }

        # Verify system prompt includes forbidden patterns
        system_prompt = command.build_system_prompt(input_data)
        assert "forbidden" in system_prompt.lower()
        assert "refactoring" in system_prompt

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "deviation_detected": True,
                "deviation_type": "scope_creep",
                "severity": "high",
                "recommendation": "Refactoring violates forbidden patterns",
                "specific_issues": ["Attempting major refactoring"],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)
        assert result["deviation_detected"] is True
