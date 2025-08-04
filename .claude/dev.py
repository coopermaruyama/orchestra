# mypy: ignore-errors
import json
import os
import sys
from typing import Any, Dict

class HookCompatibleInput:
    def __init__(self, stdin: str):
        self.stdin = stdin
        self.last_prompt_id = -1
        self.response_by_id: Dict[int, Dict[str, Any]] = {}
    def read(self) -> str:
        return self.stdin

    def isatty(self) -> bool:
        return False
    def _input(self, id: int, prompt: str, current_input: str) -> str:
        """behaves like input() in tty mode, but is compatible with Claude Code hooks"""
        if os.isatty(0):
            # If we're in a TTY, just use the normal input
            return input(prompt)
        if self.last_prompt_id == id:
            return current_input
        elif self.last_prompt_id == id - 1:
            # If we're not in a TTY, we need to use the Claude Code hooks
            print('{"continue": true, ' \
            '"decision": "block", ' \
            '"stopReason": "Enable auto-fix? [y/n]", ' \
            '"suppressOutput": false, ' \
            '"output": "Please provide more information.",' \
            '"hookSpecificOutput": {' \
                '"hookEventName": "UserPromptSubmit",' \
                '"additionalContext": "Add to context"}' \
            '}', file=sys.stdout)
        elif self.last_prompt_id < id - 1:
            match = self.response_by_id.get(id - 1, {})
            if match:
                return match.get("output", current_input)
        self.last_prompt_id = id
        return current_input
# for testing purposes: print stdin and whether we are in a tty
def print_stdin_and_tty():
    # Use JSON output to block with a specific reason
    output = {
        "decision": "block",
        "reason": f"what is your name? [John Doe]"
    }
    print(json.dumps(output))
    sys.exit(0)
    # write out json to hook
    print('{"continue": false, ' \
    '"decision": "block", ' \
    '"reason": "Enable auto-fix? [y/n]", ' \
    '"suppressOutput": false}' \
    # '"output": "Please provide more information.",' \
    , file=sys.stdout)
    print("STDIN:", os.read(0, 1024).decode('utf-8'))
    print("Is TTY:", os.isatty(0))
    svc = HookCompatibleInput(sys.stdin.read())
    is_autofix = svc._input(1, "Should I auto-fix? [y/n]", "n")
    name = svc._input(2, "What is your name?", "John Doe")
    age = svc._input(3, "What is your age?", "30")
    print(f"Auto-fix: {is_autofix}, Name: {name}, Age: {age}")
    # os._exit(2)  # Use _exit to avoid flushing stdio buffers which could interfere with the output
    # exit with a success code
    # write to stderr to indicate success
    # print("should i auto-fix? [y/n]", file=sys.stderr)
    # exit with code 2
    # os._exit(0)  # Use _exit to avoid flushing stdio buffers which could interfere with the output
    # os._exit(2) is used instead of os.exit
    # exit(2)
if __name__ == "__main__":
    print_stdin_and_tty()