"""
Enhanced Claude CLI wrapper for better subagent integration

Provides stream JSON parsing, timeout handling, and better error reporting
for external Claude CLI invocations.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterator, List, Literal, Optional, Union, overload


class OutputFormat(Enum):
    """Supported output formats for Claude CLI"""

    TEXT = "text"
    JSON = "json"
    STREAM_JSON = "stream-json"


@dataclass
class ClaudeResponse:
    """Structured response from Claude CLI"""

    success: bool
    content: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


class ClaudeCLIWrapper:
    """Enhanced wrapper for Claude CLI with streaming support"""

    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(self, default_model: Optional[str] = None):
        """Initialize wrapper with optional default model"""
        self.default_model = default_model

    @overload
    def invoke(
        self,
        prompt: str,
        model: Optional[str] = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        timeout: Optional[int] = None,
        verbose: bool = False,
        stream: Literal[False] = False,
        allowed_tools: Optional[str] = None,
    ) -> ClaudeResponse: ...

    @overload
    def invoke(
        self,
        prompt: str,
        model: Optional[str] = None,
        output_format: Literal[OutputFormat.STREAM_JSON] = OutputFormat.STREAM_JSON,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        timeout: Optional[int] = None,
        verbose: bool = False,
        stream: Literal[True] = True,
        allowed_tools: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]: ...

    def invoke(
        self,
        prompt: str,
        model: Optional[str] = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        timeout: Optional[int] = None,
        verbose: bool = False,
        stream: bool = False,
        allowed_tools: Optional[str] = None,
    ) -> Union[ClaudeResponse, Iterator[Dict[str, Any]]]:
        """Invoke Claude CLI with enhanced options

        Args:
            prompt: The prompt to send to Claude
            model: Model to use (e.g., 'sonnet', 'haiku', 'opus')
            output_format: Output format (text, json, stream-json)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt to use
            timeout: Timeout in seconds
            verbose: Whether to include verbose output
            stream: Whether to stream results (only for stream-json format)
            allowed_tools: Space-separated list of allowed tools (e.g., "Bash(git:*) Edit")

        Returns:
            ClaudeResponse object or iterator of JSON objects if streaming
        """
        model = model or self.default_model
        timeout = timeout or self.DEFAULT_TIMEOUT

        # Build command
        cmd = self._build_command(
            prompt=prompt,
            model=model,
            output_format=output_format,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            verbose=verbose,
            allowed_tools=allowed_tools,
        )

        # Execute based on streaming preference
        if stream and output_format == OutputFormat.STREAM_JSON:
            return self._invoke_streaming(cmd, timeout)
        return self._invoke_blocking(cmd, timeout, output_format)

    def _build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        verbose: bool = False,
        allowed_tools: Optional[str] = None,
    ) -> List[str]:
        """Build Claude CLI command"""
        cmd = ["claude"]

        # Add --print for non-interactive mode
        cmd.append("--print")

        # Add output format
        cmd.extend(["--output-format", output_format.value])

        # Add verbose flag
        # Note: stream-json format requires --verbose
        if verbose or output_format == OutputFormat.STREAM_JSON:
            cmd.append("--verbose")

        # Add model if specified
        if model:
            cmd.extend(["--model", model])

        # Note: Claude CLI doesn't support temperature or max_tokens directly
        # For now, we'll only use system_prompt if provided
        # TODO: Consider including constraints in the main prompt

        # Add system prompt using --append-system-prompt
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        # Add allowed tools if specified
        if allowed_tools:
            cmd.extend(["--allowedTools", allowed_tools])

        # Add the prompt
        cmd.extend(["-p", prompt])

        return cmd

    def _invoke_blocking(
        self, cmd: List[str], timeout: int, output_format: OutputFormat
    ) -> ClaudeResponse:
        """Execute Claude CLI and wait for completion"""
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.returncode == 0:
                return self._parse_response(result.stdout, output_format, duration_ms)
            error_msg = f"Claude CLI failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f"\nStderr: {result.stderr}"
            if result.stdout:
                error_msg += f"\nStdout: {result.stdout}"
            return ClaudeResponse(
                success=False,
                error=error_msg,
                exit_code=result.returncode,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ClaudeResponse(
                success=False,
                error=f"Claude CLI timed out after {timeout} seconds",
                duration_ms=duration_ms,
            )
        except FileNotFoundError:
            return ClaudeResponse(
                success=False,
                error="Claude CLI not found. Ensure 'claude' is installed and in PATH",
            )
        except Exception as e:
            return ClaudeResponse(
                success=False,
                error=f"Unexpected error: {e!s}",
            )

    def _invoke_streaming(
        self, cmd: List[str], timeout: int
    ) -> Iterator[Dict[str, Any]]:
        """Execute Claude CLI and stream results"""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Set timeout alarm
            start_time = time.time()

            # Stream stdout line by line
            if process.stdout:
                for line in process.stdout:
                    if time.time() - start_time > timeout:
                        process.terminate()
                        raise subprocess.TimeoutExpired(cmd, timeout)

                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            # Skip non-JSON lines
                            continue

            # Wait for process to complete
            process.wait()

        except subprocess.TimeoutExpired:
            yield {
                "type": "error",
                "error": f"Timed out after {timeout} seconds",
            }
        except FileNotFoundError:
            yield {
                "type": "error",
                "error": "Claude CLI not found",
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": f"Unexpected error: {e!s}",
            }

    def _parse_response(
        self, output: str, output_format: OutputFormat, duration_ms: int
    ) -> ClaudeResponse:
        """Parse Claude CLI output based on format"""
        if output_format == OutputFormat.TEXT:
            return ClaudeResponse(
                success=True,
                content=output.strip(),
                duration_ms=duration_ms,
            )

        if output_format == OutputFormat.JSON:
            try:
                data = json.loads(output.strip())

                # Extract content from different possible locations
                content = data.get("content") or data.get("result")

                # Extract model info
                model = data.get("model")

                # Extract usage info
                usage = data.get("usage")

                return ClaudeResponse(
                    success=True,
                    content=content,
                    messages=[data] if "type" in data else None,
                    model=model,
                    usage=usage,
                    duration_ms=duration_ms,
                )
            except json.JSONDecodeError:
                return ClaudeResponse(
                    success=False,
                    error="Failed to parse JSON output",
                    content=output,
                    duration_ms=duration_ms,
                )

        elif output_format == OutputFormat.STREAM_JSON:
            # Parse stream JSON format
            messages = []
            content_parts = []
            model = None
            usage = None

            for line in output.strip().split("\n"):
                if line.strip():
                    try:
                        obj = json.loads(line)
                        messages.append(obj)

                        # Extract relevant information
                        if obj.get("type") == "assistant" and "message" in obj:
                            msg = obj["message"]
                            if "content" in msg:
                                for content in msg["content"]:
                                    if content.get("type") == "text":
                                        content_parts.append(content["text"])
                            if "model" in msg:
                                model = msg["model"]
                            if "usage" in msg:
                                usage = msg["usage"]

                        elif obj.get("type") == "result":
                            if "result" in obj:
                                content_parts = [obj["result"]]
                            if "usage" in obj:
                                usage = obj["usage"]

                    except json.JSONDecodeError:
                        continue

            return ClaudeResponse(
                success=True,
                content="\n".join(content_parts) if content_parts else None,
                messages=messages,
                model=model,
                usage=usage,
                duration_ms=duration_ms,
            )

        else:
            return ClaudeResponse(
                success=False,
                error=f"Unknown output format: {output_format}",
                duration_ms=duration_ms,
            )


# Convenience function
def invoke_claude_cli(
    prompt: str, model: Optional[str] = None, **kwargs: Any
) -> Union[ClaudeResponse, Iterator[Dict[str, Any]]]:
    """Quick function to invoke Claude CLI"""
    wrapper = ClaudeCLIWrapper()
    # Type ignore needed because overloads make this complex
    return wrapper.invoke(prompt, model=model, **kwargs)  # type: ignore
