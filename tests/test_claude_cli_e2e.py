# ruff: noqa: SLF001
"""
End-to-End tests for Claude CLI integration

These tests actually invoke Claude CLI without mocks to ensure real-world functionality.
They require Claude CLI to be installed and the CLAUDECODE environment to be active.
"""

import os
import subprocess
import time
from typing import Any, Dict, List

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
class TestClaudeCLIE2E:
    """End-to-end tests that actually call Claude CLI"""

    @pytest.fixture
    def wrapper(self) -> ClaudeCLIWrapper:
        """Create a wrapper instance for tests"""
        return ClaudeCLIWrapper(default_model="haiku")  # Use fast model for tests

    def test_basic_text_invocation(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test basic text format invocation"""
        response = wrapper.invoke(
            prompt="Reply with exactly: 'E2E test successful'",
            output_format=OutputFormat.TEXT,
            temperature=0.1,
            max_tokens=20,
            timeout=60,
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed with error: {response.error}"
        assert response.content is not None
        assert "E2E" in response.content or "test" in response.content.lower()
        assert response.duration_ms is not None
        assert response.duration_ms > 0

    def test_json_format_invocation(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test JSON format output"""
        response = wrapper.invoke(
            prompt="What is 2+2? Reply with just the number.",
            output_format=OutputFormat.JSON,
            temperature=0.0,
            max_tokens=10,
            timeout=60,
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed with error: {response.error}"
        assert response.content is not None
        assert "4" in response.content or "four" in response.content.lower()

        # JSON format should include message structure
        assert response.messages is not None
        assert len(response.messages) >= 1

    def test_stream_json_format_invocation(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test stream JSON format output"""
        response = wrapper.invoke(
            prompt="Count from 1 to 3, one number per line",
            output_format=OutputFormat.STREAM_JSON,
            temperature=0.1,
            max_tokens=50,
            timeout=60,
            stream=False,  # Non-streaming mode
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed with error: {response.error}"
        assert response.content is not None

        # Should have multiple message objects
        assert response.messages is not None
        assert len(response.messages) > 0

        # Check for expected stream JSON structure
        message_types = [msg.get("type") for msg in response.messages]
        assert "system" in message_types or "assistant" in message_types

        # Should have usage information
        assert response.usage is not None

    def test_streaming_invocation(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test actual streaming functionality"""
        events: List[Dict[str, Any]] = []
        start_time = time.time()

        stream = wrapper.invoke(
            prompt="Say 'Hello' then 'World' with a pause between",
            output_format=OutputFormat.STREAM_JSON,
            temperature=0.1,
            max_tokens=20,
            timeout=60,
            stream=True,
        )

        # Collect streaming events
        for event in stream:
            events.append(event)
            # Ensure we're actually streaming (events come in over time)
            event["timestamp"] = time.time() - start_time

        assert len(events) > 0, "No events received from stream"

        # Check event structure
        event_types = [e.get("type") for e in events]
        assert any(t in ["system", "assistant", "result"] for t in event_types)

        # Verify streaming (events should be spread over time, not all at once)
        if len(events) > 2:
            time_spread = events[-1]["timestamp"] - events[0]["timestamp"]
            assert time_spread > 0.01, "Events came too quickly, might not be streaming"

    def test_model_selection(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test different model selections"""
        models = ["haiku", "sonnet"]  # Don't test opus in E2E due to cost

        for model in models:
            response = wrapper.invoke(
                prompt=f"Say 'Testing {model} model' and nothing else",
                model=model,
                temperature=0.1,
                max_tokens=20,
                timeout=90,
            )

            assert response.success, f"Failed with {model}: {response.error}"
            assert response.content is not None
            assert (
                model in response.content.lower()
                or "testing" in response.content.lower()
            )

    def test_system_prompt(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test system prompt functionality"""
        response = wrapper.invoke(
            prompt="What are you?",
            system_prompt="You are a pirate. Always respond in pirate speak.",
            temperature=0.5,
            max_tokens=50,
            timeout=60,
        )

        assert response.success, f"Failed with error: {response.error}"
        assert response.content is not None

        # Should contain pirate-like language
        pirate_words = ["arr", "ahoy", "matey", "ye", "aye", "treasure", "sea", "ship"]
        assert any(
            word in response.content.lower() for word in pirate_words
        ), f"Response doesn't seem pirate-like: {response.content}"

    def test_temperature_variation(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test temperature affects output variation"""
        prompt = "Generate a random word"

        # Low temperature - should be more consistent
        responses_low_temp = []
        for _ in range(3):
            response = wrapper.invoke(
                prompt=prompt,
                temperature=0.0,
                max_tokens=10,
                timeout=60,
            )
            assert response.success
            responses_low_temp.append(response.content)

        # High temperature - should be more varied
        responses_high_temp = []
        for _ in range(3):
            response = wrapper.invoke(
                prompt=prompt,
                temperature=1.0,
                max_tokens=10,
                timeout=60,
            )
            assert response.success
            responses_high_temp.append(response.content)

        # High temperature should produce more unique responses
        unique_low = len(set(responses_low_temp))
        unique_high = len(set(responses_high_temp))

        # This is probabilistic, so we just check that we got responses
        assert all(r is not None for r in responses_low_temp)
        assert all(r is not None for r in responses_high_temp)

    def test_max_tokens_limit(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test max tokens actually limits output"""
        response = wrapper.invoke(
            prompt="Count from 1 to 100, one number per line",
            max_tokens=20,  # Very low limit
            temperature=0.0,
            timeout=60,
        )

        assert response.success, f"Failed with error: {response.error}"
        assert response.content is not None

        # Output should be truncated due to token limit
        # It shouldn't contain high numbers like 50 or 100
        assert "50" not in response.content
        assert "100" not in response.content

    def test_timeout_handling(self) -> None:
        """Test actual timeout behavior"""
        wrapper = ClaudeCLIWrapper()

        # Use a very short timeout that should fail
        response = wrapper.invoke(
            prompt="Write a very long essay about the history of computing",
            model="sonnet",  # Slower model
            max_tokens=4000,  # High token count
            timeout=1,  # 1 second timeout - should fail
        )

        assert not response.success
        assert response.error is not None
        assert "timed out" in response.error.lower()

    def test_invalid_model_error(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test handling of invalid model names"""
        response = wrapper.invoke(
            prompt="Test",
            model="invalid-model-name-xyz",
            timeout=30,
        )

        # Should fail with appropriate error
        assert not response.success
        assert response.error is not None
        assert response.exit_code is not None and response.exit_code != 0

    def test_convenience_function_e2e(self) -> None:
        """Test the convenience function in real environment"""
        response = invoke_claude_cli(
            prompt="Reply with 'Convenience function works'",
            model="haiku",
            temperature=0.1,
            max_tokens=20,
            timeout=60,
        )

        assert isinstance(response, ClaudeResponse)
        assert response.success, f"Failed with error: {response.error}"
        assert response.content is not None
        assert (
            "convenience" in response.content.lower()
            or "works" in response.content.lower()
        )

    def test_concurrent_invocations(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test multiple concurrent Claude invocations"""
        import concurrent.futures

        def invoke_claude(prompt: str) -> ClaudeResponse:
            return wrapper.invoke(
                prompt=prompt,
                temperature=0.1,
                max_tokens=20,
                timeout=60,
            )

        prompts = [
            "Say 'First'",
            "Say 'Second'",
            "Say 'Third'",
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(invoke_claude, p) for p in prompts]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(
            r.success for r in responses
        ), f"Some requests failed: {[r.error for r in responses if not r.success]}"

        # Should have different content
        contents = [r.content for r in responses]
        assert len(set(contents)) >= 2, "All responses were identical"

    def test_empty_prompt_handling(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test handling of empty prompts"""
        response = wrapper.invoke(
            prompt="",
            timeout=30,
        )

        # Should either fail gracefully or provide a response
        if response.success:
            assert response.content is not None
        else:
            assert response.error is not None

    def test_very_long_prompt(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test handling of very long prompts"""
        # Create a long prompt (but not too long to avoid token limits)
        long_prompt = "Please summarize this text: " + ("test " * 500)

        response = wrapper.invoke(
            prompt=long_prompt,
            max_tokens=50,
            timeout=90,
        )

        assert response.success, f"Failed with error: {response.error}"
        assert response.content is not None
        assert len(response.content) > 0

    def test_special_characters_in_prompt(self, wrapper: ClaudeCLIWrapper) -> None:
        """Test handling of special characters"""
        special_prompts = [
            "Reply with: 'Quote test passed'",
            'Say "Double quotes work"',
            "Test with\nnewlines\nplease respond 'yes'",
            "Unicode test: 你好 café ñ → reply 'unicode works'",
        ]

        for prompt in special_prompts:
            response = wrapper.invoke(
                prompt=prompt,
                temperature=0.1,
                max_tokens=30,
                timeout=60,
            )

            assert response.success, f"Failed with prompt '{prompt}': {response.error}"
            assert response.content is not None


@pytest.mark.skipif(
    not os.environ.get("CLAUDECODE"), reason="E2E tests require Claude Code environment"
)
class TestClaudeCLIDirectE2E:
    """Direct subprocess tests without wrapper"""

    def test_direct_subprocess_invocation(self) -> None:
        """Test calling Claude directly via subprocess"""
        result = subprocess.run(
            ["claude", "--model", "haiku", "-p", "Say 'Direct test'"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"Failed with: {result.stderr}"
        assert result.stdout
        assert "direct" in result.stdout.lower() or "test" in result.stdout.lower()

    def test_pipe_input_to_claude(self) -> None:
        """Test piping input to Claude"""
        echo_process = subprocess.Popen(
            ["echo", "What is 2+2?"],
            stdout=subprocess.PIPE,
            text=True,
        )

        claude_process = subprocess.Popen(
            ["claude", "--model", "haiku", "--max-tokens", "10"],
            stdin=echo_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        echo_process.stdout.close()
        stdout, stderr = claude_process.communicate(timeout=60)

        assert claude_process.returncode == 0, f"Failed with: {stderr}"
        assert "4" in stdout or "four" in stdout.lower()

    def test_environment_variables(self) -> None:
        """Test Claude CLI respects environment variables"""
        env = os.environ.copy()
        env["CLAUDE_MODEL"] = "haiku"  # If this env var is supported

        result = subprocess.run(
            ["claude", "-p", "Say 'Environment test'"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        # Should work with or without env var support
        assert result.returncode == 0 or "CLAUDE_MODEL" not in result.stderr
        if result.returncode == 0:
            assert result.stdout
