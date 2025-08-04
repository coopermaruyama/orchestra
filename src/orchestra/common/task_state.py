"""
Shared task state models for Orchestra extensions
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class GitTaskState:
    """Git-aware task state that tracks branches and commits"""

    task_id: str
    task_description: str
    base_sha: str
    current_sha: str
    branch_name: str
    base_branch: str = "main"
    created_at: datetime = field(default_factory=datetime.now)
    subagent_branches: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "base_sha": self.base_sha,
            "current_sha": self.current_sha,
            "branch_name": self.branch_name,
            "base_branch": self.base_branch,
            "created_at": self.created_at.isoformat(),
            "subagent_branches": self.subagent_branches,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GitTaskState":
        """Create from dictionary (JSON deserialization)"""
        # Handle datetime parsing
        created_at = datetime.fromisoformat(data["created_at"])

        return cls(
            task_id=data["task_id"],
            task_description=data["task_description"],
            base_sha=data["base_sha"],
            current_sha=data["current_sha"],
            branch_name=data["branch_name"],
            base_branch=data.get("base_branch", "main"),
            created_at=created_at,
            subagent_branches=data.get("subagent_branches", {}),
            metadata=data.get("metadata", {}),
        )

    def save_to_file(self, file_path: str) -> None:
        """Save task state to JSON file"""
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: str) -> "GitTaskState":
        """Load task state from JSON file"""
        with open(file_path) as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class TaskRequirement:
    """Individual task requirement - kept for backward compatibility"""

    id: str
    description: str
    priority: int  # 1-5, where 1 is highest
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRequirement":
        return cls(
            id=data["id"],
            description=data["description"],
            priority=data["priority"],
            completed=data.get("completed", False),
        )
