from dataclasses import dataclass
from typing import TypedDict, Union


@dataclass
class Todo(TypedDict):
    """Data structure for tool input in a todo context"""

    content: str
    status: str
    priority: str
    id: str
    hook_event_name: str


@dataclass
class TodoInput(TypedDict):
    """Data structure for tool input in a todo context"""

    todos: list[Todo]


ToolInput = Union[TodoInput]

# 2025-08-02 05:49:23,914 - task_monitor - INFO - handle_hook:108 - Handling hook: PostToolUse
# 2025-08-02 05:49:23,914 - task_monitor - DEBUG - handle_hook:109 - Hook context: {
#   "session_id": "05e96406-4f76-4790-9058-d9032e834f3b",
#   "transcript_path": "/Users/coopermaruyama/.claude/projects/-Users-coopermaruyama-Developer-orchestra/05e96406-4f76-4790-9058-d9032e834f3b.jsonl",
#   "cwd": "/Users/coopermaruyama/Developer/orchestra",
#   "hook_event_name": "PostToolUse",
#   "tool_name": "TodoWrite",
#   "tool_input": {
#     "todos": [
#       {
#         "content": "Research current Orchestra architecture and extension structure",
#         "status": "in_progress",
#         "priority": "high",
#         "id": "research-architecture"
#       },
#       {
#         "content": "Design the tidy extension structure and state management",
#         "status": "pending",
#         "priority": "high",


class HookInput(TypedDict):
    """Base class for hook input data"""

    session_id: str
    transcript_path: str
    cwd: str
    hook_event_name: str
    tool_name: str
    stop_hook_active: bool
    tool_input: ToolInput
