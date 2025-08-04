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

# Handle special calibration commands
if [ "$1" = "tester" ] && [ "$2" = "calibrate" ]; then
    # Run tester calibration
    SCRIPT_DIR="$(dirname "$0")"
    CALIBRATION_SCRIPT="$SCRIPT_DIR/tester_calibrate.sh"
    
    # Create calibration script if it doesn't exist
    if [ ! -f "$CALIBRATION_SCRIPT" ]; then
        cat > "$CALIBRATION_SCRIPT" <<'CALIBRATION_EOF'
#!/bin/bash
# Tester Calibration Script for Orchestra

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRA_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Calibrating Tester extension for Orchestra project..."

# Create calibration data directory
CALIBRATION_DIR="$SCRIPT_DIR/.tester"
mkdir -p "$CALIBRATION_DIR"

# Generate calibration configuration
cat > "$CALIBRATION_DIR/calibration.json" <<'EOF'
{
    "project_type": "python",
    "test_framework": "pytest",
    "test_patterns": {
        "unit": "tests/unit/test_*.py",
        "integration": "tests/integration/test_*.py",
        "e2e": "tests/e2e/test_*.py"
    },
    "coverage_config": {
        "source": ["src/orchestra"],
        "omit": ["*/tests/*", "*/__pycache__/*"],
        "min_coverage": 80
    },
    "test_commands": {
        "unit": "uv run pytest tests/unit -v",
        "integration": "uv run pytest tests/integration -v",
        "e2e": "uv run pytest tests/e2e -v",
        "all": "uv run pytest -v",
        "coverage": "uv run pytest --cov=orchestra --cov-report=term-missing"
    },
    "code_quality": {
        "formatter": "black",
        "linter": "ruff",
        "type_checker": "mypy",
        "commands": {
            "format": "uv run black .",
            "lint": "uv run ruff check .",
            "typecheck": "uv run mypy src/"
        }
    },
    "markers": [
        "unit",
        "integration",
        "slow",
        "deviation_detection"
    ]
}
EOF

# Create test runner helper
cat > "$CALIBRATION_DIR/run_tests.sh" <<'EOF'
#!/bin/bash
# Test runner helper for Orchestra

ORCHESTRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ORCHESTRA_DIR"

COMMAND="${1:-all}"

case "$COMMAND" in
    unit)
        echo "Running unit tests..."
        uv run pytest tests/unit -v
        ;;
    integration)
        echo "Running integration tests..."
        uv run pytest tests/integration -v
        ;;
    e2e)
        echo "Running e2e tests..."
        uv run pytest tests/e2e -v
        ;;
    coverage)
        echo "Running tests with coverage..."
        uv run pytest --cov=orchestra --cov-report=term-missing
        ;;
    quick)
        echo "Running quick unit tests..."
        uv run pytest tests/unit -v -m "not slow"
        ;;
    all)
        echo "Running all tests..."
        uv run pytest -v
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Available commands: unit, integration, e2e, coverage, quick, all"
        exit 1
        ;;
esac
EOF

chmod +x "$CALIBRATION_DIR/run_tests.sh"

# Create tester configuration
cat > "$SCRIPT_DIR/tester.json" <<EOF
{
    "enabled": true,
    "calibrated": true,
    "calibration_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "project_root": "$ORCHESTRA_DIR",
    "calibration_dir": "$CALIBRATION_DIR",
    "test_runner": "$CALIBRATION_DIR/run_tests.sh"
}
EOF

echo ""
echo "✅ Tester calibration complete!"
echo ""
echo "Calibration files created:"
echo "  - $CALIBRATION_DIR/calibration.json"
echo "  - $CALIBRATION_DIR/run_tests.sh"
echo ""
echo "You can now run tests using:"
echo "  $CALIBRATION_DIR/run_tests.sh [unit|integration|e2e|coverage|quick|all]"
echo ""
CALIBRATION_EOF
        chmod +x "$CALIBRATION_SCRIPT"
    fi
    
    # Execute calibration
    exec "$CALIBRATION_SCRIPT"
    exit 0
fi

# For regular commands, check if orchestra is installed
if ! check_orchestra_installed; then
    show_install_instructions
    exit 1
fi

# Run orchestra with the provided arguments
exec orchestra "$@"
