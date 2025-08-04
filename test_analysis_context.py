#!/usr/bin/env python3
"""Test script to get _build_analysis_context output"""

import sys
import json
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from orchestra.extensions.task.task_monitor import TaskAlignmentMonitor
from orchestra.common.task_state import TaskRequirement

# Create a TaskAlignmentMonitor instance with test data
monitor = TaskAlignmentMonitor()

# Set up some test task data
monitor.task = "Implement user authentication system"
monitor.requirements = [
    TaskRequirement(
        id="1",
        description="Create login endpoint",
        priority=1,
        completed=True
    ),
    TaskRequirement(
        id="2", 
        description="Add JWT token generation",
        priority=1,
        completed=True
    ),
    TaskRequirement(
        id="3",
        description="Implement password hashing",
        priority=2,
        completed=False
    ),
    TaskRequirement(
        id="4",
        description="Add rate limiting",
        priority=3,
        completed=False
    )
]

# Set some test statistics
monitor.stats = {
    'commands': 15,
    'deviations': 2
}

# Build and print the analysis context
context = monitor._build_analysis_context()
print(context)
print("\n" + "="*60 + "\n")
print("Raw context length:", len(context))