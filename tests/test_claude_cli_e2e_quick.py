# ruff: noqa: SLF001
"""
Quick E2E tests for Claude CLI integration

A subset of E2E tests that run quickly for CI/CD and development.
"""

import os
import subprocess

import pytest

from orchestra.common.claude_cli_wrapper import (
    ClaudeCLIWrapper,
    ClaudeResponse,
    OutputFormat,
    invoke_claude_cli,
)


@pytest.mark.skipif(
    not os.environ.get("CLAUDECODE"), reason="E2E tests require Claude Code environment"
)
class TestClaudeCLIQuickE2E:
    """Quick E2E tests that actually call Claude CLI"""

    @pytest.fixture
    def wrapper(self) -> ClaudeCLIWrapper:
        """Create a wrapper instance for tests"""
        return ClaudeCLIWrapper(default_model="haiku")  # Fast model

    def test_text_format(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test basic text format"""
        response = wrapper.invoke(
            prompt="Reply: OK",
            output_format=OutputFormat.TEXT,
            timeout=90,  # Claude can be slow
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed: {response.error}"
        assert response.content is not None
        assert "OK" in response.content or "ok" in response.content.lower()

    def test_json_format(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test JSON format"""
        response = wrapper.invoke(
            prompt="Say YES",
            output_format=OutputFormat.JSON,
            timeout=30,
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed: {response.error}"
        assert response.content is not None
        assert "YES" in response.content or "yes" in response.content.lower()
        assert response.messages is not None
        assert response.usage is not None

    def test_stream_json_format(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test stream JSON format"""
        response = wrapper.invoke(
            prompt="Reply: STREAM",
            output_format=OutputFormat.STREAM_JSON,
            timeout=30,
            stream=False,
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed: {response.error}"
        assert response.content is not None
        assert response.messages is not None
        assert len(response.messages) > 0

    def test_streaming_mode(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test actual streaming"""
        events = []
        stream = wrapper.invoke(
            prompt="Say HI",
            output_format=OutputFormat.STREAM_JSON,
            timeout=30,
            stream=True,
        )

        for event in stream:
            events.append(event)
            if len(events) > 10:  # Limit events
                break

        assert len(events) > 0
        event_types = [e.get("type") for e in events]
        assert any(t in event_types for t in ["system", "assistant", "result"])

    def test_error_handling(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test error handling"""
        response = wrapper.invoke(
            prompt="Test",
            model="invalid-model-xyz",
            timeout=10,
        )

        assert not response.success
        assert response.error is not None
        assert response.exit_code is not None and response.exit_code != 0

    def test_system_prompt(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test system prompt"""
        response = wrapper.invoke(
            prompt="Who are you?",
            system_prompt="Always say you are a TEST BOT",
            timeout=30,
        )

        assert response.success, f"Failed: {response.error}"
        assert response.content is not None
        assert "TEST" in response.content or "BOT" in response.content

    def test_direct_cli_call(self) -> None:
        """Test direct CLI invocation"""
        result = subprocess.run(
            ["claude", "--print", "--model", "haiku", "-p", "Reply: CLI"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "CLI" in result.stdout or "cli" in result.stdout.lower()

    def test_convenience_function(self) -> None:
        """Test convenience function"""
        response = invoke_claude_cli(
            prompt="Say DONE",
            model="haiku",
            timeout=30,
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed: {response.error}"
        assert response.content is not None


# Quick tests can be run with: pytest tests/test_claude_cli_e2e_quick.py
