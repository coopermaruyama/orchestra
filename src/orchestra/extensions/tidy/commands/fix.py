"""
Tidy Fix Command

Automatically fixes code quality issues using an external Claude instance
with minimal context.
"""

import difflib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestra.common.claude_cli_wrapper import ClaudeResponse
from orchestra.common.core_command import CoreCommand


class TidyFixCommand(CoreCommand):
    """Fix code quality issues using external Claude instance"""

    def __init__(self, model: str = "haiku", logger: Optional[logging.Logger] = None):
        """Initialize with fast model for quick fixes"""
        super().__init__(model=model, logger=logger)

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input has required fields"""
        required = ["file_content", "file_path", "project_rules", "file_type"]
        if not all(key in input_data for key in required):
            self.logger.debug(f"Missing required fields. Got: {input_data.keys()}")
            return False

        # project_rules should be a dict (can be empty)
        if not isinstance(input_data.get("project_rules"), dict):
            self.logger.debug("project_rules must be a dictionary")
            return False

        return True

    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build prompt requesting complete fixed file"""
        file_content = input_data.get("file_content", "")
        file_type = input_data.get("file_type", "")

        # Truncate very large files
        max_content_len = 50000
        if len(file_content) > max_content_len:
            file_content = file_content[:max_content_len] + "\n... (truncated)"

        return f"""Fix all code quality issues in this {file_type} file:

```{file_type}
{file_content}
```

Return the complete fixed file content. Fix all formatting, linting, and style issues while preserving the code's functionality."""

    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build minimal system prompt with fixing rules"""
        rules = input_data.get("project_rules", {})

        prompt_parts = ["You are a code fixer. Fix issues based on:"]

        # Add tool configurations
        if rules.get("linter"):
            prompt_parts.append(f"- Linter: {rules['linter']}")
        if rules.get("formatter"):
            prompt_parts.append(f"- Formatter: {rules['formatter']}")
        if rules.get("type_checker"):
            prompt_parts.append(f"- Type checker: {rules['type_checker']}")

        # Add custom rules
        if rules.get("custom_rules"):
            prompt_parts.append("\nCustom rules:")
            for rule in rules["custom_rules"][:5]:  # Limit to 5 rules
                prompt_parts.append(f"- {rule}")

        prompt_parts.append("\nReturn ONLY the fixed code, no explanations.")

        return "\n".join(prompt_parts)

    def parse_response(self, response: ClaudeResponse, original_content: str = "") -> Dict[str, Any]:
        """Parse Claude's response and extract fixed code"""
        try:
            content = response.content

            # Extract code from markdown block if present
            fixed_content = self._extract_code_from_response(content)

            # Detect if changes were made
            if fixed_content.strip() == original_content.strip():
                return {
                    "fixed": False,
                    "fixed_content": fixed_content,
                    "changes_made": [],
                    "unfixable_issues": []
                }

            # Detect what changes were made
            changes_made = self._detect_changes(original_content, fixed_content)

            # Look for any mentioned unfixable issues
            unfixable_issues = self._extract_unfixable_issues(content)

            return {
                "fixed": True,
                "fixed_content": fixed_content,
                "changes_made": changes_made,
                "unfixable_issues": unfixable_issues
            }

        except Exception as e:
            self.logger.error(f"Failed to parse response: {e}")
            return {
                "fixed": False,
                "fixed_content": original_content,
                "changes_made": [],
                "unfixable_issues": [],
                "error": f"Failed to parse response: {e!s}"
            }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the fix command"""
        # Store original content for comparison
        original_content = input_data.get("file_content", "")

        # Call parent execute
        result = super().execute(input_data)

        # If successful, enhance with original content for parse_response
        if result.get("success") and "error" not in result:
            # Re-parse with original content for better diff
            try:
                response = ClaudeResponse(
                    success=True,
                    content=result.get("fixed_content", ""),
                    error=None
                )
                enhanced_result = self.parse_response(response, original_content)
                result.update(enhanced_result)
            except Exception as e:
                self.logger.warning(f"Failed to enhance result: {e}")

        return result

    def _extract_code_from_response(self, content: str) -> str:
        """Extract code from response, handling markdown blocks"""
        # Try to find code in markdown block
        code_block_pattern = r"```(?:\w+)?\s*\n(.*?)\n```"
        matches = re.findall(code_block_pattern, content, re.DOTALL)

        if matches:
            # Return the largest code block (likely the complete fixed file)
            return max(matches, key=len)

        # If no code block, assume entire response is code
        # But remove any obvious non-code lines
        lines = content.split("\n")
        code_lines = []

        for line in lines:
            # Skip lines that look like explanations
            if any(phrase in line.lower() for phrase in
                   ["here's", "here is", "the fixed", "i've", "this code"]):
                continue
            code_lines.append(line)

        return "\n".join(code_lines).strip()

    def _detect_changes(self, original: str, fixed: str) -> List[Dict[str, str]]:
        """Detect what changes were made"""
        changes = []

        # Split into lines for comparison
        original_lines = original.splitlines()
        fixed_lines = fixed.splitlines()

        # Use difflib to find changes
        differ = difflib.unified_diff(
            original_lines,
            fixed_lines,
            lineterm="",
            n=0
        )

        # Analyze diff to categorize changes
        change_types = {
            "spacing": False,
            "imports": False,
            "indentation": False,
            "type_hints": False,
            "syntax": False,
            "style": False
        }

        for line in differ:
            if line.startswith("+++") or line.startswith("---"):
                continue

            if line.startswith("-") or line.startswith("+"):
                # Detect spacing changes
                if re.search(r"[=+\-*/<>]\s*\d+|[=+\-*/<>]\d+", line):
                    change_types["spacing"] = True

                # Detect import changes
                if "import" in line:
                    change_types["imports"] = True

                # Detect indentation
                if line.startswith("+    ") or line.startswith("-    "):
                    change_types["indentation"] = True

                # Detect type hints
                if "->" in line or (": " in line and "=" not in line):
                    change_types["type_hints"] = True

                # Detect missing colons (syntax)
                if re.search(r"def \w+\(.*\)(?!:)", line) or re.search(r"class \w+(?!:)", line):
                    change_types["syntax"] = True

        # Build change list
        if change_types["spacing"]:
            changes.append({
                "line": 0,  # Would need more logic for exact lines
                "issue": "Spacing and operator formatting",
                "fix_applied": "Fixed spacing around operators"
            })

        if change_types["imports"]:
            changes.append({
                "line": 0,
                "issue": "Import statement formatting",
                "fix_applied": "Organized and formatted imports"
            })

        if change_types["indentation"]:
            changes.append({
                "line": 0,
                "issue": "Indentation inconsistency",
                "fix_applied": "Fixed indentation to match style guide"
            })

        if change_types["type_hints"]:
            changes.append({
                "line": 0,
                "issue": "Missing type annotations",
                "fix_applied": "Added type hints"
            })

        if change_types["syntax"]:
            changes.append({
                "line": 0,
                "issue": "Syntax error",
                "fix_applied": "Fixed syntax errors"
            })

        # If we detected changes but no specific types, add generic
        if original.strip() != fixed.strip() and not changes:
            changes.append({
                "line": 0,
                "issue": "Code style and formatting",
                "fix_applied": "Applied project style rules"
            })

        return changes

    def _extract_unfixable_issues(self, content: str) -> List[Dict[str, str]]:
        """Extract any mentioned unfixable issues from response"""
        unfixable = []

        # Look for TODO, FIXME, or similar markers
        todo_pattern = r"(?:TODO|FIXME|XXX|HACK|NOTE):\s*(.+)"
        for match in re.finditer(todo_pattern, content, re.IGNORECASE):
            reason = match.group(1).strip()
            if "domain knowledge" in reason.lower() or "manual" in reason.lower():
                unfixable.append({
                    "line": 0,
                    "issue": "Requires manual intervention",
                    "reason": reason
                })

        return unfixable

    def _infer_file_type(self, file_path: str) -> str:
        """Infer file type from file path"""
        path = Path(file_path)
        ext = path.suffix.lower()

        type_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".m": "objc",
            ".mm": "objcpp"
        }

        return type_map.get(ext, "text")

