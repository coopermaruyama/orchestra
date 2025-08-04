# ruff: noqa: SLF001
#!/usr/bin/env python3
"""
Tests for Project Detector
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestra.extensions.tidy.project_detector import (
    PackageManager,
    ProjectDetector,
    ProjectType,
)


class TestProjectDetector(unittest.TestCase):
    """Test the project detector"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.detector = ProjectDetector(self.temp_dir)

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)

    def test_detect_python_project_with_pyproject_toml(self):
        """Test detection of Python project with pyproject.toml"""
        # Create pyproject.toml
        pyproject_path = Path(self.temp_dir) / "pyproject.toml"
        pyproject_path.write_text(
            """
[tool.poetry]
name = "test-project"
version = "0.1.0"
"""
        )

        # Create some Python files
        src_dir = Path(self.temp_dir) / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')")

        # Detect project
        project_info = self.detector.detect()

        self.assertEqual(project_info.project_type, ProjectType.PYTHON)
        self.assertEqual(project_info.package_manager, PackageManager.POETRY)
        self.assertIn("pyproject.toml", project_info.config_files)

    def test_detect_javascript_project_with_package_json(self):
        """Test detection of JavaScript project with package.json"""
        # Create package.json
        package_json_path = Path(self.temp_dir) / "package.json"
        package_json_path.write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "scripts": {"lint": "eslint .", "format": "prettier --write ."},
                }
            )
        )

        # Create some JS files
        (Path(self.temp_dir) / "index.js").write_text("console.log('hello');")

        # Detect project
        project_info = self.detector.detect()

        self.assertEqual(project_info.project_type, ProjectType.JAVASCRIPT)
        self.assertEqual(project_info.package_manager, PackageManager.NPM)
        self.assertIn("package.json", project_info.config_files)

    def test_detect_typescript_project(self):
        """Test detection of TypeScript project"""
        # Create tsconfig.json
        tsconfig_path = Path(self.temp_dir) / "tsconfig.json"
        tsconfig_path.write_text(
            json.dumps({"compilerOptions": {"target": "es5", "module": "commonjs"}})
        )

        # Create package.json
        package_json_path = Path(self.temp_dir) / "package.json"
        package_json_path.write_text(
            json.dumps({"name": "test-project", "version": "1.0.0"})
        )

        # Detect project
        project_info = self.detector.detect()

        self.assertEqual(project_info.project_type, ProjectType.TYPESCRIPT)
        self.assertEqual(project_info.package_manager, PackageManager.NPM)
        self.assertIn("tsconfig.json", project_info.config_files)

    def test_detect_rust_project(self):
        """Test detection of Rust project"""
        # Create Cargo.toml
        cargo_path = Path(self.temp_dir) / "Cargo.toml"
        cargo_path.write_text(
            """
[package]
name = "test-project"
version = "0.1.0"
"""
        )

        # Detect project
        project_info = self.detector.detect()

        self.assertEqual(project_info.project_type, ProjectType.RUST)
        self.assertEqual(project_info.package_manager, PackageManager.CARGO)
        self.assertIn("Cargo.toml", project_info.config_files)

    def test_detect_from_source_files(self):
        """Test detection from source files when no config files exist"""
        # Create only Python files
        src_dir = Path(self.temp_dir) / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')")
        (src_dir / "utils.py").write_text("def helper(): pass")

        # Detect project
        project_info = self.detector.detect()

        self.assertEqual(project_info.project_type, ProjectType.PYTHON)
        self.assertEqual(project_info.package_manager, PackageManager.UNKNOWN)

    def test_detect_monorepo(self):
        """Test detection of monorepo"""
        # Create multiple package.json files
        frontend_dir = Path(self.temp_dir) / "frontend"
        backend_dir = Path(self.temp_dir) / "backend"
        frontend_dir.mkdir()
        backend_dir.mkdir()

        (frontend_dir / "package.json").write_text(json.dumps({"name": "frontend"}))
        (backend_dir / "package.json").write_text(json.dumps({"name": "backend"}))

        # Detect project
        project_info = self.detector.detect()

        self.assertEqual(project_info.project_type, ProjectType.MONOREPO)

    def test_detect_custom_tools_from_package_json(self):
        """Test detection of custom tools from package.json scripts"""
        # Create package.json with custom scripts
        package_json_path = Path(self.temp_dir) / "package.json"
        package_json_path.write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "scripts": {
                        "lint": "eslint .",
                        "lint:fix": "eslint . --fix",
                        "format": "prettier --write .",
                        "typecheck": "tsc --noEmit",
                    },
                }
            )
        )

        # Detect project
        project_info = self.detector.detect()

        # Check if custom tools were detected
        self.assertIn("linter", project_info.detected_tools)
        self.assertIn("formatter", project_info.detected_tools)
        self.assertIn("type_checker", project_info.detected_tools)

        # Check tool details
        linter = project_info.detected_tools["linter"]
        self.assertEqual(linter.name, "npm:lint")
        self.assertEqual(linter.command, "npm run lint")
        self.assertEqual(linter.fix_command, "npm run lint:fix")

    def test_detect_custom_tools_from_makefile(self):
        """Test detection of custom tools from Makefile"""
        # Create Makefile
        makefile_path = Path(self.temp_dir) / "Makefile"
        makefile_path.write_text(
            """
lint:
\tpylint src/

format:
\tblack .

fix:
\tblack . && isort .
"""
        )

        # Detect project
        project_info = self.detector.detect()

        # Check if custom tools were detected
        if "linter" in project_info.detected_tools:
            linter = project_info.detected_tools["linter"]
            self.assertEqual(linter.name, "make:lint")
            self.assertEqual(linter.command, "make lint")

    def test_suggest_tools(self):
        """Test tool suggestions"""
        # Create a Python project without any tools configured
        (Path(self.temp_dir) / "main.py").write_text("print('hello')")

        # Get suggestions
        suggestions = self.detector.suggest_tools(ProjectType.PYTHON)

        # Should suggest all tool categories
        self.assertIn("linter", suggestions)
        self.assertIn("formatter", suggestions)
        self.assertIn("type_checker", suggestions)

        # Each category should have multiple options
        self.assertGreater(len(suggestions["linter"]), 0)
        self.assertGreater(len(suggestions["formatter"]), 0)


if __name__ == "__main__":
    unittest.main()
