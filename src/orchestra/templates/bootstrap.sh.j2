#!/bin/sh
# Orchestra Bootstrap Script

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to find python executable
find_python() {
    if command_exists python3; then
        echo "python3"
    elif command_exists python; then
        echo "python"
    else
        echo ""
    fi
}

# Function to check if orchestra is installed
check_orchestra_installed() {
    command_exists orchestra
}

# Function to show install instructions
show_install_instructions() {
    FLAG_FILE="$HOME/.claude/.orchestra-install-shown"
    if [ -f "$FLAG_FILE" ]; then
        return
    fi

    echo "============================================================"
    echo "🎼 Orchestra not installed"
    echo "============================================================"
    echo ""
    echo "This project uses Orchestra extensions for Claude Code."
    echo ""
    echo "To install Orchestra globally:"
    echo "  pip install orchestra"
    echo ""
    echo "Or install from the project:"
    echo "  pip install -e ."
    echo ""
    echo "Then enable the task extension:"
    echo "  orchestra enable task"
    echo ""
    echo "For more info: https://github.com/anthropics/orchestra"
    echo "============================================================"

    mkdir -p "$(dirname "$FLAG_FILE")"
    touch "$FLAG_FILE"
}

# Main execution
if [ $# -lt 1 ]; then
    echo "Usage: bootstrap.sh <command> [args...]"
    exit 1
fi

# For hook commands, delegate to orchestra CLI
if [ "$1" = "hook" ]; then
    # Check if orchestra is installed
    if command -v orchestra >/dev/null 2>&1; then
        # Use orchestra hook command which handles all enabled monitors
        exec orchestra "$@"
    else
        # Fallback - try to run monitors directly
        PYTHON=$(find_python)
        if [ -z "$PYTHON" ]; then
            echo "Error: Python not found in PATH" >&2
            exit 127
        fi
        
        # Get script directory
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        
        # Try to find and run any monitor script for backward compatibility
        # This is a best-effort fallback when orchestra CLI is not available
        for ext in task timemachine tidy tester; do
            for script_path in "$SCRIPT_DIR/$ext/${ext}_monitor.py" "$HOME/.claude/orchestra/$ext/${ext}_monitor.py"; do
                if [ -f "$script_path" ]; then
                    # Run the first monitor found (not ideal but better than nothing)
                    exec "$PYTHON" "$script_path" "$@"
                fi
            done
        done
        
        echo "Error: Orchestra CLI not found and no monitor scripts available" >&2
        echo "Please install Orchestra: pip install orchestra" >&2
        exit 1
    fi
fi

# For regular commands, check if orchestra is installed
if ! check_orchestra_installed; then
    show_install_instructions
    exit 1
fi

# Run orchestra with the provided arguments
exec orchestra "$@"