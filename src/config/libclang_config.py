"""
Configure libclang path for clang-based code analysis.
"""
import os
import glob
import platform
from clang.cindex import Config

def configure_libclang():
    """
    Configure libclang path.
    
    Tries to find and set the libclang library path in the following order:
    1. User-specified paths in E:\\Program Files\\LLVM
    2. Common installation locations
    3. System PATH
    """
    # Get system info
    is_windows = platform.system() == "Windows"
    lib_ext = ".dll" if is_windows else ".so"
    
    # Normalize path format for the OS
    def normalize_path(path):
        return os.path.normpath(path)
    
    # User-specified path - handle both with and without quotes
    llvm_path = normalize_path(r"E:\Program Files\LLVM")
    if not os.path.exists(llvm_path):
        llvm_path = normalize_path("E:\\Program Files\\LLVM")
    
    # List of paths to try in order
    potential_paths = []
    
    # User-specified path
    if os.path.exists(llvm_path):
        # Try to find libclang.dll in the bin directory
        potential_paths.append(os.path.join(llvm_path, "bin", f"libclang{lib_ext}"))
        
        # Try to find version-specific DLLs in bin directory
        potential_paths.extend(glob.glob(os.path.join(llvm_path, "bin", f"libclang*{lib_ext}")))
        
        # Also check the lib directory
        potential_paths.append(os.path.join(llvm_path, "lib", f"libclang{lib_ext}"))
        potential_paths.extend(glob.glob(os.path.join(llvm_path, "lib", f"libclang*{lib_ext}")))
    
    # Additional Windows-specific paths
    if is_windows:
        # Standard installation paths
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        
        for pf in [program_files, program_files_x86]:
            potential_paths.append(os.path.join(pf, "LLVM", "bin", "libclang.dll"))
            potential_paths.extend(glob.glob(os.path.join(pf, "LLVM", "bin", "libclang*.dll")))
    else:
        # Unix-like paths
        for prefix in ["/usr/lib", "/usr/local/lib", "/usr/lib/llvm/lib"]:
            potential_paths.append(os.path.join(prefix, "libclang.so"))
            potential_paths.extend(glob.glob(os.path.join(prefix, "libclang-*.so")))
    
    # Try each path in order
    for path in potential_paths:
        if os.path.exists(path):
            try:
                Config.set_library_file(path)
                print(f"Configured libclang to use {path}")
                return True
            except Exception as e:
                print(f"Could not use {path}: {e}")
                continue
    
    # If not found, try to load from PATH as a last resort
    try:
        if is_windows:
            lib_name = "libclang.dll"
        else:
            lib_name = "libclang.so"
            
        Config.set_library_file(lib_name)
        print(f"Configured libclang to use {lib_name} from PATH")
        return True
    except Exception as e:
        print(f"Warning: Could not find libclang: {e}")
        print("Some functionality may be limited.")
        return False

if __name__ == "__main__":
    configure_libclang() 