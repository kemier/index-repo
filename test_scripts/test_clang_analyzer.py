#!/usr/bin/env python
"""
Test script for the Clang analyzer.
"""
import os
import sys
import argparse

# Add parent directory to path to help with imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.services.clang_analyzer_service import ClangAnalyzerService
    from src.services.neo4j_service import Neo4jService
    from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    IMPORTS_AVAILABLE = True
except ImportError:
    print("Warning: Unable to import project modules. Using minimal functionality.")
    IMPORTS_AVAILABLE = False
    # Define fallback values
    NEO4J_URI = "bolt://localhost:7688"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "password"


class SimpleFunction:
    """A simple function representation for when the full module isn't available."""
    def __init__(self, name, file_path=None, line_number=None, signature=None):
        self.name = name
        self.file_path = file_path
        self.line_number = line_number
        self.signature = signature
        self.calls = set()
        self.called_by = set()


class SimpleCallGraph:
    """A simple call graph representation."""
    def __init__(self):
        self.functions = {}
    
    def add_function(self, name, file_path=None, line_number=None, signature=None):
        if name not in self.functions:
            self.functions[name] = SimpleFunction(name, file_path, line_number, signature)
        return self.functions[name]
    
    def add_call(self, caller, callee):
        if caller in self.functions and callee in self.functions:
            self.functions[caller].calls.add(callee)
            self.functions[callee].called_by.add(caller)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test Clang analyzer functionality")
    parser.add_argument("path", nargs="?", help="Path to file or directory to analyze")
    parser.add_argument("--project", default="test_clang", help="Project name for indexing")
    parser.add_argument("--clear", action="store_true", help="Clear existing project data before indexing")
    parser.add_argument("--include-dirs", nargs="+", help="Include directories for Clang analysis")
    parser.add_argument("--compiler-args", nargs="+", help="Additional compiler arguments for Clang")
    parser.add_argument("--no-index", action="store_true", help="Skip Neo4j indexing (just show analysis results)")
    parser.add_argument("--function", help="Function to find neighbors for")
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


def main():
    """Main entry point."""
    args = parse_args()
    
    if not IMPORTS_AVAILABLE:
        print("Error: Required modules not available. Please install the project dependencies.")
        print("Try running: pip install -r requirements.txt")
        return 1
    
    if not args.path:
        print("Error: Please provide a path to a file or directory to analyze.")
        return 1
    
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
            
            # Show call hierarchy
            print("\nCallees (functions called by this function):")
            for callee_name in func.calls:
                if callee_name in call_graph.functions:
                    callee = call_graph.functions[callee_name]
                    display_function_details(callee, indent=2)
                else:
                    print(f"  {callee_name} (external)")
            
            print("\nCallers (functions that call this function):")
            for caller_name in func.called_by:
                if caller_name in call_graph.functions:
                    caller = call_graph.functions[caller_name]
                    display_function_details(caller, indent=2)
        else:
            print(f"Function '{args.function}' not found in the analyzed code.")
    else:
        print("\nTop-level functions:")
        for func_name, func in call_graph.functions.items():
            if not func.called_by:
                display_function_details(func)
                print()
    
    # Index in Neo4j if requested
    if not args.no_index:
        try:
            neo4j_service = Neo4jService(
                uri=NEO4J_URI,
                username=NEO4J_USER,
                password=NEO4J_PASSWORD
            )
            
            print(f"\nIndexing functions in Neo4j (project: {args.project})...")
            neo4j_service.index_clang_callgraph(call_graph, args.project, args.clear)
            print("Indexing complete.")
        except Exception as e:
            print(f"Error during Neo4j indexing: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 