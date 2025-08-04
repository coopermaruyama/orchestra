"""
Tidy Sidecar Command

Runs code quality fixes in a parallel daemon process using a git worktree.
"""

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestra.common.core_command import CoreCommand


class TidySidecarCommand(CoreCommand):
    """Run tidy fixes in a parallel daemon process"""

    def __init__(self, model: str = "haiku", logger: Optional[logging.Logger] = None):
        """Initialize sidecar command"""
        super().__init__(model=model, logger=logger)
        self.orchestra_dir = Path.home() / ".claude" / "orchestra"
        self.sidecar_state_file = self.orchestra_dir / "tidy-sidecar.json"
        self.sidecar_ready_file = self.orchestra_dir / "tidy-sidecar-ready.json"

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input has required fields"""
        required = ["action"]
        if not all(key in input_data for key in required):
            self.logger.debug(f"Missing required fields. Got: {input_data.keys()}")
            return False

        action = input_data.get("action")
        if action not in ["start", "status", "stop", "merge"]:
            self.logger.debug(f"Invalid action: {action}")
            return False

        return True

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sidecar command based on action"""
        action = input_data.get("action")

        if action == "start":
            return self._start_sidecar(input_data)
        if action == "status":
            return self._get_sidecar_status()
        if action == "stop":
            return self._stop_sidecar()
        if action == "merge":
            return self._merge_sidecar_fixes()

        return {"success": False, "error": f"Unknown action: {action}"}

    def _start_sidecar(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start the sidecar daemon process"""
        # Check if sidecar is already running
        if self._is_sidecar_running():
            return {
                "success": False,
                "error": "Sidecar is already running",
                "pid": self._get_sidecar_pid(),
            }

        # Get current working directory
        working_dir = input_data.get("working_dir", str(Path.cwd()))

        # Create worktree name
        worktree_name = f"tidy-sidecar-{int(time.time())}"
        worktree_path = Path(tempfile.gettempdir()) / worktree_name

        try:
            # Create git worktree
            self._create_worktree(working_dir, worktree_path, worktree_name)

            # Start daemon process
            pid = self._spawn_daemon(working_dir, worktree_path, input_data)

            # Save state
            state = {
                "pid": pid,
                "started_at": datetime.now().isoformat(),
                "working_dir": working_dir,
                "worktree_path": str(worktree_path),
                "worktree_name": worktree_name,
                "status": "running",
            }
            self._save_state(state)

            return {
                "success": True,
                "pid": pid,
                "worktree_path": str(worktree_path),
                "message": "Sidecar daemon started successfully",
            }

        except Exception as e:
            self.logger.exception("Failed to start sidecar")
            # Cleanup worktree if created
            if worktree_path.exists():
                self._remove_worktree(working_dir, worktree_path)
            return {"success": False, "error": f"Failed to start sidecar: {e!s}"}

    def _spawn_daemon(
        self, working_dir: str, worktree_path: Path, input_data: Dict[str, Any]
    ) -> int:
        """Spawn the daemon process"""
        # Python code to run in daemon
        daemon_code = f"""
import os
import sys
import json
import subprocess
import time
import signal
from pathlib import Path

def signal_handler(signum, frame):
    # Cleanup and exit
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Configuration
worktree_path = Path('{worktree_path}')
orchestra_dir = Path('{self.orchestra_dir}')
ready_file = orchestra_dir / 'tidy-sidecar-ready.json'
detected_tools = {json.dumps(input_data.get('detected_tools', {}))}
modified_files = {json.dumps(input_data.get('modified_files', []))}

# Change to worktree
os.chdir(worktree_path)

# Run fixes
results = {{}}
all_fixes = []

# Run each tool's fix command
for tool_name, tool_info in detected_tools.items():
    if tool_info.get('fix_command') and tool_info.get('is_available'):
        try:
            cmd = tool_info['fix_command'].split()
            # Add modified files if available
            if modified_files and tool_name in ['ruff', 'black', 'isort']:
                cmd.extend(modified_files)
            result = subprocess.run(cmd, capture_output=True, text=True)
            results[tool_name] = {{
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }}
            if result.returncode == 0:
                all_fixes.append(tool_name)
        except Exception as e:
            results[tool_name] = {{
                'success': False,
                'error': str(e)
            }}

# Generate diff
try:
    diff_result = subprocess.run(
        ['git', 'diff', '--no-index', '--no-prefix', str(Path('{working_dir}')), str(worktree_path)],
        capture_output=True,
        text=True,
        cwd=worktree_path
    )
    diff = diff_result.stdout
except Exception as e:
    diff = f"Failed to generate diff: {{e}}"

# Save results
ready_data = {{
    'completed_at': time.time(),
    'worktree_path': str(worktree_path),
    'fixes_applied': all_fixes,
    'results': results,
    'diff': diff,
    'has_changes': bool(diff.strip())
}}

with open(ready_file, 'w') as f:
    json.dump(ready_data, f, indent=2)
"""

        # Start daemon process
        process = subprocess.Popen(
            [sys.executable, "-c", daemon_code],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        return process.pid

    def _create_worktree(
        self, working_dir: str, worktree_path: Path, worktree_name: str
    ) -> None:
        """Create a git worktree"""
        # First check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            check=False,
            cwd=working_dir,
            capture_output=True,
        )
        if result.returncode != 0:
            msg = "Not in a git repository"
            raise RuntimeError(msg)

        # Create worktree
        result = subprocess.run(
            ["git", "worktree", "add", "-b", worktree_name, str(worktree_path)],
            check=False,
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            msg = f"Failed to create worktree: {result.stderr}"
            raise RuntimeError(msg)

    def _remove_worktree(self, working_dir: str, worktree_path: Path) -> None:
        """Remove a git worktree"""
        try:
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path), "--force"],
                check=False,
                cwd=working_dir,
                capture_output=True,
            )
        except Exception as e:
            self.logger.warning(f"Failed to remove worktree: {e}")

    def _is_sidecar_running(self) -> bool:
        """Check if sidecar daemon is running"""
        state = self._load_state()
        if not state or state.get("status") != "running":
            return False

        pid = state.get("pid")
        if not pid:
            return False

        # Check if process is still alive
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            # Process doesn't exist
            state["status"] = "stopped"
            self._save_state(state)
            return False
        else:
            return True

    def _get_sidecar_pid(self) -> Optional[int]:
        """Get PID of running sidecar"""
        state = self._load_state()
        return state.get("pid") if state else None

    def _get_sidecar_status(self) -> Dict[str, Any]:
        """Get current sidecar status"""
        state = self._load_state()
        if not state:
            return {
                "success": True,
                "status": "not_running",
                "message": "No sidecar process found",
            }

        # Check if ready file exists
        if self.sidecar_ready_file.exists():
            with self.sidecar_ready_file.open() as f:
                ready_data = json.load(f)

            return {
                "success": True,
                "status": "completed",
                "state": state,
                "results": ready_data,
                "message": "Sidecar has completed fixes",
            }

        # Check if still running
        if self._is_sidecar_running():
            return {
                "success": True,
                "status": "running",
                "state": state,
                "message": "Sidecar is still running",
            }

        return {
            "success": True,
            "status": "stopped",
            "state": state,
            "message": "Sidecar has stopped without completing",
        }

    def _stop_sidecar(self) -> Dict[str, Any]:
        """Stop the sidecar daemon"""
        state = self._load_state()
        if not state:
            return {"success": True, "message": "No sidecar process to stop"}

        pid = state.get("pid")
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)  # Give it time to cleanup

                # Force kill if still alive
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            except ProcessLookupError:
                pass
            except Exception:
                self.logger.exception("Failed to stop sidecar")

        # Cleanup worktree
        worktree_path = state.get("worktree_path")
        working_dir = state.get("working_dir")
        if worktree_path and working_dir:
            self._remove_worktree(working_dir, Path(worktree_path))

        # Update state
        state["status"] = "stopped"
        state["stopped_at"] = datetime.now().isoformat()
        self._save_state(state)

        # Remove ready file if exists
        if self.sidecar_ready_file.exists():
            self.sidecar_ready_file.unlink()

        return {"success": True, "message": "Sidecar stopped successfully"}

    def _merge_sidecar_fixes(self) -> Dict[str, Any]:
        """Merge fixes from sidecar worktree"""
        if not self.sidecar_ready_file.exists():
            return {"success": False, "error": "No completed sidecar fixes found"}

        with self.sidecar_ready_file.open() as f:
            ready_data = json.load(f)

        if not ready_data.get("has_changes"):
            return {"success": True, "message": "No changes to merge"}

        state = self._load_state()
        worktree_path = Path(ready_data["worktree_path"])
        working_dir = state.get("working_dir", str(Path.cwd()))

        try:
            # Apply changes from worktree
            # We'll use rsync to copy changed files
            changed_files = self._get_changed_files(working_dir, worktree_path)

            for file_path in changed_files:
                src = worktree_path / file_path
                dst = Path(working_dir) / file_path

                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    # Import already at top of file
                    shutil.copy2(src, dst)

            # Cleanup
            self._stop_sidecar()

            return {
                "success": True,
                "files_updated": len(changed_files),
                "message": f"Merged {len(changed_files)} files from sidecar",
            }

        except Exception as e:
            self.logger.exception("Failed to merge sidecar fixes")
            return {"success": False, "error": f"Failed to merge fixes: {e!s}"}

    def _get_changed_files(self, working_dir: str, worktree_path: Path) -> List[str]:
        """Get list of changed files between directories"""
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "--no-index",
                working_dir,
                str(worktree_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=working_dir,
        )

        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        return []

    def _load_state(self) -> Optional[Dict[str, Any]]:
        """Load sidecar state from file"""
        if not self.sidecar_state_file.exists():
            return None

        try:
            with self.sidecar_state_file.open() as f:
                return json.load(f)
        except Exception:
            self.logger.exception("Failed to load state")
            return None

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save sidecar state to file"""
        self.orchestra_dir.mkdir(parents=True, exist_ok=True)

        try:
            with self.sidecar_state_file.open("w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            self.logger.exception("Failed to save state")

    # Override parent methods for sidecar-specific behavior
    def build_prompt(self, input_data: Dict[str, Any]) -> str:  # noqa: ARG002
        """Not used for sidecar command"""
        return ""

    def build_system_prompt(self, input_data: Dict[str, Any]) -> str:  # noqa: ARG002
        """Not used for sidecar command"""
        return ""

    def parse_response(
        self, response: Any, original_content: str = ""
    ) -> Dict[str, Any]:  # noqa: ARG002
        """Not used for sidecar command"""
        return {}
