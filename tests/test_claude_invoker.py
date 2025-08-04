# ruff: noqa: SLF001
"""
Tests for Claude Invoker functionality including predicate system
"""

import os
import subprocess
from unittest.mock import MagicMock, Mock, patch

from orchestra.common.claude_invoker import (
    ClaudeInvoker,
    check_predicate,
    invoke_claude,
)


class TestClaudeInvoker:
    """Test ClaudeInvoker class"""

    def test_init(self):
        """Test initialization"""
        with patch.dict(os.environ, {"CLAUDECODE": "1"}):
            invoker = ClaudeInvoker()
            assert invoker.is_claude_code

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            assert not invoker.is_claude_code

    def test_model_aliases(self):
        """Test model alias resolution"""
        invoker = ClaudeInvoker()

        # Test known aliases
        assert invoker.MODELS["fast"] == "claude-3-haiku-20240307"
        assert invoker.MODELS["small"] == "claude-3-haiku-20240307"
        assert invoker.MODELS["balanced"] == "claude-3-5-sonnet-20241022"
        assert invoker.MODELS["default"] is None

    @patch("subprocess.run")
    def test_invoke_external_claude_success(self, mock_run):
        """Test successful external Claude invocation"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Test response from Claude"
        )

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.invoke_claude(
                prompt="Test prompt", model="fast", temperature=0.5
            )

        assert result["success"]
        assert result["response"] == "Test response from Claude"
        assert result["method"] == "external_claude"

        # Check command construction
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "claude" in cmd
        assert "--model" in cmd
        assert "claude-3-haiku-20240307" in cmd
        assert "--temperature" in cmd
        assert "0.5" in cmd

    @patch("subprocess.run")
    def test_invoke_external_claude_failure(self, mock_run):
        """Test failed external Claude invocation"""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error message")

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.invoke_claude(prompt="Test prompt")

        assert not result["success"]
        assert "error" in result
        assert "return code 1" in result["error"]

    def test_invoke_claude_code_environment(self):
        """Test invocation in Claude Code environment"""
        with patch.dict(os.environ, {"CLAUDECODE": "1"}):
            invoker = ClaudeInvoker()
            result = invoker.invoke_claude(prompt="Test prompt", model="balanced")

        assert result["success"]
        assert result["method"] == "task_tool"
        assert result["prompt"] == "Test prompt"
        assert result["model"] == "claude-3-5-sonnet-20241022"

    @patch("subprocess.run")
    def test_check_predicate_success(self, mock_run):
        """Test successful predicate check"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ANSWER: YES\nCONFIDENCE: 0.9\nREASONING: Test reasoning",
        )

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.check_predicate(
                question="Is this a test?", context={"test": "context"}
            )

        assert result["answer"] is True
        assert result["confidence"] == 0.9
        assert result["reasoning"] == "Test reasoning"
        assert result["definitive"] is True

    @patch("subprocess.run")
    def test_check_predicate_low_confidence(self, mock_run):
        """Test predicate check with low confidence"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ANSWER: YES\nCONFIDENCE: 0.5\nREASONING: Not sure"
        )

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.check_predicate(
                question="Is this uncertain?", confidence_threshold=0.8
            )

        assert result["answer"] is True  # Answer is kept even with low confidence
        assert result["confidence"] == 0.5
        assert result["definitive"] is False  # But marked as not definitive

    @patch("subprocess.run")
    def test_check_predicate_parse_failure(self, mock_run):
        """Test predicate parsing failure handling"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="This is not a properly formatted response but contains YES",
        )

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.check_predicate(question="Test?", confidence_threshold=0.3)

        assert result["answer"] is True  # Found YES in response
        assert result["confidence"] == 0.5  # Low confidence due to parse failure
        assert result["definitive"] is True  # Above 0.3 threshold

    @patch("subprocess.run")
    def test_check_predicate_both_yes_and_no(self, mock_run):
        """Test handling when response contains both YES and NO"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="The answer is not YES, it is NO"
        )

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.check_predicate(question="Test?")

        # Both YES and NO found (1 each), cannot determine
        assert result["answer"] is None
        assert result["confidence"] == 0.0
        assert result["definitive"] is False

    @patch("subprocess.run")
    def test_check_predicate_no_answer_found(self, mock_run):
        """Test handling when no YES/NO found in response"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="This response does not contain the expected words"
        )

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.check_predicate(question="Test?")

        assert result["answer"] is None
        assert result["confidence"] == 0.0
        assert result["definitive"] is False

    @patch("subprocess.run")
    def test_invoke_claude_unexpected_error(self, mock_run):
        """Test handling of unexpected errors"""
        mock_run.side_effect = Exception("Unexpected error")

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.invoke_claude(prompt="Test")

        assert not result["success"]
        assert "Unexpected error" in result["error"]

    @patch("subprocess.run")
    def test_git_diff_inclusion(self, mock_run):
        """Test git diff inclusion in context"""

        # Mock git diff commands
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "git" in cmd and "diff" in cmd:
                if "--staged" in cmd:
                    return MagicMock(returncode=0, stdout="staged changes")
                return MagicMock(returncode=0, stdout="unstaged changes")
            # Default Claude response
            return MagicMock(returncode=0, stdout="Test response")

        mock_run.side_effect = side_effect

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.invoke_claude(
                prompt="Test with diff", include_git_diff=True
            )

        # Check that git diff was called
        assert any(
            "git" in str(call) and "diff" in str(call)
            for call in mock_run.call_args_list
        )

    @patch("subprocess.run")
    def test_batch_check_predicates(self, mock_run):
        """Test batch predicate checking"""
        responses = [
            "ANSWER: YES\nCONFIDENCE: 0.9\nREASONING: First is true",
            "ANSWER: NO\nCONFIDENCE: 0.85\nREASONING: Second is false",
        ]
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=resp) for resp in responses
        ]

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            predicates = [
                {"question": "First question?"},
                {"question": "Second question?", "confidence_threshold": 0.8},
            ]

            results = invoker.batch_check_predicates(predicates)

        assert len(results) == 2
        assert results[0]["answer"] is True
        assert results[0]["question"] == "First question?"
        assert results[1]["answer"] is False
        assert results[1]["question"] == "Second question?"

    def test_context_formatting(self):
        """Test context formatting as string vs dict"""
        invoker = ClaudeInvoker()

        # Test with string context
        with patch.object(invoker, "invoke_claude") as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "response": "ANSWER: YES\nCONFIDENCE: 0.9\nREASONING: Test",
            }

            result = invoker.check_predicate(
                question="Test?", context="This is string context"
            )

            # Check that string context was converted to dict
            call_args = mock_invoke.call_args
            assert "context" in call_args.kwargs
            assert call_args.kwargs["context"] == {
                "additional_context": "This is string context"
            }

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test handling of subprocess timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.invoke_claude(prompt="Test")

        assert not result["success"]
        assert "timed out" in result["error"].lower()

    @patch("subprocess.run")
    def test_file_not_found_handling(self, mock_run):
        """Test handling when claude CLI is not found"""
        mock_run.side_effect = FileNotFoundError()

        with patch.dict(os.environ, {}, clear=True):
            invoker = ClaudeInvoker()
            result = invoker.invoke_claude(prompt="Test")

        assert not result["success"]
        assert "not found" in result["error"].lower()
        assert "PATH" in result["error"]


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    @patch("orchestra.common.claude_invoker.ClaudeInvoker.invoke_claude")
    def test_invoke_claude_function(self, mock_invoke):
        """Test invoke_claude convenience function"""
        mock_invoke.return_value = {"success": True, "response": "Test"}

        result = invoke_claude(prompt="Test", model="fast")

        mock_invoke.assert_called_once_with(prompt="Test", model="fast")
        assert result["success"]

    @patch("orchestra.common.claude_invoker.ClaudeInvoker.check_predicate")
    def test_check_predicate_function(self, mock_check):
        """Test check_predicate convenience function"""
        mock_check.return_value = {"answer": True, "confidence": 0.9}

        result = check_predicate(question="Test?", context={"key": "value"})

        mock_check.assert_called_once_with(question="Test?", context={"key": "value"})
        assert result["answer"] is True


class TestPredicateSystem:
    """Integration tests for predicate system with subagent runner"""

    @patch("orchestra.common.claude_invoker._default_invoker", None)
    @patch("subprocess.run")
    def test_subagent_predicate_check(self, mock_run):
        """Test subagent predicate checking"""
        from orchestra.common.git_task_manager import GitTaskManager
        from orchestra.common.subagent_runner import SubagentRunner
        from orchestra.common.task_state import GitTaskState

        # Mock both git diff and claude responses
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "git" in cmd:
                return MagicMock(returncode=0, stdout="")
            return MagicMock(
                returncode=0,
                stdout="ANSWER: YES\nCONFIDENCE: 0.85\nREASONING: Scope creep detected",
            )

        mock_run.side_effect = side_effect

        # Setup
        git_manager = Mock(spec=GitTaskManager)
        git_manager.get_task_file_changes.return_value = ["file1.py", "file2.py"]

        runner = SubagentRunner(git_manager)
        task_state = GitTaskState(
            task_id="test-task-1",
            task_description="Fix bug in login",
            branch_name="task/fix-login",
            base_branch="main",
            base_sha="abc123",
            current_sha="def456",
        )

        # Test predicate check
        with patch.dict(os.environ, {}, clear=True):
            result = runner.should_invoke_subagent(
                subagent_type="scope-creep-detector",
                task_state=task_state,
                analysis_context="Adding new features",
            )

        assert result["should_invoke"] is True
        assert result["confidence"] == 0.85
        assert "Scope creep detected" in result["reasoning"]

    @patch("orchestra.common.claude_invoker._default_invoker", None)
    @patch("subprocess.run")
    def test_check_all_subagents(self, mock_run):
        """Test checking all subagents"""
        from orchestra.common.git_task_manager import GitTaskManager
        from orchestra.common.subagent_runner import SubagentRunner
        from orchestra.common.task_state import GitTaskState

        # Mock different responses for each subagent
        responses = [
            "ANSWER: YES\nCONFIDENCE: 0.9\nREASONING: Scope creep",
            "ANSWER: NO\nCONFIDENCE: 0.95\nREASONING: No over-engineering",
            "ANSWER: YES\nCONFIDENCE: 0.8\nREASONING: Off topic",
        ]

        # Track call count to return appropriate responses
        call_count = [0]

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "git" in cmd:
                return MagicMock(returncode=0, stdout="")
            resp = responses[call_count[0] % len(responses)]
            call_count[0] += 1
            return MagicMock(returncode=0, stdout=resp)

        mock_run.side_effect = side_effect

        # Setup
        git_manager = Mock(spec=GitTaskManager)
        git_manager.get_task_file_changes.return_value = []

        runner = SubagentRunner(git_manager)
        task_state = GitTaskState(
            task_id="test-task-2",
            task_description="Test task",
            branch_name="test",
            base_branch="main",
            base_sha="abc",
            current_sha="def",
        )

        # Test
        with patch.dict(os.environ, {}, clear=True):
            result = runner.check_all_subagents(
                task_state=task_state, analysis_context="Test context"
            )

        assert result["has_recommendations"]
        assert result["recommendation_count"] == 2
        assert len(result["recommended_subagents"]) == 2

        # Check recommended subagents
        recommended_types = [r["type"] for r in result["recommended_subagents"]]
        assert "scope-creep-detector" in recommended_types
        assert "off-topic-detector" in recommended_types
        assert "over-engineering-detector" not in recommended_types
