#!/usr/bin/env python3
"""Orchestra Bootstrap Script"""
import sys
import subprocess
import os
from pathlib import Path

def check_orchestra_installed():
    try:
        result = subprocess.run(["which", "orchestra"], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except Exception:
        return False

def show_install_instructions():
    flag_file = Path.home() / ".claude" / ".orchestra-install-shown"
    if flag_file.exists():
        return
    print("=" * 60)
    print("🎼 Orchestra not installed")
    print("=" * 60)
    print("\nThis project uses Orchestra extensions for Claude Code.")
    print("\nTo install Orchestra globally:")
    print("  pip install orchestra")
    print("\nOr install from the project:")
    print("  pip install -e .")
    print("\nThen install the task-monitor extension:")
    print("  orchestra install task-monitor")
    print("\nFor more info: https://github.com/anthropics/orchestra")
    print("=" * 60)
    flag_file.parent.mkdir(parents=True, exist_ok=True)
    flag_file.touch()

def main():
    if len(sys.argv) < 2:
        print("Usage: bootstrap.py <command> [args...]")
        sys.exit(1)
    if not check_orchestra_installed():
        show_install_instructions()
        sys.exit(1)
    command = ["orchestra"] + sys.argv[1:]
    try:
        result = subprocess.run(command)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error running orchestra: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
