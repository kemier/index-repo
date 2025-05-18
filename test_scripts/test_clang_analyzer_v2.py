#!/usr/bin/env python
"""
Test script for the Clang analyzer with improved function call relationship detection.
"""
import os
import sys
import argparse
from src.services.clang_analyzer_service import ClangAnalyzerService


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test Clang analyzer functionality")
    parser.add_argument("path", help="Path to file or directory to analyze")
    parser.add_argument("--function", help="Function to find neighbors for")
    parser.add_argument("--include-dirs", nargs="+", help="Include directories for Clang analysis")
    parser.add_argument("--compiler-args", nargs="+", help="Additional compiler arguments for Clang analysis")
    return parser.parse_args()


def display_function_details(func, indent=0):
    """Display function details."""
    spaces = " " * indent
    print(f"{spaces}{func.name}")
    print(f"{spaces}  File: {func.file_path}")
    print(f"{spaces}  Line: {func.line_number}")
    print(f"{spaces}  Signature: {func.signature}")
    print(f"{spaces}  Calls ({len(func.calls)}):")
    for called in func.calls:
        print(f"{spaces}    - {called}")
    print(f"{spaces}  Called by ({len(func.called_by)}):")
    for caller in func.called_by:
        print(f"{spaces}    - {caller}")


def visualize_call_tree(call_graph, root_function, max_depth=2, current_depth=0, visited=None):
    """Visualize the call tree starting from a root function."""
    if visited is None:
        visited = set()
    
    if root_function not in call_graph.functions or current_depth > max_depth:
        return
    
    if root_function in visited:
        print("  " * current_depth + f"{root_function} (recursive call)")
        return
        
    func = call_graph.functions[root_function]
    visited.add(root_function)
    
    # Print the current function with indentation
    prefix = "  " * current_depth
    print(f"{prefix}└─ {root_function} ({func.file_path}:{func.line_number})")
    
    # Print all called functions
    for called_func in func.calls:
        visualize_call_tree(call_graph, called_func, max_depth, current_depth + 1, visited.copy())


def main():
    """Main entry point."""
    args = parse_args()
    
    # Initialize the Clang analyzer
    analyzer = ClangAnalyzerService()
    
    # Set up compiler arguments
    include_dirs = args.include_dirs if args.include_dirs else []
    compiler_args = args.compiler_args if args.compiler_args else []
    
    print(f"Analyzing {args.path}...")
    
    # Analyze the file or directory
    if os.path.isdir(args.path):
        call_graph = analyzer.analyze_directory(args.path, include_dirs=include_dirs, compiler_args=compiler_args)
    else:
        call_graph = analyzer.analyze_file(args.path, include_dirs=include_dirs, compiler_args=compiler_args)
    
    print(f"Analysis complete. Found {len(call_graph.functions)} functions.")
    
    # Display function details
    if args.function:
        if args.function in call_graph.functions:
            func = call_graph.functions[args.function]
            print("\nFunction details:")
            display_function_details(func)
            
            # Show call tree
            print("\nFunction call tree:")
            visualize_call_tree(call_graph, args.function)
            
            # Show callees (functions called by this function)
            print("\nCallees (functions called by this function):")
            for callee_name in func.calls:
                if callee_name in call_graph.functions:
                    callee = call_graph.functions[callee_name]
                    display_function_details(callee, indent=2)
                else:
                    print(f"  {callee_name} (external)")
            
            # Show callers (functions that call this function)
            print("\nCallers (functions that call this function):")
            for caller_name in func.called_by:
                if caller_name in call_graph.functions:
                    caller = call_graph.functions[caller_name]
                    display_function_details(caller, indent=2)
                else:
                    print(f"  {caller_name} (external)")
        else:
            print(f"Function '{args.function}' not found in the analyzed code.")
    else:
        print("\nAll functions:")
        for func_name, func in sorted(call_graph.functions.items()):
            display_function_details(func)
            print()


if __name__ == "__main__":
    main() 