#!/usr/bin/env python3
"""Debug tool to view _build_analysis_context output from current task state"""

import argparse
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from orchestra.common.task_state import TaskRequirement
from orchestra.extensions.task.task_monitor import TaskAlignmentMonitor


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug _build_analysis_context output")
    parser.add_argument(
        "--task-file",
        default=".claude-task.json",
        help="Path to task state file (default: .claude-task.json)",
    )
    parser.add_argument(
        "--create-test",
        action="store_true",
        help="Create a test task state if file doesn't exist",
    )

    args = parser.parse_args()

    monitor = TaskAlignmentMonitor()

    task_file = Path(args.task_file)

    if task_file.exists():
        print(f"Loading task state from: {task_file}")
        # The task monitor loads from config_file automatically
        monitor.config_file = str(task_file)
        config = monitor.load_config()
        if config:
            monitor.task = config.get("task", "")
            monitor.requirements = [
                TaskRequirement(**req) for req in config.get("requirements", [])
            ]
            monitor.stats = config.get("stats", {})
    elif args.create_test:
        print("Creating test task state...")

        monitor.task = "Test task for debugging"
        monitor.requirements = [
            TaskRequirement(
                id="1", description="First requirement", priority=1, completed=True
            ),
            TaskRequirement(
                id="2", description="Second requirement", priority=2, completed=False
            ),
            TaskRequirement(
                id="3", description="Third requirement", priority=3, completed=False
            ),
        ]
        monitor.stats = {"commands": 10, "deviations": 1}
        monitor.config_file = str(task_file)
        monitor.save_config()
        print(f"Test state saved to: {task_file}")
    else:
        print(f"Error: Task file not found: {task_file}")
        print("Use --create-test to create a test task state")
        sys.exit(1)

    # Build and display the analysis context
    print("\n" + "=" * 60)
    print("ANALYSIS CONTEXT OUTPUT:")
    print("=" * 60 + "\n")

    context = monitor._build_analysis_context()
    print(context)

    print("\n" + "=" * 60)
    print(f"Context length: {len(context)} characters")

    # Optionally save to file
    output_file = task_file.with_suffix(".context.txt")
    with output_file.open("w") as f:
        f.write(context)
    print(f"Context saved to: {output_file}")


if __name__ == "__main__":
    sys.exit(main() or 0)
