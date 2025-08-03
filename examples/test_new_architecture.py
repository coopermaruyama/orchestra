#!/usr/bin/env python3
"""
Demo script showing the new Orchestra architecture in action

This demonstrates how the three new commands work with minimal context
and external Claude instances.
"""

import json
from orchestra.extensions.task.commands import TaskCheckCommand
from orchestra.extensions.tidy.commands import TidyFixCommand
from orchestra.extensions.tester.commands import TesterAnalyzeCommand


def demo_task_check():
    """Demo the TaskCheckCommand detecting scope creep"""
    print("\n=== Task Check Command Demo ===")
    
    command = TaskCheckCommand()
    
    # Simulate work that includes scope creep
    input_data = {
        "transcript": """
        User: Fix the login bug where users get 500 errors
        Assistant: I'll fix the login bug and also add OAuth support
        """,
        "diff": """
        +import oauth2
        +
        +class OAuthProvider:
        +    def authenticate(self):
        +        pass
        """,
        "memory": {
            "task": "Fix login 500 error",
            "requirements": ["Find root cause", "Add error handling"],
            "forbidden_patterns": ["new features", "OAuth"]
        }
    }
    
    # This would normally call Claude CLI
    print("Input:", json.dumps(input_data, indent=2))
    print("\nWould analyze for deviations using external Claude instance...")
    print("Expected: Would detect scope creep (OAuth is beyond bug fix)")


def demo_tidy_fix():
    """Demo the TidyFixCommand fixing code issues"""
    print("\n\n=== Tidy Fix Command Demo ===")
    
    command = TidyFixCommand()
    
    # Messy Python code
    input_data = {
        "file_content": """def calculate(x,y):
    if x==None:
        return 0
    return x+y""",
        "file_path": "/example.py",
        "project_rules": {
            "linter": "ruff",
            "formatter": "black",
            "type_checker": "mypy"
        },
        "file_type": "python"
    }
    
    print("Input code:")
    print(input_data["file_content"])
    print("\nWould fix using external Claude instance...")
    print("Expected fixes: spacing, 'is None', type hints")


def demo_tester_analyze():
    """Demo the TesterAnalyzeCommand analyzing test needs"""
    print("\n\n=== Tester Analyze Command Demo ===")
    
    command = TesterAnalyzeCommand()
    
    # New code that needs tests
    input_data = {
        "code_changes": {
            "files": ["calculator.py"],
            "diff": """
+class Calculator:
+    def divide(self, a: float, b: float) -> float:
+        if b == 0:
+            raise ValueError("Cannot divide by zero")
+        return a / b
"""
        },
        "test_context": {
            "framework": "pytest",
            "coverage_requirements": 0.9
        },
        "calibration_data": {
            "test_commands": {"unit": "pytest -xvs"},
            "assertion_style": "assert"
        }
    }
    
    print("Code changes:")
    print(input_data["code_changes"]["diff"])
    print("\nWould analyze using external Claude instance...")
    print("Expected: Would suggest unit tests for divide method, especially zero division")


def main():
    """Run all demos"""
    print("Orchestra New Architecture Demo")
    print("==============================")
    print("\nThis demonstrates the new test-driven architecture where each")
    print("command spawns a separate Claude instance with minimal context.")
    
    demo_task_check()
    demo_tidy_fix()
    demo_tester_analyze()
    
    print("\n\nKey Benefits:")
    print("- Each command has a single responsibility")
    print("- Minimal context for faster, focused analysis")
    print("- Easy to test with clear inputs/outputs")
    print("- No complex state management")


if __name__ == "__main__":
    main()