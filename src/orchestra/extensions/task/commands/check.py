"""
Task Check Command

Analyzes work for deviations from task requirements using an external Claude instance
with minimal context.
"""

import json
import logging
from typing import Any, Dict, Optional

from orchestra.common.claude_cli_wrapper import ClaudeResponse
from orchestra.common.core_command import CoreCommand


class TaskCheckCommand(CoreCommand):
    """Check for task deviations using external Claude instance"""

    def __init__(self, model: str = "haiku", logger: Optional[logging.Logger] = None):
        """Initialize with fast model for quick analysis"""
        super().__init__(model=model, logger=logger)

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input has required fields"""
        # Check top-level required fields
        required = ["transcript", "diff", "memory"]
        if not all(key in input_data for key in required):
            self.logger.debug(f"Missing required fields. Got: {input_data.keys()}")
            return False

        # Validate memory structure
        memory = input_data.get("memory", {})
        if not isinstance(memory, dict) or "task" not in memory:
            self.logger.debug("Invalid memory structure - missing 'task' field")
            return False

        return True

    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build minimal prompt for deviation analysis"""
        transcript = input_data.get("transcript", "")
        diff = input_data.get("diff", "")

        # Truncate if too long to keep context minimal
        max_transcript_len = 2000
        max_diff_len = 5000

        if len(transcript) > max_transcript_len:
            transcript = transcript[:max_transcript_len] + "\n... (truncated)"

        if len(diff) > max_diff_len:
            diff = diff[:max_diff_len] + "\n... (truncated)"

        return f"""Analyze the following for task deviations:

TRANSCRIPT:
{transcript}

GIT DIFF:
{diff}

Identify any scope creep, over-engineering, or off-topic work.
Return a JSON response with: deviation_detected (bool), deviation_type (string or null), severity (low/medium/high), recommendation (string), and specific_issues (array of strings)."""

    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build focused system prompt"""
        memory = input_data.get("memory", {})
        task = memory.get("task", "Unknown task")
        requirements = memory.get("requirements", [])
        forbidden = memory.get("forbidden_patterns", [])

        # Keep it minimal and focused
        prompt_parts = [
            "You are a task deviation analyzer.",
            f"Current task: {task}"
        ]

        if requirements:
            req_list = ", ".join(requirements[:5])  # Limit to 5 requirements
            if len(requirements) > 5:
                req_list += f" (and {len(requirements) - 5} more)"
            prompt_parts.append(f"Requirements: {req_list}")

        if forbidden:
            forbidden_list = ", ".join(forbidden[:3])  # Limit to 3 patterns
            if len(forbidden) > 3:
                forbidden_list += f" (and {len(forbidden) - 3} more)"
            prompt_parts.append(f"Forbidden: {forbidden_list}")

        prompt_parts.append("\nOutput JSON with: deviation_detected, deviation_type, severity, recommendation, specific_issues")

        return "\n".join(prompt_parts)

    def parse_response(self, response: ClaudeResponse) -> Dict[str, Any]:
        """Parse Claude's response into structured output"""
        try:
            # Try to extract JSON from response
            result = self.extract_json_from_response(response.content)

            # Ensure all expected fields are present
            expected_fields = {
                "deviation_detected": False,
                "deviation_type": None,
                "severity": "low",
                "recommendation": "Unable to parse recommendation",
                "specific_issues": []
            }

            # Merge with defaults
            for key, default in expected_fields.items():
                if key not in result:
                    result[key] = default

            # Validate deviation_type
            valid_types = ["scope_creep", "over_engineering", "off_topic", None]
            if result["deviation_type"] not in valid_types:
                self.logger.warning(f"Invalid deviation type: {result['deviation_type']}")
                result["deviation_type"] = None

            # Validate severity
            valid_severities = ["low", "medium", "high"]
            if result["severity"] not in valid_severities:
                result["severity"] = "low"

            # Ensure specific_issues is a list
            if not isinstance(result.get("specific_issues"), list):
                result["specific_issues"] = []

            return result

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse Claude response: {e}")
            return {
                "deviation_detected": False,
                "deviation_type": None,
                "severity": "low",
                "recommendation": "Unable to analyze due to parsing error",
                "specific_issues": [],
                "error": f"Failed to parse response: {e!s}"
            }

