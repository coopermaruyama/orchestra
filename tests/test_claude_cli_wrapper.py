"""
Tests for enhanced Claude CLI wrapper
"""

import json
import os
import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from orchestra.common.claude_cli_wrapper import (
    ClaudeCLIWrapper,
    ClaudeResponse,
    OutputFormat,
    invoke_claude_cli,
)


class TestClaudeCLIWrapper:
    """Test the enhanced Claude CLI wrapper"""

    def test_build_command_basic(self) -> None:
        """Test basic command building"""
        wrapper = ClaudeCLIWrapper()
        cmd = wrapper._build_command(
            prompt="Test prompt", output_format=OutputFormat.TEXT
        )

        assert cmd == ["claude", "--output-format", "text", "-p", "Test prompt"]

    def test_build_command_full(self) -> None:
        """Test command building with all options"""
        wrapper = ClaudeCLIWrapper()
        cmd = wrapper._build_command(
            prompt="Test prompt",
            model="sonnet",
            output_format=OutputFormat.STREAM_JSON,
            temperature=0.7,
            max_tokens=1000,
            system_prompt="You are helpful",
            verbose=True,
        )

        expected = [
            "claude",
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            "sonnet",
            "--temperature",
            "0.7",
            "--max-tokens",
            "1000",
            "--system-prompt",
            "You are helpful",
            "-p",
            "Test prompt",
        ]

        assert cmd == expected

    @patch("subprocess.run")
    def test_invoke_text_success(self, mock_run: Mock) -> None:
        """Test successful text format invocation"""
        mock_run.return_value = MagicMock(returncode=0, stdout="This is the response")

        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(
            prompt="Test", output_format=OutputFormat.TEXT, stream=False
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success
        assert response.content == "This is the response"
        assert response.error is None

    @patch("subprocess.run")
    def test_invoke_json_success(self, mock_run: Mock) -> None:
        """Test successful JSON format invocation"""
        json_output = json.dumps(
            {
                "type": "message",
                "content": "Test response",
                "model": "claude-3-sonnet",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }
        )

        mock_run.return_value = MagicMock(returncode=0, stdout=json_output)

        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(
            prompt="Test", output_format=OutputFormat.JSON, stream=False
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success
        assert response.content == "Test response"
        assert response.model == "claude-3-sonnet"
        assert response.usage == {"input_tokens": 10, "output_tokens": 20}

    @patch("subprocess.run")
    def test_invoke_stream_json_success(self, mock_run: Mock) -> None:
        """Test successful stream JSON format invocation"""
        stream_output = "\n".join(
            [
                json.dumps(
                    {"type": "system", "subtype": "init", "session_id": "test-123"}
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "type": "message",
                            "content": [{"type": "text", "text": "Hello"}],
                            "model": "claude-3-sonnet",
                            "usage": {"input_tokens": 5, "output_tokens": 10},
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"content": [{"type": "text", "text": " World"}]},
                    }
                ),
                json.dumps(
                    {
                        "type": "result",
                        "result": "Hello World",
                        "usage": {"input_tokens": 5, "output_tokens": 12},
                    }
                ),
            ]
        )

        mock_run.return_value = MagicMock(returncode=0, stdout=stream_output)

        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(
            prompt="Test", output_format=OutputFormat.STREAM_JSON, stream=False
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success
        assert response.content == "Hello World"  # From result
        assert response.model == "claude-3-sonnet"
        assert response.messages is not None
        assert response.messages is not None and len(response.messages) == 4
        assert response.usage == {"input_tokens": 5, "output_tokens": 12}

    @patch("subprocess.run")
    def test_invoke_timeout(self, mock_run: Mock) -> None:
        """Test timeout handling"""
        mock_run.side_effect = subprocess.TimeoutExpired(["claude"], 30)

        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(prompt="Test", timeout=30, stream=False)

        assert isinstance(response, ClaudeResponse)
        assert not response.success
        assert response.error is not None
        assert "timed out" in response.error.lower()
        assert response.duration_ms is not None

    @patch("subprocess.run")
    def test_invoke_command_not_found(self, mock_run: Mock) -> None:
        """Test handling when claude CLI is not found"""
        mock_run.side_effect = FileNotFoundError()

        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(prompt="Test", stream=False)

        assert isinstance(response, ClaudeResponse)
        assert not response.success
        assert response.error is not None
        assert "not found" in response.error.lower()
        assert "PATH" in response.error

    @patch("subprocess.run")
    def test_invoke_error_exit_code(self, mock_run: Mock) -> None:
        """Test handling of non-zero exit codes"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error: Invalid model"
        )

        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(prompt="Test", stream=False)

        assert isinstance(response, ClaudeResponse)
        assert not response.success
        assert response.exit_code == 1
        assert response.error is not None
        assert "exit code 1" in response.error

    @patch("subprocess.Popen")
    def test_streaming_success(self, mock_popen: Mock) -> None:
        """Test streaming JSON output"""
        # Mock process with streaming stdout
        mock_process = MagicMock()
        mock_process.stdout = [
            json.dumps({"type": "init", "session": "123"}) + "\n",
            json.dumps({"type": "content", "text": "Hello"}) + "\n",
            json.dumps({"type": "content", "text": " World"}) + "\n",
            json.dumps({"type": "done"}) + "\n",
        ]
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        wrapper = ClaudeCLIWrapper()
        results_iter = wrapper.invoke(
            prompt="Test", output_format=OutputFormat.STREAM_JSON, stream=True
        )
        assert not isinstance(results_iter, ClaudeResponse)
        results = list(results_iter)

        assert len(results) == 4
        assert results[0]["type"] == "init"
        assert results[1]["text"] == "Hello"
        assert results[2]["text"] == " World"
        assert results[3]["type"] == "done"

    @patch("subprocess.run")
    def test_convenience_function(self, mock_run: Mock) -> None:
        """Test the convenience function"""
        mock_run.return_value = MagicMock(returncode=0, stdout="Test response")

        response = invoke_claude_cli(
            prompt="Quick test", model="haiku", temperature=0.5, stream=False
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success
        assert response.content == "Test response"

        # Verify command was built correctly
        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "haiku" in cmd
        assert "--temperature" in cmd
        assert "0.5" in cmd

    def test_output_format_enum(self) -> None:
        """Test OutputFormat enum values"""
        assert OutputFormat.TEXT.value == "text"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.STREAM_JSON.value == "stream-json"

    def test_claude_response_dataclass(self) -> None:
        """Test ClaudeResponse dataclass"""
        response = ClaudeResponse(
            success=True,
            content="Test",
            messages=[{"type": "test"}],
            model="claude-3",
            usage={"tokens": 100},
        )

        assert response.success is True
        assert response.content == "Test"
        assert response.messages is not None and len(response.messages) == 1
        assert response.model == "claude-3"
        assert response.usage is not None
        assert response.usage["tokens"] == 100

    @patch("subprocess.run")
    def test_parse_malformed_json(self, mock_run: Mock) -> None:
        """Test handling of malformed JSON output"""
        mock_run.return_value = MagicMock(returncode=0, stdout="This is not JSON")

        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(
            prompt="Test", output_format=OutputFormat.JSON, stream=False
        )

        assert isinstance(response, ClaudeResponse)
        assert not response.success
        assert response.error is not None
        assert "parse JSON" in response.error
        assert response.content == "This is not JSON"  # Original output preserved


@pytest.mark.skipif(
    not os.environ.get("CLAUDECODE"), reason="Not in Claude Code environment"
)
class TestClaudeCLIWrapperIntegration:
    """Integration tests that actually call Claude CLI"""

    def test_real_claude_invocation(self) -> None:
        """Test actual Claude CLI invocation"""
        wrapper = ClaudeCLIWrapper()
        response = wrapper.invoke(
            prompt="Say 'Hello from test' and nothing else",
            model="haiku",  # Use fast model for tests
            temperature=0.1,
            max_tokens=20,
            timeout=60,
            stream=False,
        )

        assert isinstance(response, ClaudeResponse)
        if response.success:
            assert response.content
            assert (
                "hello" in response.content.lower()
                or "test" in response.content.lower()
            )
        else:
            # If it fails, ensure we have a proper error
            assert response.error
            assert not response.content
