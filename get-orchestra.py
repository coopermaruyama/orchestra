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
import shutil

def check_command_exists(cmd):
    """Check if a command exists in PATH"""
    return shutil.which(cmd) is not None

def run_command(cmd, capture_output=True):
    """Run a command and return success status"""
    try:
        if capture_output:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        else:
            subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception:
        return False

def main():
    print("🎼 Orchestra Quick Installer")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required (you have {sys.version_info.major}.{sys.version_info.minor})")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Check for pipx
    has_pipx = check_command_exists("pipx")
    
    # Install Orchestra
    print("\n📦 Installing Orchestra...")
    
    if has_pipx:
        print("✨ Found pipx - using isolated install (recommended)")
        
        # Try pipx install
        if run_command(["pipx", "install", "git+https://github.com/coopermaruyama/orchestra.git"]):
            print("✅ Orchestra installed successfully with pipx!")
        elif run_command(["pipx", "install", "--force", "git+https://github.com/coopermaruyama/orchestra.git"]):
            print("✅ Orchestra updated successfully with pipx!")
        else:
            print("⚠️  pipx install failed, falling back to pip...")
            has_pipx = False
    
    if not has_pipx:
        # Fall back to pip
        print("📦 Using pip for installation...")
        
        install_cmd = [
            sys.executable, "-m", "pip", "install", "--user", "--upgrade",
            "git+https://github.com/coopermaruyama/orchestra.git"
        ]
        
        if run_command(install_cmd):
            print("✅ Orchestra installed successfully with pip!")
        else:
            # Try with --break-system-packages for newer pip versions
            print("⚠️  Retrying with --break-system-packages...")
            install_cmd.insert(-1, "--break-system-packages")
            
            if run_command(install_cmd):
                print("✅ Orchestra installed successfully!")
            else:
                print("❌ Installation failed")
                print("\nPlease try manual installation:")
                print("  git clone https://github.com/coopermaruyama/orchestra.git")
                print("  cd orchestra")
                print("  pip install .")
                sys.exit(1)
    
    # Check if orchestra is in PATH
    if check_command_exists("orchestra"):
        print("✅ Orchestra is available in PATH")
    else:
        # Provide PATH instructions based on install method
        if has_pipx:
            print("\n⚠️  Orchestra installed but not in PATH")
            print("Run: pipx ensurepath")
            print("Then restart your terminal")
        else:
            user_base = subprocess.check_output([sys.executable, "-m", "site", "--user-base"]).decode().strip()
            user_bin = os.path.join(user_base, "bin")
            print(f"\n⚠️  Add to PATH: export PATH=\"$PATH:{user_bin}\"")
    
    print("\n🎉 Installation complete!")
    print("\nNext steps:")
    print("1. Enable all extensions:     orchestra enable")
    print("2. Or specific extension:     orchestra enable task")
    print("3. Use in Claude Code:        /task start")
    
    if not has_pipx:
        print("\n💡 Tip: Install pipx for better Python app management:")
        print("   python3 -m pip install --user pipx")
    
    print("\nFor more info: https://github.com/coopermaruyama/orchestra")

if __name__ == "__main__":
    main()