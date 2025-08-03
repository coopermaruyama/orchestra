#!/bin/sh
# Orchestra Installer Script
# Usage: curl -sSL https://raw.githubusercontent.com/coopermaruyama/orchestra/main/install.sh | sh
#    or: wget -qO- https://raw.githubusercontent.com/coopermaruyama/orchestra/main/install.sh | sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "${BLUE}🎼 Orchestra Installer${NC}"
echo "===================================="
echo ""

# Check for required tools
check_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "${RED}❌ Error: $1 is required but not installed.${NC}"
        echo "Please install $1 and try again."
        exit 1
    fi
}

# Check Python
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
    else
        echo "${RED}❌ Error: Python is required but not installed.${NC}"
        echo "Please install Python 3.8+ and try again."
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 8 ]); then
        echo "${RED}❌ Error: Python 3.8+ is required (found $PYTHON_VERSION)${NC}"
        exit 1
    fi
    
    echo "✅ Found Python $PYTHON_VERSION"
}

# Check for required commands
check_command git
check_command curl
check_python

# Check for pipx first
HAS_PIPX=0
if command -v pipx >/dev/null 2>&1; then
    echo "✅ Found pipx (recommended)"
    HAS_PIPX=1
elif ! $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
    echo "${RED}❌ Error: pip is required but not installed.${NC}"
    echo "Installing pip..."
    curl -sSL https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo ""
echo "📦 Downloading Orchestra..."

# Clone the repository
cd "$TEMP_DIR"
if ! git clone --depth 1 https://github.com/coopermaruyama/orchestra.git >/dev/null 2>&1; then
    echo "${RED}❌ Error: Failed to download Orchestra${NC}"
    echo "Please check your internet connection and try again."
    exit 1
fi

cd orchestra

echo "🔧 Installing Orchestra..."

# Install with pipx or pip
if [ "$HAS_PIPX" = "1" ]; then
    echo "📦 Using pipx for isolated installation..."
    
    if pipx install . >/dev/null 2>&1; then
        echo "${GREEN}✅ Orchestra installed successfully with pipx!${NC}"
    elif pipx install --force . >/dev/null 2>&1; then
        echo "${GREEN}✅ Orchestra updated successfully with pipx!${NC}"
    else
        echo "${YELLOW}⚠️  pipx install failed, falling back to pip...${NC}"
        HAS_PIPX=0
    fi
fi

if [ "$HAS_PIPX" = "0" ]; then
    echo "📦 Using pip for installation..."
    
    if $PYTHON_CMD -m pip install --user . >/dev/null 2>&1; then
        echo "${GREEN}✅ Orchestra installed successfully!${NC}"
    else
        echo "${YELLOW}⚠️  User install failed, trying with --break-system-packages...${NC}"
        if $PYTHON_CMD -m pip install --user --break-system-packages . >/dev/null 2>&1; then
            echo "${GREEN}✅ Orchestra installed successfully!${NC}"
        else
            echo "${RED}❌ Error: Failed to install Orchestra${NC}"
            echo "Please try manual installation:"
            echo "  git clone https://github.com/coopermaruyama/orchestra.git"
            echo "  cd orchestra"
            echo "  pip install ."
            exit 1
        fi
    fi
fi

# Check if orchestra is in PATH
if ! command -v orchestra >/dev/null 2>&1; then
    echo ""
    echo "${YELLOW}⚠️  Orchestra installed but not in PATH${NC}"
    echo ""
    
    if [ "$HAS_PIPX" = "1" ]; then
        # pipx specific instructions
        echo "Run the following command:"
        echo ""
        echo "  ${GREEN}pipx ensurepath${NC}"
        echo ""
        echo "Then restart your terminal or reload your shell configuration."
    else
        # pip specific instructions
        # Detect shell and provide instructions
        if [ -n "$BASH_VERSION" ]; then
            SHELL_RC="$HOME/.bashrc"
            SHELL_NAME="bash"
        elif [ -n "$ZSH_VERSION" ]; then
            SHELL_RC="$HOME/.zshrc"
            SHELL_NAME="zsh"
        else
            SHELL_RC="$HOME/.profile"
            SHELL_NAME="sh"
        fi
        
        # Find where pip installed the script
        USER_BASE=$($PYTHON_CMD -m site --user-base)
        USER_BIN="$USER_BASE/bin"
        
        if [ -f "$USER_BIN/orchestra" ]; then
            echo "Add the following to your $SHELL_RC:"
            echo ""
            echo "  export PATH=\"\$PATH:$USER_BIN\""
            echo ""
            echo "Then reload your shell:"
            echo "  source $SHELL_RC"
            echo ""
            echo "Or for immediate use, run:"
            echo "  export PATH=\"\$PATH:$USER_BIN\""
        fi
    fi
fi

echo ""
echo "${BLUE}🎼 Orchestra Installation Complete!${NC}"
echo ""
echo "Next steps:"
echo "1. ${YELLOW}Enable all extensions:${NC}"
echo "   ${GREEN}orchestra enable${NC}"
echo ""
echo "2. ${YELLOW}Or enable specific extensions:${NC}"
echo "   ${GREEN}orchestra enable task${NC}        # Task focus & tracking"
echo "   ${GREEN}orchestra enable timemachine${NC} # Conversation checkpoints"
echo "   ${GREEN}orchestra enable tester${NC}      # Automated testing"
echo ""
echo "3. ${YELLOW}Use in Claude Code:${NC}"
echo "   ${GREEN}/task start${NC}      # Start a focused task"
echo "   ${GREEN}/timemachine list${NC} # View checkpoints"
echo "   ${GREEN}/tester calibrate${NC} # Set up testing"
echo ""

if [ "$HAS_PIPX" = "0" ]; then
    echo "💡 ${YELLOW}Tip:${NC} For better Python app isolation, install pipx:"
    echo "   ${GREEN}$PYTHON_CMD -m pip install --user pipx${NC}"
    echo ""
fi

echo "For more info: https://github.com/coopermaruyama/orchestra"
echo ""