"""
Tester Analyze Command

Analyzes code changes to determine what tests are needed using an external
Claude instance with minimal context.
"""

import json
import logging
from typing import Any, Dict, Optional

from orchestra.common.claude_cli_wrapper import ClaudeResponse
from orchestra.common.core_command import CoreCommand


class TesterAnalyzeCommand(CoreCommand):
    """Analyze code changes to determine test requirements"""

    def __init__(self, model: str = "haiku", logger: Optional[logging.Logger] = None):
        """Initialize with fast model for quick analysis"""
        super().__init__(model=model, logger=logger)

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input has required fields and structure"""
        # Check top-level required fields
        required = ["code_changes", "test_context", "calibration_data"]
        if not all(key in input_data for key in required):
            self.logger.debug(f"Missing required fields. Got: {input_data.keys()}")
            return False

        # Validate code_changes structure
        code_changes = input_data.get("code_changes", {})
        if not isinstance(code_changes, dict):
            return False
        if "files" not in code_changes or "diff" not in code_changes:
            self.logger.debug("code_changes missing files or diff")
            return False

        # Validate test_context structure
        test_context = input_data.get("test_context", {})
        if not isinstance(test_context, dict) or "framework" not in test_context:
            self.logger.debug("test_context missing framework")
            return False

        # calibration_data can be empty dict
        if not isinstance(input_data.get("calibration_data"), dict):
            return False

        return True

    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build prompt for test requirement analysis"""
        code_changes = input_data.get("code_changes", {})
        files = code_changes.get("files", [])
        diff = code_changes.get("diff", "")

        # Truncate large diffs
        max_diff_len = 10000
        if len(diff) > max_diff_len:
            diff = diff[:max_diff_len] + "\n... (truncated)"

        # Build file list
        file_list = ", ".join(files[:10])  # Limit to 10 files
        if len(files) > 10:
            file_list += f" (and {len(files) - 10} more)"

        return f"""Analyze the following code changes and determine what tests are needed:

FILES CHANGED:
{file_list}

CODE DIFF:
```diff
{diff}
```

Analyze what tests should be written for these changes. Consider:
- Unit tests for individual functions/methods
- Integration tests for interactions
- Edge cases and error handling
- Performance tests if applicable

Return JSON with: tests_needed (array of test objects), suggested_commands (array), coverage_gaps (array), existing_tests_to_update (array)."""

    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build system prompt with test framework context"""
        test_context = input_data.get("test_context", {})
        calibration = input_data.get("calibration_data", {})

        framework = test_context.get("framework", "unknown")
        coverage_req = test_context.get("coverage_requirements", 0.8)
        test_patterns = test_context.get("test_patterns", [])

        prompt_parts = [
            f"You are a test requirement analyzer specializing in {framework}.",
            f"Target coverage: {int(coverage_req * 100)}%",
        ]

        # Add test patterns if available
        if test_patterns:
            patterns_str = ", ".join(test_patterns[:3])
            prompt_parts.append(f"Test file patterns: {patterns_str}")

        # Add calibration data
        if calibration.get("test_commands"):
            cmds = calibration["test_commands"]
            cmd_list = []
            for cmd_type, cmd in list(cmds.items())[:3]:  # Limit to 3
                cmd_list.append(f"{cmd_type}: {cmd}")
            if cmd_list:
                prompt_parts.append(f"Test commands: {'; '.join(cmd_list)}")

        if calibration.get("assertion_style"):
            prompt_parts.append(f"Assertion style: {calibration['assertion_style']}")

        prompt_parts.append(
            """
Output JSON with:
- tests_needed: array of {file, test_name, test_type, reason}
- suggested_commands: array of test commands to run
- coverage_gaps: array of untested scenarios
- existing_tests_to_update: array of test files needing updates"""
        )

        return "\n".join(prompt_parts)

    def parse_response(self, response: ClaudeResponse) -> Dict[str, Any]:
        """Parse Claude's test analysis response"""
        try:
            # Extract JSON from response
            result = self.extract_json_from_response(response.content)

            # Ensure all expected fields with defaults
            expected_fields = {
                "tests_needed": [],
                "suggested_commands": [],
                "coverage_gaps": [],
                "existing_tests_to_update": [],
            }

            for key, default in expected_fields.items():
                if key not in result:
                    result[key] = default

            # Validate tests_needed structure
            if isinstance(result.get("tests_needed"), list):
                valid_tests = []
                for test in result["tests_needed"]:
                    if isinstance(test, dict) and all(
                        k in test for k in ["file", "test_name", "test_type", "reason"]
                    ):
                        # Validate test_type
                        valid_types = ["unit", "integration", "e2e", "performance"]
                        if test["test_type"] not in valid_types:
                            test["test_type"] = "unit"  # Default to unit
                        valid_tests.append(test)
                result["tests_needed"] = valid_tests

            # Ensure other fields are lists
            for field in [
                "suggested_commands",
                "coverage_gaps",
                "existing_tests_to_update",
            ]:
                if not isinstance(result.get(field), list):
                    result[field] = []

            return result

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse test analysis: {e}")
            return {
                "tests_needed": [],
                "suggested_commands": [],
                "coverage_gaps": [],
                "existing_tests_to_update": [],
                "error": f"Failed to parse response: {e!s}",
            }
