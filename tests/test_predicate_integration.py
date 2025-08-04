# ruff: noqa: SLF001
"""
Integration tests for the predicate system with extensions
"""

import os
from unittest.mock import Mock, patch

from orchestra.common import GitAwareExtension, check_predicate
from orchestra.common.task_state import GitTaskState


class TestExtension(GitAwareExtension):
    """Test extension for integration testing"""

    def get_default_config_filename(self) -> str:
        return "test_extension.json"

    def handle_hook(self, hook_event: str, context: dict) -> dict:
        return {"handled": True}


class TestPredicateIntegration:
    """Test predicate system integration with extensions"""

    @patch("subprocess.run")
    def test_extension_check_predicate(self, mock_run: Mock) -> None:
        """Test extension's check_predicate method"""

        # Mock git status check
        def side_effect(*args, **kwargs) -> Mock:
            cmd = args[0]
            if "git" in cmd and "status" in cmd:
                return Mock(returncode=0, stdout="On branch main")
            if "git" in cmd:
                return Mock(returncode=0, stdout="")
            return Mock(
                returncode=0,
                stdout="ANSWER: YES\nCONFIDENCE: 0.85\nREASONING: Test passed",
            )

        mock_run.side_effect = side_effect

        # Create extension with task state
        with patch.dict(os.environ, {}, clear=True):
            with patch("orchestra.common.claude_invoker._default_invoker", None):
                extension = TestExtension()

                # Create a task state
                task_state = GitTaskState(
                    task_id="test-1",
                    task_description="Fix login bug",
                    branch_name="fix/login-bug",
                    base_branch="main",
                    base_sha="abc123",
                    current_sha="def456",
                )
                extension._current_task_state = task_state

                # Check predicate with task context
                result = extension.check_predicate(
                    question="Is this task related to authentication?"
                )

                assert result["answer"] is True
                assert result["confidence"] == 0.85
                assert result["definitive"] is True

                # Verify task context was included
                call_args = [call[0][0] for call in mock_run.call_args_list]
                claude_call = next(c for c in call_args if "claude" in c)
                prompt_idx = claude_call.index("-p") + 1
                prompt = claude_call[prompt_idx]

                assert "Fix login bug" in prompt
                assert "fix/login-bug" in prompt

    @patch("subprocess.run")
    def test_extension_should_invoke_subagent(self, mock_run):
        """Test extension's should_invoke_subagent method"""

        # Mock responses
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "git" in cmd:
                return Mock(returncode=0, stdout="")
            return Mock(
                returncode=0,
                stdout="ANSWER: NO\nCONFIDENCE: 0.9\nREASONING: No scope creep detected",
            )

        mock_run.side_effect = side_effect

        with patch.dict(os.environ, {}, clear=True):
            with patch("orchestra.common.claude_invoker._default_invoker", None):
                extension = TestExtension()

                # Create task state
                task_state = GitTaskState(
                    task_id="test-2",
                    task_description="Add user authentication",
                    branch_name="feature/auth",
                    base_branch="main",
                    base_sha="abc123",
                    current_sha="def456",
                )
                extension._current_task_state = task_state

                # Check if scope-creep-detector should be invoked
                result = extension.should_invoke_subagent(
                    subagent_type="scope-creep-detector",
                    analysis_context="Implementing basic login functionality",
                )

                assert result["should_invoke"] is False
                assert result["confidence"] == 0.9
                assert result["definitive"] is True
                assert "scope-creep-detector" in result["subagent_type"]

    def test_check_predicate_convenience_function(self):
        """Test the module-level check_predicate function"""
        with patch(
            "orchestra.common.claude_invoker.ClaudeInvoker.check_predicate"
        ) as mock_check:
            mock_check.return_value = {
                "answer": True,
                "confidence": 0.95,
                "reasoning": "Test reasoning",
                "definitive": True,
            }

            result = check_predicate(
                question="Is this a test?", context={"key": "value"}
            )

            assert result["answer"] is True
            assert result["confidence"] == 0.95
            mock_check.assert_called_once_with(
                question="Is this a test?", context={"key": "value"}
            )
