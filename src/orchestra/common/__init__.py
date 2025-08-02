"""
Orchestra Common Library

Shared functionality for Orchestra extensions including git task management,
subagent integration, and base extension classes.
"""

from .git_task_manager import GitTaskManager
from .task_state import GitTaskState, TaskRequirement
from .subagent_runner import SubagentRunner
from .base_extension import BaseExtension, GitAwareExtension, HookHandler

__all__ = [
    "GitTaskManager",
    "GitTaskState",
    "TaskRequirement",
    "SubagentRunner",
    "BaseExtension",
    "GitAwareExtension",
    "HookHandler"
]