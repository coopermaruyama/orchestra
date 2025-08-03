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

# For hook commands, we need to run the Python script directly
if [ "$1" = "hook" ]; then
    PYTHON=$(find_python)
    if [ -z "$PYTHON" ]; then
        echo "Error: Python not found in PATH" >&2
        exit 127
    fi

    # Determine which extension is being called based on which scripts exist
    SCRIPT_DIR="$(dirname "$0")"
    MONITOR_SCRIPT=""

    # Check for task monitor
    LOCAL_TASK="$SCRIPT_DIR/task/task_monitor.py"
    GLOBAL_TASK="$HOME/.claude/orchestra/task/task_monitor.py"

    # Check for timemachine monitor
    LOCAL_TM="$SCRIPT_DIR/timemachine/timemachine_monitor.py"
    GLOBAL_TM="$HOME/.claude/orchestra/timemachine/timemachine_monitor.py"

    # Check for tidy monitor
    LOCAL_TIDY="$SCRIPT_DIR/tidy/tidy_monitor.py"
    GLOBAL_TIDY="$HOME/.claude/orchestra/tidy/tidy_monitor.py"

    # Check for tester monitor
    LOCAL_TESTER="$SCRIPT_DIR/tester/tester_monitor.py"
    GLOBAL_TESTER="$HOME/.claude/orchestra/tester/tester_monitor.py"

    # Priority: local task, global task, local timemachine, global timemachine, local tidy, global tidy, local tester, global tester
    if [ -f "$LOCAL_TASK" ]; then
        MONITOR_SCRIPT="$LOCAL_TASK"
    elif [ -f "$GLOBAL_TASK" ]; then
        MONITOR_SCRIPT="$GLOBAL_TASK"
    elif [ -f "$LOCAL_TM" ]; then
        MONITOR_SCRIPT="$LOCAL_TM"
    elif [ -f "$GLOBAL_TM" ]; then
        MONITOR_SCRIPT="$GLOBAL_TM"
    elif [ -f "$LOCAL_TIDY" ]; then
        MONITOR_SCRIPT="$LOCAL_TIDY"
    elif [ -f "$GLOBAL_TIDY" ]; then
        MONITOR_SCRIPT="$GLOBAL_TIDY"
    elif [ -f "$LOCAL_TESTER" ]; then
        MONITOR_SCRIPT="$LOCAL_TESTER"
    elif [ -f "$GLOBAL_TESTER" ]; then
        MONITOR_SCRIPT="$GLOBAL_TESTER"
    else
        echo "Error: No monitor script found" >&2
        exit 1
    fi

    # Execute the hook
    exec "$PYTHON" "$MONITOR_SCRIPT" "$@"
fi

# For regular commands, check if orchestra is installed
if ! check_orchestra_installed; then
    show_install_instructions
    exit 1
fi

# Run orchestra with the provided arguments
exec orchestra "$@"
