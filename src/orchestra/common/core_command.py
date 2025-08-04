"""
Core Command Base Class for Orchestra Extensions

Provides a base class for all extension commands that use external Claude instances
with minimal context for focused, single-purpose analysis.
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .claude_cli_wrapper import ClaudeCLIWrapper, ClaudeResponse, OutputFormat


class CoreCommand(ABC):
    """Base class for all extension core commands

    Each command spawns a separate Claude instance with minimal context,
    following the principle of multiple specialized agents rather than
    one monolithic instance.
    """

    def __init__(self, model: str = "haiku", logger: Optional[logging.Logger] = None):
        """Initialize command with Claude wrapper

        Args:
            model: Claude model to use (default: haiku for speed)
            logger: Optional logger instance
        """
        self.claude = ClaudeCLIWrapper(default_model=model)
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input structure before processing

        Args:
            input_data: Input data to validate

        Returns:
            True if input is valid, False otherwise
        """

    @abstractmethod
    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build minimal prompt for Claude from input data

        Keep prompts focused and minimal - only include what's needed
        for the specific analysis task.

        Args:
            input_data: Validated input data

        Returns:
            Prompt string for Claude
        """

    @abstractmethod
    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build focused system prompt with minimal context

        System prompts should be short and focused on the specific task.
        Avoid including unnecessary context or instructions.

        Args:
            input_data: Validated input data

        Returns:
            System prompt string
        """

    @abstractmethod
    def parse_response(self, response: ClaudeResponse) -> Dict[str, Any]:
        """Parse Claude's response into structured output

        Args:
            response: Claude's response object

        Returns:
            Parsed response dictionary
        """

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command via external Claude CLI

        This spawns a separate Claude instance with minimal context
        for the specific task.

        Args:
            input_data: Input data for the command

        Returns:
            Command result dictionary
        """
        # Validate input
        if not self.validate_input(input_data):
            self.logger.error(f"Invalid input structure: {input_data.keys()}")
            return {"success": False, "error": "Invalid input structure"}

        # Build prompts
        try:
            prompt = self.build_prompt(input_data)
            system_prompt = self.build_system_prompt(input_data)
        except Exception as e:
            self.logger.error(f"Error building prompts: {e}")
            return {"success": False, "error": f"Failed to build prompts: {e!s}"}

        self.logger.debug(f"Calling Claude with prompt: {prompt[:200]}...")
        self.logger.debug(f"System prompt: {system_prompt[:100]}...")

        # Call external Claude instance
        try:
            response = self.claude.invoke(
                prompt=prompt,
                system_prompt=system_prompt,
                output_format=OutputFormat.STREAM_JSON,
                timeout=120,  # 2 minutes default
                verbose=True,
            )
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Claude invocation timed out after {e.timeout} seconds")
            return {
                "success": False,
                "error": f"Request timed out after {e.timeout} seconds",
            }

        # Handle response
        if not response.success:
            self.logger.error(f"Claude invocation failed: {response.error}")
            return {
                "success": False,
                "error": f"Claude invocation failed: {response.error}",
            }

        # Parse response
        try:
            result = self.parse_response(response)
            result["success"] = True
            return result
        except Exception as e:
            self.logger.error(f"Error parsing response: {e}")
            return {
                "success": False,
                "error": f"Failed to parse response: {e!s}",
                "raw_response": response.content,
            }

    def extract_json_from_response(self, content: str) -> Dict[str, Any]:
        """Helper to extract JSON from Claude's response

        Claude sometimes includes explanation text around JSON,
        this extracts just the JSON part.

        Args:
            content: Response content that may contain JSON

        Returns:
            Extracted JSON as dictionary

        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        # Try direct parse first
        try:
            result = json.loads(content)
            return result if isinstance(result, dict) else {}
        except json.JSONDecodeError:
            pass

        # Look for JSON block in response
        import re

        # Try to find JSON between ```json and ```
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
            return result if isinstance(result, dict) else {}

        # Try to find raw JSON object (handle nested objects)
        # Look for balanced braces
        start_idx = content.find("{")
        if start_idx != -1:
            brace_count = 0
            in_string = False
            escape = False

            for i, char in enumerate(content[start_idx:], start_idx):
                if escape:
                    escape = False
                    continue

                if char == "\\":
                    escape = True
                    continue

                if char == '"' and not escape:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            # Found complete JSON object
                            json_str = content[start_idx : i + 1]
                            result = json.loads(json_str)
                            return result if isinstance(result, dict) else {}

        # If all else fails, raise the error
        raise json.JSONDecodeError("No valid JSON found in response", content, 0)
