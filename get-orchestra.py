#!/usr/bin/env python3
"""
Orchestra Quick Installer
Cross-platform installation script

Usage:
    curl -sSL https://raw.githubusercontent.com/coopermaruyama/orchestra/main/get-orchestra.py | python3
    wget -qO- https://raw.githubusercontent.com/coopermaruyama/orchestra/main/get-orchestra.py | python3
"""

import subprocess
import sys
import os

def main():
    print("🎼 Orchestra Quick Installer")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required (you have {sys.version_info.major}.{sys.version_info.minor})")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install Orchestra
    print("\n📦 Installing Orchestra...")
    
    install_cmd = [
        sys.executable, "-m", "pip", "install", "--user", "--upgrade",
        "git+https://github.com/coopermaruyama/orchestra.git"
    ]
    
    try:
        subprocess.check_call(install_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print("✅ Orchestra installed successfully!")
    except subprocess.CalledProcessError:
        # Try with --break-system-packages for newer pip versions
        print("⚠️  Retrying with --break-system-packages...")
        install_cmd.insert(-1, "--break-system-packages")
        try:
            subprocess.check_call(install_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            print("✅ Orchestra installed successfully!")
        except subprocess.CalledProcessError as e:
            print("❌ Installation failed")
            print("\nPlease try manual installation:")
            print("  git clone https://github.com/coopermaruyama/orchestra.git")
            print("  cd orchestra")
            print("  pip install .")
            sys.exit(1)
    
    # Check if orchestra is in PATH
    user_base = subprocess.check_output([sys.executable, "-m", "site", "--user-base"]).decode().strip()
    user_bin = os.path.join(user_base, "bin")
    orchestra_path = os.path.join(user_bin, "orchestra")
    
    print("\n🎉 Installation complete!")
    print("\nNext steps:")
    print("1. Enable all extensions:     orchestra enable")
    print("2. Or specific extension:     orchestra enable task")
    print("3. Use in Claude Code:        /task start")
    
    if not os.path.exists(orchestra_path):
        print(f"\n⚠️  Add to PATH: export PATH=\"$PATH:{user_bin}\"")
    
    print("\nFor more info: https://github.com/coopermaruyama/orchestra")

if __name__ == "__main__":
    main()