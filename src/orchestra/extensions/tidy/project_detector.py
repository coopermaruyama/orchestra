"""
Project Detection Module for Tidy Extension

Automatically detects project type, package manager, and available tools.
"""

import json
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ProjectType(Enum):
    """Supported project types"""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    RUBY = "ruby"
    JAVA = "java"
    CPP = "cpp"
    MONOREPO = "monorepo"
    UNKNOWN = "unknown"


class PackageManager(Enum):
    """Supported package managers"""

    # Python
    PIP = "pip"
    UV = "uv"
    POETRY = "poetry"
    PIPENV = "pipenv"

    # JavaScript/TypeScript
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    BUN = "bun"

    # Other
    CARGO = "cargo"
    GO_MOD = "go mod"
    BUNDLER = "bundler"
    MAVEN = "maven"
    GRADLE = "gradle"
    CMAKE = "cmake"

    UNKNOWN = "unknown"


@dataclass
class ToolInfo:
    """Information about a detected tool"""

    name: str
    command: str
    fix_command: Optional[str] = None
    config_file: Optional[str] = None
    version: Optional[str] = None
    is_available: bool = False


@dataclass
class ProjectInfo:
    """Complete project information"""

    project_type: ProjectType
    package_manager: PackageManager
    detected_tools: Dict[str, ToolInfo]
    config_files: List[str]
    source_files: List[str]


class ProjectDetector:
    """Detects project type and available tools"""

    def __init__(self, working_dir: str = "."):
        self.working_dir = Path(working_dir)

        # Configuration file patterns (order matters for priority)
        self.config_patterns = {
            # Python
            "pyproject.toml": (ProjectType.PYTHON, PackageManager.POETRY),
            "setup.py": (ProjectType.PYTHON, PackageManager.PIP),
            "setup.cfg": (ProjectType.PYTHON, PackageManager.PIP),
            "requirements.txt": (ProjectType.PYTHON, PackageManager.PIP),
            "Pipfile": (ProjectType.PYTHON, PackageManager.PIPENV),
            "poetry.lock": (ProjectType.PYTHON, PackageManager.POETRY),
            "Pipfile.lock": (ProjectType.PYTHON, PackageManager.PIPENV),
            # JavaScript/TypeScript - check tsconfig.json before package.json
            "tsconfig.json": (ProjectType.TYPESCRIPT, PackageManager.NPM),
            "package.json": (ProjectType.JAVASCRIPT, PackageManager.NPM),
            "package-lock.json": (ProjectType.JAVASCRIPT, PackageManager.NPM),
            "yarn.lock": (ProjectType.JAVASCRIPT, PackageManager.YARN),
            "pnpm-lock.yaml": (ProjectType.JAVASCRIPT, PackageManager.PNPM),
            "bun.lockb": (ProjectType.JAVASCRIPT, PackageManager.BUN),
            # Other languages
            "Cargo.toml": (ProjectType.RUST, PackageManager.CARGO),
            "go.mod": (ProjectType.GO, PackageManager.GO_MOD),
            "Gemfile": (ProjectType.RUBY, PackageManager.BUNDLER),
            "pom.xml": (ProjectType.JAVA, PackageManager.MAVEN),
            "build.gradle": (ProjectType.JAVA, PackageManager.GRADLE),
            "CMakeLists.txt": (ProjectType.CPP, PackageManager.CMAKE),
        }

        # Tool definitions by language
        self.tool_definitions = {
            ProjectType.PYTHON: {
                "linter": [
                    ToolInfo(
                        "ruff", "ruff check .", "ruff check . --fix", "pyproject.toml"
                    ),
                    ToolInfo("flake8", "flake8", None, ".flake8"),
                    ToolInfo("pylint", "pylint src", None, ".pylintrc"),
                ],
                "formatter": [
                    ToolInfo("black", "black . --check", "black .", "pyproject.toml"),
                    ToolInfo(
                        "autopep8", "autopep8 --diff -r .", "autopep8 -r .", "setup.cfg"
                    ),
                    ToolInfo("yapf", "yapf -d -r .", "yapf -i -r .", ".style.yapf"),
                ],
                "type_checker": [
                    ToolInfo("mypy", "mypy src/", None, "mypy.ini"),
                    ToolInfo("pyright", "pyright", None, "pyrightconfig.json"),
                    ToolInfo("pyre", "pyre check", None, ".pyre_configuration"),
                ],
                "security": [
                    ToolInfo("bandit", "bandit -r .", None, ".bandit"),
                ],
            },
            ProjectType.JAVASCRIPT: {
                "linter": [
                    ToolInfo("eslint", "eslint .", "eslint . --fix", ".eslintrc.json"),
                    ToolInfo("standard", "standard", "standard --fix", None),
                ],
                "formatter": [
                    ToolInfo(
                        "prettier",
                        "prettier . --check",
                        "prettier . --write",
                        ".prettierrc",
                    ),
                ],
            },
            ProjectType.TYPESCRIPT: {
                "linter": [
                    ToolInfo(
                        "eslint",
                        "eslint . --ext .ts,.tsx",
                        "eslint . --ext .ts,.tsx --fix",
                        ".eslintrc.json",
                    ),
                ],
                "formatter": [
                    ToolInfo(
                        "prettier",
                        "prettier . --check",
                        "prettier . --write",
                        ".prettierrc",
                    ),
                ],
                "type_checker": [
                    ToolInfo("tsc", "tsc --noEmit", None, "tsconfig.json"),
                ],
            },
            ProjectType.RUST: {
                "formatter": [
                    ToolInfo(
                        "rustfmt", "cargo fmt -- --check", "cargo fmt", "rustfmt.toml"
                    ),
                ],
                "linter": [
                    ToolInfo("clippy", "cargo clippy", None, None),
                ],
            },
            ProjectType.GO: {
                "formatter": [
                    ToolInfo("gofmt", "gofmt -l .", "gofmt -w .", None),
                ],
                "linter": [
                    ToolInfo("golint", "golint ./...", None, None),
                    ToolInfo("go vet", "go vet ./...", None, None),
                ],
            },
        }

    def detect(self) -> ProjectInfo:
        """Detect project type and available tools"""
        # First, check for explicit configuration files
        project_type, package_manager = self._detect_from_config_files()

        # If not found, check source files
        if project_type == ProjectType.UNKNOWN:
            project_type = self._detect_from_source_files()

        # Detect if it's a monorepo
        if self._is_monorepo():
            project_type = ProjectType.MONOREPO

        # Detect available tools
        detected_tools = self._detect_tools(project_type)

        # Get list of config files and source files
        config_files = self._find_config_files()
        source_files = self._find_source_files()

        return ProjectInfo(
            project_type=project_type,
            package_manager=package_manager,
            detected_tools=detected_tools,
            config_files=config_files,
            source_files=source_files,
        )

    def _detect_from_config_files(self) -> Tuple[ProjectType, PackageManager]:
        """Detect project type from configuration files"""
        for pattern, (proj_type, pkg_mgr) in self.config_patterns.items():
            if (self.working_dir / pattern).exists():
                return proj_type, pkg_mgr

        return ProjectType.UNKNOWN, PackageManager.UNKNOWN

    def _detect_from_source_files(self) -> ProjectType:
        """Detect project type from source file extensions"""
        extension_map = {
            ".py": ProjectType.PYTHON,
            ".js": ProjectType.JAVASCRIPT,
            ".jsx": ProjectType.JAVASCRIPT,
            ".ts": ProjectType.TYPESCRIPT,
            ".tsx": ProjectType.TYPESCRIPT,
            ".rs": ProjectType.RUST,
            ".go": ProjectType.GO,
            ".rb": ProjectType.RUBY,
            ".java": ProjectType.JAVA,
            ".cpp": ProjectType.CPP,
            ".cc": ProjectType.CPP,
            ".cxx": ProjectType.CPP,
            ".c": ProjectType.CPP,
            ".h": ProjectType.CPP,
            ".hpp": ProjectType.CPP,
        }

        # Count files by extension
        file_counts = {}
        for ext, proj_type in extension_map.items():
            count = len(list(self.working_dir.rglob(f"*{ext}")))
            if count > 0:
                file_counts[proj_type] = file_counts.get(proj_type, 0) + count

        if file_counts:
            # Return the most common project type
            return max(file_counts, key=file_counts.get)

        return ProjectType.UNKNOWN

    def _is_monorepo(self) -> bool:
        """Check if this is a monorepo"""
        # Check for common monorepo patterns
        monorepo_indicators = [
            "lerna.json",
            "nx.json",
            "rush.json",
            "pnpm-workspace.yaml",
            "workspaces",  # in package.json
        ]

        for indicator in monorepo_indicators:
            if (self.working_dir / indicator).exists():
                return True

        # Check for multiple package.json or other project files in subdirectories
        project_files = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod"]
        for proj_file in project_files:
            matches = list(self.working_dir.rglob(proj_file))
            if len(matches) > 1:
                return True

        return False

    def _detect_tools(self, project_type: ProjectType) -> Dict[str, ToolInfo]:
        """Detect available tools for the project type"""
        detected = {}

        if project_type not in self.tool_definitions:
            return detected

        for tool_category, tools in self.tool_definitions[project_type].items():
            for tool in tools:
                if self._is_tool_available(tool):
                    detected[tool_category] = tool
                    break

        # Also check for tools specified in package.json scripts, Makefile, etc.
        custom_tools = self._detect_custom_tools()
        detected.update(custom_tools)

        return detected

    def _is_tool_available(self, tool: ToolInfo) -> bool:
        """Check if a tool is available"""
        # First check if config file exists (if specified)
        if tool.config_file and (self.working_dir / tool.config_file).exists():
            tool.is_available = True
            return True

        # Try to run the tool with --version or --help
        base_command = tool.command.split()[0]
        test_commands = [
            [base_command, "--version"],
            [base_command, "--help"],
            [base_command, "-v"],
            [base_command, "-h"],
        ]

        for test_cmd in test_commands:
            try:
                result = subprocess.run(
                    test_cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=str(self.working_dir),
                    timeout=2,
                )
                if result.returncode == 0:
                    tool.is_available = True
                    tool.version = self._extract_version(result.stdout + result.stderr)
                    return True
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        return False

    def _extract_version(self, output: str) -> Optional[str]:
        """Extract version from tool output"""
        import re

        # Common version patterns
        patterns = [
            r"(\d+\.\d+\.\d+)",
            r"version (\d+\.\d+\.\d+)",
            r"v(\d+\.\d+\.\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _detect_custom_tools(self) -> Dict[str, ToolInfo]:
        """Detect custom tools from package.json scripts, Makefile, etc."""
        custom_tools = {}

        # Check package.json scripts
        package_json_path = self.working_dir / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path) as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})

                    # Common script patterns
                    lint_patterns = ["lint", "eslint", "tslint", "check"]
                    format_patterns = ["format", "fmt", "prettier"]
                    test_patterns = ["test", "jest", "mocha"]
                    typecheck_patterns = [
                        "typecheck",
                        "type-check",
                        "tsc",
                        "type:check",
                    ]

                    for script_name, script_cmd in scripts.items():
                        if any(p in script_name.lower() for p in lint_patterns):
                            if "linter" not in custom_tools:
                                custom_tools["linter"] = ToolInfo(
                                    f"npm:{script_name}",
                                    f"npm run {script_name}",
                                    (
                                        f"npm run {script_name}:fix"
                                        if f"{script_name}:fix" in scripts
                                        else None
                                    ),
                                    "package.json",
                                    is_available=True,
                                )
                        elif any(p in script_name.lower() for p in format_patterns):
                            if "formatter" not in custom_tools:
                                custom_tools["formatter"] = ToolInfo(
                                    f"npm:{script_name}",
                                    f"npm run {script_name}",
                                    (
                                        f"npm run {script_name}:fix"
                                        if f"{script_name}:fix" in scripts
                                        else None
                                    ),
                                    "package.json",
                                    is_available=True,
                                )
                        elif any(p in script_name.lower() for p in typecheck_patterns):
                            if "type_checker" not in custom_tools:
                                custom_tools["type_checker"] = ToolInfo(
                                    f"npm:{script_name}",
                                    f"npm run {script_name}",
                                    None,
                                    "package.json",
                                    is_available=True,
                                )
            except (json.JSONDecodeError, KeyError):
                pass

        # Check Makefile
        makefile_path = self.working_dir / "Makefile"
        if makefile_path.exists():
            try:
                with open(makefile_path) as f:
                    content = f.read()

                    # Look for common targets
                    if "lint:" in content and "linter" not in custom_tools:
                        custom_tools["linter"] = ToolInfo(
                            "make:lint",
                            "make lint",
                            "make fix" if "fix:" in content else None,
                            "Makefile",
                            is_available=True,
                        )
                    if "format:" in content and "formatter" not in custom_tools:
                        custom_tools["formatter"] = ToolInfo(
                            "make:format",
                            "make format",
                            None,
                            "Makefile",
                            is_available=True,
                        )
            except OSError:
                pass

        return custom_tools

    def _find_config_files(self) -> List[str]:
        """Find all configuration files in the project"""
        config_files = []

        # Common config file patterns
        patterns = [
            # Python
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements*.txt",
            ".flake8",
            ".pylintrc",
            "mypy.ini",
            ".bandit",
            # JavaScript/TypeScript
            "package.json",
            "tsconfig.json",
            ".eslintrc*",
            ".prettierrc*",
            "jest.config.*",
            "webpack.config.*",
            ".babelrc*",
            # Rust
            "Cargo.toml",
            "Cargo.lock",
            # Other
            "Makefile",
            "Dockerfile",
            ".gitignore",
            ".editorconfig",
            ".pre-commit-config.yaml",
            "tox.ini",
        ]

        for pattern in patterns:
            for path in self.working_dir.glob(pattern):
                if path.is_file():
                    config_files.append(str(path.relative_to(self.working_dir)))

        return sorted(config_files)

    def _find_source_files(self) -> List[str]:
        """Find source files in the project (limited list for context)"""
        source_files = []

        # Common source directories
        source_dirs = ["src", "lib", "app", "tests", "test", "spec"]

        # Limit to prevent too many files
        max_files = 20

        for dir_name in source_dirs:
            dir_path = self.working_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                for ext in [
                    ".py",
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                    ".rs",
                    ".go",
                    ".rb",
                    ".java",
                    ".cpp",
                ]:
                    for path in dir_path.rglob(f"*{ext}"):
                        if len(source_files) >= max_files:
                            return source_files
                        source_files.append(str(path.relative_to(self.working_dir)))

        return source_files

    def suggest_tools(self, project_type: ProjectType) -> Dict[str, List[ToolInfo]]:
        """Suggest tools that could be added to the project"""
        if project_type not in self.tool_definitions:
            return {}

        suggestions = {}
        for category, tools in self.tool_definitions[project_type].items():
            available_tools = [t for t in tools if self._is_tool_available(t)]
            if not available_tools:
                suggestions[category] = tools

        return suggestions
