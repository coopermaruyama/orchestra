"""
Orchestra Common Library

Shared functionality for Orchestra extensions including git task management,
subagent integration, and base extension classes.
"""

from .base_extension import BaseExtension, GitAwareExtension, HookHandler
from .claude_invoker import ClaudeInvoker, check_predicate, get_invoker, invoke_claude
from .core_command import CoreCommand
from .git_task_manager import GitTaskManager
from .subagent_runner import SubagentRunner
from .task_state import GitTaskState, TaskRequirement
from .log_utils import setup_logger, truncate_value, format_hook_context, LogContext

__all__ = [
    "BaseExtension",
    "ClaudeInvoker",
    "CoreCommand",
    "GitAwareExtension",
    "GitTaskManager",
    "GitTaskState",
    "HookHandler",
    "SubagentRunner",
    "TaskRequirement",
    "check_predicate",
    "get_invoker",
    "invoke_claude",
    "setup_logger",
    "truncate_value",
    "format_hook_context",
    "LogContext"
]
