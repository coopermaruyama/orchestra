#!/usr/bin/env python3
"""
Plancheck Monitor for Claude Code
Monitors ExitPlanMode tool usage and handles plan detection and review blocking.
Communicates with TimeMachine extension via session state for checkpoint creation.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import from common library
from orchestra.common import (
    BaseExtension,
    HookHandler,
    format_hook_context,
    setup_logger,
    truncate_value,
)


class PlancheckMonitor(BaseExtension):
    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use CLAUDE_WORKING_DIR if available, otherwise use common project directory logic
        working_dir = os.environ.get("CLAUDE_WORKING_DIR")
        if not working_dir:
            working_dir = self._get_project_directory()
            
        log_dir = os.path.join(working_dir, ".claude", "logs")

        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "plancheck.log")

        # Configure logger with truncation
        self.logger = setup_logger(
            "plancheck", log_file, logging.DEBUG, truncate=True, max_length=300
        )
        self.logger.info("PlancheckMonitor initialized")

        # Initialize base class
        base_working_dir = working_dir or "."
        super().__init__(
            config_file=config_path,  # Let base class handle the default path
            working_dir=base_working_dir,
        )
        
        # Ensure settings exist with defaults
        self._ensure_settings_exist()

        # Plancheck specific state
        self.enabled: bool = True
        self.settings: Dict[str, Any] = {}
        self.plans_saved: int = 0  # Counter for plans saved

        self.load_config()

    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""
        return "plancheck.json"
    
    def _ensure_settings_exist(self) -> None:
        """Ensure extension settings exist with defaults"""
        settings = self.load_settings()
        if not settings.get("plancheck"):
            # Create default settings for plancheck
            default_plancheck_settings = {
                "enabled": True,
                "plans_directory": "plans",
                "auto_save": True
            }
            settings["plancheck"] = default_plancheck_settings
            self.save_settings(settings)
            self.logger.info("Created default plancheck settings")

    def load_config(self) -> Dict[str, Any]:
        """Load state and settings"""
        # Load state from the state file (dot-prefixed)
        state = super().load_config()
        
        # Load settings from shared settings.json
        self.settings = self.get_extension_settings("plancheck")
        if not self.settings:
            # Default settings if not found in settings.json
            self.settings = {
                "enabled": True,
                "save_plans": True,
                "auto_review": True
            }

        # Load state data
        self.enabled = state.get("enabled", self.settings.get("enabled", True))
        self.plans_saved = state.get("plans_saved", 0)

        return state

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save state (not settings - those go in settings.json)"""
        if config is None:
            config = {
                "enabled": self.enabled,
                "plans_saved": self.plans_saved,
                "updated": datetime.now().isoformat(),
            }

        super().save_config(config)

    def handle_hook(self, hook_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Universal hook handler"""
        self.logger.info(f"Handling hook: {hook_type}")
        self.logger.debug(f"Hook context: {format_hook_context(context)}")

        if not self.enabled:
            return HookHandler.create_allow_response()

        if hook_type == "PostToolUse":
            return self._handle_post_tool_use_hook(context)

        return HookHandler.create_allow_response()

    def _handle_post_tool_use_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PostToolUse hook by detecting ExitPlanMode tool usage"""
        tool_name = context.get("tool_name", "")
        
        if tool_name == "ExitPlanMode":
            self.logger.info("ExitPlanMode tool detected - processing plan")
            
            try:
                # 1. Save plan to file
                plan_title = self._save_plan_to_file(context)
                
                # 2. Signal TimeMachine that a plan is now active via session state
                self.update_session_state(context, {
                    "plan_active": True,
                    "plan_title": plan_title,
                    "plan_timestamp": datetime.now().isoformat()
                })
                
                # 3. Block with plancheck agent review request
                reason = "ask the plancheck agent to review the current plan and decide if it needs more work"
                self.logger.info(f"Blocking ExitPlanMode for review: {reason}")
                
                return {
                    "block": True,
                    "reason": reason
                }
                
            except Exception as e:
                self.logger.error(f"Error handling ExitPlanMode: {e}")
                import traceback
                self.logger.error(f"Traceback:\n{traceback.format_exc()}")
                # On error, allow the tool to proceed
                return HookHandler.create_allow_response()

        return HookHandler.create_allow_response()

    def _save_plan_to_file(self, context: Dict[str, Any]) -> str:
        """Save plan content from ExitPlanMode tool to a markdown file
        
        Args:
            context: Hook context containing tool input
            
        Returns:
            Generated plan title/filename
        """
        try:
            # Get the plan content from tool input
            tool_input = context.get("tool_input", {})
            plan_content = tool_input.get("plan", "")
            
            if not plan_content:
                self.logger.warning("No plan content found in ExitPlanMode tool input")
                return "untitled-plan"

            # Extract a title from the plan content
            plan_title = self._extract_plan_title(plan_content)
            
            # Create plans directory
            plans_dir = Path(self.orchestra_dir) / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp and sanitized title
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            sanitized_title = self._sanitize_filename(plan_title)
            filename = f"{timestamp}_{sanitized_title}.md"
            plan_file = plans_dir / filename

            # Write plan content to file
            with open(plan_file, 'w', encoding='utf-8') as f:
                f.write(f"# {plan_title}\n\n")
                f.write(f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
                f.write(plan_content)
                f.write("\n")

            self.logger.info(f"Plan saved to: {plan_file}")
            
            # Update counter and save state
            self.plans_saved += 1
            self.save_config()
            
            return plan_title

        except Exception as e:
            self.logger.error(f"Failed to save plan to file: {e}")
            import traceback
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            return "error-saving-plan"

    def _extract_plan_title(self, plan_content: str) -> str:
        """Extract a meaningful title from plan content
        
        Args:
            plan_content: The plan content text
            
        Returns:
            Extracted or generated title
        """
        # Try to find first heading
        lines = plan_content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
            elif line.startswith('## '):
                return line[3:].strip()
        
        # Try to find first meaningful sentence
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and len(line) > 10:
                # Take first 50 characters and clean up
                title = line[:50].strip()
                if title.endswith('.'):
                    title = title[:-1]
                return title
        
        # Fallback to generic title
        return "Plan"

    def _sanitize_filename(self, title: str) -> str:
        """Sanitize title for use as filename
        
        Args:
            title: Raw title text
            
        Returns:
            Sanitized filename-safe string
        """
        # Remove/replace problematic characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
        sanitized = re.sub(r'\s+', '-', sanitized)
        sanitized = sanitized.strip('-').lower()
        
        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        # Ensure not empty
        if not sanitized:
            sanitized = "untitled"
            
        return sanitized


def main():
    """CLI entry point for Plancheck commands"""
    if len(sys.argv) < 2:
        print("Usage: plancheck_monitor.py <command> [args]")
        print("Commands: hook <event>, status")
        return

    command = sys.argv[1]
    monitor = PlancheckMonitor()

    if command == "status":
        print(f"🔍 Plancheck Monitor Status")
        print(f"Enabled: {monitor.enabled}")
        print(f"Plans saved: {monitor.plans_saved}")
        
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