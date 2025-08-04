"""
Base Extension Classes for Orchestra

Provides common functionality for Orchestra extensions including
git integration, hook handling, and subagent management.
"""

import json
import os
import sys
import tempfile
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestra.common.types import HookInput

from .claude_invoker import check_predicate, invoke_claude
from .git_task_manager import GitTaskManager
from .subagent_runner import SubagentRunner
from .task_state import GitTaskState


class SessionStateManager:
    """Manages cross-hook state persistence for Orchestra extensions.

    Since each hook invocation runs as a separate process, this class
    provides a mechanism to persist state between hook calls using
    temporary files.
    """

    def __init__(self, extension_name: str):
        """Initialize state manager for an extension.

        Args:
            extension_name: Name of the extension (used for namespacing)
        """
        self.extension_name = extension_name
        self._lock = threading.Lock()

        # Get temp directory from environment or use system default
        temp_base = os.environ.get("TMPDIR", tempfile.gettempdir())
        self.state_dir = Path(temp_base) / "orchestra_state"
        self.state_dir.mkdir(exist_ok=True)

        # Clean up old state files on initialization
        self._cleanup_old_states()

    def _get_state_path(self, session_id: str, transcript_id: str) -> Path:
        """Get the path for a state file.

        Args:
            session_id: Claude session ID
            transcript_id: Transcript ID for the conversation

        Returns:
            Path to the state file
        """
        # Create a unique filename for this session/transcript/extension combo
        filename = f"{session_id}_{transcript_id}_{self.extension_name}.json"
        return self.state_dir / filename

    def get_state(self, session_id: str, transcript_id: str) -> Dict[str, Any]:
        """Get state for a session/transcript.

        Args:
            session_id: Claude session ID
            transcript_id: Transcript ID for the conversation

        Returns:
            State dictionary (empty dict if no state exists)
        """
        state_path = self._get_state_path(session_id, transcript_id)

        with self._lock:
            if state_path.exists():
                try:
                    with state_path.open() as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError):
                    # Return empty dict if file is corrupted or can't be read
                    return {}
            return {}

    def set_state(
        self, session_id: str, transcript_id: str, state: Dict[str, Any]
    ) -> None:
        """Set state for a session/transcript.
        e
                Args:
                    session_id: Claude session ID
                    transcript_id: Transcript ID for the conversation
                    state: State dictionary to persist
        """
        state_path = self._get_state_path(session_id, transcript_id)

        with self._lock:
            try:
                # Add timestamp for cleanup purposes
                state["_last_updated"] = datetime.now().isoformat()

                # Write atomically by using a temp file
                temp_path = state_path.with_suffix(".tmp")
                with temp_path.open("w") as f:
                    json.dump(state, f, indent=2)

                # Atomic rename
                temp_path.replace(state_path)
            except OSError as e:
                # Log error but don't crash - state persistence is best-effort
                print(f"Warning: Failed to persist state: {e}")

    def update_state(
        self, session_id: str, transcript_id: str, updates: Dict[str, Any]
    ) -> None:
        """Update specific fields in the state.

        Args:
            session_id: Claude session ID
            transcript_id: Transcript ID for the conversation
            updates: Dictionary of updates to apply
        """
        current_state = self.get_state(session_id, transcript_id)
        current_state.update(updates)
        self.set_state(session_id, transcript_id, current_state)

    def clear_state(self, session_id: str, transcript_id: str) -> None:
        """Clear state for a session/transcript.

        Args:
            session_id: Claude session ID
            transcript_id: Transcript ID for the conversation
        """
        state_path = self._get_state_path(session_id, transcript_id)

        with self._lock:
            try:
                if state_path.exists():
                    state_path.unlink()
            except OSError:
                # Ignore errors when cleaning up
                pass

    def _cleanup_old_states(self, max_age_hours: int = 24) -> None:
        """Clean up state files older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        try:
            for state_file in self.state_dir.glob(f"*_{self.extension_name}.json"):
                try:
                    # Check file modification time
                    mtime = datetime.fromtimestamp(state_file.stat().st_mtime)
                    if mtime < cutoff_time:
                        state_file.unlink()
                except OSError:
                    # Skip files we can't process
                    continue
        except OSError:
            # If we can't read the directory, skip cleanup
            pass


class BaseExtension(ABC):
    """Base class for all Orchestra extensions"""

    def __init__(
        self, config_file: Optional[str] = None, working_dir: Optional[str] = None
    ):
        """Initialize base extension

        Args:
            config_file: Path to configuration file
            working_dir: Working directory for the extension
        """
        self.working_dir = working_dir or os.getcwd()

        # If no config file specified, use the new orchestra directory structure
        if config_file is None:
            orchestra_dir = os.path.join(self.working_dir, ".claude", "orchestra")
            os.makedirs(orchestra_dir, exist_ok=True)
            config_file = os.path.join(
                orchestra_dir, self.get_default_config_filename()
            )

        self.config_file = config_file
        self.last_prompt_id = -1
        self.response_by_id: Dict[int, Dict[str, Any]] = {}

        # Initialize session state manager
        # Use the config filename (without .json) as the extension name
        extension_name = Path(self.get_default_config_filename()).stem
        self._state_manager = SessionStateManager(extension_name)

    @abstractmethod
    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""

    @abstractmethod
    def handle_hook(self, hook_event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a Claude Code hook event

        Args:
            hook_event: The hook event name (e.g., 'Stop', 'PreToolUse')
            context: Hook context data

        Returns:
            Hook response data
        """

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Failed to load config from {self.config_file}: {e}")
        return {}

    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            print(f"Error: Failed to save config to {self.config_file}: {e}")

    def is_claude_code_environment(self) -> bool:
        """Check if running inside Claude Code"""
        return os.environ.get("CLAUDECODE") == "1"

    def get_session_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get session state for the current hook context.

        Args:
            context: Hook context containing session_id and transcript_path

        Returns:
            Session state dictionary
        """
        session_id = context.get("session_id", "")
        transcript_path = context.get("transcript_path", "")

        if not session_id or not transcript_path:
            return {}

        # Extract transcript ID from path
        transcript_id = Path(transcript_path).stem

        return self._state_manager.get_state(session_id, transcript_id)

    def set_session_state(self, context: Dict[str, Any], state: Dict[str, Any]) -> None:
        """Set session state for the current hook context.

        Args:
            context: Hook context containing session_id and transcript_path
            state: State dictionary to persist
        """
        session_id = context.get("session_id", "")
        transcript_path = context.get("transcript_path", "")

        if not session_id or not transcript_path:
            return

        # Extract transcript ID from path
        transcript_id = Path(transcript_path).stem

        self._state_manager.set_state(session_id, transcript_id, state)

    def update_session_state(
        self, context: Dict[str, Any], updates: Dict[str, Any]
    ) -> None:
        """Update specific fields in session state.

        Args:
            context: Hook context containing session_id and transcript_path
            updates: Dictionary of updates to apply
        """
        session_id = context.get("session_id", "")
        transcript_path = context.get("transcript_path", "")

        if not session_id or not transcript_path:
            return

        # Extract transcript ID from path
        transcript_id = Path(transcript_path).stem

        self._state_manager.update_state(session_id, transcript_id, updates)

    def clear_session_state(self, context: Dict[str, Any]) -> None:
        """Clear session state for the current hook context.

        Args:
            context: Hook context containing session_id and transcript_path
        """
        session_id = context.get("session_id", "")
        transcript_path = context.get("transcript_path", "")

        if not session_id or not transcript_path:
            return

        # Extract transcript ID from path
        transcript_id = Path(transcript_path).stem

        self._state_manager.clear_state(session_id, transcript_id)


class GitAwareExtension(BaseExtension):
    """Base class for git-aware Orchestra extensions"""

    def __init__(
        self, config_file: Optional[str] = None, working_dir: Optional[str] = None
    ):
        """Initialize git-aware extension

        Args:
            config_file: Path to configuration file
            working_dir: Working directory for the extension
        """
        super().__init__(config_file, working_dir)

        # Initialize git components
        self.git_manager = GitTaskManager(self.working_dir)
        self.subagent_runner = SubagentRunner(self.git_manager)

        # Current task state
        self._current_task_state: Optional[GitTaskState] = None

    @property
    def current_task_state(self) -> Optional[GitTaskState]:
        """Get current task state"""
        return self._current_task_state

    def create_task_snapshot(
        self, task_id: Optional[str] = None, task_description: str = ""
    ) -> GitTaskState:
        """Create a non-invasive task snapshot and set as current task

        Args:
            task_id: Unique task identifier
            task_description: Human-readable task description

        Returns:
            Created GitTaskState
        """
        task_state = self.git_manager.create_task_snapshot(
            task_id=task_id, task_description=task_description
        )

        self._current_task_state = task_state
        return task_state

    def load_task_state_from_config(self) -> Optional[GitTaskState]:
        """Load task state from configuration file

        Returns:
            GitTaskState if found in config, None otherwise
        """
        config = self.load_config()
        if not config:
            return None

        task_data = config.get("git_task_state")

        if task_data:
            try:
                task_state = GitTaskState.from_dict(task_data)
                self._current_task_state = task_state
                return task_state
            except Exception as e:
                print(f"Warning: Failed to load task state from config: {e}")

        return None

    def save_task_state_to_config(self, task_state: GitTaskState) -> None:
        """Save task state to configuration file

        Args:
            task_state: Task state to save
        """
        config = self.load_config()
        config["git_task_state"] = task_state.to_dict()
        self.save_config(config)

        # Update current task state
        self._current_task_state = task_state

    def get_task_diff(self, target_sha: Optional[str] = None) -> str:
        """Get git diff for current task

        Args:
            target_sha: Target SHA to diff to (defaults to HEAD)

        Returns:
            Git diff output
        """
        if not self._current_task_state:
            return ""

        return self.git_manager.get_task_diff(self._current_task_state, target_sha)

    def get_task_file_changes(self, target_sha: Optional[str] = None) -> List[str]:
        """Get list of files changed in current task

        Args:
            target_sha: Target SHA to diff to (defaults to HEAD)

        Returns:
            List of changed file paths
        """
        if not self._current_task_state:
            return []

        return self.git_manager.get_task_file_changes(
            self._current_task_state, target_sha
        )

    def invoke_subagent(
        self, subagent_type: str, analysis_context: str, create_branch: bool = True
    ) -> Dict[str, Any]:
        """Invoke a subagent with current task context

        Args:
            subagent_type: Type of subagent to invoke
            analysis_context: Context for subagent analysis
            create_branch: Whether to create dedicated branch for subagent

        Returns:
            Subagent response
        """
        if not self._current_task_state:
            return {
                "error": "No current task state. Create a task branch first.",
                "suggestion": "Call create_task_branch() to initialize task tracking",
            }

        return self.subagent_runner.invoke_subagent(
            subagent_type=subagent_type,
            task_state=self._current_task_state,
            analysis_context=analysis_context,
            create_branch=create_branch,
        )

    def invoke_multiple_subagents(
        self, subagent_types: List[str], analysis_context: str
    ) -> Dict[str, Any]:
        """Invoke multiple subagents with current task context

        Args:
            subagent_types: List of subagent types to invoke
            analysis_context: Context for analysis

        Returns:
            Combined subagent responses
        """
        if not self._current_task_state:
            return {
                "error": "No current task state. Create a task branch first.",
                "suggestion": "Call create_task_branch() to initialize task tracking",
            }

        return self.subagent_runner.invoke_multiple_subagents(
            subagent_types=subagent_types,
            task_state=self._current_task_state,
            analysis_context=analysis_context,
        )

    def should_invoke_subagent(
        self, subagent_type: str, analysis_context: str, include_diff: bool = True
    ) -> Dict[str, Any]:
        """Check if a subagent should be invoked using predicate system

        Args:
            subagent_type: Type of subagent to check
            analysis_context: Context for analysis
            include_diff: Whether to include git diff in check

        Returns:
            Dict with 'should_invoke' (bool), 'reasoning', and metadata
        """
        if not self._current_task_state:
            return {
                "should_invoke": False,
                "reasoning": "No current task state available",
                "error": True,
            }

        return self.subagent_runner.should_invoke_subagent(
            subagent_type=subagent_type,
            task_state=self._current_task_state,
            analysis_context=analysis_context,
            include_diff=include_diff,
        )

    def check_all_subagents(
        self, analysis_context: str, include_diff: bool = True
    ) -> Dict[str, Any]:
        """Check all subagents to see which ones should be invoked

        Args:
            analysis_context: Context for analysis
            include_diff: Whether to include git diff

        Returns:
            Dict with recommendations for each subagent
        """
        if not self._current_task_state:
            return {
                "error": "No current task state available",
                "has_recommendations": False,
            }

        return self.subagent_runner.check_all_subagents(
            task_state=self._current_task_state,
            analysis_context=analysis_context,
            include_diff=include_diff,
        )

    def check_predicate(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        include_git_diff: bool = False,
    ) -> Dict[str, Any]:
        """Check a yes/no predicate using Claude

        Args:
            question: Yes/no question to ask
            context: Additional context
            include_git_diff: Whether to include git diff

        Returns:
            Dict with 'answer' (bool), 'confidence', 'reasoning'
        """
        # Add task context if available
        if self._current_task_state and context is None:
            context = {}

        if self._current_task_state:
            context = context or {}
            context["task_description"] = self._current_task_state.task_description
            context["task_branch"] = self._current_task_state.branch_name

        return check_predicate(
            question=question, context=context, include_git_diff=include_git_diff
        )

    def invoke_claude(
        self,
        prompt: str,
        model: Optional[str] = None,
        include_task_context: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """Invoke Claude with optional task context

        Args:
            prompt: Prompt for Claude
            model: Model to use (or alias)
            include_task_context: Whether to include current task context
            **kwargs: Additional arguments for invoke_claude

        Returns:
            Claude response
        """
        # Build context if requested
        context = kwargs.get("context", {})

        if include_task_context and self._current_task_state:
            context["task_description"] = self._current_task_state.task_description
            context["task_branch"] = self._current_task_state.branch_name
            context["changed_files"] = self.get_task_file_changes()

        kwargs["context"] = context if context else None

        return invoke_claude(prompt=prompt, model=model, **kwargs)

    def update_task_state(self) -> Optional[GitTaskState]:
        """Update current task state with latest git information

        Returns:
            Updated task state, or None if no current task
        """
        if not self._current_task_state:
            return None

        updated_state = self.git_manager.update_task_state(self._current_task_state)
        self._current_task_state = updated_state
        return updated_state

    def cleanup_task_branch(
        self, merge_back: bool = False, delete_branch: bool = True
    ) -> None:
        """Clean up current task branch

        Args:
            merge_back: Whether to merge changes back to base branch
            delete_branch: Whether to delete the task branch
        """
        if not self._current_task_state:
            print("Warning: No current task state to clean up")
            return

        self.git_manager.cleanup_task_branch(
            task_state=self._current_task_state,
            merge_back=merge_back,
            delete_branch=delete_branch,
        )

        # Clear current task state
        self._current_task_state = None

    def validate_git_environment(self) -> Dict[str, Any]:
        """Validate git environment for the extension

        Returns:
            Validation results
        """
        git_status = self.git_manager.get_git_status()
        subagent_validation = self.subagent_runner.validate_subagent_environment()

        return {
            "git_status": git_status,
            "subagent_environment": subagent_validation,
            "current_task": (
                self._current_task_state.to_dict() if self._current_task_state else None
            ),
            "config_file": self.config_file,
            "working_directory": self.working_dir,
        }

    def get_available_subagents(self) -> Dict[str, str]:
        """Get available subagent types and descriptions"""
        return self.subagent_runner.get_available_subagents()


class HookHandler:
    """Utility class for handling Claude Code hook input/output"""

    @staticmethod
    def read_hook_input() -> Dict[str, Any]:
        """Read hook input from stdin

        Returns:
            Parsed hook input data
        """
        try:
            input_data = sys.stdin.read()
            return json.loads(input_data)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON input: {e}", "raw_input": input_data}

    @staticmethod
    def write_hook_output(output: Dict[str, Any]) -> None:
        """Write hook output to stdout

        Args:
            output: Hook output data to write
        """
        print(json.dumps(output))

    @staticmethod
    def create_block_response(reason: str) -> Dict[str, Any]:
        """Create a hook response that blocks the operation

        Args:
            reason: Reason for blocking

        Returns:
            Block response dictionary
        """
        return {"decision": "block", "reason": reason}

    @staticmethod
    def create_allow_response() -> Dict[str, Any]:
        """Create a hook response that allows the operation

        Returns:
            Allow response dictionary
        """
        return {"decision": "approve"}

    @staticmethod
    def is_stop_hook_active(context: HookInput) -> bool:
        """Check if a stop hook is already active (for recursion prevention)

        Args:
            context: Hook context data

        Returns:
            True if stop hook is already active
        """
        return context.get("stop_hook_active", False)
