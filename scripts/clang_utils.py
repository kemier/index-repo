#!/usr/bin/env python
"""
Consolidated Clang utilities for the code indexing system.
This script combines functionality from:
- setup_clang.py
- find_libclang.py

It provides tools for finding libclang, configuring the Python bindings,
and setting up the Clang environment for code analysis.
"""
import os
import sys
import glob
import platform
import subprocess
from pathlib import Path

def find_libclang():
    """
    Find libclang.so (or libclang.dll on Windows) in the system.
    
    Returns:
        str: Path to libclang directory
    """
    # Common paths where libclang might be found
    common_paths = [
        "/usr/lib/llvm*/lib",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu",
        "/usr/lib/i386-linux-gnu",
        "/usr/local/lib",
        "C:/Program Files/LLVM/lib",
        "C:/Program Files (x86)/LLVM/lib"
    ]
    
    # Check for platform
    is_windows = platform.system() == "Windows"
    lib_file = "libclang.dll" if is_windows else "libclang.so"
    symlink_file = "libclang.dll" if is_windows else "libclang.so"
    
    # First, try to find using ldconfig on Linux
    if not is_windows:
        try:
            cmd = ["ldconfig", "-p"]
            output = subprocess.check_output(cmd, universal_newlines=True)
            for line in output.splitlines():
                if "libclang.so" in line:
                    path = line.split("=>")[-1].strip()
                    lib_path = path.strip()
                    print(f"Found libclang using ldconfig: {lib_path}")
                    return os.path.dirname(lib_path)
        except (subprocess.SubprocessError, FileNotFoundError):
            print("Could not use ldconfig to find libclang.so")
    
    # On macOS, check Homebrew locations
    if platform.system() == "Darwin":
        homebrew_paths = [
            "/usr/local/opt/llvm/lib",
            "/opt/homebrew/opt/llvm/lib"
        ]
        common_paths.extend(homebrew_paths)
    
    # Try to find libclang in common paths
    found_libs = []
    for path_pattern in common_paths:
        for path in glob.glob(path_pattern):
            # Check for libclang.so or libclang.so.1 or similar
            for lib in glob.glob(os.path.join(path, f"{lib_file}*")):
                found_libs.append(lib)
    
    if not found_libs:
        print("Could not find libclang in common paths.")
        return None
    
    # Sort by name to prefer libclang.so over versioned ones
    found_libs.sort(key=lambda x: len(x))
    lib_path = found_libs[0]
    lib_dir = os.path.dirname(lib_path)
    
    # Check if a symlink is needed
    symlink_path = os.path.join(lib_dir, symlink_file)
    if not os.path.exists(symlink_path):
        try:
            print(f"Creating symlink {symlink_path} -> {lib_path}")
            if is_windows:
                # Windows needs administrator privileges for symlinks
                # Just inform the user
                print(f"On Windows, please create a copy or symlink of {lib_path} to {symlink_path} manually")
            else:
                # Create the symlink on Linux/macOS
                os.symlink(os.path.basename(lib_path), symlink_path)
        except Exception as e:
            print(f"Failed to create symlink: {e}")
            print(f"Please create it manually: ln -s {lib_path} {symlink_path}")
    
    print(f"Using libclang from: {lib_dir}")
    return lib_dir

def install_clang():
    """
    Install Clang if not already installed.
    This will attempt to use the appropriate package manager for the current OS.
    """
    system = platform.system()
    
    if system == "Linux":
        # Detect distribution
        try:
            with open("/etc/os-release") as f:
                os_release = f.read()
                is_debian = "debian" in os_release.lower() or "ubuntu" in os_release.lower()
                is_fedora = "fedora" in os_release.lower() or "redhat" in os_release.lower()
                is_arch = "arch" in os_release.lower()
        except FileNotFoundError:
            print("Could not determine Linux distribution. Please install Clang manually.")
            return
        
        if is_debian:
            print("Detected Debian/Ubuntu system.")
            print("Installing Clang and libclang development files...")
            subprocess.check_call(["sudo", "apt", "update"])
            subprocess.check_call(["sudo", "apt", "install", "-y", "clang", "libclang-dev"])
        elif is_fedora:
            print("Detected Fedora/RHEL system.")
            print("Installing Clang and libclang development files...")
            subprocess.check_call(["sudo", "dnf", "install", "-y", "clang", "clang-devel"])
        elif is_arch:
            print("Detected Arch Linux system.")
            print("Installing Clang and libclang development files...")
            subprocess.check_call(["sudo", "pacman", "-Sy", "clang"])
        else:
            print("Unsupported Linux distribution. Please install Clang manually.")
    
    elif system == "Darwin":
        # macOS
        print("Installing Clang on macOS via Homebrew...")
        try:
            subprocess.check_call(["brew", "install", "llvm"])
            print("LLVM/Clang installed successfully via Homebrew.")
        except Exception:
            print("Failed to install via Homebrew. Please install LLVM/Clang manually.")
    
    elif system == "Windows":
        print("On Windows, please download and install LLVM/Clang from: https://llvm.org/builds/")
        print("Make sure to add LLVM bin directory to your PATH.")
    
    else:
        print(f"Unsupported system: {system}. Please install Clang manually.")
    
    print("Clang installation complete.\n")

def install_requirements():
    """Install Python requirements."""
    print("Installing Python requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Requirements installed successfully.\n")
    except subprocess.CalledProcessError:
        print("Failed to install requirements. Please check your pip installation and try again.\n")

def setup_configuration():
    """Configure the project to use the installed libclang."""
    # Find libclang
    libclang_dir = find_libclang()
    
    if not libclang_dir:
        print("Error: Could not find libclang. Please install Clang and try again.")
        return False
    
    # Create config directory if it doesn't exist
    config_dir = os.path.join("src", "config")
    os.makedirs(config_dir, exist_ok=True)
    
    # Create a local configuration file
    config_file = os.path.join(config_dir, "libclang_config.py")
    with open(config_file, "w") as f:
        f.write(f"""\"\"\"
Libclang configuration.
Auto-generated by clang_utils.py.
\"\"\"

# Path to libclang directory
LIBCLANG_PATH = "{libclang_dir}"

def configure_libclang():
    \"\"\"Configure libclang to use the detected library.\"\"\"
    from clang.cindex import Config
    Config.set_library_path(LIBCLANG_PATH)
""")
    
    print(f"Configuration saved to: {config_file}")
    return True

def verify_installation():
    """Verify that libclang is correctly installed and configured."""
    print("Verifying libclang installation...")
    try:
        # Try to import and use clang.cindex
        import clang.cindex
        from clang.cindex import Config, Index
        
        # Set library path
        libclang_dir = find_libclang()
        if not libclang_dir:
            return False
            
        Config.set_library_path(libclang_dir)
        
        # Try to create an index
        idx = Index.create()
        print("Libclang is correctly installed and configured!")
        print(f"Using libclang from: {libclang_dir}")
        return True
    except ImportError:
        print("Error: clang.cindex module not found. Please install the Python bindings for libclang.")
        print("Run: pip install clang")
        return False
    except Exception as e:
        print(f"Error verifying libclang installation: {e}")
        return False

def parse_args():
    """Parse command line arguments."""
    import argparse
    parser = argparse.ArgumentParser(description="Clang utilities for code indexing setup")
    parser.add_argument("--find", action="store_true", help="Find libclang location")
    parser.add_argument("--install", action="store_true", help="Install Clang (if not already installed)")
    parser.add_argument("--setup", action="store_true", help="Setup the configuration")
    parser.add_argument("--verify", action="store_true", help="Verify the installation")
    parser.add_argument("--all", action="store_true", help="Perform all actions")
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    
    # If no specific arguments are provided, show help
    if not any([args.find, args.install, args.setup, args.verify, args.all]):
        print("Clang Utilities for Code Indexing Setup")
        print("======================================\n")
        print("Usage examples:")
        print("  Find libclang: python clang_utils.py --find")
        print("  Install Clang: python clang_utils.py --install")
        print("  Setup config: python clang_utils.py --setup")
        print("  Verify installation: python clang_utils.py --verify")
        print("  Do all: python clang_utils.py --all\n")
        return
    
    if args.find or args.all:
        print("\n=== Finding libclang ===")
        libclang_dir = find_libclang()
        if libclang_dir:
            print(f"Found libclang at: {libclang_dir}")
        else:
            print("Failed to find libclang")
    
    if args.install or args.all:
        print("\n=== Installing Clang ===")
        install_clang()
    
    if args.setup or args.all:
        print("\n=== Setting up configuration ===")
        setup_configuration()
    
    if args.verify or args.all:
        print("\n=== Verifying installation ===")
        if verify_installation():
            print("Verification successful!")
        else:
            print("Verification failed!")
    
    if args.all:
        print("\nAll tasks completed!")

if __name__ == "__main__":
    main() 