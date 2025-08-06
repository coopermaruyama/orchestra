#!/usr/bin/env python3
"""
Never Again Monitor for Claude Code

Learns from user corrections to prevent repeated mistakes.
Analyzes transcripts for user corrections and stores them as instructions.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import from common library
from orchestra.common import (
    BaseExtension,
    HookHandler,
    format_hook_context,
    setup_logger,
)
from orchestra.common.types import HookInput
from orchestra.common.claude_invoker import invoke_claude


class NeverAgainMonitor(BaseExtension):
    """Extension that learns from user corrections to prevent repeated mistakes"""

    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use CLAUDE_WORKING_DIR if available, otherwise use common project directory logic
        working_dir = os.environ.get("CLAUDE_WORKING_DIR") or self._get_project_directory()

        # Set up logging
        log_dir = os.path.join(working_dir, ".claude", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "neveragain_monitor.log")

        # Configure logger
        self.logger = setup_logger(
            "neveragain_monitor", log_file, logging.DEBUG, truncate=True, max_length=300
        )
        self.logger.info("NeverAgainMonitor initialized")

        # Initialize base class
        super().__init__(config_file=config_path, working_dir=working_dir)

        # Set up memory directory
        self.memory_dir = Path(working_dir) / ".claude" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "neveragain.md"

        # State: track last processed position in transcript
        self.last_processed_position = 0
        self.load_config()

    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""
        return "neveragain.json"

    def load_config(self) -> Dict[str, Any]:
        """Load state"""
        state = super().load_config()
        self.last_processed_position = state.get("last_processed_position", 0)
        return state

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save state"""
        if config is None:
            config = {
                "last_processed_position": self.last_processed_position,
                "updated": datetime.now().isoformat(),
            }
        super().save_config(config)

    def handle_hook(self, hook_event: str, context: HookInput) -> Dict[str, Any]:
        """Handle Claude Code hook events"""
        self.logger.info(f"Handling hook event: {hook_event}")
        self.logger.debug(f"Hook context: {format_hook_context(context)}")

        if hook_event == "Stop":
            return self._handle_stop_hook(context)

        # Always allow other hooks to proceed
        return HookHandler.create_allow_response()

    def _handle_stop_hook(self, context: HookInput) -> Dict[str, Any]:
        """Handle Stop hook - analyze transcript for user corrections"""
        self.logger.info("Processing Stop hook for mistake learning")

        try:
            transcript_path = context.get("transcript_path")
            if not transcript_path or not os.path.exists(transcript_path):
                self.logger.warning(f"Transcript not found: {transcript_path}")
                return HookHandler.create_allow_response()

            # Parse transcript for new messages since last processing
            new_messages = self._parse_new_messages(transcript_path)
            
            if not new_messages:
                self.logger.debug("No new messages to process")
                return HookHandler.create_allow_response()

            # Analyze messages for user corrections (async, non-blocking)
            self._analyze_corrections_async(new_messages)

        except Exception as e:
            self.logger.error(f"Error in Stop hook: {e}")
            import traceback
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")

        # Always allow stopping - never block
        return HookHandler.create_allow_response()

    def _parse_new_messages(self, transcript_path: str) -> List[Dict[str, Any]]:
        """Parse transcript and get new messages since last processing"""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Find messages after last processed position
            new_messages = []
            current_position = 0
            current_message = None
            
            for line in lines:
                current_position += len(line)
                
                # Skip lines before last processed position
                if current_position <= self.last_processed_position:
                    continue
                
                line = line.strip()
                if not line:
                    continue

                # Try to parse as JSONL
                try:
                    data = json.loads(line)
                    if data.get("type") == "message":
                        role = data.get("role")
                        content = data.get("content", "")
                        
                        if role and content:
                            new_messages.append({
                                "role": role,
                                "content": content,
                                "timestamp": data.get("timestamp", "")
                            })
                except json.JSONDecodeError:
                    # Handle plain text format as fallback
                    if line.startswith("user: ") or line.startswith("assistant: "):
                        parts = line.split(": ", 1)
                        if len(parts) == 2:
                            role, content = parts
                            new_messages.append({
                                "role": role,
                                "content": content,
                                "timestamp": datetime.now().isoformat()
                            })

            # Update last processed position
            self.last_processed_position = current_position
            self.save_config()

            self.logger.info(f"Found {len(new_messages)} new messages")
            return new_messages

        except Exception as e:
            self.logger.error(f"Error parsing transcript: {e}")
            return []

    def _analyze_corrections_async(self, messages: List[Dict[str, Any]]) -> None:
        """Analyze messages for corrections and update memory (async)"""
        if not messages:
            return

        try:
            # Build conversation context
            conversation = []
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                conversation.append(f"{role}: {content}")

            conversation_text = "\n\n".join(conversation)

            # Create analysis prompt
            prompt = f"""Analyze the following conversation transcript and identify instances where the user is correcting the assistant regarding a mistake made by the assistant.

TRANSCRIPT:
{conversation_text}

TASK:
1. Look for patterns where:
   - The assistant made an error, assumption, or took an incorrect approach
   - The user corrected, disagreed with, or pointed out the mistake
   - The correction provides guidance on what should have been done instead

2. For each correction found, format it EXACTLY as shown below. Do not include any analysis, explanation, or additional text - just the formatted guidelines:

- <Clear description of the guideline to follow>

Good:
<Good example if applicable, or omit this section if no good example>

Bad:
<Bad example showing what NOT to do, or omit this section if no bad example>

3. If you find any corrections, respond with ONLY the formatted guidelines exactly as shown above. No additional text, analysis, or explanation.

4. If no corrections are found, respond with "NO_CORRECTIONS_FOUND".

Remember: Output ONLY the guidelines in the exact format shown, nothing else."""

            # Invoke Claude to analyze the corrections
            self.logger.info("Invoking Claude to analyze user corrections")
            
            # Set ORCH_PROJECT_DIR to preserve our project context in environment
            # This will be inherited by any subprocess calls
            original_orch_dir = os.environ.get("ORCH_PROJECT_DIR")
            os.environ["ORCH_PROJECT_DIR"] = self.working_dir
            
            try:
                response_data = invoke_claude(prompt=prompt)
                
                # Extract response text from the response data
                response_text = ""
                if isinstance(response_data, dict):
                    response_text = response_data.get("response", "") or response_data.get("content", "")
                else:
                    response_text = str(response_data)

                if response_text and response_text.strip() != "NO_CORRECTIONS_FOUND":
                    self._update_memory_file(response_text.strip())
                    self.logger.info("Updated memory with new corrections")
                else:
                    self.logger.debug("No corrections found in recent messages")
                    
            finally:
                # Restore original ORCH_PROJECT_DIR
                if original_orch_dir is not None:
                    os.environ["ORCH_PROJECT_DIR"] = original_orch_dir
                else:
                    os.environ.pop("ORCH_PROJECT_DIR", None)

        except Exception as e:
            self.logger.error(f"Error analyzing corrections: {e}")
            import traceback
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")

    def _update_memory_file(self, corrections: str) -> None:
        """Update the neveragain.md memory file with new corrections"""
        try:
            # Read existing content
            existing_content = ""
            if self.memory_file.exists():
                existing_content = self.memory_file.read_text(encoding='utf-8')

            # Create header if file is new
            if not existing_content.strip():
                existing_content = "# Must Follow Guidelines\n\nNo code shall violate the guidelines below. You MUST follow these guidelines at all times:\n\n"

            # Add new corrections without timestamp
            new_entry = f"\n{corrections}\n"

            # Write updated content
            updated_content = existing_content + new_entry
            self.memory_file.write_text(updated_content, encoding='utf-8')

            self.logger.info(f"Updated {self.memory_file} with new corrections")

        except Exception as e:
            self.logger.error(f"Error updating memory file: {e}")


def main() -> None:
    """CLI interface and hook handler"""
    if len(sys.argv) < 2:
        print("Claude Code Never Again Monitor")
        print("Usage: neveragain_monitor.py <command> [args]")
        print("\nCommands:")
        print("  hook <type>                     - Handle Claude Code hook")
        print("  status                          - Show memory file status")
        print("  view                           - View learned corrections")
        return

    monitor = NeverAgainMonitor()
    command = sys.argv[1]

    if command == "hook":
        if len(sys.argv) < 3:
            return

        hook_type = sys.argv[2]

        # Read context from stdin
        context = HookHandler.read_hook_input()

        # Handle the hook
        result = monitor.handle_hook(hook_type, context)

        # Output result
        HookHandler.write_hook_output(result)

    elif command == "status":
        print(f"📝 Never Again Monitor Status")
        print(f"📍 Memory file: {monitor.memory_file}")
        print(f"📊 Last processed position: {monitor.last_processed_position}")
        
        if monitor.memory_file.exists():
            size = monitor.memory_file.stat().st_size
            print(f"📄 Memory file size: {size} bytes")
        else:
            print("📄 Memory file: Not created yet")

    elif command == "view":
        if monitor.memory_file.exists():
            content = monitor.memory_file.read_text(encoding='utf-8')
            print(content)
        else:
            print("No corrections learned yet.")


if __name__ == "__main__":
    main()