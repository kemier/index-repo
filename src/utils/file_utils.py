"""
Utility functions for file operations
"""
import os
import sys
from typing import List, Dict, Optional


def ensure_dir(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary
    
    Args:
        directory: Path to directory to ensure
    """
    if directory and not os.path.exists(directory):
        os.makedirs(directory)


def read_file_content(file_path: str) -> str:
    """
    Read the content of a file
    
    Args:
        file_path: Path to file to read
        
    Returns:
        String content of the file
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found")
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def write_file_content(file_path: str, content: str) -> None:
    """
    Write content to a file
    
    Args:
        file_path: Path to file to write
        content: Content to write to file
    """
    ensure_dir(os.path.dirname(file_path))
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def normalize_path(path: str) -> str:
    """
    Normalize a file path for the current operating system
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized path
    """
    # Convert to absolute path
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    
    # Normalize path separators
    return os.path.normpath(path)


def find_files(directory: str, pattern: str) -> List[str]:
    """
    Find files in a directory matching a pattern
    
    Args:
        directory: Directory to search
        pattern: File pattern to match (comma-separated)
        
    Returns:
        List of matching file paths
    """
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Directory {directory} not found")
    
    file_patterns = pattern.split(',')
    matching_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(p.replace('*', '')) for p in file_patterns):
                matching_files.append(os.path.join(root, file))
    
    return matching_files


def get_extension(file_path: str) -> str:
    """
    Get the extension of a file
    
    Args:
        file_path: Path to file
        
    Returns:
        File extension (with dot)
    """
    _, ext = os.path.splitext(file_path)
    return ext 