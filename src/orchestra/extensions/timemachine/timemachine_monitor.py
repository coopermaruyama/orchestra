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
from typing import Any, Dict, List, Optional

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
        # Use CLAUDE_WORKING_DIR if available, otherwise use TMPDIR
        working_dir = os.environ.get("CLAUDE_WORKING_DIR")
        if working_dir:
            log_dir = os.path.join(working_dir, ".claude", "logs")
        else:
            # Fallback to system temp directory
            import tempfile

            temp_dir = os.environ.get("TMPDIR", tempfile.gettempdir())
            log_dir = os.path.join(temp_dir, "claude-timemachine")

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
        self.checkpoints: List[Dict[str, Any]] = []
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
        """Load or create configuration"""
        config = super().load_config()

        self.enabled = config.get("enabled", True)
        self.checkpoints = config.get("checkpoints", [])
        self.settings = config.get(
            "settings",
            {"max_checkpoints": 100, "auto_cleanup": True, "include_untracked": False},
        )

        return config

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration and checkpoint history"""
        if config is None:
            config = {
                "enabled": self.enabled,
                "checkpoints": self.checkpoints,
                "settings": self.settings,
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
        """Track file modifications"""
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
            # Create the checkpoint
            checkpoint_id = self._create_checkpoint(context)
            if checkpoint_id:
                self.logger.info(
                    f"Created checkpoint: {checkpoint_id} for prompt: {truncate_value(current_prompt, 50)}"
                )

                # Clean up old checkpoints if needed
                if self.settings.get("auto_cleanup", True):
                    self._cleanup_old_checkpoints()
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")

        # Clear session state for next turn
        self.clear_session_state(context)

        return HookHandler.create_allow_response()

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
                # Add to checkpoint history
                checkpoint = {
                    "id": f"checkpoint-{len(self.checkpoints)}",
                    "commit_sha": commit_sha,
                    "prompt_preview": current_prompt[:80],
                    "timestamp": metadata["timestamp"],
                }
                self.checkpoints.append(checkpoint)
                self.save_config()

                return checkpoint["id"]

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
                    refs = result.stdout.strip().split('\n')
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

    def _cleanup_old_checkpoints(self) -> None:
        """Remove old checkpoints beyond max_checkpoints limit"""
        max_checkpoints = self.settings.get("max_checkpoints", 100)
        if len(self.checkpoints) > max_checkpoints:
            # Remove oldest checkpoints
            self.checkpoints = self.checkpoints[-max_checkpoints:]
            self.save_config()

    # CLI Commands
    def list_checkpoints(self) -> None:
        """List all checkpoints"""
        # Don't reload config, just load checkpoints from git
        old_checkpoints = self.checkpoints.copy()
        self._load_checkpoints_from_git()
        
        # If no checkpoints were loaded from git, use the ones from config
        if not self.checkpoints and old_checkpoints:
            self.checkpoints = old_checkpoints
        
        if not self.checkpoints:
            print("No checkpoints found.")
            return

        print("\n🕐 TimeMachine Checkpoints:")
        print("=" * 80)

        for i, checkpoint in enumerate(reversed(self.checkpoints)):
            turns_ago = i

            # Handle old checkpoints that might not have timestamp
            if "timestamp" in checkpoint:
                timestamp = datetime.fromisoformat(checkpoint["timestamp"])
                relative_time = self._format_relative_time(timestamp)
            else:
                relative_time = "unknown time"

            prompt_preview = checkpoint.get("prompt_preview", "No preview available")
            checkpoint_id = checkpoint.get("id", f"checkpoint-{len(self.checkpoints) - i - 1}")

            if turns_ago == 0:
                print(f"→ [{checkpoint_id}] {relative_time} - {prompt_preview}")
            else:
                print(f"  [{checkpoint_id}] {relative_time} - {prompt_preview}")

        print("=" * 80)
        print(f"\nTotal checkpoints: {len(self.checkpoints)}")
        print("\nUse 'orchestra timemachine view <id>' to see full details")
        print("Use 'orchestra timemachine checkout <id>' to restore a checkpoint")

    def checkout_checkpoint(self, checkpoint_id: str) -> None:
        """Checkout a specific checkpoint"""
        # First, try to load checkpoints from git
        self._load_checkpoints_from_git()
        
        checkpoint = self._find_checkpoint(checkpoint_id)
        if not checkpoint:
            print(f"❌ Checkpoint not found: {checkpoint_id}")
            return

        try:
            # Checkout the commit
            self.git_manager._run_git_command(["checkout", checkpoint["commit_sha"]])
            print(f"✅ Checked out checkpoint: {checkpoint_id}")
            print(f"   Prompt: {checkpoint['prompt_preview']}")
        except Exception as e:
            print(f"❌ Failed to checkout: {e}")

    def view_checkpoint(self, checkpoint_id: str) -> None:
        """View full details of a checkpoint"""
        # First, try to load checkpoints from git
        self._load_checkpoints_from_git()
        
        checkpoint = self._find_checkpoint(checkpoint_id)
        if not checkpoint:
            print(f"❌ Checkpoint not found: {checkpoint_id}")
            return

        try:
            # Get commit metadata
            result = self.git_manager._run_git_command(
                ["show", "--no-patch", "--format=%B", checkpoint["commit_sha"]]
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
        if n >= len(self.checkpoints):
            print(
                f"❌ Cannot rollback {n} turns. Only {len(self.checkpoints)} checkpoints available."
            )
            return

        # Get checkpoint from n turns ago
        checkpoint_index = -(n + 1)  # -1 for latest, -2 for 1 turn ago, etc.
        checkpoint = self.checkpoints[checkpoint_index]

        self.checkout_checkpoint(checkpoint["id"])

    def _find_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Find checkpoint by ID"""
        for checkpoint in self.checkpoints:
            if checkpoint["id"] == checkpoint_id:
                return checkpoint
        return None

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
    
    def _load_checkpoints_from_git(self) -> None:
        """Load checkpoints from git history"""
        if not self.git_manager._is_git_repo():
            return
        
        try:
            # Find the wip branch
            wip_refs = []
            try:
                result = self.git_manager._run_git_command(
                    ["for-each-ref", "--format=%(refname)", "refs/wip/"]
                )
                wip_refs = [ref.strip() for ref in result.stdout.strip().split('\n') if ref.strip()]
            except Exception as e:
                self.logger.debug(f"Failed to get wip refs: {e}")
                pass
            
            if not wip_refs:
                self.logger.debug("No wip refs found")
                return
            
            self.logger.debug(f"Found wip refs: {wip_refs}")
            
            # Clear existing checkpoints to avoid duplicates
            self.checkpoints = []
            
            # Get all commits from the wip branch
            for wip_ref in wip_refs:
                try:
                    # Get the log of all TimeMachine commits
                    result = self.git_manager._run_git_command([
                        "log", wip_ref, 
                        "--grep=TimeMachine:", 
                        "--format=%H|%ct|%s",
                        "--reverse"  # Oldest first
                    ])
                    
                    self.logger.debug(f"Git log result for {wip_ref}: {result.stdout[:200]}")
                    
                    if not result.stdout.strip():
                        self.logger.debug(f"No TimeMachine commits found in {wip_ref}")
                        continue
                    
                    # Parse each commit
                    checkpoint_count = 0
                    for line in result.stdout.strip().split('\n'):
                        if not line:
                            continue
                        
                        parts = line.split('|', 2)
                        if len(parts) < 3:
                            continue
                        
                        commit_sha = parts[0]
                        commit_time = int(parts[1])
                        subject = parts[2]
                        
                        # Extract prompt preview from subject
                        if subject.startswith("TimeMachine: "):
                            prompt_preview = subject[13:].rstrip('.')
                            if len(prompt_preview) > 80:
                                prompt_preview = prompt_preview[:80]
                            
                            # Get full metadata from commit message
                            try:
                                result = self.git_manager._run_git_command(
                                    ["show", "--no-patch", "--format=%B", commit_sha]
                                )
                                
                                # Parse metadata from commit message
                                lines = result.stdout.strip().split("\n")
                                timestamp = datetime.fromtimestamp(commit_time).isoformat()
                                
                                checkpoint = {
                                    "id": f"checkpoint-{checkpoint_count}",
                                    "commit_sha": commit_sha,
                                    "prompt_preview": prompt_preview,
                                    "timestamp": timestamp
                                }
                                
                                self.checkpoints.append(checkpoint)
                                checkpoint_count += 1
                                
                            except Exception as e:
                                self.logger.debug(f"Failed to get metadata for {commit_sha}: {e}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to load checkpoints from {wip_ref}: {e}")
            
            # Save the loaded checkpoints to config
            if self.checkpoints:
                self.save_config()
                self.logger.info(f"Loaded {len(self.checkpoints)} checkpoints from git")
                
        except Exception as e:
            self.logger.error(f"Failed to load checkpoints from git: {e}")


def main():
    """CLI entry point for TimeMachine commands"""
    if len(sys.argv) < 2:
        print("Usage: timemachine_monitor.py <command> [args]")
        print("Commands: list, checkout <id>, view <id>, rollback <n>, hook <event>")
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
