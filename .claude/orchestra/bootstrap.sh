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
    echo "Then install the task-monitor extension:"
    echo "  orchestra install task-monitor"
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

# For hook commands, we need to run the Python script directly
if [ "$1" = "hook" ]; then
    PYTHON=$(find_python)
    if [ -z "$PYTHON" ]; then
        echo "Error: Python not found in PATH" >&2
        exit 127
    fi
    
    # Find the task_monitor.py script
    SCRIPT_DIR="$(dirname "$0")"
    LOCAL_SCRIPT="$SCRIPT_DIR/task-monitor/task_monitor.py"
    GLOBAL_SCRIPT="$HOME/.claude/orchestra/task-monitor/task_monitor.py"
    
    if [ -f "$LOCAL_SCRIPT" ]; then
        TASK_MONITOR="$LOCAL_SCRIPT"
    elif [ -f "$GLOBAL_SCRIPT" ]; then
        TASK_MONITOR="$GLOBAL_SCRIPT"
    else
        echo "Error: task_monitor.py not found" >&2
        exit 1
    fi
    
    # Execute the hook
    exec "$PYTHON" "$TASK_MONITOR" "$@"
fi

# For regular commands, check if orchestra is installed
if ! check_orchestra_installed; then
    show_install_instructions
    exit 1
fi

# Run orchestra with the provided arguments
exec orchestra "$@"
