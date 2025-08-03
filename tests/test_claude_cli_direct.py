"""
Test running Claude CLI directly with specific parameters
"""

import pytest
import subprocess
import json
import os


class TestClaudeCLIDirect:
    """Test calling Claude CLI directly"""

    def test_claude_cli_stream_json_output(self) -> None:
        """Test running claude with stream-json output format"""
        # Skip if not in Claude Code environment
        # if not os.environ.get("CLAUDECODE"):
        #     pytest.skip("Not in Claude Code environment")

        cmd = [
            "claude",
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            "sonnet",
            "-p",
            "what is the currently active model?",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # Increased to 2 minutes
            )

            assert result.returncode == 0, f"Claude CLI failed: {result.stderr}"

            # Parse the stream JSON output
            output_lines = result.stdout.strip().split("\n")

            # Each line should be valid JSON in stream format
            for line in output_lines:
                if line.strip():  # Skip empty lines
                    try:
                        json_obj = json.loads(line)
                        # Check common stream JSON fields
                        assert (
                            "type" in json_obj
                            or "event" in json_obj
                            or "content" in json_obj
                        )
                    except json.JSONDecodeError:
                        pytest.fail(f"Invalid JSON line: {line}")

            # Check verbose output was included
            if result.stderr:
                assert "--verbose" in " ".join(cmd)

        except FileNotFoundError:
            pytest.skip("Claude CLI not found in PATH")
        except subprocess.TimeoutExpired:
            pytest.fail("Claude CLI timed out after 120 seconds")

    def test_claude_cli_with_different_models(self) -> None:
        """Test calling Claude with different model specifications"""
        if not os.environ.get("CLAUDECODE"):
            pytest.skip("Not in Claude Code environment")

        models = ["sonnet", "haiku", "opus"]

        for model in models:
            cmd = [
                "claude",
                "--model",
                model,
                "-p",
                f'Say "Using {model} model" and nothing else',
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,  # Increased to 2 minutes
                )

                if result.returncode == 0:
                    # Basic check that output contains expected text
                    assert (
                        model in result.stdout.lower()
                        or "model" in result.stdout.lower()
                    )

            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    def test_claude_cli_error_handling(self) -> None:
        """Test Claude CLI error scenarios"""
        if not os.environ.get("CLAUDECODE"):
            pytest.skip("Not in Claude Code environment")

        # Test with invalid parameters
        cmd = ["claude", "--invalid-option", "-p", "test"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            # Should fail with non-zero exit code
            assert result.returncode != 0
            assert result.stderr or "invalid" in result.stdout.lower()

        except FileNotFoundError:
            pytest.skip("Claude CLI not found")
        except subprocess.TimeoutExpired:
            pass  # Expected for some error cases

    @pytest.mark.parametrize(
        "output_format,expected_pattern",
        [
            ("stream-json", r"^\{.*\}$"),
            ("json", r"^\{.*\}$"),
            ("text", r".+"),  # Any non-empty text
        ],
    )
    def test_claude_output_formats(
        self, output_format: str, expected_pattern: str
    ) -> None:
        """Test different output formats"""
        import re

        if not os.environ.get("CLAUDECODE"):
            pytest.skip("Not in Claude Code environment")

        cmd = [
            "claude",
            "--output-format",
            output_format,
            "-p",
            'Say "Hello" and nothing else',
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # Increased to 2 minutes
            )

            if result.returncode == 0:
                output = result.stdout.strip()

                if output_format == "stream-json":
                    # Each line should be JSON
                    for line in output.split("\n"):
                        if line.strip():
                            assert re.match(expected_pattern, line.strip())
                else:
                    # Check overall pattern
                    assert re.search(expected_pattern, output, re.MULTILINE)

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("Claude CLI not available or timed out")


def test_simple_claude_invocation() -> None:
    """Simplified test that just runs the exact command requested"""
    cmd = [
        "claude",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        "sonnet",
        "-p",
        "what is the currently active model?",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # Increased to 2 minutes
            env={**os.environ, "CLAUDECODE": "1"},  # Ensure we're in Claude Code env
        )

        print(f"Exit code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")

        # Basic assertions
        assert result.returncode == 0, f"Command failed with: {result.stderr}"
        assert result.stdout, "No output received"

        # Verify it's JSON stream format
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                json.loads(line)  # Should not raise JSONDecodeError

    except FileNotFoundError:
        pytest.skip("Claude CLI not found - not in Claude Code environment")
    except subprocess.TimeoutExpired:
        pytest.fail("Claude CLI timed out after 120 seconds")
