"""
Tool Runner Module for Tidy Extension

Provides abstract base class and implementations for various code quality tools.
"""

import json
import re
import subprocess
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ToolResult:
    """Result from running a tool"""

    success: bool
    output: str
    error: str
    issues_count: int
    issues: List[Dict[str, Any]]
    exit_code: int
    duration: float
    can_fix: bool = False
    fixed_count: int = 0


class ToolRunner(ABC):
    """Abstract base class for tool runners"""

    def __init__(
        self,
        working_dir: str = ".",
        command: str = "",
        fix_command: Optional[str] = None,
    ):
        self.working_dir = Path(working_dir)
        self.command = command
        self.fix_command = fix_command

    @abstractmethod
    def check(self, files: Optional[List[str]] = None) -> ToolResult:
        """Run the tool in check mode"""

    @abstractmethod
    def fix(self, files: Optional[List[str]] = None) -> ToolResult:
        """Run the tool in fix mode"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the tool is available"""

    @abstractmethod
    def parse_output(
        self, output: str, error: str, exit_code: int
    ) -> List[Dict[str, Any]]:
        """Parse tool output into structured issues"""

    def _run_command(
        self, command: List[str], timeout: int = 60
    ) -> Tuple[str, str, int]:
        """Run a command and return output, error, and exit code"""
        import time

        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                cwd=str(self.working_dir),
                timeout=timeout,
            )
            duration = time.time() - start_time
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {timeout} seconds", -1
        except Exception as e:
            return "", str(e), -1


# Python Tool Runners


class RuffRunner(ToolRunner):
    """Runner for Ruff linter"""

    def check(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["ruff", "check"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        command.extend(["--output-format", "json"])

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        issues = self.parse_output(output, error, exit_code)

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=len(issues),
            issues=issues,
            exit_code=exit_code,
            duration=duration,
            can_fix=bool(self.fix_command),
        )

    def fix(self, files: Optional[List[str]] = None) -> ToolResult:
        if not self.fix_command:
            return ToolResult(
                success=False,
                output="",
                error="Fix command not available",
                issues_count=0,
                issues=[],
                exit_code=-1,
                duration=0.0,
            )

        command = ["ruff", "check", "--fix"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        # Count fixed issues from output
        fixed_count = 0
        if "Fixed" in output:
            match = re.search(r"Fixed (\d+) error", output)
            if match:
                fixed_count = int(match.group(1))

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=0,
            issues=[],
            exit_code=exit_code,
            duration=duration,
            fixed_count=fixed_count,
        )

    def is_available(self) -> bool:
        output, error, exit_code = self._run_command(["ruff", "--version"], timeout=5)
        return exit_code == 0

    def parse_output(
        self, output: str, error: str, exit_code: int
    ) -> List[Dict[str, Any]]:
        issues = []

        try:
            # Ruff outputs JSON when using --output-format json
            data = json.loads(output)
            for issue in data:
                issues.append(
                    {
                        "file": issue.get("filename", ""),
                        "line": issue.get("location", {}).get("row", 0),
                        "column": issue.get("location", {}).get("column", 0),
                        "severity": "error",
                        "message": issue.get("message", ""),
                        "code": issue.get("code", ""),
                        "fixable": issue.get("fix") is not None,
                    }
                )
        except json.JSONDecodeError:
            # Fallback to text parsing
            for line in output.split("\n"):
                if ":" in line and len(line.split(":")) >= 4:
                    parts = line.split(":", 3)
                    issues.append(
                        {
                            "file": parts[0],
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "column": int(parts[2]) if parts[2].isdigit() else 0,
                            "severity": "error",
                            "message": parts[3].strip() if len(parts) > 3 else "",
                            "code": "",
                            "fixable": False,
                        }
                    )

        return issues


class BlackRunner(ToolRunner):
    """Runner for Black formatter"""

    def check(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["black", "--check"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        issues = self.parse_output(output, error, exit_code)

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=len(issues),
            issues=issues,
            exit_code=exit_code,
            duration=duration,
            can_fix=True,
        )

    def fix(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["black"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        # Count reformatted files
        fixed_count = 0
        if "reformatted" in output:
            matches = re.findall(r"reformatted", output)
            fixed_count = len(matches)

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=0,
            issues=[],
            exit_code=exit_code,
            duration=duration,
            fixed_count=fixed_count,
        )

    def is_available(self) -> bool:
        output, error, exit_code = self._run_command(["black", "--version"], timeout=5)
        return exit_code == 0

    def parse_output(
        self, output: str, error: str, exit_code: int
    ) -> List[Dict[str, Any]]:
        issues = []

        # Black outputs files that would be reformatted
        for line in error.split("\n") + output.split("\n"):
            if "would reformat" in line:
                match = re.match(r"would reformat (.+)", line)
                if match:
                    issues.append(
                        {
                            "file": match.group(1),
                            "line": 0,
                            "column": 0,
                            "severity": "warning",
                            "message": "File needs formatting",
                            "code": "black",
                            "fixable": True,
                        }
                    )

        return issues


class MypyRunner(ToolRunner):
    """Runner for Mypy type checker"""

    def check(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["mypy"]
        if files:
            command.extend(files)
        else:
            command.append("src/")

        command.extend(["--no-error-summary", "--show-column-numbers"])

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        issues = self.parse_output(output, error, exit_code)

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=len(issues),
            issues=issues,
            exit_code=exit_code,
            duration=duration,
            can_fix=False,
        )

    def fix(self, files: Optional[List[str]] = None) -> ToolResult:
        # Mypy doesn't have auto-fix
        return ToolResult(
            success=False,
            output="",
            error="Mypy does not support auto-fixing",
            issues_count=0,
            issues=[],
            exit_code=-1,
            duration=0.0,
        )

    def is_available(self) -> bool:
        output, error, exit_code = self._run_command(["mypy", "--version"], timeout=5)
        return exit_code == 0

    def parse_output(
        self, output: str, error: str, exit_code: int
    ) -> List[Dict[str, Any]]:
        issues = []

        # Mypy output format: file:line:column: severity: message
        for line in output.split("\n"):
            match = re.match(r"(.+):(\d+):(\d+): (\w+): (.+)", line)
            if match:
                issues.append(
                    {
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "column": int(match.group(3)),
                        "severity": match.group(4),
                        "message": match.group(5),
                        "code": "mypy",
                        "fixable": False,
                    }
                )

        return issues


# JavaScript/TypeScript Tool Runners


class ESLintRunner(ToolRunner):
    """Runner for ESLint"""

    def check(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["eslint"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        command.extend(["--format", "json"])

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        issues = self.parse_output(output, error, exit_code)

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=len(issues),
            issues=issues,
            exit_code=exit_code,
            duration=duration,
            can_fix=bool(self.fix_command),
        )

    def fix(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["eslint", "--fix"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=0,
            issues=[],
            exit_code=exit_code,
            duration=duration,
        )

    def is_available(self) -> bool:
        output, error, exit_code = self._run_command(["eslint", "--version"], timeout=5)
        return exit_code == 0

    def parse_output(
        self, output: str, error: str, exit_code: int
    ) -> List[Dict[str, Any]]:
        issues = []

        try:
            # ESLint outputs JSON when using --format json
            data = json.loads(output)
            for file_result in data:
                for message in file_result.get("messages", []):
                    issues.append(
                        {
                            "file": file_result.get("filePath", ""),
                            "line": message.get("line", 0),
                            "column": message.get("column", 0),
                            "severity": (
                                "error"
                                if message.get("severity", 0) == 2
                                else "warning"
                            ),
                            "message": message.get("message", ""),
                            "code": message.get("ruleId", ""),
                            "fixable": message.get("fix") is not None,
                        }
                    )
        except json.JSONDecodeError:
            pass

        return issues


class PrettierRunner(ToolRunner):
    """Runner for Prettier formatter"""

    def check(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["prettier", "--check"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        issues = self.parse_output(output, error, exit_code)

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=len(issues),
            issues=issues,
            exit_code=exit_code,
            duration=duration,
            can_fix=True,
        )

    def fix(self, files: Optional[List[str]] = None) -> ToolResult:
        command = ["prettier", "--write"]
        if files:
            command.extend(files)
        else:
            command.append(".")

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        # Count formatted files
        fixed_count = 0
        for line in output.split("\n"):
            if line.strip() and not line.startswith("Checking"):
                fixed_count += 1

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=0,
            issues=[],
            exit_code=exit_code,
            duration=duration,
            fixed_count=fixed_count,
        )

    def is_available(self) -> bool:
        output, error, exit_code = self._run_command(
            ["prettier", "--version"], timeout=5
        )
        return exit_code == 0

    def parse_output(
        self, output: str, error: str, exit_code: int
    ) -> List[Dict[str, Any]]:
        issues = []

        # Prettier outputs files that need formatting
        for line in error.split("\n") + output.split("\n"):
            if (
                line.strip()
                and not line.startswith("Checking")
                and "needs formatting" in line
            ):
                file_path = line.replace("[warn]", "").replace("[error]", "").strip()
                file_path = file_path.replace(" needs formatting", "")
                issues.append(
                    {
                        "file": file_path,
                        "line": 0,
                        "column": 0,
                        "severity": "warning",
                        "message": "File needs formatting",
                        "code": "prettier",
                        "fixable": True,
                    }
                )

        return issues


class CustomCommandRunner(ToolRunner):
    """Runner for custom commands (e.g., npm scripts, make targets)"""

    def __init__(
        self,
        working_dir: str = ".",
        command: str = "",
        fix_command: Optional[str] = None,
        name: str = "custom",
    ):
        super().__init__(working_dir, command, fix_command)
        self.name = name

    def check(self, files: Optional[List[str]] = None) -> ToolResult:
        # Custom commands typically don't support file arguments
        command = self.command.split()

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        issues = self.parse_output(output, error, exit_code)

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=len(issues),
            issues=issues,
            exit_code=exit_code,
            duration=duration,
            can_fix=bool(self.fix_command),
        )

    def fix(self, files: Optional[List[str]] = None) -> ToolResult:
        if not self.fix_command:
            return ToolResult(
                success=False,
                output="",
                error="Fix command not available",
                issues_count=0,
                issues=[],
                exit_code=-1,
                duration=0.0,
            )

        command = self.fix_command.split()

        import time

        start_time = time.time()
        output, error, exit_code = self._run_command(command)
        duration = time.time() - start_time

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=error,
            issues_count=0,
            issues=[],
            exit_code=exit_code,
            duration=duration,
        )

    def is_available(self) -> bool:
        # For custom commands, check if the base command exists
        base_cmd = self.command.split()[0]
        if base_cmd in ["npm", "yarn", "pnpm", "make"]:
            output, error, exit_code = self._run_command(
                [base_cmd, "--version"], timeout=5
            )
            return exit_code == 0
        return True  # Assume custom commands are available

    def parse_output(
        self, output: str, error: str, exit_code: int
    ) -> List[Dict[str, Any]]:
        issues = []

        # Generic parsing for common patterns
        for line in (output + "\n" + error).split("\n"):
            # Look for file:line:column patterns
            match = re.match(r"(.+):(\d+):(\d+):\s*(.+)", line)
            if match:
                issues.append(
                    {
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "column": int(match.group(3)),
                        "severity": "error",
                        "message": match.group(4),
                        "code": self.name,
                        "fixable": False,
                    }
                )
            # Look for ERROR/WARNING patterns
            elif "ERROR" in line or "Error" in line:
                issues.append(
                    {
                        "file": "",
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": line.strip(),
                        "code": self.name,
                        "fixable": False,
                    }
                )

        return issues


class ToolRunnerFactory:
    """Factory for creating tool runners"""

    @staticmethod
    def create(
        tool_name: str,
        working_dir: str = ".",
        command: str = "",
        fix_command: Optional[str] = None,
    ) -> ToolRunner:
        """Create a tool runner based on tool name"""
        runners = {
            "ruff": RuffRunner,
            "black": BlackRunner,
            "mypy": MypyRunner,
            "eslint": ESLintRunner,
            "prettier": PrettierRunner,
        }

        runner_class = runners.get(tool_name.lower())
        if runner_class:
            return runner_class(working_dir, command, fix_command)
        # Default to custom command runner
        return CustomCommandRunner(working_dir, command, fix_command, tool_name)


class ParallelToolRunner:
    """Run multiple tools in parallel"""

    def __init__(self, runners: List[Tuple[str, ToolRunner]], max_workers: int = 4):
        self.runners = runners
        self.max_workers = max_workers

    def check_all(self, files: Optional[List[str]] = None) -> Dict[str, ToolResult]:
        """Run all tools in parallel and return results"""
        results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_name = {
                executor.submit(runner.check, files): name
                for name, runner in self.runners
            }

            # Collect results
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    results[name] = result
                except Exception as e:
                    results[name] = ToolResult(
                        success=False,
                        output="",
                        error=str(e),
                        issues_count=0,
                        issues=[],
                        exit_code=-1,
                        duration=0.0,
                    )

        return results

    def fix_all(self, files: Optional[List[str]] = None) -> Dict[str, ToolResult]:
        """Run all fixable tools in parallel"""
        results = {}

        # Only run tools that have fix commands
        fixable_runners = [
            (name, runner) for name, runner in self.runners if runner.fix_command
        ]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_name = {
                executor.submit(runner.fix, files): name
                for name, runner in fixable_runners
            }

            # Collect results
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    results[name] = result
                except Exception as e:
                    results[name] = ToolResult(
                        success=False,
                        output="",
                        error=str(e),
                        issues_count=0,
                        issues=[],
                        exit_code=-1,
                        duration=0.0,
                    )

        return results
