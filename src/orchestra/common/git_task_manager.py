"""
Git Task Manager for Orchestra Extensions

Provides git branch management for task isolation and tracking.
"""

import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .task_state import GitTaskState


class GitTaskManager:
    """Manages git branches and state for task isolation"""

    def __init__(self, working_dir: Optional[str] = None):
        """Initialize git task manager

        Args:
            working_dir: Working directory for git operations (defaults to current dir)
        """
        self.working_dir = working_dir or os.getcwd()
        self.branch_prefix = "task-monitor"

    def _run_git_command(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run git command in working directory"""
        return subprocess.run(
            ["git"] + args,
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            check=True,
        )

    def _run_git_wip_command(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run git-wip command in working directory"""
        return subprocess.run(
            args, cwd=self.working_dir, capture_output=True, text=True, check=True
        )

    def _get_git_wip_path(self) -> str:
        """Get path to git-wip script"""
        # Try to find git-wip in same directory as this module
        current_dir = Path(__file__).parent.absolute()
        git_wip_path = current_dir / "git-wip"

        if git_wip_path.exists():
            # Make sure it's executable
            import os
            import stat

            if not os.access(str(git_wip_path), os.X_OK):
                # Try to make it executable
                try:
                    git_wip_path.chmod(git_wip_path.stat().st_mode | stat.S_IEXEC)
                except Exception:
                    pass
            return str(git_wip_path.absolute())

        # Fallback: assume git-wip is in PATH
        import shutil

        if shutil.which("git-wip"):
            return "git-wip"

        # If still not found, raise a more helpful error
        raise FileNotFoundError(
            f"git-wip not found. Expected at: {git_wip_path}\n"
            f"Current directory: {current_dir}\n"
            f"Module file: {__file__}"
        )

    def _get_current_branch(self) -> str:
        """Get current git branch name"""
        result = self._run_git_command(["branch", "--show-current"])
        return result.stdout.strip()

    def _get_current_sha(self) -> str:
        """Get current commit SHA"""
        result = self._run_git_command(["rev-parse", "HEAD"])
        return result.stdout.strip()

    def _branch_exists(self, branch_name: str) -> bool:
        """Check if branch exists"""
        try:
            self._run_git_command(["rev-parse", "--verify", branch_name])
            return True
        except subprocess.CalledProcessError:
            return False

    def _is_git_repo(self) -> bool:
        """Check if current directory is a git repository"""
        try:
            self._run_git_command(["rev-parse", "--git-dir"])
            return True
        except subprocess.CalledProcessError:
            return False

    def create_task_snapshot(
        self, task_id: Optional[str] = None, task_description: str = ""
    ) -> GitTaskState:
        """Create a non-invasive task snapshot using git-wip

        Args:
            task_id: Unique task identifier (generates if None)
            task_description: Human-readable task description

        Returns:
            GitTaskState with snapshot information

        Raises:
            RuntimeError: If not in git repository or git operations fail
        """
        if not self._is_git_repo():
            raise RuntimeError("Not in a git repository")

        # Generate task ID if not provided
        if task_id is None:
            task_id = str(uuid.uuid4())[:8]

        # Get current branch (user stays on this branch)
        current_branch = self._get_current_branch()
        base_sha = self._get_current_sha()

        # Create WIP snapshot without switching branches
        wip_message = (
            f"Task: {task_description}" if task_description else f"Task {task_id}"
        )

        try:
            # Use git-wip to create snapshot with untracked files
            git_wip_path = self._get_git_wip_path()
            result = self._run_git_wip_command(
                [git_wip_path, "save", wip_message, "--untracked"]
            )
        except subprocess.CalledProcessError as e:
            # Check if it's just "no changes" error (exit code 1 with stderr "no changes")
            if e.returncode == 1 and e.stderr.strip() == "no changes":
                # This is expected when working tree hasn't changed since last WIP
                pass
            else:
                # Try without untracked files as fallback
                try:
                    result = self._run_git_wip_command(
                        [git_wip_path, "save", wip_message]
                    )
                except subprocess.CalledProcessError as e2:
                    if e2.returncode == 1 and e2.stderr.strip() == "no changes":
                        # This is expected when working tree hasn't changed
                        pass
                    else:
                        raise RuntimeError(f"Failed to create task snapshot: {e}")

        # Get WIP branch reference
        wip_branch = f"refs/wip/{current_branch}"

        # Create task state
        task_state = GitTaskState(
            task_id=task_id,
            task_description=task_description,
            base_sha=base_sha,
            current_sha=base_sha,  # Same as base since we just created snapshot
            branch_name=current_branch,  # User stays on original branch
            base_branch=current_branch,
            created_at=datetime.now(),
            subagent_branches={"wip_snapshot": wip_branch},
        )

        return task_state

    def get_task_diff(
        self, task_state: GitTaskState, target_sha: Optional[str] = None
    ) -> str:
        """Get git diff for task changes

        Args:
            task_state: Task state with WIP snapshot
            target_sha: Target SHA to diff to (defaults to HEAD)

        Returns:
            Git diff output as string
        """
        if target_sha is None:
            target_sha = "HEAD"

        # Use WIP snapshot as base if available
        wip_ref = task_state.subagent_branches.get("wip_snapshot")
        if wip_ref:
            # Show changes since WIP snapshot was created
            result = self._run_git_command(["diff", f"{wip_ref}..{target_sha}"])
        else:
            # Fallback to base SHA
            result = self._run_git_command(
                ["diff", f"{task_state.base_sha}..{target_sha}"]
            )
        return result.stdout

    def get_task_file_changes(
        self, task_state: GitTaskState, target_sha: Optional[str] = None
    ) -> List[str]:
        """Get list of files changed in task

        Args:
            task_state: Task state with WIP snapshot
            target_sha: Target SHA to diff to (defaults to HEAD)

        Returns:
            List of file paths that changed
        """
        if target_sha is None:
            target_sha = "HEAD"

        # Use WIP snapshot as base if available
        wip_ref = task_state.subagent_branches.get("wip_snapshot")
        if wip_ref:
            # Show files changed since WIP snapshot was created
            result = self._run_git_command(
                ["diff", "--name-only", f"{wip_ref}..{target_sha}"]
            )
        else:
            # Fallback to base SHA
            result = self._run_git_command(
                ["diff", "--name-only", f"{task_state.base_sha}..{target_sha}"]
            )

        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return [f for f in files if f]  # Filter empty strings

    def update_task_state(self, task_state: GitTaskState) -> GitTaskState:
        """Update task state with current git information

        Args:
            task_state: Existing task state to update

        Returns:
            Updated task state with current SHA
        """
        # Switch to task branch if not already there
        current_branch = self._get_current_branch()
        if current_branch != task_state.branch_name:
            self._run_git_command(["checkout", task_state.branch_name])

        # Update current SHA
        task_state.current_sha = self._get_current_sha()
        return task_state

    def cleanup_task_branch(
        self,
        task_state: GitTaskState,
        merge_back: bool = False,
        delete_branch: bool = True,
    ) -> None:
        """Clean up task branch

        Args:
            task_state: Task state with branch information
            merge_back: Whether to merge changes back to base branch
            delete_branch: Whether to delete the task branch
        """
        # Switch to base branch
        self._run_git_command(["checkout", task_state.base_branch])

        if merge_back:
            # Merge task branch back
            self._run_git_command(["merge", task_state.branch_name])

        if delete_branch:
            # Delete task branch
            self._run_git_command(["branch", "-D", task_state.branch_name])

    def switch_to_task_branch(self, task_state: GitTaskState) -> None:
        """Switch to task branch

        Args:
            task_state: Task state with branch information
        """
        self._run_git_command(["checkout", task_state.branch_name])

    def create_subagent_branch(self, task_state: GitTaskState, agent_name: str) -> str:
        """Create a branch for subagent analysis

        Args:
            task_state: Parent task state
            agent_name: Name of the subagent

        Returns:
            Name of created subagent branch
        """
        subagent_branch = f"{task_state.branch_name}/{agent_name}"

        # Create branch from task branch
        self._run_git_command(
            ["checkout", "-b", subagent_branch, task_state.branch_name]
        )

        # Update task state with subagent branch
        task_state.subagent_branches[agent_name] = subagent_branch

        return subagent_branch

    def list_task_branches(self) -> List[str]:
        """List all task branches

        Returns:
            List of task branch names
        """
        result = self._run_git_command(["branch", "--list", f"{self.branch_prefix}/*"])
        branches = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line:
                # Remove leading * and whitespace
                branch = line.lstrip("* ").strip()
                if branch:
                    branches.append(branch)
        return branches

    def get_git_status(self) -> Dict[str, Any]:
        """Get current git status information

        Returns:
            Dictionary with git status information
        """
        current_branch = self._get_current_branch()
        current_sha = self._get_current_sha()

        # Check if working directory is clean
        result = self._run_git_command(["status", "--porcelain"])
        is_clean = len(result.stdout.strip()) == 0

        return {
            "branch": current_branch,
            "sha": current_sha,
            "is_clean": is_clean,
            "working_dir": self.working_dir,
        }

    def create_worktree(
        self,
        worktree_path: str,
        branch_name: Optional[str] = None,
        base_ref: Optional[str] = None,
    ) -> str:
        """Create a git worktree

        Args:
            worktree_path: Path where worktree should be created
            branch_name: Optional branch name for the worktree
            base_ref: Base reference to create worktree from (defaults to HEAD)

        Returns:
            Path to created worktree

        Raises:
            subprocess.CalledProcessError: If git command fails
        """
        cmd = ["worktree", "add"]

        if branch_name:
            cmd.extend(["-b", branch_name])

        cmd.append(worktree_path)

        if base_ref:
            cmd.append(base_ref)

        self._run_git_command(cmd)
        return worktree_path

    def remove_worktree(self, worktree_path: str, force: bool = False) -> None:
        """Remove a git worktree

        Args:
            worktree_path: Path to worktree to remove
            force: Force removal even if there are changes
        """
        cmd = ["worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(worktree_path)

        try:
            self._run_git_command(cmd)
        except subprocess.CalledProcessError as e:
            # Log but don't fail - worktree might already be removed
            import logging

            logging.warning(f"Failed to remove worktree: {e}")

    def list_worktrees(self) -> List[Dict[str, str]]:
        """List all git worktrees

        Returns:
            List of worktree information dicts
        """
        result = self._run_git_command(["worktree", "list", "--porcelain"])

        worktrees = []
        current_worktree = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current_worktree:
                    worktrees.append(current_worktree)
                    current_worktree = {}
                continue

            if line.startswith("worktree "):
                current_worktree["path"] = line.split(" ", 1)[1]
            elif line.startswith("HEAD "):
                current_worktree["head"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                current_worktree["branch"] = line.split(" ", 1)[1]

        if current_worktree:
            worktrees.append(current_worktree)

        return worktrees

    def prune_worktrees(self) -> None:
        """Prune stale worktree information"""
        self._run_git_command(["worktree", "prune"])
