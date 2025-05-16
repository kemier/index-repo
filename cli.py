#!/usr/bin/env python
import os
import sys
import json
import glob
import argparse
from pathlib import Path
from src.main import CodeAnalysisSystem

class CodeAnalysisCLI:
    """Command-line interface for the C/C++ code analysis system."""
    
    def __init__(self):
        """Initialize the code analysis CLI."""
        self.system = CodeAnalysisSystem()
        self.project_analyzed = False
    
    def analyze_project(self, project_path, file_patterns=None, compile_args=None, recursive=False):
        """
        Analyze a C/C++ project.
        
        Args:
            project_path: Path to the project directory
            file_patterns: List of file patterns to include
            compile_args: Optional compilation arguments
            recursive: Whether to search for files recursively
        """
        # Default file patterns if none provided
        if not file_patterns:
            file_patterns = ["*.cpp", "*.h", "*.hpp", "*.c", "*.cc"]
        
        # Default compile arguments if none provided
        if not compile_args:
            compile_args = ["-std=c++17"]
        
        # Resolve project path
        abs_project_path = os.path.abspath(project_path)
        if not os.path.exists(abs_project_path):
            print(f"Error: Project path '{project_path}' does not exist.")
            return False
        
        print(f"Analyzing project: {abs_project_path}")
        
        # Find all source files matching the patterns
        source_files = []
        for pattern in file_patterns:
            if recursive:
                # Recursive search
                for root, _, _ in os.walk(abs_project_path):
                    glob_pattern = os.path.join(root, pattern)
                    source_files.extend(glob.glob(glob_pattern))
            else:
                # Non-recursive search
                glob_pattern = os.path.join(abs_project_path, pattern)
                source_files.extend(glob.glob(glob_pattern))
        
        # Remove duplicates and sort
        source_files = sorted(set(source_files))
        
        if not source_files:
            print(f"Error: No source files found matching patterns: {file_patterns}")
            return False
        
        print(f"Found {len(source_files)} source files")
        
        # Add include path to compile args
        compile_args.extend(["-I", abs_project_path])
        
        try:
            print("Analyzing source files...")
            self.system.analyze_codebase(source_files, compile_args)
            self.project_analyzed = True
            print("Analysis completed successfully.")
            return True
        except Exception as e:
            print(f"Error during analysis: {str(e)}")
            return False
    
    def query_functions(self, query_text, result_file=None, extract_bodies=True):
        """
        Query functions using natural language.
        
        Args:
            query_text: Natural language query
            result_file: Optional file to save results
            extract_bodies: Whether to extract function bodies
        """
        if not self.project_analyzed:
            print("Error: No project analyzed yet. Use the 'analyze' command first.")
            return
        
        print(f"Executing query: {query_text}")
        try:
            result_key = "QueryResults"
            results = self.system.query_by_natural_language(
                query_text, 
                result_key, 
                extract_function_bodies=extract_bodies
            )
            
            functions = results.get(result_key, [])
            print(f"Found {len(functions)} matching functions")
            
            # Print a summary of each function
            for i, func in enumerate(functions, 1):
                print(f"\n[{i}] {func.get('name', 'Unknown function')}")
                print(f"    File: {func.get('file_path', 'Unknown')}:{func.get('line_number', 0)}")
                if func.get('is_callback', False):
                    print(f"    Type: Callback ({func.get('callback_type', 'Unknown')})")
                
                # Show call relationships
                if 'calls_functions' in func and func['calls_functions']:
                    print(f"    Calls: {', '.join(cf.get('name', 'Unknown') for cf in func['calls_functions'][:5])}")
                    if len(func['calls_functions']) > 5:
                        print(f"           ... and {len(func['calls_functions']) - 5} more")
                
                if 'called_by_functions' in func and func['called_by_functions']:
                    print(f"    Called by: {', '.join(cf.get('name', 'Unknown') for cf in func['called_by_functions'][:5])}")
                    if len(func['called_by_functions']) > 5:
                        print(f"               ... and {len(func['called_by_functions']) - 5} more")
            
            # Save results to file if requested
            if result_file:
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"\nResults saved to: {result_file}")
            
            # Return the raw results in case it's called programmatically
            return results
            
        except Exception as e:
            print(f"Error during query: {str(e)}")
            return None
    
    def show_function_body(self, function_name, file_path=None):
        """
        Show the complete body of a specific function.
        
        Args:
            function_name: Name of the function
            file_path: Optional file path to narrow search
        """
        if not self.project_analyzed:
            print("Error: No project analyzed yet. Use the 'analyze' command first.")
            return
        
        query = f"Find details about the function named {function_name}"
        if file_path:
            query += f" in file {file_path}"
        
        try:
            results = self.system.query_by_natural_language(
                query,
                "FunctionDetails",
                extract_function_bodies=True
            )
            
            functions = results.get("FunctionDetails", [])
            if not functions:
                print(f"No function named '{function_name}' found.")
                return
            
            # If we found multiple functions with the same name
            if len(functions) > 1:
                print(f"Found {len(functions)} functions named '{function_name}':")
                for i, func in enumerate(functions, 1):
                    print(f"[{i}] {func.get('name')} in {func.get('file_path')}:{func.get('line_number')}")
                
                # Ask user to select a function
                try:
                    idx = int(input("\nSelect a function (number): ")) - 1
                    if idx < 0 or idx >= len(functions):
                        print("Invalid selection.")
                        return
                    selected_function = functions[idx]
                except (ValueError, IndexError):
                    print("Invalid selection.")
                    return
            else:
                selected_function = functions[0]
            
            # Print function details
            print(f"\nFunction: {selected_function.get('name')}")
            print(f"File: {selected_function.get('file_path')}:{selected_function.get('line_number')}")
            if selected_function.get('is_callback', False):
                print(f"Type: Callback ({selected_function.get('callback_type', 'Unknown')})")
            
            print("\nFunction Body:")
            print("=" * 80)
            print(selected_function.get('function_body', 'No function body found'))
            print("=" * 80)
            
            return selected_function
            
        except Exception as e:
            print(f"Error getting function body: {str(e)}")
            return None

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="C/C++ Code Analysis CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py analyze /path/to/project --patterns "*.cpp" "*.h" --recursive
  python cli.py query "Find all functions related to error handling"
  python cli.py function calculate_total_price
  python cli.py function validate_order --file order_system.cpp
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a C/C++ project')
    analyze_parser.add_argument('project_path', type=str, help='Path to the project directory')
    analyze_parser.add_argument('--patterns', nargs='*', type=str, 
                              help='File patterns to include (default: *.cpp *.h *.hpp *.c *.cc)')
    analyze_parser.add_argument('--compile-args', nargs='*', type=str,
                              help='Compilation arguments (default: -std=c++17)')
    analyze_parser.add_argument('--recursive', action='store_true',
                              help='Search for files recursively')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query functions using natural language')
    query_parser.add_argument('query_text', type=str, help='Natural language query')
    query_parser.add_argument('--output', type=str, help='File to save query results')
    query_parser.add_argument('--no-bodies', action='store_true',
                            help='Do not extract function bodies')
    
    # Function command
    function_parser = subparsers.add_parser('function', 
                                         help='Show details of a specific function')
    function_parser.add_argument('function_name', type=str, help='Name of the function')
    function_parser.add_argument('--file', type=str, help='File path to narrow search')
    
    return parser.parse_args()

def main():
    """Main function for the CLI tool."""
    args = parse_args()
    cli = CodeAnalysisCLI()
    
    if args.command == 'analyze':
        cli.analyze_project(
            args.project_path,
            file_patterns=args.patterns,
            compile_args=args.compile_args,
            recursive=args.recursive
        )
    
    elif args.command == 'query':
        cli.query_functions(
            args.query_text,
            result_file=args.output,
            extract_bodies=not args.no_bodies
        )
    
    elif args.command == 'function':
        cli.show_function_body(args.function_name, file_path=args.file)
    
    else:
        print("Please specify a command: analyze, query, or function")
        print("Run 'python cli.py --help' for more information.")

if __name__ == "__main__":
    main() 