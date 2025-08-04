"""Hook command for Orchestra CLI."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import click


def find_enabled_monitors() -> List[Dict[str, Any]]:
    """Find all enabled monitor scripts in the orchestra directory."""
    monitors = []

    # Check both global and local orchestra directories
    orchestra_dirs = []

    # Global directory
    global_dir = Path.home() / ".claude" / "orchestra"
    if global_dir.exists():
        orchestra_dirs.append(global_dir)

    # Local directory (if CLAUDE_WORKING_DIR is set)
    working_dir = os.environ.get("CLAUDE_WORKING_DIR")
    if working_dir:
        local_dir = Path(working_dir) / ".claude" / "orchestra"
        if local_dir.exists():
            orchestra_dirs.append(local_dir)

    # Map of extension names to monitor scripts
    extension_monitors = {
        "task": "task_monitor.py",
        "timemachine": "timemachine_monitor.py",
        "tidy": "tidy_monitor.py",
        "tester": "tester_monitor.py",
    }

    # Find all monitor scripts
    for orchestra_dir in orchestra_dirs:
        for extension, monitor_script in extension_monitors.items():
            monitor_path = orchestra_dir / extension / monitor_script
            if monitor_path.exists():
                monitors.append(
                    {
                        "extension": extension,
                        "path": str(monitor_path),
                        "directory": str(orchestra_dir),
                    }
                )

    # Remove duplicates (prefer local over global)
    seen_extensions = set()
    unique_monitors = []
    for monitor in monitors:
        if monitor["extension"] not in seen_extensions:
            seen_extensions.add(monitor["extension"])
            unique_monitors.append(monitor)

    return unique_monitors


def invoke_monitor_hook(
    monitor: Dict[str, Any], hook_type: str, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Invoke a monitor's hook handler using JSON input."""
    import subprocess

    # Prepare the command
    cmd = [
        sys.executable,  # Use the current Python interpreter
        monitor["path"],
        "hook",
        hook_type,
    ]

    # Convert context to JSON
    json_input = json.dumps(context)

    try:
        # Run the monitor script with JSON input
        result = subprocess.run(
            cmd,
            check=False,
            input=json_input,
            capture_output=True,
            text=True,
            timeout=5,  # 5 second timeout for hooks
        )

        if result.returncode == 0 and result.stdout:
            # Parse the JSON response
            response = json.loads(result.stdout)
            return (
                response
                if isinstance(response, dict)
                else {"error": "Invalid response format", "continue": True}
            )
        # Return error response
        error_msg = (
            result.stderr
            or f"Monitor {monitor['extension']} failed with code {result.returncode}"
        )
        return {"error": error_msg, "continue": True}
    except subprocess.TimeoutExpired:
        return {"error": f"Monitor {monitor['extension']} timed out", "continue": True}
    except json.JSONDecodeError as e:
        return {
            "error": f"Invalid JSON response from {monitor['extension']}: {e}",
            "continue": True,
        }
    except Exception as e:
        return {
            "error": f"Error invoking {monitor['extension']}: {e}",
            "continue": True,
        }


@click.command()
@click.argument("hook_type")
@click.argument("args", nargs=-1)
def hook(hook_type: str, args: tuple) -> None:
    """Handle hooks from Claude Code and notify all enabled monitors.

    This command is called by Claude Code hooks and distributes the hook
    events to all enabled Orchestra extensions.
    """
    # Read JSON context from stdin
    try:
        context = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If no JSON input, create empty context
        context = {}

    # Add any additional args to context
    if args:
        context["args"] = list(args)

    # Find all enabled monitors
    monitors = find_enabled_monitors()

    if not monitors:
        # No monitors enabled, just allow the operation
        print(json.dumps({"decision": "approve"}))
        return

    # Collect responses from all monitors
    responses: List[Dict[str, Any]] = []
    errors: List[str] = []

    for monitor in monitors:
        response = invoke_monitor_hook(monitor, hook_type, context)

        if "error" in response:
            errors.append(f"{monitor['extension']}: {response['error']}")
            if not response.get("continue", True):
                # If any monitor says don't continue, block the operation
                print(
                    json.dumps(
                        {
                            "decision": "block",
                            "message": f"Blocked by {monitor['extension']}: {response['error']}",
                        }
                    )
                )
                sys.exit(1)
        else:
            responses.append(response)

            # Check if any monitor wants to block
            if response.get("decision") == "block":
                print(json.dumps(response))
                sys.exit(1)

            # Check if any monitor wants to modify the context
            if response.get("decision") == "modify":
                # For now, we don't support context modification
                # but we could aggregate modifications here
                pass

    # If we get here, all monitors approved or had non-blocking errors
    final_response = {"decision": "approve"}

    # Include any errors as warnings
    if errors:
        final_response["warnings"] = errors

    # Output the final response
    print(json.dumps(final_response))


if __name__ == "__main__":
    hook()
