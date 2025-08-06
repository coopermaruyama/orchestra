#!/usr/bin/env python3
"""
TimeMachine Monitor for Claude Code
Automatic git checkpointing for conversation history and rollback
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import from common library
from orchestra.common import (
    GitAwareExtension,
    HookHandler,
    format_hook_context,
    setup_logger,
    truncate_value,
)


class CheckpointInfo:
    """Information about a TimeMachine checkpoint"""

    def __init__(self, commit_sha: str, metadata: Dict[str, Any]):
        self.commit_sha = commit_sha
        self.metadata = metadata
        self.timestamp = metadata.get("timestamp", "")
        self.user_prompt = metadata.get("user_prompt", "")
        self.task_id = metadata.get("task_id", "")
        self.transcript_id = metadata.get("transcript_id", "")
        self.tools_used = metadata.get("tools_used", [])
        self.files_modified = metadata.get("files_modified", [])


class TimeMachineMonitor(GitAwareExtension):
    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use CLAUDE_WORKING_DIR if available, otherwise use common project directory logic
        working_dir = os.environ.get("CLAUDE_WORKING_DIR")
        if not working_dir:
            working_dir = self._get_project_directory()

        log_dir = os.path.join(working_dir, ".claude", "logs")

        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "timemachine.log")

        # Configure logger with truncation
        self.logger = setup_logger(
            "timemachine", log_file, logging.DEBUG, truncate=True, max_length=300
        )
        self.logger.info("TimeMachineMonitor initialized")

        # Initialize base class
        base_working_dir = working_dir or "."
        super().__init__(
            config_file=config_path,  # Let base class handle the default path
            working_dir=base_working_dir,
        )

        # TimeMachine specific state
        self.enabled: bool = True
        # Typed checkpoint counters - migrated from single checkpoint_counter
        self.prompt_counter: int = 0  # For regular prompt checkpoints
        self.plan_counter: int = 0    # For plan-related checkpoints
        self.todo_counter: int = 0    # For todo change checkpoints
        self.settings: Dict[str, Any] = {}

        self.load_config()

        # Check if git-wip is available on initialization
        self._check_git_wip_availability()

    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""
        return "timemachine.json"

    def _check_git_wip_availability(self) -> None:
        """Check if git-wip is available and log a warning if not"""
        try:
            git_wip_path = self.git_manager._get_git_wip_path()
            self.logger.debug(f"git-wip found at: {git_wip_path}")
        except FileNotFoundError as e:
            self.logger.error(
                "git-wip not found. TimeMachine requires git-wip for creating checkpoints."
            )
            self.logger.error(str(e))
            self.logger.info(
                "Please ensure Orchestra is properly installed with all dependencies."
            )
        except Exception as e:
            self.logger.error(f"Error checking git-wip availability: {e}")

    def load_config(self) -> Dict[str, Any]:
        """Load state and settings"""
        # Load state from the state file (dot-prefixed)
        state = super().load_config()

        # Load settings from shared settings.json
        self.settings = self.get_extension_settings("timemachine")
        if not self.settings:
            # Default settings if not found in settings.json
            self.settings = {
                "enabled": True,
                "max_checkpoints": 100,
                "auto_cleanup": True,
                "include_untracked": False
            }

        # Load state data
        self.enabled = state.get("enabled", self.settings.get("enabled", True))

        # Load typed counters (no migration - start fresh)
        self.prompt_counter = state.get("prompt_counter", 0)
        self.plan_counter = state.get("plan_counter", 0)
        self.todo_counter = state.get("todo_counter", 0)

        return state

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save state (not settings - those go in settings.json)"""
        if config is None:
            config = {
                "enabled": self.enabled,
                "prompt_counter": self.prompt_counter,
                "plan_counter": self.plan_counter,
                "todo_counter": self.todo_counter,
                "updated": datetime.now().isoformat(),
            }

        super().save_config(config)

    def handle_hook(self, hook_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Universal hook handler"""
        self.logger.info(f"Handling hook: {hook_type}")
        self.logger.debug(f"Hook context: {format_hook_context(context)}")

        if not self.enabled:
            return HookHandler.create_allow_response()

        if hook_type == "PreToolUse":
            return self._handle_pre_tool_use_hook(context)
        if hook_type == "PostToolUse":
            return self._handle_post_tool_use_hook(context)
        if hook_type == "Stop":
            return self._handle_stop_hook(context)
        if hook_type == "UserPromptSubmit":
            return self._handle_user_prompt_submit_hook(context)

        return HookHandler.create_allow_response()

    def _handle_user_prompt_submit_hook(
        self, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture the user prompt for the checkpoint"""
        prompt = context.get("prompt", "")
        session_id = context.get("session_id", "")

        # Store prompt and reset tracking in persistent state
        self.set_session_state(
            context,
            {
                "current_prompt": prompt,
                "session_id": session_id,
                "tools_used_this_turn": [],
                "files_modified_this_turn": [],
            },
        )

        self.logger.debug(f"Captured user prompt: {truncate_value(prompt, 100)}")

        return HookHandler.create_allow_response()

    def _handle_pre_tool_use_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Track tools being used"""
        tool_name = context.get("tool_name", "")
        if tool_name:
            # Get current state and update tools list
            state = self.get_session_state(context)
            tools_used = state.get("tools_used_this_turn", [])

            if tool_name not in tools_used:
                tools_used.append(tool_name)
                self.update_session_state(context, {"tools_used_this_turn": tools_used})

        return HookHandler.create_allow_response()

    def _handle_post_tool_use_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Track file modifications and TodoWrite changes"""
        tool_name = context.get("tool_name", "")
        tool_input = context.get("tool_input", {})

        # Track file modifications
        if tool_name in ["Write", "Edit", "MultiEdit", "NotebookEdit"]:
            file_path = tool_input.get("file_path", "")
            if file_path:
                # Get current state and update files list
                state = self.get_session_state(context)
                files_modified = state.get("files_modified_this_turn", [])

                if file_path not in files_modified:
                    files_modified.append(file_path)
                    self.update_session_state(
                        context, {"files_modified_this_turn": files_modified}
                    )

        # Track TodoWrite changes
        elif tool_name == "TodoWrite":
            self.logger.info("TodoWrite detected - marking todos as changed")
            self.update_session_state(context, {"todos_changed": True})

        return HookHandler.create_allow_response()

    def _handle_stop_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create checkpoint when conversation turn completes"""
        # Get state from persistent storage
        state = self.get_session_state(context)
        current_prompt = state.get("current_prompt", "")

        if not current_prompt:
            self.logger.debug("No prompt captured, skipping checkpoint")
            return HookHandler.create_allow_response()

        # Don't create checkpoint if we're in a stop hook loop
        if HookHandler.is_stop_hook_active(context):
            self.logger.debug("Stop hook already active, avoiding recursion")
            return HookHandler.create_allow_response()

        try:
            # Determine checkpoint type based on session state
            checkpoint_type = self._determine_checkpoint_type(context)

            # Create the typed checkpoint
            checkpoint_id = self._create_typed_checkpoint(context, checkpoint_type)
            if checkpoint_id:
                self.logger.info(
                    f"Created {checkpoint_type} checkpoint: {checkpoint_id} for prompt: {truncate_value(current_prompt, 50)}"
                )

        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")

        # Clear session state for next turn
        self.clear_session_state(context)

        return HookHandler.create_allow_response()

    def _determine_checkpoint_type(self, context: Dict[str, Any]) -> str:
        """Determine the type of checkpoint to create based on session state

        Args:
            context: Hook context

        Returns:
            Checkpoint type: 'plan', 'todo', or 'prompt'
        """
        state = self.get_session_state(context)

        # Check if a plan was just completed (plancheck extension sets this)
        if state.get("plan_active"):
            self.logger.debug("Plan completion detected - creating plan checkpoint")
            return "plan"

        # Check if todos were changed during this turn
        elif state.get("todos_changed"):
            self.logger.debug("Todo changes detected - creating todo checkpoint")
            return "todo"

        # Default to prompt checkpoint
        else:
            self.logger.debug("Regular prompt completion - creating prompt checkpoint")
            return "prompt"

    def _create_typed_checkpoint(self, context: Dict[str, Any], checkpoint_type: str) -> Optional[str]:
        """Create a git checkpoint with typed prefix and metadata

        Args:
            context: Hook context
            checkpoint_type: Type of checkpoint ('plan', 'todo', 'prompt')

        Returns:
            Checkpoint ID if successful, None otherwise
        """
        # Get appropriate counter and increment it
        if checkpoint_type == "plan":
            counter = self.plan_counter
            self.plan_counter += 1
        elif checkpoint_type == "todo":
            counter = self.todo_counter
            self.todo_counter += 1
        else:  # prompt
            counter = self.prompt_counter
            self.prompt_counter += 1

        # Create checkpoint ID with typed prefix
        checkpoint_id = f"{checkpoint_type}-{counter}"

        # Use the existing checkpoint creation logic but with typed ID
        result = self._create_checkpoint_with_id(context, checkpoint_id, checkpoint_type)

        if result:
            # Save updated counters
            self.save_config()

        return result

    def _create_checkpoint_with_id(self, context: Dict[str, Any], checkpoint_id: str, checkpoint_type: str) -> Optional[str]:
        """Create a git checkpoint with specific ID and type (refactored from _create_checkpoint)"""
        if not self.git_manager._is_git_repo():
            self.logger.warning("Not in a git repository, cannot create checkpoint")
            return None

        # Get state from persistent storage
        state = self.get_session_state(context)
        current_prompt = state.get("current_prompt", "")
        session_id = state.get("session_id", "")
        tools_used = state.get("tools_used_this_turn", [])
        files_modified = state.get("files_modified_this_turn", [])

        # Extract transcript ID from path
        transcript_path = context.get("transcript_path", "")
        transcript_id = Path(transcript_path).stem if transcript_path else ""

        # Get current task info if available
        task_info = self._get_current_task_info()

        # Build metadata with checkpoint type information
        metadata = {
            "user_prompt": current_prompt,
            "checkpoint_type": checkpoint_type,
            "task_id": task_info.get("task_id", ""),
            "task_description": task_info.get("task_description", ""),
            "transcript_id": transcript_id,
            "timestamp": datetime.now().isoformat(),
            "tools_used": tools_used,
            "files_modified": files_modified,
            "session_id": session_id,
        }

        # Create checkpoint-type-specific commit message with relevant content
        if checkpoint_type == "plan":
            # For plan checkpoints, include the plan title and try to get plan content
            plan_title = state.get("plan_title", "Untitled Plan")

            # Try to read the plan content from the most recent plan file
            plan_preview = self._get_recent_plan_content(context)
            if plan_preview:
                commit_message = f"TimeMachine [plan]: {plan_title}\n\nPlan Content Preview:\n{plan_preview}\n\nMetadata:\n{json.dumps(metadata, indent=2)}"
            else:
                commit_message = f"TimeMachine [plan]: {plan_title}\n\n{json.dumps(metadata, indent=2)}"

            # Add plan-specific metadata
            metadata["plan_title"] = plan_title

        elif checkpoint_type == "todo":
            # For todo checkpoints, describe what todos were changed and include todo summary
            todo_summary = self._get_todo_summary_from_prompt(current_prompt)
            if todo_summary:
                commit_message = f"TimeMachine [todo]: {todo_summary}\n\nPrompt: {current_prompt[:100]}...\n\nMetadata:\n{json.dumps(metadata, indent=2)}"
            else:
                commit_message = f"TimeMachine [todo]: Todo list updated\n\nPrompt: {current_prompt[:100]}...\n\nMetadata:\n{json.dumps(metadata, indent=2)}"

        else:  # prompt
            # For prompt checkpoints, include the full user prompt (with reasonable limit)
            prompt_preview = current_prompt[:200] + ("..." if len(current_prompt) > 200 else "")
            commit_message = f"TimeMachine [prompt]: {prompt_preview}\n\nMetadata:\n{json.dumps(metadata, indent=2)}"

        try:
            # Get git-wip path (will raise FileNotFoundError if not found)
            git_wip_path = self.git_manager._get_git_wip_path()

            # Create the checkpoint
            result = self.git_manager._run_git_wip_command(
                [git_wip_path, "save", commit_message, "--untracked"]
            )

            # Get the commit SHA
            commit_sha = self._get_latest_wip_commit()

            if commit_sha:
                # Create git tag for better visibility in git log
                tag_name = f"timemachine/{checkpoint_id}"
                try:
                    self.git_manager._run_git_command([
                        "tag", "-a", tag_name, commit_sha,
                        "-m", f"{checkpoint_type} checkpoint: {current_prompt[:50]}..."
                    ])
                    self.logger.debug(f"Created git tag: {tag_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to create git tag {tag_name}: {e}")

                return checkpoint_id

        except FileNotFoundError as e:
            self.logger.error(f"Cannot create checkpoint: {e}")
            return None
        except subprocess.CalledProcessError as e:
            # Check if it's just "no changes" error
            if e.returncode == 1 and "no changes" in e.stderr:
                self.logger.debug("No changes since last checkpoint")
            else:
                self.logger.error(f"git-wip command failed: {e}")
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")

        return None

    def _create_checkpoint(self, context: Dict[str, Any]) -> Optional[str]:
        """Create a git checkpoint with metadata"""
        if not self.git_manager._is_git_repo():
            self.logger.warning("Not in a git repository, cannot create checkpoint")
            return None

        # Get state from persistent storage
        state = self.get_session_state(context)
        current_prompt = state.get("current_prompt", "")
        session_id = state.get("session_id", "")
        tools_used = state.get("tools_used_this_turn", [])
        files_modified = state.get("files_modified_this_turn", [])

        # Extract transcript ID from path
        transcript_path = context.get("transcript_path", "")
        transcript_id = Path(transcript_path).stem if transcript_path else ""

        # Get current task info if available
        task_info = self._get_current_task_info()

        # Build metadata
        metadata = {
            "user_prompt": current_prompt,
            "task_id": task_info.get("task_id", ""),
            "task_description": task_info.get("task_description", ""),
            "transcript_id": transcript_id,
            "timestamp": datetime.now().isoformat(),
            "tools_used": tools_used,
            "files_modified": files_modified,
            "session_id": session_id,
        }

        # Create commit message with JSON metadata
        commit_message = (
            f"TimeMachine: {current_prompt[:50]}...\n\n{json.dumps(metadata, indent=2)}"
        )

        try:
            # Get git-wip path (will raise FileNotFoundError if not found)
            git_wip_path = self.git_manager._get_git_wip_path()

            # Create the checkpoint
            result = self.git_manager._run_git_wip_command(
                [git_wip_path, "save", commit_message, "--untracked"]
            )

            # Get the commit SHA
            commit_sha = self._get_latest_wip_commit()

            if commit_sha:
                # Create checkpoint ID using counter
                checkpoint_id = f"ckpt-{self.checkpoint_counter}"

                # Create git tag for better visibility in git log
                tag_name = f"timemachine/{checkpoint_id}"
                try:
                    self.git_manager._run_git_command([
                        "tag", "-a", tag_name, commit_sha,
                        "-m", f"TimeMachine checkpoint: {current_prompt[:50]}..."
                    ])
                    self.logger.debug(f"Created git tag: {tag_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to create git tag {tag_name}: {e}")

                # Increment counter for next checkpoint
                self.checkpoint_counter += 1
                self.save_config()

                return checkpoint_id

        except FileNotFoundError as e:
            self.logger.error(f"Cannot create checkpoint: {e}")
            return None
        except subprocess.CalledProcessError as e:
            # Check if it's just "no changes" error
            if e.returncode == 1 and "no changes" in e.stderr:
                self.logger.debug("No changes since last checkpoint")
            else:
                self.logger.error(f"git-wip command failed: {e}")
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")

        return None

    def _get_recent_plan_content(self, context: Dict[str, Any]) -> Optional[str]:
        """Get content preview from the most recently created plan file

        Args:
            context: Hook context

        Returns:
            Plan content preview (first 300 chars) or None if not found
        """
        try:
            plans_dir = Path(self.orchestra_dir) / "plans"
            if not plans_dir.exists():
                return None

            # Find the most recent plan file
            plan_files = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not plan_files:
                return None

            # Read the most recent plan file
            latest_plan = plan_files[0]
            with open(latest_plan, 'r', encoding='utf-8') as f:
                content = f.read()

            # Return first 300 characters as preview, skip the header
            lines = content.split('\n')
            content_lines = []
            skip_header = True

            for line in lines:
                if skip_header and line.startswith('*Created:'):
                    skip_header = False
                    continue
                elif not skip_header and line.strip():
                    content_lines.append(line)

            preview_content = '\n'.join(content_lines)
            return preview_content[:300] + ("..." if len(preview_content) > 300 else "")

        except Exception as e:
            self.logger.debug(f"Could not read plan content: {e}")
            return None

    def _get_todo_summary_from_prompt(self, prompt: str) -> Optional[str]:
        """Extract a summary of todo-related activity from the user prompt

        Args:
            prompt: User prompt text

        Returns:
            Summary of todo activity or None if not clear
        """
        prompt_lower = prompt.lower()

        # Look for common todo-related patterns
        if "todo" in prompt_lower or "task" in prompt_lower:
            # Try to extract a meaningful summary
            if "add" in prompt_lower or "create" in prompt_lower:
                return "Added new todos"
            elif "complete" in prompt_lower or "done" in prompt_lower or "finished" in prompt_lower:
                return "Marked todos as completed"
            elif "update" in prompt_lower or "change" in prompt_lower or "modify" in prompt_lower:
                return "Updated todo list"
            else:
                return "Modified todo list"

        # Look for action words that might indicate todo changes
        action_words = ["implement", "fix", "add", "create", "build", "test", "refactor"]
        for word in action_words:
            if word in prompt_lower:
                return f"Todo activity: {word}"

        return None

    def _get_latest_wip_commit(self) -> Optional[str]:
        """Get the SHA of the latest WIP commit"""
        try:
            # First try refs/wip/HEAD
            result = self.git_manager._run_git_command(
                ["rev-parse", "--verify", "refs/wip/HEAD"]
            )
            return result.stdout.strip()
        except:
            try:
                # Fall back to refs/wip/main (common case)
                result = self.git_manager._run_git_command(
                    ["rev-parse", "--verify", "refs/wip/main"]
                )
                return result.stdout.strip()
            except:
                # Try to find any wip branch
                try:
                    result = self.git_manager._run_git_command(
                        ["for-each-ref", "--format=%(refname)", "refs/wip/"]
                    )
                    refs = result.stdout.strip().split("\n")
                    if refs and refs[0]:
                        # Use the first wip ref found
                        result = self.git_manager._run_git_command(
                            ["rev-parse", "--verify", refs[0]]
                        )
                        return result.stdout.strip()
                except:
                    pass
            return None

    def _get_current_task_info(self) -> Dict[str, Any]:
        """Get current task information from task monitor if available"""
        # Check new location first
        task_config_path = os.path.join(
            self.working_dir, ".claude", "orchestra", "task.json"
        )

        # Fall back to old location for compatibility
        if not os.path.exists(task_config_path):
            task_config_path = os.path.join(self.working_dir, ".claude-task.json")

        if os.path.exists(task_config_path):
            try:
                with open(task_config_path) as f:
                    task_config = json.load(f)
                    return {
                        "task_id": task_config.get("git_task_state", {}).get(
                            "task_id", ""
                        ),
                        "task_description": task_config.get("task", ""),
                    }
            except:
                pass
        return {}


    # CLI Commands
    def list_checkpoints(self) -> None:
        """List all checkpoints"""
        total_checkpoints = self.prompt_counter + self.plan_counter + self.todo_counter

        if total_checkpoints == 0:
            print("No checkpoints found.")
            return

        print("\n🕐 TimeMachine Checkpoints:")
        print("=" * 80)

        # Get all timemachine tags to show details
        try:
            result = self.git_manager._run_git_command([
                "tag", "-l", "--sort=-creatordate",
                "--format=%(refname:short)|%(creatordate:relative)|%(subject)",
                "timemachine/*"
            ])

            if not result.stdout.strip():
                print("No checkpoint tags found.")
                return

            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                if not line:
                    continue

                parts = line.split('|', 2)
                if len(parts) >= 3:
                    tag_name = parts[0]
                    relative_time = parts[1]
                    subject = parts[2]

                    # Extract checkpoint ID from tag name
                    checkpoint_id = tag_name.replace('timemachine/', '')

                    if i == 0:
                        print(f"→ [{checkpoint_id}] {relative_time} - {subject}")
                    else:
                        print(f"  [{checkpoint_id}] {relative_time} - {subject}")

        except Exception as e:
            # Fallback: show typed checkpoint counts if any exist
            if self.prompt_counter > 0:
                print(f"Prompt checkpoints: prompt-0 to prompt-{self.prompt_counter - 1}")
            if self.plan_counter > 0:
                print(f"Plan checkpoints: plan-0 to plan-{self.plan_counter - 1}")
            if self.todo_counter > 0:
                print(f"Todo checkpoints: todo-0 to todo-{self.todo_counter - 1}")
            if total_checkpoints == 0:
                print("No typed checkpoints found.")
            print(f"(Error getting details: {e})")

        print("=" * 80)
        print(f"\nTotal checkpoints: {total_checkpoints}")
        print(f"  Prompt: {self.prompt_counter}, Plan: {self.plan_counter}, Todo: {self.todo_counter}")
        print("\nUse 'orchestra timemachine view <id>' to see full details")
        print("Use 'orchestra timemachine rollback <n>' to go back n turns")

    def checkout_checkpoint(self, checkpoint_id: str) -> None:
        """Checkout a specific checkpoint"""
        tag_name = f"timemachine/{checkpoint_id}"
        self._checkout_by_tag(tag_name, checkpoint_id)

    def view_checkpoint(self, checkpoint_id: str) -> None:
        """View full details of a checkpoint"""
        tag_name = f"timemachine/{checkpoint_id}"

        try:
            # Get commit hash from tag
            result = self.git_manager._run_git_command(["rev-list", "-n", "1", tag_name])
            commit_sha = result.stdout.strip()

            if not commit_sha:
                print(f"❌ Checkpoint not found: {checkpoint_id}")
                return

            # Get commit metadata
            result = self.git_manager._run_git_command(
                ["show", "--no-patch", "--format=%B", commit_sha]
            )

            # Parse metadata from commit message
            lines = result.stdout.strip().split("\n")
            if len(lines) > 2:
                # Skip first line and parse JSON
                json_str = "\n".join(lines[2:])
                metadata = json.loads(json_str)

                print(f"\n📋 Checkpoint Details: {checkpoint_id}")
                print("=" * 80)
                print(f"Timestamp: {metadata.get('timestamp', 'N/A')}")
                print(f"Session ID: {metadata.get('session_id', 'N/A')}")
                print("\nUser Prompt:")
                print("-" * 40)
                print(metadata.get("user_prompt", "No prompt recorded"))
                print("-" * 40)

                if metadata.get("task_description"):
                    print(f"\nTask: {metadata['task_description']}")

                if metadata.get("tools_used"):
                    print(f"\nTools Used: {', '.join(metadata['tools_used'])}")

                if metadata.get("files_modified"):
                    print("\nFiles Modified:")
                    for file in metadata["files_modified"]:
                        print(f"  - {file}")

        except Exception as e:
            print(f"❌ Failed to view checkpoint: {e}")

    def rollback_n_turns(self, n: int) -> None:
        """Rollback n conversation turns"""
        if n <= 0:
            print(f"❌ Cannot rollback {n} turns. Must be positive number.")
            return

        if self.checkpoint_counter == 0:
            print("❌ No checkpoints available to rollback to.")
            return

        # Calculate target checkpoint: current counter - n
        target_checkpoint_num = self.checkpoint_counter - n

        if target_checkpoint_num < 0:
            print(f"❌ Cannot rollback {n} turns. Only {self.checkpoint_counter} checkpoints exist.")
            return

        checkpoint_id = f"ckpt-{target_checkpoint_num}"
        tag_name = f"timemachine/{checkpoint_id}"

        # Direct checkout using git tag
        self._checkout_by_tag(tag_name, checkpoint_id)

    def _checkout_by_tag(self, tag_name: str, checkpoint_id: str) -> None:
        """Checkout a specific checkpoint by git tag"""
        try:
            # Check if working directory is clean
            status_result = self.git_manager._run_git_command(["status", "--porcelain"])
            if status_result.stdout.strip():
                # Working directory is dirty, stash changes
                print("⚠️  Working directory has changes, stashing...")
                # Add untracked files first
                self.git_manager._run_git_command(["add", "."])
                self.git_manager._run_git_command(["stash", "push", "-m", f"Auto-stash before rollback {checkpoint_id}"])
                print("   Changes stashed successfully")

            # Checkout the tag
            self.git_manager._run_git_command(["checkout", tag_name])
            print(f"✅ Rolled back to checkpoint: {checkpoint_id}")

            if status_result.stdout.strip():
                print("   Use 'git stash pop' to restore your stashed changes")

        except Exception as e:
            print(f"❌ Failed to rollback to {checkpoint_id}: {e}")

    def _format_relative_time(self, timestamp: datetime) -> str:
        """Format timestamp as relative time"""
        now = datetime.now()
        if hasattr(timestamp, "tzinfo") and timestamp.tzinfo is None:
            # Add timezone info if missing
            timestamp = timestamp.replace(tzinfo=now.tzinfo)

        delta = now - timestamp

        if delta.total_seconds() < 60:
            return "just now"
        if delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        if delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        days = delta.days
        return f"{days} day{'s' if days > 1 else ''} ago"


    def prune_checkpoints(self, force: bool = False) -> None:
        """Delete all TimeMachine checkpoints and tags"""
        if self.checkpoint_counter == 0:
            print("No checkpoints to prune.")
            return

        print(f"Found {self.checkpoint_counter} checkpoints to delete.")

        if not force:
            response = input("Are you sure you want to delete ALL TimeMachine checkpoints? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("Prune cancelled.")
                return

        deleted_count = 0

        # Delete git tags with timemachine/ prefix
        try:
            # Get all timemachine tags
            result = self.git_manager._run_git_command([
                "tag", "-l", "timemachine/*"
            ])
            tags = [tag.strip() for tag in result.stdout.strip().split('\n') if tag.strip()]

            if tags:
                print(f"Deleting {len(tags)} TimeMachine tags...")
                for tag in tags:
                    try:
                        self.git_manager._run_git_command(["tag", "-d", tag])
                        deleted_count += 1
                    except Exception as e:
                        print(f"⚠️  Failed to delete tag {tag}: {e}")

        except Exception as e:
            print(f"⚠️  Failed to list timemachine tags: {e}")

        # Reset checkpoint counter
        self.checkpoint_counter = 0
        self.save_config()

        print(f"✅ Pruned {deleted_count} TimeMachine tags and reset checkpoint counter.")
        print("Note: The actual git commits in refs/wip/ are preserved.")


def main():
    """CLI entry point for TimeMachine commands"""
    if len(sys.argv) < 2:
        print("Usage: timemachine_monitor.py <command> [args]")
        print("Commands: list, checkout <id>, view <id>, rollback <n>, prune [--force], hook <event>")
        return

    command = sys.argv[1]
    monitor = TimeMachineMonitor()

    if command == "list":
        monitor.list_checkpoints()
    elif command == "checkout" and len(sys.argv) > 2:
        monitor.checkout_checkpoint(sys.argv[2])
    elif command == "view" and len(sys.argv) > 2:
        monitor.view_checkpoint(sys.argv[2])
    elif command == "rollback" and len(sys.argv) > 2:
        try:
            n = int(sys.argv[2])
            monitor.rollback_n_turns(n)
        except ValueError:
            print("❌ Please provide a number for rollback")
    elif command == "prune":
        force = "--force" in sys.argv
        monitor.prune_checkpoints(force)
    elif command == "hook" and len(sys.argv) > 2:
        # Handle hook invocation
        hook_event = sys.argv[2]
        try:
            context = json.load(sys.stdin)
            result = monitor.handle_hook(hook_event, context)
            print(json.dumps(result))
        except Exception as e:
            error_response = {"error": str(e), "continue": True}
            print(json.dumps(error_response))
            sys.exit(1)
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
